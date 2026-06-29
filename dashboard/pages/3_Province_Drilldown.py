import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401, E402

import streamlit as st

from queries import get_all_provinces, get_province_map_data, get_province_towers
from viz import build_network_map

st.set_page_config(page_title="Province Drilldown | netpulse", layout="wide")
st.title("Province Drilldown")
st.caption("Focus on a province and inspect all towers within it.")

if "drilldown_province" not in st.session_state:
    st.session_state["drilldown_province"] = None

query_province = st.query_params.get("province")
if query_province:
    st.session_state["drilldown_province"] = query_province

window = st.selectbox("Time window", ["24h", "7d", "30d"], index=1)

try:
    provinces = get_all_provinces()
    if not provinces:
        st.warning("No provinces found. Run the tower seed script first.")
        st.stop()

    default_idx = 0
    if st.session_state["drilldown_province"] in provinces:
        default_idx = provinces.index(st.session_state["drilldown_province"])

    selected = st.selectbox("Province", provinces, index=default_idx)
    st.session_state["drilldown_province"] = selected

    province_df = get_province_map_data(window)
    province_summary = province_df[province_df["province_name"] == selected]
    towers = get_province_towers(selected, window)

    if not province_summary.empty:
        row = province_summary.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Towers", int(row["tower_count"]))
        c2.metric("Congested", int(row["congested_tower_count"]))
        c3.metric("Avg health", f"{row['avg_health_score']:.1f}")
        c4.metric("Avg PRB", f"{row.get('avg_prb_utilization', 0):.1f}%")

    if towers.empty:
        st.warning(f"No towers found in {selected}.")
        st.stop()

    st.subheader(f"Towers in {selected}")
    deck = build_network_map(
        towers,
        province_df,
        tower_filter=towers,
    )
    st.pydeck_chart(deck, use_container_width=True, key=f"prov_map_{selected}_{window}")

    freq_col = "congestion_frequency_7d" if window == "7d" else "congestion_frequency_30d"
    display = towers[
        [
            "tower_id",
            "radio",
            "cell_type",
            "health_score",
            "avg_prb_utilization",
            "connected_subscribers",
            freq_col,
        ]
    ].rename(
        columns={
            "avg_prb_utilization": "avg_prb_pct",
            freq_col: "congestion_frequency_pct",
            "connected_subscribers": "subscribers",
        }
    )
    display["congestion_frequency_pct"] = display["congestion_frequency_pct"].round(1)
    display["avg_prb_pct"] = display["avg_prb_pct"].round(1)

    st.caption("Select a tower row to open tower drilldown.")

    tower_selection = st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"prov_towers_{selected}_{window}",
    )

    if tower_selection is not None:
        sel = getattr(tower_selection, "selection", None) or tower_selection.get("selection", {})
        selected_rows = getattr(sel, "rows", None) or sel.get("rows", [])
        if selected_rows:
            picked_id = display.iloc[selected_rows[0]]["tower_id"]
            st.session_state["drilldown_tower_id"] = picked_id
            st.switch_page("pages/4_Tower_Drilldown.py")

except Exception as e:
    st.error(f"Failed to load province drilldown: {e}")
