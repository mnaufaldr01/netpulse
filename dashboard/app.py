"""netpulse Streamlit dashboard — Phase 1 stub."""

import streamlit as st

st.set_page_config(page_title="netpulse", layout="wide")

st.title("netpulse")
st.markdown("Telco Network Congestion Hotspot Intelligence")

st.info(
    "Dashboard pages will be implemented in Week 2. "
    "Ensure PostgreSQL is running and pipeline marts are built via dbt."
)

st.markdown("""
### Pages (coming soon)
1. **Network Health Map** — pydeck tower map + province choropleth
2. **Hotspot Leaderboard** — tower and province rankings
3. **Tower Drilldown** — per-tower metrics and charts
4. **Active Alerts** — operational alert panel
""")

if st.button("Check database connection"):
    try:
        from netpulse.db import db_cursor
        with db_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tower_master")
            count = cur.fetchone()[0]
        st.success(f"Connected — {count} towers in tower_master")
    except Exception as e:
        st.error(f"Connection failed: {e}")
