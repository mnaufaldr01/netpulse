import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401, E402

import streamlit as st

from components.sidebar_tower import (
    render_province_detail,
    render_selection_placeholder,
    render_tower_detail,
)
from queries import get_province_map_data, get_tower_map_data
from viz import build_network_map, geojson_path

st.set_page_config(page_title="Network Health Map | netpulse", layout="wide")
st.title("Network Health Map")
st.caption("Province choropleth and tower health overlay from OpenCelliD coordinates.")

if "map_tower_id" not in st.session_state:
    st.session_state["map_tower_id"] = None
if "map_province" not in st.session_state:
    st.session_state["map_province"] = None

window = st.selectbox("Time window", ["24h", "7d", "30d"], index=1)

map_col, detail_col = st.columns([7, 3])

with map_col:
    if not geojson_path().exists():
        st.error(
            f"Province GeoJSON not found at `{geojson_path()}`. "
            "Run `python scripts/download_boundaries.py` first."
        )
    else:
        try:
            tower_df = get_tower_map_data(window)
            province_df = get_province_map_data(window)

            if tower_df.empty:
                st.warning("No towers found. Run `scripts/seed_opencellid_local.py` first.")
            else:
                deck = build_network_map(tower_df, province_df)
                selection = st.pydeck_chart(
                    deck,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="single-object",
                    key=f"health_map_{window}",
                )

                if selection and selection.get("selection", {}).get("objects"):
                    objects = selection["selection"]["objects"]
                    if objects.get("ScatterplotLayer"):
                        picked = objects["ScatterplotLayer"][0]
                        st.session_state["map_tower_id"] = picked.get("tower_id")
                        st.session_state["map_province"] = None
                    elif objects.get("GeoJsonLayer"):
                        props = objects["GeoJsonLayer"][0].get("properties", {})
                        name = (
                            props.get("nama")
                            or props.get("name")
                            or props.get("NAME_1")
                            or props.get("PROVINSI")
                        )
                        st.session_state["map_province"] = name
                        st.session_state["map_tower_id"] = None

                with st.expander("Manual selection (fallback)"):
                    tower_options = ["—"] + tower_df["tower_id"].tolist()
                    province_options = ["—"] + sorted(
                        tower_df["province_name"].dropna().unique().tolist()
                    )
                    sel_tower = st.selectbox("Select tower", tower_options, key="manual_tower")
                    sel_province = st.selectbox(
                        "Select province", province_options, key="manual_province"
                    )
                    if sel_tower != "—":
                        st.session_state["map_tower_id"] = sel_tower
                        st.session_state["map_province"] = None
                    elif sel_province != "—":
                        st.session_state["map_province"] = sel_province
                        st.session_state["map_tower_id"] = None

        except Exception as e:
            st.error(f"Failed to load map data: {e}")

with detail_col:
    try:
        tower_df = get_tower_map_data(window)
        province_df = get_province_map_data(window)

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
            render_selection_placeholder()
    except Exception:
        render_selection_placeholder()
