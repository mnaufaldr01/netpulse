"""Clean raw subscriber sessions and write to staging zone + PostgreSQL."""

from datetime import date

import pandas as pd

from netpulse.db import db_cursor
from netpulse.paths import raw_subscriber_sessions_key, staging_subscriber_sessions_key
from netpulse.storage import download_parquet, upload_parquet


def load_valid_ids() -> tuple[set[str], set[str]]:
    with db_cursor() as cur:
        cur.execute("SELECT tower_id FROM tower_master")
        towers = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT subscriber_id FROM subscriber_master")
        subscribers = {r[0] for r in cur.fetchall()}
    return towers, subscribers


def clean(df: pd.DataFrame, partition_date: date) -> pd.DataFrame:
    valid_towers, valid_subscribers = load_valid_ids()
    df = df.copy()
    df["session_start"] = pd.to_datetime(df["session_start"])
    df["session_end"] = pd.to_datetime(df["session_end"])
    df = df.dropna(subset=["subscriber_id", "tower_id", "session_start", "service_type"])
    df = df[df["tower_id"].isin(valid_towers) & df["subscriber_id"].isin(valid_subscribers)]
    df = df.drop_duplicates(subset=["subscriber_id", "tower_id", "session_start"])
    df["partition_date"] = partition_date
    df["session_duration_min"] = pd.to_numeric(df["session_duration_min"], errors="coerce")
    df["bytes_transferred"] = pd.to_numeric(df["bytes_transferred"], errors="coerce").fillna(0).astype(int)
    return df


def load_to_postgres(df: pd.DataFrame, partition_date: date):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM staging.subscriber_sessions_cleaned WHERE partition_date = %s",
            (partition_date,),
        )
        rows = [
            (
                r.subscriber_id, r.tower_id, r.session_start, r.session_end,
                r.session_duration_min, r.service_type, r.bytes_transferred, partition_date,
            )
            for r in df.itertuples()
        ]
        cur.executemany(
            """
            INSERT INTO staging.subscriber_sessions_cleaned (
                subscriber_id, tower_id, session_start, session_end,
                session_duration_min, service_type, bytes_transferred, partition_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )


def run(partition_date: date) -> str:
    raw_key = raw_subscriber_sessions_key(partition_date)
    df = download_parquet(raw_key)
    cleaned = clean(df, partition_date)
    staging_key = staging_subscriber_sessions_key(partition_date)
    upload_parquet(cleaned, staging_key)
    load_to_postgres(cleaned, partition_date)
    return staging_key
