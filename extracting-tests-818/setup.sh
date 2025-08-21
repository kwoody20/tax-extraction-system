#!/bin/bash

echo "Setting up Property Tax Data Extractor..."

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "Error: Python 3.8+ is required. Current version: $python_version"
    exit 1
fi

echo "✓ Python version OK: $python_version"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install chromium

# Make run script executable
chmod +x run_extraction.py

echo ""
echo "✓ Setup complete!"
echo ""
echo "To activate the environment and run the extractor:"
echo "  source venv/bin/activate"
echo ""
echo "Usage examples:"
echo "  # Test mode (extract 5 sample properties with visible browser):"
echo "  python run_extraction.py --mode test --limit 5"
echo ""
echo "  # Extract all properties:"
echo "  python run_extraction.py --mode all"
echo ""
echo "  # Extract specific jurisdiction:"
echo "  python run_extraction.py --mode jurisdiction --jurisdiction 'Harris'"
echo ""
echo "  # Extract specific properties by ID:"
echo "  python run_extraction.py --mode specific --ids 0647afda-e37a-4044-83df-89b1a44a6f35"