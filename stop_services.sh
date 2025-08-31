#!/bin/bash

# Stop all tax extractor services

echo "Stopping Tax Extractor Services..."

# Stop Streamlit
echo "Stopping Streamlit dashboard..."
pkill -f "streamlit run dashboard.py"

# Stop FastAPI
echo "Stopping FastAPI service..."
pkill -f "uvicorn api_public:app"

# Stop Celery workers
echo "Stopping Celery workers..."
celery -A celery_queue control shutdown

# Stop Celery beat
echo "Stopping Celery beat..."
pkill -f "celery -A celery_queue beat"

# Stop Flower if running
pkill -f "celery -A celery_queue flower"

# Optional: Stop Redis (comment out if you want to keep Redis running)
# echo "Stopping Redis..."
# redis-cli shutdown

echo ""
echo "All services stopped."