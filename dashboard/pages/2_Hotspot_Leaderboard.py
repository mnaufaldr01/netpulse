import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401, E402

import streamlit as st

from queries import get_hotspot_towers, get_province_leaderboard

st.set_page_config(page_title="Hotspot Leaderboard | netpulse", layout="wide")
st.title("Hotspot Leaderboard")
st.caption("Ranked congestion hotspots for network operations and planning teams.")

window = st.selectbox("Rolling window", ["7d", "30d"], index=0)
tab_tower, tab_province = st.tabs(["Tower leaderboard", "Province leaderboard"])

try:
    with tab_tower:
        towers = get_hotspot_towers(window)
        if towers.empty:
            st.warning("No hotspot data available. Run dbt marts first.")
        else:
            display = towers.copy()
            display.insert(0, "rank", range(1, len(display) + 1))
            display = display[
                [
                    "rank",
                    "tower_id",
                    "province_name",
                    "cell_type",
                    "radio",
                    "congestion_frequency",
                    "avg_prb_utilization",
                    "peak_congestion_hour",
                    "total_affected_subscriber_hours",
                ]
            ].rename(
                columns={
                    "province_name": "province",
                    "congestion_frequency": "congestion_frequency_pct",
                    "avg_prb_utilization": "avg_prb_pct",
                    "total_affected_subscriber_hours": "affected_subscriber_hours",
                }
            )
            display["congestion_frequency_pct"] = display["congestion_frequency_pct"].round(1)
            display["avg_prb_pct"] = display["avg_prb_pct"].round(1)

            selection = st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"tower_lb_{window}",
            )

            selected_rows = []
            if selection is not None:
                sel = getattr(selection, "selection", None) or selection.get("selection", {})
                selected_rows = getattr(sel, "rows", None) or sel.get("rows", [])

            tower_pick = st.selectbox(
                "Or select tower for drilldown",
                ["—"] + display["tower_id"].tolist(),
                key="tower_drill_pick",
            )
            if selected_rows:
                picked_id = display.iloc[selected_rows[0]]["tower_id"]
                if st.button("Open tower drilldown", key="lb_drill_btn"):
                    st.session_state["drilldown_tower_id"] = picked_id
                    st.switch_page("pages/3_Tower_Drilldown.py")
            elif tower_pick != "—":
                if st.button("Open tower drilldown", key="lb_drill_pick_btn"):
                    st.session_state["drilldown_tower_id"] = tower_pick
                    st.switch_page("pages/3_Tower_Drilldown.py")

    with tab_province:
        provinces = get_province_leaderboard()
        if provinces.empty:
            st.warning("No provinces with congested towers.")
        else:
            display = provinces.copy()
            display.insert(0, "rank", range(1, len(display) + 1))
            display = display[
                [
                    "rank",
                    "province_name",
                    "island_group",
                    "tower_count",
                    "congested_tower_count",
                    "congestion_rate",
                    "avg_health_score",
                    "total_affected_subscriber_hours",
                ]
            ].rename(
                columns={
                    "congested_tower_count": "congested_towers",
                    "congestion_rate": "congestion_rate_pct",
                    "total_affected_subscriber_hours": "affected_subscriber_hours_7d",
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)
            st.caption(
                "Province subscriber-hours column reflects 7-day rolling window "
                "(mart_province_summary limitation)."
            )

except Exception as e:
    st.error(f"Failed to load leaderboard: {e}")
