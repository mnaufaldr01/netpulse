import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401, E402

import pandas as pd
import streamlit as st

from queries import (
    get_all_tower_ids,
    get_congestion_events,
    get_neighbour_impact,
    get_peak_hour_heatmap,
    get_peak_hour_prb_by_dow,
    get_subscriber_impact_summary,
    get_tower_metadata,
    get_tower_prb_series,
)
from viz import build_hourly_pattern_chart, build_peak_hour_heatmap, build_prb_line_chart

st.set_page_config(page_title="Tower Drilldown | netpulse", layout="wide")
st.title("Tower Drilldown")

if "drilldown_tower_id" not in st.session_state:
    st.session_state["drilldown_tower_id"] = None

query_tower = st.query_params.get("tower_id")
if query_tower:
    st.session_state["drilldown_tower_id"] = query_tower

try:
    tower_ids = get_all_tower_ids()
    if not tower_ids:
        st.warning("No towers in tower_master. Run the seed script first.")
        st.stop()

    default_idx = 0
    if st.session_state["drilldown_tower_id"] in tower_ids:
        default_idx = tower_ids.index(st.session_state["drilldown_tower_id"])

    selected = st.selectbox("Tower", tower_ids, index=default_idx)
    st.session_state["drilldown_tower_id"] = selected

    meta = get_tower_metadata(selected)
    if meta is None:
        st.error(f"Metadata not found for tower {selected}")
        st.stop()

    st.subheader(f"Tower `{selected}`")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latitude", f"{meta['lat']:.4f}")
    c2.metric("Longitude", f"{meta['lon']:.4f}")
    c3.metric("Radio / MNC", f"{meta['radio']} / {meta['mnc']}")
    c4.metric("Cell type", meta["cell_type"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Province", meta["province_name"] or "—")
    c2.metric("Island group", meta["island_group"] or "—")
    c3.metric("Warn PRB %", f"{meta['prb_warn_pct']:.0f}")
    c4.metric("Critical PRB %", f"{meta['prb_critical_pct']:.0f}")

    prb_series = get_tower_prb_series(selected, days=7)
    st.plotly_chart(
        build_prb_line_chart(
            prb_series,
            float(meta["prb_warn_pct"]),
            float(meta["prb_critical_pct"]),
        ),
        use_container_width=True,
    )

    st.subheader("Congestion event history")
    events = get_congestion_events(selected)
    if events.empty:
        st.info("No congestion events recorded for this tower.")
    else:
        ev_display = events.copy()
        ev_display["event_date"] = pd.to_datetime(ev_display["event_hour"]).dt.date
        ev_display["event_hour_num"] = pd.to_datetime(ev_display["event_hour"]).dt.hour
        ev_display = ev_display[
            [
                "event_date",
                "event_hour_num",
                "severity",
                "subscriber_count_affected",
                "degraded_session_minutes",
            ]
        ].rename(
            columns={
                "event_hour_num": "hour",
                "subscriber_count_affected": "subscribers_affected",
                "degraded_session_minutes": "degraded_minutes",
            }
        )
        st.dataframe(ev_display, use_container_width=True, hide_index=True)

    st.subheader("Peak hour patterns")
    heatmap_df = get_peak_hour_prb_by_dow(selected)
    if not heatmap_df.empty:
        st.plotly_chart(build_peak_hour_heatmap(heatmap_df), use_container_width=True)
    else:
        pattern = get_peak_hour_heatmap(selected)
        st.plotly_chart(build_hourly_pattern_chart(pattern), use_container_width=True)

    st.subheader("Neighbour impact")
    neighbours = get_neighbour_impact(selected)
    if neighbours.empty:
        st.info("No neighbour spillover relationships detected.")
    else:
        nb = neighbours.rename(
            columns={
                "neighbour_tower_id": "neighbour_tower",
                "province_name": "province",
                "is_spillover": "spillover",
            }
        )
        st.dataframe(nb, use_container_width=True, hide_index=True)

    st.subheader("Subscriber impact")
    impact = get_subscriber_impact_summary(selected)
    c1, c2, c3 = st.columns(3)
    c1.metric("Congestion events", int(impact["congestion_events"]))
    c2.metric("Affected sessions", int(impact["total_affected_sessions"]))
    c3.metric("Degraded minutes", f"{impact['total_degraded_minutes']:.0f}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Voice sessions", int(impact["voice_sessions"]))
    c2.metric("Data sessions", int(impact["data_sessions"]))
    c3.metric("SMS sessions", int(impact["sms_sessions"]))
    st.caption(
        "Service-type breakdown shows session counts; per-type degraded minutes "
        "are not available in the current mart schema."
    )

except Exception as e:
    st.error(f"Failed to load tower drilldown: {e}")
