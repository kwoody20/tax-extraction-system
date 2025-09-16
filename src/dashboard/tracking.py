"""Utilities for injecting analytics scripts into Streamlit dashboards."""

from __future__ import annotations

import os
from typing import Optional

import streamlit as st
from streamlit.components.v1 import html

_DEFAULT_GA_KEY = "goog_analytics_ga_id"


def _resolve_tracking_id(candidate: Optional[str], fallback: Optional[str]) -> Optional[str]:
    """Return the first available tracking id from secrets/env/defaults."""
    if candidate:
        return candidate

    try:
        secret_value = st.secrets.get("GA_MEASUREMENT_ID")  # type: ignore[attr-defined]
    except Exception:
        secret_value = None

    return secret_value or os.getenv("GA_MEASUREMENT_ID") or fallback


def inject_google_analytics(tracking_id: Optional[str] = None, *, default: Optional[str] = None) -> None:
    """Embed a Google Analytics tag once per session.

    Parameters
    ----------
    tracking_id:
        Explicit GA measurement ID. If omitted, the function looks for
        ``GA_MEASUREMENT_ID`` in Streamlit secrets or environment variables.
    default:
        Optional fallback used when neither the explicit value nor the
        configuration value is available.
    """

    measurement_id = _resolve_tracking_id(tracking_id, default)
    if not measurement_id:
        return

    # Avoid duplicating the tag across reruns within the same session.
    session_key = f"_{_DEFAULT_GA_KEY}"
    if st.session_state.get(session_key) == measurement_id:
        return

    html(
        f"""
        <!-- Google tag (gtag.js) -->
        <script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){{dataLayer.push(arguments);}}
          gtag('js', new Date());
          gtag('config', '{measurement_id}');
        </script>
        """,
        height=0,
    )
    st.session_state[session_key] = measurement_id


__all__ = ["inject_google_analytics"]
