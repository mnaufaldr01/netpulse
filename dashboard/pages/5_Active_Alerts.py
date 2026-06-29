import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401, E402

import streamlit as st

from queries import get_active_alerts, get_alert_summary, get_filter_options

st.set_page_config(page_title="Active Alerts | netpulse", layout="wide")
st.title("Active Alerts")
st.caption("Operational alert panel sourced from the alerts table (ACTIVE only).")

try:
    summary = get_alert_summary()
    options = get_filter_options()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total active", summary["total_active"])
    c2.metric("Critical", summary["critical_count"])
    c3.metric("Towers affected", summary["towers_affected"])
    c4.metric("Provinces affected", summary["provinces_affected"])
    c5.metric("Oldest alert (days)", summary["oldest_alert_days"])

    f1, f2, f3 = st.columns(3)
    with f1:
        alert_type = st.selectbox(
            "Alert type",
            ["All", "CRITICAL", "WARN", "PATTERN", "SPILLOVER"],
        )
    with f2:
        province = st.selectbox("Province", options["provinces"])
    with f3:
        island_group = st.selectbox("Island group", options["island_groups"])

    alerts = get_active_alerts(alert_type, province, island_group)

    if alerts.empty:
        st.warning("No active alerts match the selected filters.")
    else:
        display = alerts[
            [
                "tower_id",
                "province_name",
                "alert_type",
                "severity",
                "message",
                "triggered_at",
                "days_active",
            ]
        ].copy()
        display["days_active"] = display["days_active"].round(1)
        display = display.rename(
            columns={
                "province_name": "province",
                "triggered_at": "triggered_at",
            }
        )
        st.dataframe(display, use_container_width=True, hide_index=True)

        st.caption(f"Showing {len(display)} alert(s).")

except Exception as e:
    st.error(f"Failed to load alerts: {e}")
    st.info("Ensure PostgreSQL is running, marts are built, and the alert DAG has run.")
