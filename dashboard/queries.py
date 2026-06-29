"""Parameterized SQL queries for the netpulse dashboard."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from sqlalchemy import create_engine, text

from netpulse.config import settings

WINDOW_INTERVALS = {"24h": "1 day", "7d": "7 days", "30d": "30 days"}


def _engine():
    return create_engine(settings.sqlalchemy_url)


def _read_sql(sql: str, params: Optional[dict[str, Any]] = None) -> pd.DataFrame:
    with _engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def window_interval(window: str) -> str:
    if window not in WINDOW_INTERVALS:
        raise ValueError(f"Unknown window: {window}")
    return WINDOW_INTERVALS[window]


def get_tower_map_data(window: str = "7d") -> pd.DataFrame:
    interval = window_interval(window)
    sql = f"""
        WITH latest AS (
            SELECT max(event_hour) AS max_hour
            FROM public_staging.stg_tower_telemetry
        ),
        windowed AS (
            SELECT
                t.tower_id,
                t.prb_utilization,
                t.latency_ms,
                t.dropped_call_rate,
                t.connected_subscribers
            FROM public_staging.stg_tower_telemetry t
            CROSS JOIN latest l
            WHERE t.is_sensor_fault = false
              AND t.event_hour >= l.max_hour - interval '{interval}'
        ),
        scored AS (
            SELECT
                w.tower_id,
                greatest(0, least(100,
                    100
                    - greatest(0, (w.prb_utilization - th.prb_warn_pct) * 1.5)
                    - (w.latency_ms / 10)
                    - (w.dropped_call_rate * 10)
                )) AS health_score,
                w.connected_subscribers,
                w.prb_utilization
            FROM windowed w
            INNER JOIN public.tower_master tm ON w.tower_id = tm.tower_id
            INNER JOIN public_staging.tower_thresholds th ON tm.cell_type = th.cell_type
        )
        SELECT
            tm.tower_id,
            tm.lat,
            tm.lon,
            tm.radio,
            tm.mnc,
            tm.cell_type,
            tm.province_name,
            tm.island_group,
            round(avg(s.health_score)::numeric, 1) AS health_score,
            max(s.connected_subscribers) AS connected_subscribers,
            round(avg(s.prb_utilization)::numeric, 1) AS avg_prb_utilization
        FROM public.tower_master tm
        LEFT JOIN scored s ON tm.tower_id = s.tower_id
        GROUP BY
            tm.tower_id, tm.lat, tm.lon, tm.radio, tm.mnc,
            tm.cell_type, tm.province_name, tm.island_group
        ORDER BY tm.tower_id
    """
    return _read_sql(sql)


def get_province_map_data(window: str = "7d") -> pd.DataFrame:
    towers = get_tower_map_data(window)
    if towers.empty:
        return pd.DataFrame()

    agg = (
        towers.groupby(["province_name", "island_group"], dropna=False)
        .agg(
            tower_count=("tower_id", "count"),
            congested_tower_count=(
                "health_score",
                lambda s: int((s.fillna(100) < 40).sum()),
            ),
            avg_health_score=("health_score", "mean"),
            avg_prb_utilization=("avg_prb_utilization", "mean"),
            total_connected_subscribers=("connected_subscribers", "sum"),
        )
        .reset_index()
    )
    agg["congestion_rate"] = (
        agg["congested_tower_count"] / agg["tower_count"].replace(0, 1) * 100
    ).round(1)
    agg["avg_health_score"] = agg["avg_health_score"].round(1)
    agg["avg_prb_utilization"] = agg["avg_prb_utilization"].round(1)
    return agg.sort_values("congestion_rate", ascending=False)


def get_tower_latest_prb(tower_id: str) -> Optional[dict[str, Any]]:
    sql = """
        SELECT
            t.prb_utilization,
            t.connected_subscribers,
            t.event_hour
        FROM public_staging.stg_tower_telemetry t
        WHERE t.tower_id = :tower_id
          AND t.is_sensor_fault = false
        ORDER BY t.event_hour DESC
        LIMIT 1
    """
    df = _read_sql(sql, {"tower_id": tower_id})
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_hotspot_towers(window: str = "7d") -> pd.DataFrame:
    freq_col = "congestion_frequency_7d" if window == "7d" else "congestion_frequency_30d"
    sql = f"""
        SELECT
            h.tower_id,
            tm.province_name,
            tm.cell_type,
            tm.radio,
            h.congestion_frequency_7d,
            h.congestion_frequency_30d,
            h.avg_prb_utilization,
            h.peak_congestion_hour,
            h.total_affected_subscriber_hours
        FROM public_marts.mart_hotspot_summary h
        INNER JOIN public.tower_master tm ON h.tower_id = tm.tower_id
        ORDER BY h.{freq_col} DESC NULLS LAST
        LIMIT 20
    """
    df = _read_sql(sql)
    df["congestion_frequency"] = df[freq_col]
    return df


def get_province_leaderboard(window: str = "7d") -> pd.DataFrame:
    """Aggregate province rankings from hotspot mart (aligned with tower leaderboard)."""
    freq_col = "congestion_frequency_7d" if window == "7d" else "congestion_frequency_30d"
    sql = f"""
        SELECT
            tm.province_name,
            max(tm.island_group) AS island_group,
            count(distinct tm.tower_id) AS tower_count,
            count(distinct CASE WHEN h.{freq_col} > 0 THEN tm.tower_id END) AS congested_tower_count,
            round(
                count(distinct CASE WHEN h.{freq_col} > 0 THEN tm.tower_id END)::numeric
                / nullif(count(distinct tm.tower_id), 0) * 100,
                1
            ) AS congestion_rate,
            round(avg(h.{freq_col})::numeric, 1) AS avg_congestion_frequency,
            round(avg(hs.health_score)::numeric, 1) AS avg_health_score,
            coalesce(sum(CASE WHEN h.{freq_col} > 0 THEN h.total_affected_subscriber_hours END), 0)
                AS total_affected_subscriber_hours
        FROM public.tower_master tm
        LEFT JOIN public_marts.mart_hotspot_summary h ON tm.tower_id = h.tower_id
        LEFT JOIN public_marts.mart_network_health_snapshot hs ON tm.tower_id = hs.tower_id
        WHERE tm.province_name IS NOT NULL
        GROUP BY tm.province_name
        HAVING count(distinct CASE WHEN h.{freq_col} > 0 THEN tm.tower_id END) >= 1
        ORDER BY avg(h.{freq_col}) DESC NULLS LAST
    """
    return _read_sql(sql)


def get_province_towers(province_name: str, window: str = "7d") -> pd.DataFrame:
    """All towers in a province with health and congestion metrics."""
    interval = window_interval(window)
    sql = f"""
        WITH latest AS (
            SELECT max(event_hour) AS max_hour
            FROM public_staging.stg_tower_telemetry
        ),
        windowed AS (
            SELECT
                t.tower_id,
                t.prb_utilization,
                t.latency_ms,
                t.dropped_call_rate,
                t.connected_subscribers
            FROM public_staging.stg_tower_telemetry t
            CROSS JOIN latest l
            WHERE t.is_sensor_fault = false
              AND t.event_hour >= l.max_hour - interval '{interval}'
        ),
        scored AS (
            SELECT
                w.tower_id,
                greatest(0, least(100,
                    100
                    - greatest(0, (w.prb_utilization - th.prb_warn_pct) * 1.5)
                    - (w.latency_ms / 10)
                    - (w.dropped_call_rate * 10)
                )) AS health_score,
                w.connected_subscribers,
                w.prb_utilization
            FROM windowed w
            INNER JOIN public.tower_master tm ON w.tower_id = tm.tower_id
            INNER JOIN public_staging.tower_thresholds th ON tm.cell_type = th.cell_type
        )
        SELECT
            tm.tower_id,
            tm.lat,
            tm.lon,
            tm.radio,
            tm.mnc,
            tm.cell_type,
            tm.province_name,
            round(avg(s.health_score)::numeric, 1) AS health_score,
            max(s.connected_subscribers) AS connected_subscribers,
            round(avg(s.prb_utilization)::numeric, 1) AS avg_prb_utilization,
            coalesce(h.congestion_frequency_7d, 0) AS congestion_frequency_7d,
            coalesce(h.congestion_frequency_30d, 0) AS congestion_frequency_30d,
            coalesce(h.avg_prb_utilization, 0) AS hotspot_avg_prb
        FROM public.tower_master tm
        LEFT JOIN scored s ON tm.tower_id = s.tower_id
        LEFT JOIN public_marts.mart_hotspot_summary h ON tm.tower_id = h.tower_id
        WHERE tm.province_name = :province_name
        GROUP BY
            tm.tower_id, tm.lat, tm.lon, tm.radio, tm.mnc, tm.cell_type,
            tm.province_name, h.congestion_frequency_7d, h.congestion_frequency_30d,
            h.avg_prb_utilization
        ORDER BY health_score ASC NULLS LAST, tm.tower_id
    """
    return _read_sql(sql, {"province_name": province_name})


def get_all_provinces() -> list[str]:
    df = _read_sql(
        """
        SELECT DISTINCT province_name
        FROM public.tower_master
        WHERE province_name IS NOT NULL
        ORDER BY province_name
        """
    )
    return df["province_name"].tolist()


def get_active_alerts(
    alert_type: Optional[str] = None,
    province: Optional[str] = None,
    island_group: Optional[str] = None,
) -> pd.DataFrame:
    conditions = ["a.status = 'ACTIVE'"]
    params: dict[str, Any] = {}

    if alert_type and alert_type != "All":
        conditions.append("a.alert_type = :alert_type")
        params["alert_type"] = alert_type
    if province and province != "All":
        conditions.append("tm.province_name = :province")
        params["province"] = province
    if island_group and island_group != "All":
        conditions.append("tm.island_group = :island_group")
        params["island_group"] = island_group

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            a.alert_id,
            a.tower_id,
            tm.province_name,
            tm.island_group,
            a.alert_type,
            a.alert_category,
            a.severity,
            a.message,
            a.triggered_at,
            extract(epoch FROM (now() - a.triggered_at)) / 86400.0 AS days_active
        FROM public.alerts a
        INNER JOIN public.tower_master tm ON a.tower_id = tm.tower_id
        WHERE {where}
        ORDER BY a.severity DESC, a.triggered_at ASC
    """
    return _read_sql(sql, params)


