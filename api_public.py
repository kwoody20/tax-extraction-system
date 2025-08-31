#!/usr/bin/env python3
"""
Entry point for the API service - redirects to the actual implementation.
This file is kept at root for deployment compatibility.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run the actual API
from src.api.api_public import *

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))