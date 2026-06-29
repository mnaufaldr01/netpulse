"""Visualization helpers for the netpulse dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk

from netpulse.config import settings

GEOJSON_FILENAME = "indonesia_provinces_simplified.geojson"
PROVINCE_NAME_CANDIDATES = ["nama", "name", "NAME_1", "PROVINSI", "province", "Provinsi", "Propinsi"]
DOW_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def health_to_rgb(score: Optional[float]) -> list[int]:
    if score is None or pd.isna(score):
        return [156, 163, 175]
    if score >= 70:
        return [34, 197, 94]
    if score >= 40:
        return [234, 179, 8]
    return [239, 68, 68]


def health_to_rgba(score: Optional[float], alpha: int = 160) -> list[int]:
    rgb = health_to_rgb(score)
    return rgb + [alpha]


def subscriber_radius(count: Optional[float]) -> float:
    if count is None or pd.isna(count) or count <= 0:
        return 800.0
    return float(min(5000, max(500, count * 3)))


def geojson_path() -> Path:
    return Path(settings.boundaries_data_path) / GEOJSON_FILENAME


def load_geojson() -> Optional[dict[str, Any]]:
    path = geojson_path()
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _province_name_column(props: dict[str, Any]) -> Optional[str]:
    for col in PROVINCE_NAME_CANDIDATES:
        if col in props:
            return col
    return None


def enrich_geojson_with_health(
    geojson: dict[str, Any],
    province_df: pd.DataFrame,
) -> dict[str, Any]:
    if province_df.empty:
        return geojson

    lookup = province_df.set_index("province_name")["avg_health_score"].to_dict()
    features = []
    for feature in geojson.get("features", []):
        props = dict(feature.get("properties", {}))
        name_col = _province_name_column(props)
        province_name = props.get(name_col) if name_col else None
        score = lookup.get(province_name)
        props["health_score"] = float(score) if score is not None and not pd.isna(score) else None
        props["fill_color"] = health_to_rgba(props["health_score"], alpha=120)
        features.append({**feature, "properties": props})
    return {**geojson, "features": features}


def build_network_map(
    tower_df: pd.DataFrame,
    province_df: pd.DataFrame,
) -> pdk.Deck:
    geojson = load_geojson()
    layers = []

    if geojson is not None:
        enriched = enrich_geojson_with_health(geojson, province_df)
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data=enriched,
                pickable=True,
                stroked=True,
                filled=True,
                get_fill_color="properties.fill_color",
                get_line_color=[80, 80, 80, 200],
                line_width_min_pixels=1,
            )
        )

    if not tower_df.empty:
        towers = tower_df.copy()
        towers["color"] = towers["health_score"].apply(health_to_rgba)
        towers["radius"] = towers["connected_subscribers"].apply(subscriber_radius)
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=towers,
                get_position="[lon, lat]",
                get_fill_color="color",
                get_radius="radius",
                pickable=True,
                opacity=0.85,
            )
        )

    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=-2.5,
            longitude=118.0,
            zoom=4,
            pitch=0,
        ),
        map_style="mapbox://styles/mapbox/light-v9",
        tooltip={
            "html": "<b>{tower_id}</b><br/>Health: {health_score}<br/>PRB: {avg_prb_utilization}",
            "style": {"color": "white"},
        },
    )


def build_prb_line_chart(
    series_df: pd.DataFrame,
    warn_pct: float,
    critical_pct: float,
) -> go.Figure:
    fig = go.Figure()
    if not series_df.empty:
        fig.add_trace(
            go.Scatter(
                x=series_df["event_hour"],
                y=series_df["prb_utilization"],
                mode="lines",
                name="PRB utilization",
                line=dict(color="#2563eb", width=2),
            )
        )
    fig.add_hline(
        y=warn_pct,
        line_dash="dash",
        line_color="#eab308",
        annotation_text=f"Warn ({warn_pct}%)",
    )
    fig.add_hline(
        y=critical_pct,
        line_dash="dash",
        line_color="#ef4444",
        annotation_text=f"Critical ({critical_pct}%)",
    )
    fig.update_layout(
        title="Hourly PRB Utilization (7 days)",
        xaxis_title="Time",
        yaxis_title="PRB %",
        yaxis_range=[0, 100],
        height=380,
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def build_peak_hour_heatmap(heatmap_df: pd.DataFrame) -> go.Figure:
    if heatmap_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Peak Hour PRB Heatmap (30 days)", height=360)
        return fig

    pivot = heatmap_df.pivot_table(
        index="day_of_week",
        columns="hour_of_day",
        values="avg_prb",
        aggfunc="mean",
    )
    pivot = pivot.reindex(range(7))
    pivot.index = [DOW_LABELS[i] for i in pivot.index]
    for hour in range(24):
        if hour not in pivot.columns:
            pivot[hour] = None
    pivot = pivot[sorted(pivot.columns)]

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=[str(h) for h in pivot.columns],
            y=pivot.index.tolist(),
            colorscale="YlOrRd",
            zmin=0,
            zmax=100,
            colorbar=dict(title="PRB %"),
        )
    )
    fig.update_layout(
        title="PRB by Hour of Day × Day of Week",
        xaxis_title="Hour of day",
        yaxis_title="Day of week",
        height=360,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig


def build_hourly_pattern_chart(pattern_df: pd.DataFrame) -> go.Figure:
    """Fallback bar chart from mart_peak_hour_patterns."""
    fig = go.Figure()
    if pattern_df.empty:
        fig.update_layout(title="Congestion by Hour of Day", height=300)
        return fig
    fig.add_trace(
        go.Bar(
            x=pattern_df["hour_of_day"],
            y=pattern_df["avg_prb_utilization"],
            name="Avg PRB",
            marker_color="#f97316",
        )
    )
    fig.update_layout(
        title="Average PRB by Hour of Day (30d)",
        xaxis_title="Hour",
        yaxis_title="PRB %",
        height=300,
    )
    return fig
