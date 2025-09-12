#!/usr/bin/env python3
"""
Entry point for the Streamlit dashboard.

Previously this file relied on a star-import of the real app module
which only executes once. Streamlit reruns the script on every
interaction; without re-executing the app module, the page can
appear blank on reruns. We now import the module and reload it on
each run so its top-level UI code executes every time.
"""

import os
import sys
import importlib

# Ensure project root is on sys.path so `src` is importable
ROOT_DIR = os.path.dirname(__file__)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Import the actual dashboard module and reload it to ensure
# its top-level Streamlit code runs on every rerun.
import src.dashboard.streamlit_app as _dashboard_app
importlib.reload(_dashboard_app)