def get_alert_summary() -> dict[str, Any]:
    sql = """
        SELECT
            count(*) AS total_active,
            count(*) FILTER (WHERE a.alert_type = 'CRITICAL') AS critical_count,
            count(DISTINCT a.tower_id) AS towers_affected,
            count(DISTINCT tm.province_name) AS provinces_affected,
            min(a.triggered_at) AS oldest_triggered_at
        FROM public.alerts a
        INNER JOIN public.tower_master tm ON a.tower_id = tm.tower_id
        WHERE a.status = 'ACTIVE'
    """
    df = _read_sql(sql)
    if df.empty or pd.isna(df.iloc[0]["total_active"]):
        return {
            "total_active": 0,
            "critical_count": 0,
            "towers_affected": 0,
            "provinces_affected": 0,
            "oldest_alert_days": 0.0,
        }
    row = df.iloc[0]
    oldest_days = 0.0
    if pd.notna(row["oldest_triggered_at"]):
        oldest_days = (
            pd.Timestamp.now(tz=None) - pd.Timestamp(row["oldest_triggered_at"])
        ).total_seconds() / 86400.0
    return {
        "total_active": int(row["total_active"]),
        "critical_count": int(row["critical_count"] or 0),
        "towers_affected": int(row["towers_affected"] or 0),
        "provinces_affected": int(row["provinces_affected"] or 0),
        "oldest_alert_days": round(oldest_days, 1),
    }


