#!/usr/bin/env python3
"""
Entry point for the Streamlit dashboard - redirects to the actual implementation.
This file is kept at root for deployment compatibility.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run the actual dashboard
from src.dashboard.streamlit_app import *