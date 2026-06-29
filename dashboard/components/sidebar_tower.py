"""Reusable sidebar detail panels for map interactions."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import streamlit as st

from queries import get_tower_latest_prb


def render_tower_detail(row: pd.Series) -> None:
    st.subheader("Tower details")
    st.markdown(f"**Tower ID:** `{row['tower_id']}`")
    st.markdown(f"**Radio:** {row.get('radio', '—')}")
    st.markdown(f"**Operator MNC:** {row.get('mnc', '—')}")
    st.markdown(f"**Cell type:** {row.get('cell_type', '—')}")
    st.markdown(f"**Province:** {row.get('province_name', '—')}")

    health = row.get("health_score")
    st.metric("Health score", f"{health:.1f}" if pd.notna(health) else "—")

    prb = row.get("avg_prb_utilization")
    if pd.notna(prb):
        st.metric("Avg PRB (window)", f"{prb:.1f}%")
    else:
        latest = get_tower_latest_prb(row["tower_id"])
        if latest:
            st.metric("Current PRB", f"{latest['prb_utilization']:.1f}%")
        else:
            st.metric("Current PRB", "—")

    if st.button("Open tower drilldown", key=f"drill_{row['tower_id']}"):
        st.session_state["drilldown_tower_id"] = row["tower_id"]
        st.switch_page("pages/4_Tower_Drilldown.py")


def render_province_detail(row: pd.Series) -> None:
    st.subheader("Province details")
    st.markdown(f"**Province:** {row.get('province_name', '—')}")
    st.markdown(f"**Island group:** {row.get('island_group', '—')}")
    c1, c2 = st.columns(2)
    c1.metric("Towers", int(row.get("tower_count", 0)))
    c2.metric("Congested", int(row.get("congested_tower_count", 0)))
    c1.metric("Congestion rate", f"{row.get('congestion_rate', 0):.1f}%")
    c2.metric("Avg health", f"{row.get('avg_health_score', 0):.1f}")
    prb = row.get("avg_prb_utilization")
    if pd.notna(prb):
        st.metric("Avg PRB (window)", f"{prb:.1f}%")

    if st.button("Open province drilldown", key=f"prov_drill_{row.get('province_name', '')}"):
        st.session_state["drilldown_province"] = row["province_name"]
        st.switch_page("pages/3_Province_Drilldown.py")