def get_filter_options() -> dict[str, list[str]]:
    sql = """
        SELECT DISTINCT tm.province_name, tm.island_group
        FROM public.tower_master tm
        WHERE tm.province_name IS NOT NULL
        ORDER BY tm.province_name
    """
    df = _read_sql(sql)
    provinces = ["All"] + sorted(df["province_name"].dropna().unique().tolist())
    islands = ["All"] + sorted(df["island_group"].dropna().unique().tolist())
    return {"provinces": provinces, "island_groups": islands}


def get_all_tower_ids() -> list[str]:
    df = _read_sql("SELECT tower_id FROM public.tower_master ORDER BY tower_id")
    return df["tower_id"].tolist()


def get_tower_metadata(tower_id: str) -> Optional[pd.Series]:
    sql = """
        SELECT
            tm.tower_id,
            tm.lat,
            tm.lon,
            tm.radio,
            tm.mnc,
            tm.cell_type,
            tm.province_name,
            tm.island_group,
            th.prb_warn_pct,
            th.prb_critical_pct,
            th.latency_warn_ms
        FROM public.tower_master tm
        INNER JOIN public_staging.tower_thresholds th ON tm.cell_type = th.cell_type
        WHERE tm.tower_id = :tower_id
    """
    df = _read_sql(sql, {"tower_id": tower_id})
    if df.empty:
        return None
    return df.iloc[0]


def get_tower_prb_series(tower_id: str, days: int = 7) -> pd.DataFrame:
    sql = """
        WITH latest AS (
            SELECT max(event_hour) AS max_hour
            FROM public_staging.stg_tower_telemetry
            WHERE tower_id = :tower_id
        )
        SELECT
            t.event_hour,
            t.prb_utilization,
            t.connected_subscribers
        FROM public_staging.stg_tower_telemetry t
        CROSS JOIN latest l
        WHERE t.tower_id = :tower_id
          AND t.is_sensor_fault = false
          AND t.event_hour >= l.max_hour - make_interval(days => :days)
        ORDER BY t.event_hour
    """
    return _read_sql(sql, {"tower_id": tower_id, "days": days})


