# Property Tax Management System - Replit Implementation Guide

## 🎯 Project Overview

A comprehensive property tax extraction and management system built on Replit, featuring automated tax data extraction from county websites, property/entity management, and real-time monitoring dashboards.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React/Next.js)                 │
├───────────────────┬─────────────────┬───────────────────────┤
│ Property Dashboard│ Extractor Control│  Reports & Analytics  │
└───────────────────┴─────────────────┴───────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                     │
├─────────────┬──────────────┬─────────────┬─────────────────┤
│  Properties │  Extractors  │   Jobs      │    Reports      │
│   Service   │   Service    │   Queue     │    Service      │
└─────────────┴──────────────┴─────────────┴─────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                               │
├─────────────────────┬───────────────────────────────────────┤
│   SQLite/PostgreSQL │        Redis (Queue/Cache)            │
└─────────────────────┴───────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Extraction Engine                           │
├──────────────┬──────────────┬──────────────┬───────────────┤
│   Maricopa   │  Montgomery  │    Harris    │    Generic    │
│   Extractor  │   Extractor  │   Extractor  │   Extractor   │
└──────────────┴──────────────┴──────────────┴───────────────┘
```

## 📁 Project Structure

```
property-tax-system/
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app
│   │   ├── routes/
│   │   │   ├── properties.py       # Property CRUD endpoints
│   │   │   ├── extractors.py       # Extraction control endpoints
│   │   │   ├── jobs.py            # Job monitoring endpoints
│   │   │   └── reports.py         # Reporting endpoints
│   │   ├── models/
│   │   │   ├── property.py        # SQLAlchemy models
│   │   │   ├── extraction.py
│   │   │   └── job.py
│   │   ├── services/
│   │   │   ├── extraction_service.py
│   │   │   ├── property_service.py
│   │   │   └── notification_service.py
│   │   └── database.py            # Database configuration
│   │
│   ├── extractors/                # Core extraction engine
│   │   ├── tax_extractor.py       # Main extractor (existing)
│   │   ├── strategies/
│   │   │   ├── maricopa.py
│   │   │   ├── montgomery.py
│   │   │   ├── harris.py
│   │   │   └── generic.py
│   │   └── config.yaml            # Extractor configurations
│   │
│   ├── workers/
│   │   ├── extraction_worker.py   # Background job processor
│   │   └── scheduler.py           # Scheduled task runner
│   │
│   └── utils/
│       ├── validators.py
│       └── formatters.py
│
├── frontend/
│   ├── pages/
│   │   ├── index.js               # Main dashboard
│   │   ├── properties/
│   │   │   ├── index.js           # Properties list
│   │   │   └── [id].js           # Property detail
│   │   ├── extractors/
│   │   │   ├── index.js           # Extractor control panel
│   │   │   └── deploy.js          # Deployment interface
│   │   └── reports/
│   │       └── index.js           # Reports dashboard
│   │
│   ├── components/
│   │   ├── PropertyCard.js
│   │   ├── ExtractionStatus.js
│   │   ├── JobMonitor.js
│   │   └── TaxDataTable.js
│   │
│   └── lib/
│       ├── api.js                 # API client
│       └── utils.js
│
├── database/
│   ├── schema.sql                 # Database schema
│   └── migrations/
│
├── tests/
│   ├── test_extractors.py
│   └── test_api.py
│
├── requirements.txt               # Python dependencies
├── package.json                   # Node dependencies
├── .replit                       # Replit configuration
└── replit.nix                    # Nix packages configuration
```

## 🚀 Implementation Steps

### Phase 1: Core Setup (Days 1-2)

#### 1.1 Initialize Replit Project
```bash
# .replit file
run = "python backend/api/main.py"
language = "python3"

[nix]
channel = "stable-23_05"

[deployment]
run = ["sh", "-c", "python backend/api/main.py"]
```

#### 1.2 Install Dependencies
```python
# requirements.txt
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
alembic==1.12.1
redis==5.0.1
celery==5.3.4
playwright==1.40.0
beautifulsoup4==4.12.2
requests==2.31.0
pandas==2.1.3
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.0
```

#### 1.3 Database Schema
```sql
-- database/schema.sql

