"""netpulse Streamlit dashboard."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: F401, E402

import streamlit as st

from queries import check_db_connection, get_home_metrics

st.set_page_config(page_title="netpulse", layout="wide", page_icon="📡")

st.session_state.setdefault("drilldown_tower_id", None)
st.session_state.setdefault("map_tower_id", None)
st.session_state.setdefault("map_province", None)

st.title("netpulse")
st.markdown("**Telco Network Congestion Hotspot Intelligence**")

st.markdown(
    """
Use the sidebar to navigate:
- **Network Health Map** — province choropleth and tower health overlay
- **Hotspot Leaderboard** — ranked towers and provinces
- **Tower Drilldown** — per-tower metrics and charts
- **Active Alerts** — operational alert panel
"""
)

if st.button("Check database connection"):
    ok, message = check_db_connection()
    if ok:
        st.success(message)
    else:
        st.error(f"Connection failed: {message}")

try:
    metrics = get_home_metrics()
    c1, c2, c3 = st.columns(3)
    c1.metric("Towers", metrics["tower_count"])
    c2.metric("Active alerts", metrics["active_alerts"])
    c3.metric("Avg network health", f"{metrics['avg_health_score']:.1f}")
except Exception as e:
    st.warning(f"Could not load pipeline metrics: {e}")
    st.info("Ensure PostgreSQL is running and dbt marts are built.")
