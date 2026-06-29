import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401, E402

import streamlit as st

from components.sidebar_tower import (
    render_province_detail,
    render_tower_detail,
)
from queries import get_province_map_data, get_tower_map_data
from viz import (
    PROVINCE_CHOROPLETH_LAYER_ID,
    TOWER_LAYER_ID,
    build_network_map,
    geojson_path,
)

st.set_page_config(page_title="Network Health Map | netpulse", layout="wide")
st.title("Network Health Map")
st.caption("Province choropleth and tower health overlay from OpenCelliD coordinates.")

if "map_tower_id" not in st.session_state:
    st.session_state["map_tower_id"] = None
if "map_province" not in st.session_state:
    st.session_state["map_province"] = None
if "map_reset_nonce" not in st.session_state:
    st.session_state["map_reset_nonce"] = 0


def _clear_map_selection() -> None:
    st.session_state["map_tower_id"] = None
    st.session_state["map_province"] = None
    st.session_state["map_reset_nonce"] += 1


def _province_name_from_props(props: dict) -> str | None:
    return (
        props.get("province_name")
        or props.get("PROVINSI")
        or props.get("nama")
        or props.get("name")
        or props.get("NAME_1")
        or props.get("Provinsi")
    )


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


window = st.selectbox("Time window", ["24h", "7d", "30d"], index=1)

if not geojson_path().exists():
    st.error(
        f"Province GeoJSON not found at `{geojson_path()}`. "
        "Run `python scripts/download_boundaries.py` first."
    )
    st.stop()

try:
    tower_df = get_tower_map_data(window)
    province_df = get_province_map_data(window)
except Exception as e:
    st.error(f"Failed to load map data: {e}")
    st.stop()

if tower_df.empty:
    st.warning("No towers found. Run `scripts/seed_opencellid_local.py` first.")
    st.stop()

selected_province = st.session_state["map_province"]
selected_tower_id = st.session_state["map_tower_id"]

if selected_tower_id:
    tower_match = tower_df[tower_df["tower_id"] == selected_tower_id]
    if not tower_match.empty:
        selected_province = tower_match.iloc[0]["province_name"]
        st.session_state["map_province"] = selected_province
    map_towers = (
        tower_df[tower_df["province_name"] == selected_province]
        if selected_province
        else tower_df[tower_df["tower_id"] == selected_tower_id]
    )
    show_towers = not map_towers.empty
elif selected_province:
    map_towers = tower_df[tower_df["province_name"] == selected_province]
    show_towers = not map_towers.empty
else:
    map_towers = None
    show_towers = False

map_col, detail_col = st.columns([7, 3])

with map_col:
    deck = build_network_map(
        tower_df,
        province_df,
        tower_filter=map_towers,
        show_towers=show_towers,
        selected_province=selected_province,
    )
    if selected_tower_id:
        map_caption = "Tower selected — click another marker or clear selection."
    elif selected_province:
        map_caption = f"Showing towers in {selected_province}. Click a marker for tower details."
    else:
        map_caption = "Click a province to see its towers, then click a marker for tower details."
    st.caption(map_caption)

    selection = st.pydeck_chart(
        deck,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-object",
        key=f"health_map_{window}_{st.session_state['map_reset_nonce']}_{selected_province or 'national'}",
    )

    objects = _selection_objects(selection)
    if objects.get(TOWER_LAYER_ID):
        picked = objects[TOWER_LAYER_ID][0]
        tower_id = picked.get("tower_id")
        if tower_id and tower_id != st.session_state["map_tower_id"]:
            st.session_state["map_tower_id"] = tower_id
            if picked.get("province_name"):
                st.session_state["map_province"] = picked["province_name"]
            st.rerun()
    elif objects.get(PROVINCE_CHOROPLETH_LAYER_ID):
        props = objects[PROVINCE_CHOROPLETH_LAYER_ID][0]
        if isinstance(props, dict) and "properties" in props:
            props = props["properties"]
        name = _province_name_from_props(props)
        if name and name != st.session_state["map_province"]:
            st.session_state["map_province"] = name
            st.session_state["map_tower_id"] = None
            st.rerun()

with detail_col:
    if st.button("Clear selection", type="secondary", use_container_width=True):
        _clear_map_selection()
        st.rerun()

    if st.session_state["map_tower_id"]:
        match = tower_df[tower_df["tower_id"] == st.session_state["map_tower_id"]]
        if not match.empty:
            render_tower_detail(match.iloc[0])
        else:
            st.warning("Selected tower not found in current window.")
    elif st.session_state["map_province"]:
        match = province_df[province_df["province_name"] == st.session_state["map_province"]]
        if not match.empty:
            render_province_detail(match.iloc[0])
        else:
            st.warning("Selected province not found.")
    else:
        st.info("Click a province on the map to begin.")
