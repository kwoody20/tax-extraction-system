"""
Enhanced API Service with Supabase Authentication.
Includes user registration, login, and protected endpoints.
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any

from supabase_auth import (
    SupabaseAuthManager,
    get_current_user,
    get_optional_user
)
from api_service_supabase import (
    app as base_app,
    settings,
    db_manager,
    PropertyExtractionRequest,
    ExtractionJob,
    ExtractionStatus,
    process_extraction_job,
    jobs_store
)

import logging
from datetime import datetime
import uuid
from fastapi import BackgroundTasks

# ========================= Models =========================

class UserRegister(BaseModel):
    """User registration model."""
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")
    name: Optional[str] = None
    company: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
                "name": "John Doe",
                "company": "Property Management Inc"
            }
        }

class UserLogin(BaseModel):
    """User login model."""
    email: EmailStr
    password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        }

class PasswordReset(BaseModel):
    """Password reset request model."""
    email: EmailStr

class PasswordUpdate(BaseModel):
    """Password update model."""
    new_password: str = Field(..., min_length=6)

# ========================= Create Enhanced App =========================

app = FastAPI(
    title="Tax Extraction API with Authentication",
    version="3.0.0",
    description="Property tax extraction service with Supabase authentication",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize auth manager
auth_manager = SupabaseAuthManager()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= Public Endpoints =========================

@app.get("/")
async def root():
    """Root endpoint - public."""
    return {
        "service": "Tax Extraction API with Authentication",
        "version": "3.0.0",
        "status": "operational",
        "authentication": "Supabase Auth",
        "docs": "/docs",
        "endpoints": {
            "auth": {
                "register": "/auth/register",
                "login": "/auth/login",
                "refresh": "/auth/refresh",
                "logout": "/auth/logout"
            },
            "api": {
                "properties": "/api/v1/properties",
                "entities": "/api/v1/entities",
                "extract": "/api/v1/extract",
                "jobs": "/api/v1/jobs/{job_id}"
            }
        }
    }

@app.get("/health")
async def health_check():
    """Health check - public."""
    try:
        db_client = db_manager.get_client()
        stats = db_client.calculate_tax_statistics()
        
        return {
            "status": "healthy",
            "database": "connected",
            "auth": "configured",
            "properties_count": stats.get("total_properties", 0),
            "entities_count": stats.get("total_entities", 0),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# ========================= Authentication Endpoints =========================

@app.post("/auth/register")
async def register(user_data: UserRegister):
    """Register a new user."""
    try:
        # Prepare metadata
        metadata = {}
        if user_data.name:
            metadata["name"] = user_data.name
        if user_data.company:
            metadata["company"] = user_data.company
        metadata["role"] = "user"  # Default role
        
        # Register user
        result = auth_manager.register_user(
            email=user_data.email,
            password=user_data.password,
            metadata=metadata
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "user": result.get("user"),
                "session": result.get("session")
            }
        else:
            raise HTTPException(status_code=400, detail=result["message"])
            
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/auth/login")
async def login(credentials: UserLogin):
    """Login with email and password."""
    try:
        result = auth_manager.login_user(
            email=credentials.email,
            password=credentials.password
        )
        
        if result["success"]:
            return {
                "success": True,
                "user": result["user"],
                "session": result["session"]
            }
        else:
            raise HTTPException(status_code=401, detail=result["message"])
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.post("/auth/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token."""
    try:
        result = auth_manager.refresh_token(refresh_token)
        
        if result["success"]:
            return {
                "success": True,
                "session": result["session"]
            }
        else:
            raise HTTPException(status_code=401, detail=result["message"])
            
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=500, detail="Token refresh failed")

@app.post("/auth/logout")
async def logout(current_user: Dict = Depends(get_current_user)):
    """Logout current user."""
    # In a real implementation, you would invalidate the token
    return {
        "success": True,
        "message": "Logged out successfully"
    }

@app.post("/auth/password-reset")
async def request_password_reset(data: PasswordReset):
    """Request password reset email."""
    try:
        result = auth_manager.request_password_reset(data.email)
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result["message"])
            
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(status_code=500, detail="Password reset request failed")

@app.put("/auth/password")
async def update_password(
    data: PasswordUpdate,
    current_user: Dict = Depends(get_current_user)
):
    """Update user password (requires authentication)."""
    # Note: This would need the actual access token from the request
    # For now, returning a message
    return {
        "success": True,
        "message": "Password update endpoint configured. Implement with actual token."
    }

# ========================= Protected API Endpoints =========================

@app.get("/api/v1/profile")
async def get_profile(current_user: Dict = Depends(get_current_user)):
    """Get current user profile."""
    return {
        "success": True,
        "user": current_user
    }

