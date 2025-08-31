"""
Celery Job Queue System for Tax Extractor
Provides distributed task processing with Redis backend
"""

from celery import Celery, Task
from celery.result import AsyncResult
from celery.signals import task_success, task_failure, task_retry
import redis
import json
import sys
import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional
import tempfile
import traceback

# Import master extractor
from MASTER_TAX_EXTRACTOR import TaxExtractor

# Configure Celery
app = Celery(
    'tax_extractor_queue',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3000,  # 50 min soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=10,
    result_expires=86400,  # Results expire after 24 hours
)

# Redis client for progress tracking
redis_client = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)

class ExtractorTask(Task):
    """Custom task class with progress tracking"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        redis_client.hset(f"task:{task_id}", mapping={
            "status": "failed",
            "error": str(exc),
            "traceback": str(einfo),
            "completed_at": datetime.now().isoformat()
        })
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        redis_client.hset(f"task:{task_id}", mapping={
            "status": "completed",
            "completed_at": datetime.now().isoformat()
        })

@app.task(bind=True, base=ExtractorTask, name='extract_taxes')
def extract_taxes(
    self,
    input_file: str,
    output_file: Optional[str] = None,
    concurrent: bool = True,
    max_workers: int = 5,
    save_screenshots: bool = False,
    batch_size: int = 10
) -> Dict[str, Any]:
    """
    Main extraction task
    """
    task_id = self.request.id
    
    # Initialize task metadata
    redis_client.hset(f"task:{task_id}", mapping={
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "progress": 0,
        "processed": 0,
        "total": 0,
        "successful": 0,
        "failed": 0
    })
    
    try:
        # Initialize extractor
        extractor = TaxExtractor()
        
        # Set up progress tracking
        def update_progress(processed, total, successful, failed):
            progress = (processed / total * 100) if total > 0 else 0
            redis_client.hset(f"task:{task_id}", mapping={
                "progress": progress,
                "processed": processed,
                "total": total,
                "successful": successful,
                "failed": failed
            })
            
            # Update Celery task state
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': processed,
                    'total': total,
                    'progress': progress,
                    'successful': successful,
                    'failed': failed
                }
            )
        
        extractor.progress_callback = update_progress
        
        # Generate output file if not provided
        if not output_file:
            output_file = f"/tmp/extraction_results_{task_id}.xlsx"
        
        # Run extraction
        success_count, fail_count = extractor.run_extraction(
            input_file=input_file,
            output_file=output_file,
            concurrent=concurrent,
            max_workers=max_workers,
            save_screenshots=save_screenshots
        )
        
        # Store results
        result = {
            "task_id": task_id,
            "status": "completed",
            "successful": success_count,
            "failed": fail_count,
            "output_file": output_file,
            "completed_at": datetime.now().isoformat()
        }
        
        redis_client.hset(f"task:{task_id}", mapping=result)
        redis_client.expire(f"task:{task_id}", 86400)  # Expire after 24 hours
        
        return result
        
    except Exception as e:
        # Store error information
        error_info = {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        redis_client.hset(f"task:{task_id}", mapping=error_info)
        raise

@app.task(bind=True, name='extract_batch')
def extract_batch(
    self,
    urls: list,
    batch_name: str = "batch",
    concurrent: bool = True,
    max_workers: int = 3
) -> Dict[str, Any]:
    """
    Extract a batch of URLs without a CSV file
    """
    task_id = self.request.id
    
    # Create temporary CSV
    temp_df = pd.DataFrame({
        'Tax Bill Link': urls,
        'Property Name': [f'{batch_name}_{i+1}' for i in range(len(urls))]
    })
    
    input_file = f"/tmp/batch_input_{task_id}.csv"
    temp_df.to_csv(input_file, index=False)
    
    # Call main extraction task
    return extract_taxes(
        input_file=input_file,
        concurrent=concurrent,
        max_workers=max_workers
    )

@app.task(bind=True, name='extract_scheduled')
def extract_scheduled(
    self,
    schedule_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Scheduled extraction task for periodic runs
    """
    task_id = self.request.id
    
    # Extract configuration
    input_file = schedule_config.get('input_file')
    recipient_emails = schedule_config.get('emails', [])
    
    # Run extraction
    result = extract_taxes(
        input_file=input_file,
        concurrent=True,
        max_workers=5
    )
    
    # Send notification (placeholder for email logic)
    if recipient_emails:
        send_completion_email(recipient_emails, result)
    
    return result

def send_completion_email(emails: list, result: dict):
    """Send completion notification (implement with your email service)"""
    pass

# Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'cleanup-old-results': {
        'task': 'cleanup_old_results',
        'schedule': 3600.0,  # Every hour
    },
}

@app.task(name='cleanup_old_results')
def cleanup_old_results():
    """Clean up old result files and Redis keys"""
    import glob
    from datetime import datetime, timedelta
    
    # Clean files older than 24 hours
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    for file_path in glob.glob('/tmp/extraction_results_*.xlsx'):
        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        if file_time < cutoff_time:
            os.remove(file_path)
    
    return {"cleaned": True}

# Task management functions
def submit_extraction(
    input_file: str,
    **kwargs
) -> str:
    """Submit an extraction task to the queue"""
    task = extract_taxes.delay(input_file, **kwargs)
    return task.id

def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a task"""
    # Try Redis first for detailed info
    task_data = redis_client.hgetall(f"task:{task_id}")
    
    if task_data:
        return task_data
    
    # Fall back to Celery result
    result = AsyncResult(task_id, app=app)
    
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
        "info": result.info
    }

def cancel_task(task_id: str) -> bool:
    """Cancel a running task"""
    app.control.revoke(task_id, terminate=True)
    redis_client.hset(f"task:{task_id}", "status", "cancelled")
    return True

def list_active_tasks() -> list:
    """List all active tasks"""
    inspect = app.control.inspect()
    active = inspect.active()
    
    tasks = []
    if active:
        for worker, task_list in active.items():
            tasks.extend(task_list)
    
    return tasks

def get_queue_stats() -> Dict[str, Any]:
    """Get queue statistics"""
    inspect = app.control.inspect()
    
    stats = {
        "active": len(list_active_tasks()),
        "scheduled": len(inspect.scheduled() or {}),
        "reserved": len(inspect.reserved() or {}),
        "workers": list(inspect.active_queues().keys()) if inspect.active_queues() else []
    }
    
    return stats

if __name__ == "__main__":
    # Start worker
    app.worker_main([
        'worker',
        '--loglevel=INFO',
        '--concurrency=4',
        '--autoscale=8,2',
        '--max-tasks-per-child=10'
    ])