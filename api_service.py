"""
REST API Service for Tax Extractor
Provides async endpoints for tax extraction jobs
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import uuid
import os
import sys
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
import tempfile
import traceback

# Import the master extractor
from MASTER_TAX_EXTRACTOR import TaxExtractor

app = FastAPI(title="Tax Extractor API", version="1.0.0")

# In-memory job storage (replace with Redis in production)
jobs: Dict[str, Dict[str, Any]] = {}

class ExtractionRequest(BaseModel):
    csv_file_path: Optional[str] = None
    urls: Optional[List[str]] = None
    concurrent: bool = True
    max_workers: int = 5
    save_screenshots: bool = False

class ExtractionResponse(BaseModel):
    job_id: str
    status: str
    message: str

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: float
    total_properties: int
    processed: int
    successful: int
    failed: int
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    results_available: bool = False

def run_extraction(job_id: str, request: ExtractionRequest):
    """Background task to run extraction"""
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["started_at"] = datetime.now().isoformat()
        
        # Initialize extractor
        extractor = TaxExtractor()
        
        # Prepare input file
        if request.csv_file_path:
            input_file = request.csv_file_path
        else:
            # Create temp file from URLs if provided
            temp_df = pd.DataFrame({
                'Tax Bill Link': request.urls or [],
                'Property Name': [f'Property_{i+1}' for i in range(len(request.urls or []))]
            })
            input_file = f"/tmp/temp_input_{job_id}.csv"
            temp_df.to_csv(input_file, index=False)
        
        # Track progress
        def progress_callback(processed, total, successful, failed):
            jobs[job_id].update({
                "processed": processed,
                "total_properties": total,
                "successful": successful,
                "failed": failed,
                "progress": (processed / total * 100) if total > 0 else 0
            })
        
        # Run extraction
        output_file = f"/tmp/results_{job_id}.xlsx"
        extractor.progress_callback = progress_callback
        
        success_count, fail_count = extractor.run_extraction(
            input_file=input_file,
            output_file=output_file,
            concurrent=request.concurrent,
            max_workers=request.max_workers,
            save_screenshots=request.save_screenshots
        )
        
        # Update job status
        jobs[job_id].update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "successful": success_count,
            "failed": fail_count,
            "progress": 100,
            "results_file": output_file,
            "results_available": True
        })
        
    except Exception as e:
        jobs[job_id].update({
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "completed_at": datetime.now().isoformat()
        })

@app.get("/")
async def root():
    return {
        "name": "Tax Extractor API",
        "version": "1.0.0",
        "endpoints": {
            "POST /extract": "Submit extraction job",
            "POST /extract/upload": "Upload CSV and extract",
            "GET /jobs/{job_id}": "Get job status",
            "GET /jobs/{job_id}/results": "Download results",
            "GET /jobs": "List all jobs",
            "DELETE /jobs/{job_id}": "Cancel job"
        }
    }

@app.post("/extract", response_model=ExtractionResponse)
async def submit_extraction(request: ExtractionRequest, background_tasks: BackgroundTasks):
    """Submit a new extraction job"""
    job_id = str(uuid.uuid4())
    
    # Initialize job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "total_properties": 0,
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "error": None,
        "results_available": False
    }
    
    # Start background task
    background_tasks.add_task(run_extraction, job_id, request)
    
    return ExtractionResponse(
        job_id=job_id,
        status="pending",
        message="Extraction job submitted successfully"
    )

@app.post("/extract/upload", response_model=ExtractionResponse)
async def upload_and_extract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    concurrent: bool = True,
    max_workers: int = 5
):
    """Upload CSV file and start extraction"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")
    
    # Save uploaded file
    job_id = str(uuid.uuid4())
    upload_path = f"/tmp/upload_{job_id}.csv"
    
    try:
        contents = await file.read()
        with open(upload_path, 'wb') as f:
            f.write(contents)
        
        # Create extraction request
        request = ExtractionRequest(
            csv_file_path=upload_path,
            concurrent=concurrent,
            max_workers=max_workers
        )
        
        # Initialize job
        jobs[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "progress": 0,
            "total_properties": 0,
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "error": None,
            "results_available": False,
            "input_file": file.filename
        }
        
        # Start background task
        background_tasks.add_task(run_extraction, job_id, request)
        
        return ExtractionResponse(
            job_id=job_id,
            status="pending",
            message=f"File '{file.filename}' uploaded and extraction started"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get status of a specific job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatus(**jobs[job_id])

@app.get("/jobs/{job_id}/results")
async def get_job_results(job_id: str, format: str = "excel"):
    """Download extraction results"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job is {job['status']}, results not available")
    
    if not job.get("results_available"):
        raise HTTPException(status_code=404, detail="Results file not found")
    
    results_file = job.get("results_file")
    if not results_file or not os.path.exists(results_file):
        raise HTTPException(status_code=404, detail="Results file not found")
    
    if format == "json":
        # Convert Excel to JSON
        df = pd.read_excel(results_file, sheet_name='Results')
        return JSONResponse(content=df.to_dict(orient='records'))
    else:
        # Return Excel file
        return FileResponse(
            results_file,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=f"tax_extraction_results_{job_id}.xlsx"
        )

@app.get("/jobs")
async def list_jobs(status: Optional[str] = None, limit: int = 50):
    """List all jobs with optional status filter"""
    job_list = list(jobs.values())
    
    if status:
        job_list = [j for j in job_list if j["status"] == status]
    
    # Sort by created_at desc
    job_list.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {
        "total": len(job_list),
        "jobs": job_list[:limit]
    }

@app.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a pending or running job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job with status: {job['status']}")
    
    job["status"] = "cancelled"
    job["completed_at"] = datetime.now().isoformat()
    
    return {"message": f"Job {job_id} cancelled successfully"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_jobs": len([j for j in jobs.values() if j["status"] == "running"]),
        "total_jobs": len(jobs)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)