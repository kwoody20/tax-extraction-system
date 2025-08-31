#!/usr/bin/env python3
"""
Self-hosted Tax Extractor UI Service
Handles complex Selenium/Playwright extractors with real-time updates to Supabase
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import uuid4
import threading
from queue import Queue, Empty

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
from supabase import create_client, Client
from dotenv import load_dotenv

# Import existing extractors
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.extractors.MASTER_TAX_EXTRACTOR import (
    PropertyTaxRecord,
    MasterExtractor,
    EXTRACTION_CONFIG
)
from src.extractors.selenium_tax_extractors import (
    MaricopaCountyExtractor,
    HarrisCountyExtractor,
    TaxExtractionResult
)
from src.extractors.robust_tax_extractor import RobustTaxExtractor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extractor_ui_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://klscgjbachumeojhxyno.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_KEY else None

# ================================================================================
# DATA MODELS
# ================================================================================

class ExtractionRequest(BaseModel):
    """Request model for extraction jobs"""
    property_ids: Optional[List[str]] = None
    entity_id: Optional[str] = None
    jurisdiction: Optional[str] = None
    extraction_method: str = "auto"  # auto, selenium, playwright, http
    priority: str = "normal"  # low, normal, high, urgent
    notify_on_complete: bool = True
    save_to_supabase: bool = True

class ExtractionJob(BaseModel):
    """Model for extraction job tracking"""
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    property_id: str
    property_name: str
    jurisdiction: str
    status: str = "queued"  # queued, running, completed, failed, cancelled
    progress: int = 0
    extraction_method: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

class SystemStatus(BaseModel):
    """System status information"""
    status: str = "operational"  # operational, degraded, maintenance
    active_jobs: int = 0
    queued_jobs: int = 0
    completed_today: int = 0
    failed_today: int = 0
    average_duration: float = 0
    extractors_available: List[str] = []
    supabase_connected: bool = False
    last_sync: Optional[datetime] = None

# ================================================================================
# EXTRACTION JOB MANAGER
# ================================================================================

class ExtractionJobManager:
    """Manages extraction job queue and execution"""
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.job_queue: Queue = Queue()
        self.active_jobs: Dict[str, ExtractionJob] = {}
        self.completed_jobs: List[ExtractionJob] = []
        self.job_history: List[ExtractionJob] = []
        self.websocket_clients: List[WebSocket] = []
        self.executor_threads: List[threading.Thread] = []
        self.running = False
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "total_duration": 0
        }
        
        # Initialize extractors
        self.extractors = {
            "maricopa": MaricopaCountyExtractor(headless=True),
            "harris": HarrisCountyExtractor(headless=True),
            "master": MasterExtractor(),
            "robust": RobustTaxExtractor()
        }
    
    def start(self):
        """Start the job manager"""
        self.running = True
        for i in range(self.max_concurrent):
            thread = threading.Thread(target=self._job_executor, daemon=True)
            thread.start()
            self.executor_threads.append(thread)
        logger.info(f"Started {self.max_concurrent} executor threads")
    
    def stop(self):
        """Stop the job manager"""
        self.running = False
        for thread in self.executor_threads:
            thread.join(timeout=5)
        logger.info("Stopped all executor threads")
    
    def add_job(self, job: ExtractionJob) -> str:
        """Add a job to the queue"""
        self.job_queue.put(job)
        self.job_history.append(job)
        asyncio.create_task(self._broadcast_status_update())
        logger.info(f"Added job {job.job_id} to queue")
        return job.job_id
    
    def get_job_status(self, job_id: str) -> Optional[ExtractionJob]:
        """Get status of a specific job"""
        # Check active jobs
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        
        # Check completed jobs
        for job in self.completed_jobs:
            if job.job_id == job_id:
                return job
        
        # Check history
        for job in self.job_history:
            if job.job_id == job_id:
                return job
        
        return None
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        job = self.get_job_status(job_id)
        if job and job.status in ["queued", "running"]:
            job.status = "cancelled"
            asyncio.create_task(self._broadcast_status_update())
            return True
        return False
    
    def _job_executor(self):
        """Execute jobs from the queue"""
        while self.running:
            try:
                job = self.job_queue.get(timeout=1)
                if job.status == "cancelled":
                    continue
                
                job.status = "running"
                job.started_at = datetime.now()
                self.active_jobs[job.job_id] = job
                
                asyncio.create_task(self._broadcast_job_update(job))
                
                # Execute extraction
                try:
                    result = self._execute_extraction(job)
                    job.result = result
                    job.status = "completed"
                    self.stats["successful"] += 1
                    
                    # Save to Supabase if enabled
                    if result and supabase:
                        self._save_to_supabase(job, result)
                    
                except Exception as e:
                    logger.error(f"Extraction failed for job {job.job_id}: {str(e)}")
                    job.error = str(e)
                    job.status = "failed"
                    self.stats["failed"] += 1
                    
                    # Retry logic
                    if job.retry_count < job.max_retries:
                        job.retry_count += 1
                        job.status = "queued"
                        self.job_queue.put(job)
                        logger.info(f"Retrying job {job.job_id} (attempt {job.retry_count})")
                
                finally:
                    job.completed_at = datetime.now()
                    job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
                    self.stats["total_duration"] += job.duration_seconds
                    self.stats["total_processed"] += 1
                    
                    del self.active_jobs[job.job_id]
                    self.completed_jobs.append(job)
                    
                    # Keep only last 100 completed jobs
                    if len(self.completed_jobs) > 100:
                        self.completed_jobs = self.completed_jobs[-100:]
                    
                    asyncio.create_task(self._broadcast_job_update(job))
                    
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in job executor: {str(e)}")
    
    def _execute_extraction(self, job: ExtractionJob) -> Dict:
        """Execute the actual extraction"""
        logger.info(f"Executing extraction for {job.property_name} in {job.jurisdiction}")
        
        # Determine which extractor to use
        jurisdiction_lower = job.jurisdiction.lower()
        
        if "maricopa" in jurisdiction_lower:
            extractor = self.extractors["maricopa"]
            result = extractor.extract_tax_data(job.property_id)
        elif "harris" in jurisdiction_lower:
            extractor = self.extractors["harris"]
            result = extractor.extract_tax_data(job.property_id)
        else:
            # Use master extractor for all other jurisdictions
            extractor = self.extractors["master"]
            # Create PropertyTaxRecord from job
            record = PropertyTaxRecord(
                property_id=job.property_id,
                property_name=job.property_name,
                jurisdiction=job.jurisdiction,
                state="",  # Will be filled from database
                property_type="",
                close_date=None,
                amount_due=None,
                previous_year_taxes=None,
                extraction_steps="",
                acct_number=None,
                property_address=None,
                next_due_date=None,
                tax_bill_link="",
                parent_entity=None
            )
            result = asyncio.run(extractor.extract_single(record))
        
        return result
    
    def _save_to_supabase(self, job: ExtractionJob, result: Dict):
        """Save extraction result to Supabase"""
        try:
            # Prepare data for Supabase
            extraction_data = {
                "property_id": job.property_id,
                "extraction_date": datetime.now().isoformat(),
                "extraction_method": job.extraction_method or "selenium",
                "status": job.status,
                "amount_due": result.get("amount_due"),
                "due_date": result.get("due_date"),
                "tax_year": result.get("tax_year"),
                "raw_data": json.dumps(result),
                "duration_seconds": job.duration_seconds,
                "error_message": job.error
            }
            
            # Insert into tax_extractions table
            response = supabase.table("tax_extractions").insert(extraction_data).execute()
            
            # Update property record with latest extraction
            if result.get("amount_due"):
                property_update = {
                    "amount_due": result.get("amount_due"),
                    "next_due_date": result.get("due_date"),
                    "last_extraction_date": datetime.now().isoformat(),
                    "extraction_status": "success"
                }
                supabase.table("properties").update(property_update).eq("id", job.property_id).execute()
            
            logger.info(f"Saved extraction result to Supabase for property {job.property_id}")
            
        except Exception as e:
            logger.error(f"Failed to save to Supabase: {str(e)}")
    
    async def _broadcast_job_update(self, job: ExtractionJob):
        """Broadcast job update to all WebSocket clients"""
        message = {
            "type": "job_update",
            "job": job.dict()
        }
        await self._broadcast_message(message)
    
    async def _broadcast_status_update(self):
        """Broadcast system status update"""
        status = self.get_system_status()
        message = {
            "type": "status_update",
            "status": status.dict()
        }
        await self._broadcast_message(message)
    
    async def _broadcast_message(self, message: Dict):
        """Broadcast message to all WebSocket clients"""
        for client in self.websocket_clients[:]:
            try:
                await client.send_json(message)
            except:
                self.websocket_clients.remove(client)
    
    def get_system_status(self) -> SystemStatus:
        """Get current system status"""
        avg_duration = 0
        if self.stats["total_processed"] > 0:
            avg_duration = self.stats["total_duration"] / self.stats["total_processed"]
        
        return SystemStatus(
            status="operational" if self.running else "stopped",
            active_jobs=len(self.active_jobs),
            queued_jobs=self.job_queue.qsize(),
            completed_today=self.stats["successful"],
            failed_today=self.stats["failed"],
            average_duration=avg_duration,
            extractors_available=list(self.extractors.keys()),
            supabase_connected=supabase is not None,
            last_sync=datetime.now() if supabase else None
        )

# ================================================================================
# FASTAPI APPLICATION
# ================================================================================

app = FastAPI(
    title="Tax Extractor UI Service",
    description="Self-hosted UI for complex tax extraction with Supabase integration",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize job manager
job_manager = ExtractionJobManager(max_concurrent=3)

@app.on_event("startup")
async def startup_event():
    """Start the job manager on application startup"""
    job_manager.start()
    logger.info("Tax Extractor UI Service started")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop the job manager on application shutdown"""
    job_manager.stop()
    logger.info("Tax Extractor UI Service stopped")

