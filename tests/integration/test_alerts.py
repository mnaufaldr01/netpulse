import pytest

from netpulse.alerts import evaluate_hotspot_alerts, expire_resolved_alerts
from netpulse.db import db_cursor


def _ensure_mart_hotspot_table():
    with db_cursor(commit=True) as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS public_marts")
        cur.execute("DROP TABLE IF EXISTS public_marts.mart_hotspot_summary")
        cur.execute(
            """
            CREATE TABLE public_marts.mart_hotspot_summary (
                tower_id VARCHAR PRIMARY KEY,
                congestion_frequency_7d DOUBLE PRECISION NOT NULL,
                congestion_frequency_30d DOUBLE PRECISION,
                avg_prb_utilization DOUBLE PRECISION,
                peak_congestion_hour DOUBLE PRECISION,
                total_affected_subscriber_hours INTEGER
            )
            """
        )


def _insert_hotspot(tower_id: str, frequency_7d: float):
    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO public_marts.mart_hotspot_summary (
                tower_id, congestion_frequency_7d, congestion_frequency_30d,
                avg_prb_utilization, total_affected_subscriber_hours
            ) VALUES (%s, %s, 0, 0, 0)
            ON CONFLICT (tower_id) DO UPDATE SET congestion_frequency_7d = EXCLUDED.congestion_frequency_7d
            """,
            (tower_id, frequency_7d),
        )


def _active_hotspot_alerts(tower_id: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM alerts
            WHERE tower_id = %s AND alert_category = 'HOTSPOT' AND status = 'ACTIVE'
            """,
            (tower_id,),
        )
        return cur.fetchone()[0]


@pytest.mark.integration
def test_evaluate_hotspot_alerts_creates_warn_and_critical(integration_env, seeded_database):
    _ensure_mart_hotspot_table()

    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM alerts WHERE alert_category = 'HOTSPOT'")

    _insert_hotspot("twr_warn", 35.0)
    _insert_hotspot("twr_critical", 55.0)

    created = evaluate_hotspot_alerts()
    assert created == 2
    assert _active_hotspot_alerts("twr_warn") == 1
    assert _active_hotspot_alerts("twr_critical") == 1

    with db_cursor() as cur:
        cur.execute(
            "SELECT alert_type FROM alerts WHERE tower_id = %s AND status = 'ACTIVE'",
            ("twr_critical",),
        )
        assert cur.fetchone()[0] == "CRITICAL"


@pytest.mark.integration
def test_expire_resolved_alerts(integration_env, seeded_database):
    _ensure_mart_hotspot_table()

    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM alerts WHERE alert_category = 'HOTSPOT'")
        cur.execute(
            """
            INSERT INTO alerts (
                tower_id, alert_type, alert_category, severity, message, triggered_at, status
            ) VALUES (
                'twr_expire', 'WARN', 'HOTSPOT', 2, 'test', NOW(), 'ACTIVE'
            )
            """
        )

    _insert_hotspot("twr_expire", 5.0)
    resolved = expire_resolved_alerts()
    assert resolved == 1

    with db_cursor() as cur:
        cur.execute(
            "SELECT status FROM alerts WHERE tower_id = 'twr_expire' ORDER BY alert_id DESC LIMIT 1"
        )
        assert cur.fetchone()[0] == "RESOLVED"
