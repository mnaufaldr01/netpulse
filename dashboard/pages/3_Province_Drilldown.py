import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401, E402

import streamlit as st

from components.sidebar_tower import render_tower_detail
from queries import get_all_provinces, get_province_map_data, get_province_towers
from viz import TOWER_LAYER_ID, build_province_focus_map

st.set_page_config(page_title="Province Drilldown | netpulse", layout="wide")
st.title("Province Drilldown")
st.caption("Focus on a province and inspect all towers within it.")

if "drilldown_province" not in st.session_state:
    st.session_state["drilldown_province"] = None
if "prov_map_tower_id" not in st.session_state:
    st.session_state["prov_map_tower_id"] = None
if "prov_map_reset_nonce" not in st.session_state:
    st.session_state["prov_map_reset_nonce"] = 0
if "prov_map_province" not in st.session_state:
    st.session_state["prov_map_province"] = None


def _clear_tower_selection() -> None:
    st.session_state["prov_map_tower_id"] = None
    st.session_state["prov_map_reset_nonce"] += 1


def _selection_objects(selection) -> dict:
    if not selection:
        return {}
    sel = (
        selection.get("selection")
        if isinstance(selection, dict)
        else getattr(selection, "selection", None)
    )
    if not sel:
        return {}
    if isinstance(sel, dict):
        return sel.get("objects") or {}
    return getattr(sel, "objects", None) or {}


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

    if st.session_state["prov_map_province"] != selected:
        st.session_state["prov_map_tower_id"] = None
        st.session_state["prov_map_reset_nonce"] += 1
        st.session_state["prov_map_province"] = selected

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
    map_col, detail_col = st.columns([7, 3])

    with map_col:
        deck = build_province_focus_map(towers, selected, province_df)
        selected_tower_id = st.session_state["prov_map_tower_id"]
        if selected_tower_id:
            st.caption("Tower selected — click another marker or clear selection.")
        else:
            st.caption("Click a tower marker for details.")

        selection = st.pydeck_chart(
            deck,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-object",
            key=(
                f"prov_map_{selected}_{window}_"
                f"{st.session_state['prov_map_reset_nonce']}"
            ),
        )

        objects = _selection_objects(selection)
        if objects.get(TOWER_LAYER_ID):
            picked = objects[TOWER_LAYER_ID][0]
            tower_id = picked.get("tower_id")
            if tower_id and tower_id != st.session_state["prov_map_tower_id"]:
                st.session_state["prov_map_tower_id"] = tower_id
                st.rerun()

    with detail_col:
        if st.button("Clear selection", type="secondary", use_container_width=True):
            _clear_tower_selection()
            st.rerun()

        if st.session_state["prov_map_tower_id"]:
            match = towers[towers["tower_id"] == st.session_state["prov_map_tower_id"]]
            if not match.empty:
                render_tower_detail(match.iloc[0])
            else:
                st.warning("Selected tower not found in current window.")
        else:
            st.info("Click a tower marker on the map.")

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

    st.caption("Select a tower row to highlight it in the details panel.")

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
            if picked_id != st.session_state["prov_map_tower_id"]:
                st.session_state["prov_map_tower_id"] = picked_id
                st.rerun()

except Exception as e:
    st.error(f"Failed to load province drilldown: {e}")