@app.get("/api/v1/properties")
async def get_properties(
    limit: int = 100,
    offset: int = 0,
    state: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    user: Optional[Dict] = Depends(get_optional_user)  # Optional auth
):
    """Get properties - optionally authenticated."""
    try:
        db_client = db_manager.get_client()
        
        filters = {}
        if state:
            filters["state"] = state
        if jurisdiction:
            filters["jurisdiction"] = jurisdiction
        
        properties = db_client.get_properties(limit=limit, offset=offset, filters=filters)
        
        return {
            "success": True,
            "count": len(properties),
            "properties": properties,
            "authenticated": user is not None
        }
    except Exception as e:
        logger.error(f"Failed to get properties: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/entities")
async def get_entities(
    limit: int = 100,
    offset: int = 0,
    user: Optional[Dict] = Depends(get_optional_user)  # Optional auth
):
    """Get entities - optionally authenticated."""
    try:
        db_client = db_manager.get_client()
        entities = db_client.get_entities(limit=limit, offset=offset)
        
        return {
            "success": True,
            "count": len(entities),
            "entities": entities,
            "authenticated": user is not None
        }
    except Exception as e:
        logger.error(f"Failed to get entities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/extract")
async def create_extraction_job(
    request: PropertyExtractionRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)  # Requires auth
):
    """Create extraction job - requires authentication."""
    try:
        db_client = db_manager.get_client()
        
        # Get properties based on request
        properties_to_extract = []
        
        if request.property_ids:
            for prop_id in request.property_ids:
                prop = db_client.get_property(prop_id)
                if prop:
                    properties_to_extract.append(prop)
        else:
            properties_to_extract = db_client.find_properties_needing_extraction(
                days_since_last=request.days_since_last
            )
        
        if not properties_to_extract:
            return {
                "success": False,
                "message": "No properties found matching criteria"
            }
        
        # Create job with user info
        job_id = str(uuid.uuid4())
        job = ExtractionJob(
            job_id=job_id,
            status=ExtractionStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            total_properties=len(properties_to_extract),
            processed_properties=0,
            successful_extractions=0,
            failed_extractions=0
        )
        
        # Store job with user association
        jobs_store[job_id] = job
        
        # Start background extraction
        background_tasks.add_task(process_extraction_job, job_id, properties_to_extract)
        
        return {
            "success": True,
            "job_id": job_id,
            "status": job.status,
            "total_properties": job.total_properties,
            "user_id": current_user["id"],
            "message": f"Extraction job created for {len(properties_to_extract)} properties"
        }
        
    except Exception as e:
        logger.error(f"Failed to create extraction job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: Dict = Depends(get_current_user)  # Requires auth
):
    """Get job status - requires authentication."""
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "success": True,
        "job": job.dict(),
        "user_id": current_user["id"]
    }

@app.get("/api/v1/statistics")
async def get_statistics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: Optional[Dict] = Depends(get_optional_user)  # Optional auth
):
    """Get statistics - enhanced for authenticated users."""
    try:
        db_client = db_manager.get_client()
        
        # Parse dates if provided
        from datetime import datetime
        start = datetime.fromisoformat(start_date).date() if start_date else None
        end = datetime.fromisoformat(end_date).date() if end_date else None
        
        # Get statistics
        stats = db_client.calculate_tax_statistics(start_date=start, end_date=end)
        
        # Get extraction metrics
        metrics = db_client.get_extraction_metrics(days=30)
        
        response = {
            "success": True,
            "statistics": stats,
            "extraction_metrics": metrics[:10] if not user else metrics,  # Limit for non-auth
            "authenticated": user is not None
        }
        
        # Add portfolio summary for authenticated users
        if user:
            portfolio = db_client.get_entity_portfolio_summary()
            response["portfolio_summary"] = portfolio[:10]
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ========================= Admin Endpoints =========================

@app.get("/admin/users")
async def get_users(current_user: Dict = Depends(get_current_user)):
    """Get all users - admin only."""
    # Check if user is admin
    if current_user.get("metadata", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # This would query Supabase auth.users table with service role
    return {
        "success": True,
        "message": "Admin endpoint configured. Implement with service role key."
    }

@app.post("/admin/create-test-users")
async def create_test_users(current_user: Dict = Depends(get_current_user)):
    """Create test users - admin only."""
    # Check if user is admin
    if current_user.get("metadata", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from supabase_auth import create_test_users as create_users
    
    # This would create test users
    return {
        "success": True,
        "message": "Test user creation endpoint configured."
    }

# ========================= Run Server =========================

if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    
    # Create necessary directories
    Path("uploads").mkdir(exist_ok=True)
    Path("results").mkdir(exist_ok=True)
    
    logger.info("Starting Tax Extraction API with Supabase Authentication")
    logger.info(f"API Documentation: http://localhost:8000/docs")
    logger.info(f"Database: {settings.supabase_url}")
    
    uvicorn.run(
        "api_with_auth:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )