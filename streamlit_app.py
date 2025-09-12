#!/usr/bin/env python3
"""
Entry point for the Streamlit dashboard.

Adds a resilient blank-page status fallback: we attempt to
load the real dashboard module each run; if it fails or renders
no content, we display a friendly diagnostic message instead of
a blank page.
"""

import os
import sys
import importlib
import traceback

# Ensure project root is on sys.path so `src` is importable
ROOT_DIR = os.path.dirname(__file__)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Signal not-yet-rendered; the dashboard module will flip this to "1"
# after it successfully builds the UI.
os.environ["DASHBOARD_RENDERED"] = "0"

def _show_blank_page_status(error: Exception | None = None):
    """Render a minimal status UI when the page would otherwise be blank."""
    # Import here so we don't call any Streamlit APIs before the
    # dashboard module has a chance to set page config when it works.
    import streamlit as st

    st.title("🏢 Property Tax Dashboard")

    if error is None:
        st.warning("Dashboard loaded but no content rendered yet.")
        st.info(
            "If this persists, try Refresh, clear cache, or check API availability."
        )
    else:
        st.error("Dashboard failed to load the main module.")
        with st.expander("Show error details"):
            st.code("""{}""".format(traceback.format_exc()), language="text")

    st.caption("Blank-page fallback active · This message disappears once the dashboard renders.")

# Import the actual dashboard module and reload it to ensure
# its top-level Streamlit code runs on every rerun.
_mod_name = "src.dashboard.streamlit_app"
try:
    if _mod_name in sys.modules:
        importlib.reload(sys.modules[_mod_name])
    else:
        importlib.import_module(_mod_name)
except Exception as e:
    # On import failure, show a helpful fallback instead of a blank page.
    _show_blank_page_status(error=e)
else:
    # If the module loaded but didn't render any UI, show the fallback.
    if os.environ.get("DASHBOARD_RENDERED") != "1":
        _show_blank_page_status()
