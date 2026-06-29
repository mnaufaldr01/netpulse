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

    lookup = province_df.set_index("province_name")
    features = []
    for feature in geojson.get("features", []):
        props = dict(feature.get("properties", {}))
        name_col = _province_name_column(props)
        province_name = props.get(name_col) if name_col else None

        if province_name and province_name in lookup.index:
            row = lookup.loc[province_name]
            health = row["avg_health_score"]
            tower_count = int(row["tower_count"])
            avg_prb = row.get("avg_prb_utilization")
            props["province_name"] = province_name
            props["tower_count"] = tower_count
            props["avg_health_score"] = (
                float(health) if health is not None and not pd.isna(health) else None
            )
            props["avg_prb_utilization"] = (
                float(avg_prb) if avg_prb is not None and not pd.isna(avg_prb) else None
            )
            props["health_score"] = props["avg_health_score"]
            props["fill_color"] = health_to_rgba(props["health_score"], alpha=120)
            prb_str = (
                f"{props['avg_prb_utilization']:.1f}%"
                if props["avg_prb_utilization"] is not None
                else "—"
            )
            health_str = (
                f"{props['avg_health_score']:.1f}"
                if props["avg_health_score"] is not None
                else "—"
            )
            props["t_line1"] = f"Province: {province_name}"
            props["t_line2"] = f"Towers: {tower_count}"
            props["t_line3"] = f"Avg health: {health_str}"
            props["t_line4"] = f"Avg PRB: {prb_str}"
        else:
            props["health_score"] = None
            props["fill_color"] = health_to_rgba(None, alpha=80)
            props["t_line1"] = province_name or "Unknown province"
            props["t_line2"] = ""
            props["t_line3"] = ""
            props["t_line4"] = ""

        features.append({**feature, "properties": props})
    return {**geojson, "features": features}


def _tower_tooltip_lines(row: pd.Series) -> dict[str, str]:
    health = row.get("health_score")
    prb = row.get("avg_prb_utilization")
    health_str = f"{health:.1f}" if pd.notna(health) else "—"
    prb_str = f"{prb:.1f}%" if pd.notna(prb) else "—"
    return {
        "t_line1": f"Tower: {row['tower_id']}",
        "t_line2": f"Province: {row.get('province_name', '—')}",
        "t_line3": f"Health: {health_str}",
        "t_line4": f"Avg PRB: {prb_str}",
    }


MAP_TOOLTIP = {
    "html": (
        "<div style='font-family:sans-serif;font-size:12px;line-height:1.5'>"
        "<b>{t_line1}</b><br/>{t_line2}<br/>{t_line3}<br/>{t_line4}"
        "</div>"
    ),
    "style": {"color": "white", "backgroundColor": "#1e293b"},
}


def build_network_map(
    tower_df: pd.DataFrame,
    province_df: pd.DataFrame,
    *,
    view_state: Optional[pdk.ViewState] = None,
    tower_filter: Optional[pd.DataFrame] = None,
) -> pdk.Deck:
    geojson = load_geojson()
    layers = []
    towers = tower_filter if tower_filter is not None else tower_df

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

    if towers is not None and not towers.empty:
        plot_towers = towers.copy()
        plot_towers["color"] = plot_towers["health_score"].apply(health_to_rgba)
        plot_towers["radius"] = plot_towers["connected_subscribers"].apply(subscriber_radius)
        tooltip_lines = plot_towers.apply(_tower_tooltip_lines, axis=1, result_type="expand")
        plot_towers = pd.concat([plot_towers, tooltip_lines], axis=1)
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=plot_towers,
                get_position="[lon, lat]",
                get_fill_color="color",
                get_radius="radius",
                pickable=True,
                opacity=0.85,
            )
        )

    if view_state is None:
        view_state = pdk.ViewState(latitude=-2.5, longitude=118.0, zoom=4, pitch=0)
    elif towers is not None and not towers.empty and len(towers) <= 50:
        center_lat = towers["lat"].mean()
        center_lon = towers["lon"].mean()
        view_state = pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=7 if len(towers) <= 20 else 6,
            pitch=0,
        )

    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/light-v9",
        tooltip=MAP_TOOLTIP,
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
        fig.update_layout(title="Peak Hour PRB Heatmap (backfill)", height=360)
        return fig

    df = heatmap_df.copy()
    df["day_of_week"] = df["day_of_week"].astype(int)
    df["hour_of_day"] = df["hour_of_day"].astype(int)

    pivot = df.pivot_table(
        index="day_of_week",
        columns="hour_of_day",
        values="avg_prb",
        aggfunc="mean",
    )
    pivot = pivot.reindex(range(7))
    pivot.index = [DOW_LABELS[i] for i in range(7)]
    for hour in range(24):
        if hour not in pivot.columns:
            pivot[hour] = float("nan")
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
        title="PRB by Hour of Day × Day of Week (full backfill)",
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