-- Entities table
CREATE TABLE entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- 'entity' or 'sub-entity'
    parent_id INTEGER REFERENCES entities(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Properties table
CREATE TABLE properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    address TEXT,
    jurisdiction TEXT NOT NULL,
    state TEXT NOT NULL,
    property_type TEXT NOT NULL,
    entity_id INTEGER REFERENCES entities(id),
    acct_number TEXT,
    tax_bill_link TEXT,
    extraction_steps TEXT,
    close_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Extractions table
CREATE TABLE extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER REFERENCES properties(id),
    status TEXT NOT NULL, -- 'pending', 'running', 'success', 'failed'
    extracted_data JSON,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Jobs table
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL, -- 'single', 'batch', 'scheduled'
    status TEXT NOT NULL,
    payload JSON,
    result JSON,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Tax data table
CREATE TABLE tax_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER REFERENCES properties(id),
    extraction_id INTEGER REFERENCES extractions(id),
    tax_year INTEGER,
    amount_due DECIMAL(10,2),
    previous_year_taxes DECIMAL(10,2),
    due_date DATE,
    raw_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Phase 2: Backend API (Days 3-5)

#### 2.1 FastAPI Application
```python
# backend/api/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn

app = FastAPI(title="Property Tax Management System")

# CORS configuration for Replit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from routes import properties, extractors, jobs, reports
app.include_router(properties.router, prefix="/api/properties", tags=["properties"])
app.include_router(extractors.router, prefix="/api/extractors", tags=["extractors"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

@app.get("/")
def root():
    return {"message": "Property Tax Management System API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

#### 2.2 Property Management Endpoints
```python
# backend/api/routes/properties.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/")
def list_properties(
    skip: int = 0, 
    limit: int = 100,
    entity_id: Optional[int] = None,
    jurisdiction: Optional[str] = None
):
    """List all properties with filtering"""
    # Implementation here
    pass

@router.post("/")
def create_property(property_data: dict):
    """Create a new property"""
    pass

@router.get("/{property_id}")
def get_property(property_id: int):
    """Get property details with latest tax data"""
    pass

@router.put("/{property_id}")
def update_property(property_id: int, property_data: dict):
    """Update property information"""
    pass

@router.delete("/{property_id}")
def delete_property(property_id: int):
    """Delete a property"""
    pass

@router.post("/import-csv")
async def import_csv(file: UploadFile):
    """Import properties from CSV file"""
    pass
```

#### 2.3 Extractor Control Endpoints
```python
# backend/api/routes/extractors.py
from fastapi import APIRouter, BackgroundTasks
from typing import List

router = APIRouter()

@router.post("/deploy/single/{property_id}")
async def deploy_single_extraction(
    property_id: int,
    background_tasks: BackgroundTasks
):
    """Deploy extraction for a single property"""
    background_tasks.add_task(run_extraction, property_id)
    return {"message": "Extraction started", "job_id": job_id}

@router.post("/deploy/batch")
async def deploy_batch_extraction(
    property_ids: List[int],
    background_tasks: BackgroundTasks
):
    """Deploy extraction for multiple properties"""
    job_id = create_batch_job(property_ids)
    background_tasks.add_task(run_batch_extraction, property_ids, job_id)
    return {"message": "Batch extraction started", "job_id": job_id}

@router.post("/deploy/all")
async def deploy_all_extractions(background_tasks: BackgroundTasks):
    """Deploy extraction for all properties"""
    pass

@router.get("/status")
def get_extractor_status():
    """Get current extractor system status"""
    return {
        "active_jobs": 0,
        "queued_jobs": 0,
        "completed_today": 0,
        "failed_today": 0,
        "extractors": {
            "maricopa": "online",
            "montgomery": "online",
            "harris": "online",
            "generic": "online"
        }
    }

@router.get("/config")
def get_extractor_config():
    """Get extractor configurations"""
    pass

@router.put("/config")
def update_extractor_config(config: dict):
    """Update extractor configurations"""
    pass
```

### Phase 3: Frontend Dashboard (Days 6-8)

#### 3.1 Main Dashboard
```javascript
// frontend/pages/index.js
import { useState, useEffect } from 'react';
import Link from 'next/link';

export default function Dashboard() {
  const [stats, setStats] = useState({
    totalProperties: 0,
    totalEntities: 0,
    extractionsToday: 0,
    failedExtractions: 0,
    upcomingDueDates: []
  });

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  return (
    <div className="dashboard">
      <h1>Property Tax Management System</h1>
      
      <div className="stats-grid">
        <StatCard title="Total Properties" value={stats.totalProperties} />
        <StatCard title="Total Entities" value={stats.totalEntities} />
        <StatCard title="Extractions Today" value={stats.extractionsToday} />
        <StatCard title="Failed Extractions" value={stats.failedExtractions} alert />
      </div>

      <div className="quick-actions">
        <Link href="/properties">
          <button>Manage Properties</button>
        </Link>
        <Link href="/extractors">
          <button>Deploy Extractors</button>
        </Link>
        <Link href="/reports">
          <button>View Reports</button>
        </Link>
      </div>

      <div className="upcoming-dues">
        <h2>Upcoming Due Dates</h2>
        <DueDatesList items={stats.upcomingDueDates} />
      </div>
    </div>
  );
}
```

#### 3.2 Property Management Dashboard
```javascript
// frontend/pages/properties/index.js
import { useState, useEffect } from 'react';
import PropertyCard from '../../components/PropertyCard';
import { api } from '../../lib/api';

export default function Properties() {
  const [properties, setProperties] = useState([]);
  const [filters, setFilters] = useState({
    entity: null,
    jurisdiction: null,
    status: null
  });
  const [view, setView] = useState('grid'); // 'grid' or 'table'

  useEffect(() => {
    loadProperties();
  }, [filters]);

  const loadProperties = async () => {
    const data = await api.get('/properties', { params: filters });
    setProperties(data);
  };

  const handleExtract = async (propertyId) => {
    await api.post(`/extractors/deploy/single/${propertyId}`);
    // Show notification
  };

  return (
    <div className="properties-dashboard">
      <div className="header">
        <h1>Properties & Entities</h1>
        <div className="actions">
          <button onClick={() => setView(view === 'grid' ? 'table' : 'grid')}>
            Toggle View
          </button>
          <button className="import-btn">Import CSV</button>
          <button className="add-btn">Add Property</button>
        </div>
      </div>

      <div className="filters">
        <select onChange={(e) => setFilters({...filters, entity: e.target.value})}>
          <option value="">All Entities</option>
          {/* Entity options */}
        </select>
        <select onChange={(e) => setFilters({...filters, jurisdiction: e.target.value})}>
          <option value="">All Jurisdictions</option>
          {/* Jurisdiction options */}
        </select>
        <input type="text" placeholder="Search properties..." />
      </div>

      {view === 'grid' ? (
        <div className="properties-grid">
          {properties.map(property => (
            <PropertyCard 
              key={property.id}
              property={property}
              onExtract={handleExtract}
            />
          ))}
        </div>
      ) : (
        <PropertiesTable 
          properties={properties}
          onExtract={handleExtract}
        />
      )}
    </div>
  );
}
```

#### 3.3 Extractor Deployment Dashboard
```javascript
// frontend/pages/extractors/index.js
import { useState, useEffect } from 'react';
import JobMonitor from '../../components/JobMonitor';

export default function Extractors() {
  const [activeJobs, setActiveJobs] = useState([]);
  const [extractorStatus, setExtractorStatus] = useState({});
  const [selectedProperties, setSelectedProperties] = useState([]);
  const [deploymentMode, setDeploymentMode] = useState('single'); // 'single', 'batch', 'all'

  const deployExtraction = async () => {
    if (deploymentMode === 'single') {
      // Deploy for selected property
    } else if (deploymentMode === 'batch') {
      // Deploy batch
    } else {
      // Deploy all
    }
  };

  return (
    <div className="extractor-dashboard">
      <h1>Extractor Control Panel</h1>
      
      <div className="extractor-status">
        <h2>System Status</h2>
        <div className="status-grid">
          <StatusIndicator name="Maricopa" status={extractorStatus.maricopa} />
          <StatusIndicator name="Montgomery" status={extractorStatus.montgomery} />
          <StatusIndicator name="Harris" status={extractorStatus.harris} />
          <StatusIndicator name="Generic" status={extractorStatus.generic} />
        </div>
      </div>

      <div className="deployment-section">
        <h2>Deploy Extractors</h2>
        <div className="deployment-controls">
          <select value={deploymentMode} onChange={(e) => setDeploymentMode(e.target.value)}>
            <option value="single">Single Property</option>
            <option value="batch">Batch</option>
            <option value="all">All Properties</option>
          </select>
          
          {deploymentMode !== 'all' && (
            <PropertySelector 
              mode={deploymentMode}
              selected={selectedProperties}
              onChange={setSelectedProperties}
            />
          )}
          
          <button className="deploy-btn" onClick={deployExtraction}>
            Deploy Extraction
          </button>
        </div>
      </div>

      <div className="job-monitor">
        <h2>Active Jobs</h2>
        <JobMonitor jobs={activeJobs} />
      </div>

      <div className="extraction-history">
        <h2>Recent Extractions</h2>
        <ExtractionHistory />
      </div>
    </div>
  );
}
```

### Phase 4: Background Workers (Days 9-10)

#### 4.1 Extraction Worker
```python
# backend/workers/extraction_worker.py
import asyncio
from celery import Celery
from extractors.tax_extractor import PropertyTaxExtractor, PropertyTaxRecord

app = Celery('tasks', broker='redis://localhost:6379')

@app.task
def run_single_extraction(property_id: int):
    """Run extraction for a single property"""
    # Load property from database
    property_data = get_property_from_db(property_id)
    
    # Create PropertyTaxRecord
    record = PropertyTaxRecord(**property_data)
    
    # Run extraction
    extractor = PropertyTaxExtractor(headless=True)
    result = asyncio.run(extractor.extract_single(record))
    
    # Save results to database
    save_extraction_result(result)
    
    return {"status": "success", "property_id": property_id}

@app.task
def run_batch_extraction(property_ids: list):
    """Run extraction for multiple properties"""
    results = []
    for property_id in property_ids:
        try:
            result = run_single_extraction(property_id)
            results.append(result)
        except Exception as e:
            results.append({"status": "failed", "property_id": property_id, "error": str(e)})
    return results
```

#### 4.2 Scheduler
```python
# backend/workers/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

scheduler = BackgroundScheduler()

def schedule_daily_extractions():
    """Run daily extraction for properties with upcoming due dates"""
    # Get properties with due dates in next 30 days
    properties = get_properties_with_upcoming_dues(days=30)
    
    for property in properties:
        run_single_extraction.delay(property.id)

def schedule_weekly_full_extraction():
    """Run weekly extraction for all properties"""
    all_properties = get_all_active_properties()
    
    # Batch into groups of 10
    for i in range(0, len(all_properties), 10):
        batch = all_properties[i:i+10]
        run_batch_extraction.delay([p.id for p in batch])

# Schedule jobs
scheduler.add_job(schedule_daily_extractions, 'cron', hour=6)
scheduler.add_job(schedule_weekly_full_extraction, 'cron', day_of_week='sun', hour=2)
scheduler.start()
```

### Phase 5: Deployment & Configuration (Day 11)

#### 5.1 Replit Configuration
```nix
# replit.nix
{ pkgs }: {
  deps = [
    pkgs.python310
    pkgs.nodejs-18_x
    pkgs.redis
    pkgs.postgresql
    pkgs.chromium
    pkgs.chromedriver
  ];
}
```

#### 5.2 Environment Variables
```bash
# .env
DATABASE_URL=sqlite:///./property_tax.db
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key-here
EXTRACTION_TIMEOUT=30000
MAX_CONCURRENT_EXTRACTIONS=3
HEADLESS_BROWSER=true
LOG_LEVEL=INFO
```

#### 5.3 Startup Script
```python
# start.py
import subprocess
import time
import os

def start_services():
    """Start all required services"""
    
    # Start Redis
    subprocess.Popen(['redis-server'])
    time.sleep(2)
    
    # Start Celery worker
    subprocess.Popen(['celery', '-A', 'backend.workers.extraction_worker', 'worker', '--loglevel=info'])
    time.sleep(2)
    
    # Start scheduler
    subprocess.Popen(['python', 'backend/workers/scheduler.py'])
    time.sleep(1)
    
    # Start FastAPI
    subprocess.Popen(['uvicorn', 'backend.api.main:app', '--host', '0.0.0.0', '--port', '8000'])
    
    # Start Next.js frontend
    os.chdir('frontend')
    subprocess.Popen(['npm', 'run', 'dev'])

if __name__ == "__main__":
    start_services()
    print("All services started!")
    
    # Keep the main process running
    while True:
        time.sleep(60)
```

## 📊 Key Features

### Property Management
- ✅ CRUD operations for properties and entities
- ✅ CSV import/export
- ✅ Entity hierarchy (parent/child relationships)
- ✅ Search and filtering
- ✅ Bulk operations

### Extraction Engine
- ✅ County-specific extractors
- ✅ Automatic retry with exponential backoff
- ✅ Concurrent extraction support
- ✅ Error handling and logging
- ✅ Direct HTTP and browser-based extraction

### Monitoring & Reporting
- ✅ Real-time job monitoring
- ✅ Extraction success/failure rates
- ✅ Historical data tracking
- ✅ Due date alerts
- ✅ Export to Excel/PDF

### Dashboard Features
- ✅ Property overview with tax data
- ✅ Extractor deployment interface
- ✅ Job queue visualization
- ✅ Performance metrics
- ✅ Alert management

## 🔧 Maintenance & Operations

### Adding New County Extractors
1. Create new extractor class in `backend/extractors/strategies/`
2. Add configuration to `extractors/config.yaml`
3. Register in `PropertyTaxExtractor` class
4. Test with sample properties
5. Deploy to production

### Monitoring Checklist
- [ ] Daily extraction success rate > 95%
- [ ] Average extraction time < 30 seconds
- [ ] Queue depth < 100 jobs
- [ ] Error rate < 5%
- [ ] Database size monitoring

### Backup Strategy
```python
# backup.py
import shutil
from datetime import datetime

def backup_database():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy('property_tax.db', f'backups/property_tax_{timestamp}.db')

# Run daily via scheduler
```

## 🚦 Getting Started

1. **Fork the Replit template** (once created)
2. **Set environment variables** in Replit Secrets
3. **Run database migrations**:
   ```bash
   python -m alembic upgrade head
   ```
4. **Import initial data**:
   ```bash
   python scripts/import_csv.py completed-proptax-data.csv
   ```
5. **Start the application**:
   ```bash
   python start.py
   ```
6. **Access the dashboard** at your Replit URL

## 📈 Scaling Considerations

### Performance Optimization
- Implement Redis caching for frequently accessed data
- Use connection pooling for database
- Optimize Playwright browser reuse
- Implement request batching

### High Availability
- Use Replit Always On for 24/7 availability
- Implement health checks and auto-restart
- Set up error alerting via email/Slack
- Regular automated backups

## 🔒 Security

- API authentication with JWT tokens
- Rate limiting on extraction endpoints
- Input validation and sanitization
- Secure storage of tax bill URLs
- Audit logging for all operations

## 📝 Testing

```python
# tests/test_extractors.py
import pytest
from backend.extractors.tax_extractor import PropertyTaxExtractor

@pytest.mark.asyncio
async def test_montgomery_extraction():
    """Test Montgomery County extraction"""
    # Test implementation
    pass

@pytest.mark.asyncio  
async def test_maricopa_extraction():
    """Test Maricopa County extraction"""
    # Test implementation
    pass
```

## 🎯 Success Metrics

- **Extraction Success Rate**: Target > 95%
- **Processing Time**: < 30 seconds per property
- **System Uptime**: > 99.5%
- **User Response Time**: < 200ms for dashboard
- **Data Accuracy**: 100% for extracted amounts

## 📚 Documentation

### API Documentation
Available at `/docs` endpoint (FastAPI automatic documentation)

### User Guide
1. Property management workflows
2. Extraction deployment procedures
3. Report generation
4. Troubleshooting guide

## 🤝 Support & Maintenance

- Weekly extraction pattern reviews
- Monthly performance optimization
- Quarterly security audits
- Continuous monitoring and alerting

---

**Built with ❤️ for efficient property tax management**