#!/bin/bash

# Start all tax extractor services

echo "Starting Tax Extractor Services..."

# Check if Redis is running
if ! pgrep -x "redis-server" > /dev/null
then
    echo "Starting Redis..."
    redis-server --daemonize yes
fi

# Start Celery worker in background
echo "Starting Celery worker..."
celery -A celery_queue worker --loglevel=info --detach

# Start Celery beat scheduler (for periodic tasks)
echo "Starting Celery beat..."
celery -A celery_queue beat --loglevel=info --detach

# Optional: Start Flower for Celery monitoring
# echo "Starting Flower (Celery monitoring)..."
# celery -A celery_queue flower --detach

# Start FastAPI service
echo "Starting FastAPI service..."
uvicorn api_public:app --host 0.0.0.0 --port 8000 --reload &

# Wait for API to start
sleep 3

# Start Streamlit dashboard
echo "Starting Streamlit dashboard..."
streamlit run dashboard.py --server.port 8501 &

echo ""
echo "Services started successfully!"
echo ""
echo "Access points:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Dashboard: http://localhost:8501"
# echo "  - Celery Flower: http://localhost:5555"
echo ""
echo "To stop all services, run: ./stop_services.sh"