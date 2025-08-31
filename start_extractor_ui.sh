#!/bin/bash

# Tax Extractor UI Service Startup Script
# This script starts the self-hosted tax extractor UI with proper configuration

set -e

echo "🚀 Tax Extractor UI Service Startup"
echo "=================================="

# Check for required environment variables
if [ -z "$SUPABASE_ANON_KEY" ]; then
    echo "⚠️  Warning: SUPABASE_ANON_KEY not set. Supabase integration will be disabled."
    echo "   To enable, set SUPABASE_ANON_KEY in .env file"
fi

# Create necessary directories
mkdir -p logs
mkdir -p extraction_data
mkdir -p screenshots

# Check if running with Docker
if [ "$1" == "docker" ]; then
    echo "📦 Starting with Docker Compose..."
    
    # Build the Docker image
    docker-compose -f docker-compose.extractor.yml build
    
    # Start the services
    docker-compose -f docker-compose.extractor.yml up -d
    
    echo "✅ Services started!"
    echo "   - UI: http://localhost:8001"
    echo "   - API Docs: http://localhost:8001/docs"
    echo ""
    echo "📊 View logs: docker-compose -f docker-compose.extractor.yml logs -f"
    echo "🛑 Stop services: docker-compose -f docker-compose.extractor.yml down"
    
else
    echo "🐍 Starting with Python..."
    
    # Check Python version
    python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
    required_version="3.9"
    
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
        echo "❌ Error: Python $required_version or higher is required (found $python_version)"
        exit 1
    fi
    
    # Install/update dependencies if needed
    if [ "$1" == "install" ] || [ ! -d "venv" ]; then
        echo "📦 Installing dependencies..."
        
        # Create virtual environment if it doesn't exist
        if [ ! -d "venv" ]; then
            python3 -m venv venv
        fi
        
        # Activate virtual environment
        source venv/bin/activate
        
        # Upgrade pip
        pip install --upgrade pip
        
        # Install requirements
        pip install -r requirements.txt
        
        # Install Playwright browsers
        playwright install chromium
        playwright install-deps
        
        echo "✅ Dependencies installed!"
    else
        # Activate existing virtual environment
        source venv/bin/activate
    fi
    
    # Load environment variables
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
    
    # Start the service
    echo "🌐 Starting Tax Extractor UI Service..."
    echo "   - UI: http://localhost:8001"
    echo "   - API Docs: http://localhost:8001/docs"
    echo ""
    echo "Press Ctrl+C to stop"
    echo ""
    
    # Run the service
    python extractor_ui_service.py
fi