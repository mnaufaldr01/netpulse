"""Alert evaluation logic for DAG 4."""

from datetime import datetime, timedelta

from netpulse.db import db_cursor


def evaluate_hotspot_alerts():
    sql = """
        INSERT INTO alerts (tower_id, alert_type, alert_category, severity, message, triggered_at, status)
        SELECT
            h.tower_id,
            CASE WHEN h.congestion_frequency_7d >= 50 THEN 'CRITICAL' ELSE 'WARN' END,
            'HOTSPOT',
            CASE WHEN h.congestion_frequency_7d >= 50 THEN 3 ELSE 2 END,
            'Tower ' || h.tower_id || ' congestion frequency ' ||
                ROUND(h.congestion_frequency_7d::numeric, 1) || '% over 7 days',
            NOW(),
            'ACTIVE'
        FROM public_marts.mart_hotspot_summary h
        WHERE h.congestion_frequency_7d >= 30
          AND NOT EXISTS (
              SELECT 1 FROM alerts a
              WHERE a.tower_id = h.tower_id
                AND a.alert_category = 'HOTSPOT'
                AND a.status = 'ACTIVE'
          )
    """
    with db_cursor(commit=True) as cur:
        cur.execute(sql)
        return cur.rowcount


def evaluate_peak_hour_alerts():
    sql = """
        INSERT INTO alerts (tower_id, alert_type, alert_category, severity, message, triggered_at, status)
        SELECT
            p.tower_id,
            'PATTERN',
            'PEAK_HOUR',
            2,
            'Tower ' || p.tower_id || ' peak congestion at hour ' || p.hour_of_day,
            NOW(),
            'ACTIVE'
        FROM public_marts.mart_peak_hour_patterns p
        WHERE p.congestion_occurrence_rate >= 70
          AND p.days_congested >= 5
          AND NOT EXISTS (
              SELECT 1 FROM alerts a
              WHERE a.tower_id = p.tower_id
                AND a.alert_category = 'PEAK_HOUR'
                AND a.status = 'ACTIVE'
          )
    """
    with db_cursor(commit=True) as cur:
        cur.execute(sql)
        return cur.rowcount


def evaluate_neighbour_alerts():
    sql = """
        INSERT INTO alerts (tower_id, alert_type, alert_category, severity, message, triggered_at, status)
        SELECT
            n.neighbour_tower_id,
            'SPILLOVER',
            'NEIGHBOUR',
            2,
            'Spillover detected from congested tower ' || n.source_tower_id,
            NOW(),
            'ACTIVE'
        FROM public_marts.mart_neighbour_impact n
        WHERE n.is_spillover = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM alerts a
              WHERE a.tower_id = n.neighbour_tower_id
                AND a.alert_category = 'NEIGHBOUR'
                AND a.status = 'ACTIVE'
          )
    """
    with db_cursor(commit=True) as cur:
        cur.execute(sql)
        return cur.rowcount


def expire_resolved_alerts():
    sql = """
        UPDATE alerts a
        SET status = 'RESOLVED', resolved_at = NOW()
        WHERE a.status = 'ACTIVE'
          AND a.alert_category = 'HOTSPOT'
          AND NOT EXISTS (
              SELECT 1 FROM public_marts.mart_hotspot_summary h
              WHERE h.tower_id = a.tower_id
                AND h.congestion_frequency_7d >= 10
          )
    """
    with db_cursor(commit=True) as cur:
        cur.execute(sql)
        return cur.rowcount