# ================================================================================
# API ENDPOINTS
# ================================================================================

@app.get("/")
async def root():
    """Serve the main UI"""
    return HTMLResponse(content=open("extractor_ui.html").read())

@app.get("/api/status")
async def get_status() -> SystemStatus:
    """Get system status"""
    return job_manager.get_system_status()

@app.get("/api/properties")
async def get_properties():
    """Get all properties from Supabase"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    
    try:
        response = supabase.table("properties").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/entities")
async def get_entities():
    """Get all entities from Supabase"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    
    try:
        response = supabase.table("entities").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract")
async def start_extraction(request: ExtractionRequest):
    """Start extraction jobs"""
    jobs_created = []
    
    try:
        # Get properties to extract
        properties = []
        
        if request.property_ids:
            # Extract specific properties
            if supabase:
                response = supabase.table("properties").select("*").in_("id", request.property_ids).execute()
                properties = response.data
        elif request.entity_id:
            # Extract all properties for an entity
            if supabase:
                response = supabase.table("properties").select("*").eq("parent_entity_id", request.entity_id).execute()
                properties = response.data
        elif request.jurisdiction:
            # Extract all properties in a jurisdiction
            if supabase:
                response = supabase.table("properties").select("*").eq("jurisdiction", request.jurisdiction).execute()
                properties = response.data
        else:
            raise HTTPException(status_code=400, detail="Must specify property_ids, entity_id, or jurisdiction")
        
        # Create jobs for each property
        for prop in properties:
            job = ExtractionJob(
                property_id=prop["id"],
                property_name=prop["property_name"],
                jurisdiction=prop["jurisdiction"],
                extraction_method=request.extraction_method
            )
            job_id = job_manager.add_job(job)
            jobs_created.append(job_id)
        
        return {
            "message": f"Created {len(jobs_created)} extraction jobs",
            "job_ids": jobs_created
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs")
async def get_jobs():
    """Get all jobs"""
    return {
        "active": [job.dict() for job in job_manager.active_jobs.values()],
        "queued": job_manager.job_queue.qsize(),
        "completed": [job.dict() for job in job_manager.completed_jobs[-20:]]  # Last 20
    }

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get specific job status"""
    job = job_manager.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a job"""
    if job_manager.cancel_job(job_id):
        return {"message": f"Job {job_id} cancelled"}
    else:
        raise HTTPException(status_code=404, detail="Job not found or already completed")

@app.get("/api/extractions")
async def get_extractions(limit: int = 50):
    """Get recent extractions from Supabase"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    
    try:
        response = supabase.table("tax_extractions").select("*").order("extraction_date", desc=True).limit(limit).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================================
# WEBSOCKET ENDPOINT
# ================================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    job_manager.websocket_clients.append(websocket)
    
    try:
        # Send initial status
        status = job_manager.get_system_status()
        await websocket.send_json({
            "type": "connected",
            "status": status.dict()
        })
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            
    except WebSocketDisconnect:
        job_manager.websocket_clients.remove(websocket)
        logger.info("WebSocket client disconnected")

# ================================================================================
# MAIN ENTRY POINT
# ================================================================================

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=False
    )