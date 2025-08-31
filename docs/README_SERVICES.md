# Tax Extractor Services

This package provides three integrated services for the Tax Extractor system:

## Components

### 1. REST API Service (`api_service.py`)
FastAPI-based REST API for submitting and managing extraction jobs.

**Features:**
- Async job submission
- File upload endpoint
- Job status monitoring
- Results download (Excel/JSON)
- Health checks

**Endpoints:**
- `POST /extract` - Submit extraction job
- `POST /extract/upload` - Upload CSV and extract
- `GET /jobs/{job_id}` - Get job status
- `GET /jobs/{job_id}/results` - Download results
- `GET /jobs` - List all jobs
- `DELETE /jobs/{job_id}` - Cancel job

### 2. Celery Job Queue (`celery_queue.py`)
Distributed task queue for background processing.

**Features:**
- Redis-backed job queue
- Progress tracking
- Scheduled extractions
- Batch processing
- Auto-cleanup of old results

### 3. Streamlit Dashboard (`dashboard.py`)
Interactive web UI for extraction management.

**Features:**
- File upload interface
- Real-time job monitoring
- Results download
- Analytics and metrics
- Job history

## Installation

```bash
# Install additional requirements
pip install -r requirements_services.txt

# Install Redis (macOS)
brew install redis

# Install Redis (Ubuntu)
sudo apt-get install redis-server
```

## Quick Start

```bash
# Start all services
./start_services.sh

# Access services
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Dashboard: http://localhost:8501

# Stop all services
./stop_services.sh
```

## Manual Service Start

```bash
# 1. Start Redis
redis-server

# 2. Start Celery worker
celery -A celery_queue worker --loglevel=info

# 3. Start API service
uvicorn api_service:app --reload

# 4. Start Dashboard
streamlit run dashboard.py
```

## Usage Examples

### Using the API

```python
import requests

# Submit extraction job
with open('properties.csv', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/extract/upload',
        files={'file': f},
        params={'concurrent': True, 'max_workers': 5}
    )
    job_id = response.json()['job_id']

# Check job status
status = requests.get(f'http://localhost:8000/jobs/{job_id}')
print(status.json())

# Download results
results = requests.get(f'http://localhost:8000/jobs/{job_id}/results')
with open('results.xlsx', 'wb') as f:
    f.write(results.content)
```

### Using Celery Queue

```python
from celery_queue import submit_extraction, get_task_status

# Submit task
task_id = submit_extraction(
    input_file='properties.csv',
    concurrent=True,
    max_workers=5
)

# Check status
status = get_task_status(task_id)
print(status)
```

## Configuration

### API Configuration
Edit `api_service.py`:
- Change port: `uvicorn.run(app, port=8000)`
- Adjust timeouts and limits

### Celery Configuration
Edit `celery_queue.py`:
- Redis connection: `broker='redis://localhost:6379/0'`
- Task time limits
- Worker concurrency

### Dashboard Configuration
Edit `dashboard.py`:
- API URL: `API_BASE_URL = "http://localhost:8000"`
- Refresh interval
- UI themes

## Monitoring

### Celery Flower (Optional)
```bash
# Install
pip install flower

# Start
celery -A celery_queue flower

# Access at http://localhost:5555
```

### API Health Check
```bash
curl http://localhost:8000/health
```

## Troubleshooting

### Redis Connection Issues
```bash
# Check Redis status
redis-cli ping

# Start Redis if not running
redis-server --daemonize yes
```

### Port Already in Use
```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Celery Worker Issues
```bash
# Check worker status
celery -A celery_queue status

# Purge all tasks
celery -A celery_queue purge
```

## Production Deployment

### Using Docker
Create a `docker-compose.yml` for containerized deployment.

### Using Systemd
Create service files for each component.

### Scaling
- Use multiple Celery workers
- Deploy API behind a load balancer
- Use Redis Cluster for high availability

## Security Considerations

- Add authentication to API endpoints
- Use HTTPS in production
- Secure Redis with password
- Implement rate limiting
- Validate file uploads