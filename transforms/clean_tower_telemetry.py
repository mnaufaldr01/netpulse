"""Clean raw tower telemetry and write to staging zone + PostgreSQL."""

from datetime import date

import pandas as pd

from netpulse.db import db_cursor
from netpulse.paths import raw_tower_telemetry_key, staging_tower_telemetry_key
from netpulse.storage import download_parquet, upload_parquet


def load_valid_tower_ids() -> set[str]:
    with db_cursor() as cur:
        cur.execute("SELECT tower_id FROM tower_master")
        return {r[0] for r in cur.fetchall()}


def clean(df: pd.DataFrame, partition_date: date) -> pd.DataFrame:
    valid_towers = load_valid_tower_ids()
    df = df.copy()
    df["event_hour"] = pd.to_datetime(df["event_hour"])
    df = df[df["tower_id"].isin(valid_towers)]
    df["is_sensor_fault"] = df["prb_utilization"] > 100.0
    df["partition_date"] = partition_date

    numeric_cols = [
        "prb_utilization", "throughput_mbps", "latency_ms",
        "dropped_call_rate", "handover_count", "connected_subscribers",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["handover_count"] = df["handover_count"].fillna(0).astype(int)
    df["connected_subscribers"] = df["connected_subscribers"].fillna(0).astype(int)
    return df


def load_to_postgres(df: pd.DataFrame, partition_date: date):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM staging.tower_telemetry_cleaned WHERE partition_date = %s",
            (partition_date,),
        )
        rows = [
            (
                r.tower_id, r.event_hour, r.prb_utilization, r.throughput_mbps,
                r.latency_ms, r.dropped_call_rate, r.handover_count,
                r.connected_subscribers, bool(r.is_sensor_fault), partition_date,
            )
            for r in df.itertuples()
        ]
        cur.executemany(
            """
            INSERT INTO staging.tower_telemetry_cleaned (
                tower_id, event_hour, prb_utilization, throughput_mbps,
                latency_ms, dropped_call_rate, handover_count,
                connected_subscribers, is_sensor_fault, partition_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )


def run(partition_date: date) -> str:
    raw_key = raw_tower_telemetry_key(partition_date)
    df = download_parquet(raw_key)
    cleaned = clean(df, partition_date)
    staging_key = staging_tower_telemetry_key(partition_date)
    upload_parquet(cleaned, staging_key)
    load_to_postgres(cleaned, partition_date)
    return staging_key