def get_congestion_events(tower_id: str) -> pd.DataFrame:
    sql = """
        SELECT
            c.event_hour,
            c.prb_utilization,
            c.severity,
            coalesce(s.subscriber_count_affected, 0) AS subscriber_count_affected,
            coalesce(s.degraded_session_minutes, 0) AS degraded_session_minutes
        FROM public_marts.mart_congestion_events c
        LEFT JOIN public_marts.mart_subscriber_impact s
            ON c.tower_id = s.tower_id AND c.event_hour = s.event_hour
        WHERE c.tower_id = :tower_id
        ORDER BY c.event_hour DESC
    """
    return _read_sql(sql, {"tower_id": tower_id})


def get_peak_hour_heatmap(tower_id: str) -> pd.DataFrame:
    sql = """
        SELECT
            hour_of_day,
            avg_prb_utilization,
            congestion_occurrence_rate
        FROM public_marts.mart_peak_hour_patterns
        WHERE tower_id = :tower_id
        ORDER BY hour_of_day
    """
    return _read_sql(sql, {"tower_id": tower_id})


def get_peak_hour_prb_by_dow(tower_id: str) -> pd.DataFrame:
    """Hour x day-of-week PRB for drilldown heatmap (all backfill partitions)."""
    sql = """
        SELECT
            extract(dow FROM t.event_hour)::int AS day_of_week,
            extract(hour FROM t.event_hour)::int AS hour_of_day,
            avg(t.prb_utilization) AS avg_prb
        FROM public_staging.stg_tower_telemetry t
        WHERE t.tower_id = :tower_id
          AND t.is_sensor_fault = false
        GROUP BY 1, 2
        ORDER BY 1, 2
    """
    return _read_sql(sql, {"tower_id": tower_id})


def get_neighbour_impact(tower_id: str) -> pd.DataFrame:
    sql = """
        SELECT
            n.neighbour_tower_id,
            tm.province_name,
            tm.cell_type,
            n.is_spillover
        FROM public_marts.mart_neighbour_impact n
        INNER JOIN public.tower_master tm ON n.neighbour_tower_id = tm.tower_id
        WHERE n.source_tower_id = :tower_id
        ORDER BY n.is_spillover DESC, n.neighbour_tower_id
    """
    return _read_sql(sql, {"tower_id": tower_id})


def get_subscriber_impact_summary(tower_id: str) -> dict[str, Any]:
    sql = """
        SELECT
            count(DISTINCT event_hour) AS congestion_events,
            coalesce(sum(subscriber_count_affected), 0) AS total_affected_sessions,
            coalesce(sum(degraded_session_minutes), 0) AS total_degraded_minutes,
            coalesce(sum(voice_sessions), 0) AS voice_sessions,
            coalesce(sum(data_sessions), 0) AS data_sessions,
            coalesce(sum(sms_sessions), 0) AS sms_sessions
        FROM public_marts.mart_subscriber_impact
        WHERE tower_id = :tower_id
    """
    df = _read_sql(sql, {"tower_id": tower_id})
    if df.empty:
        return {
            "congestion_events": 0,
            "total_affected_sessions": 0,
            "total_degraded_minutes": 0,
            "voice_sessions": 0,
            "data_sessions": 0,
            "sms_sessions": 0,
        }
    return df.iloc[0].to_dict()


def get_home_metrics() -> dict[str, Any]:
    sql = """
        SELECT
            (SELECT count(*) FROM public.tower_master) AS tower_count,
            (SELECT count(*) FROM public.alerts WHERE status = 'ACTIVE') AS active_alerts,
            (SELECT round(avg(health_score)::numeric, 1)
             FROM public_marts.mart_network_health_snapshot) AS avg_health_score
    """
    df = _read_sql(sql)
    row = df.iloc[0]
    return {
        "tower_count": int(row["tower_count"] or 0),
        "active_alerts": int(row["active_alerts"] or 0),
        "avg_health_score": float(row["avg_health_score"] or 0),
    }


def check_db_connection() -> tuple[bool, str]:
    try:
        df = _read_sql("SELECT count(*) AS n FROM public.tower_master")
        count = int(df.iloc[0]["n"])
        return True, f"Connected — {count} towers in tower_master"
    except Exception as e:
        return False, str(e)
