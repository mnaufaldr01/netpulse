"""Generate synthetic subscriber session records for a partition date."""

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from netpulse.config import settings
from netpulse.db import db_cursor
from netpulse.paths import raw_subscriber_sessions_key
from netpulse.storage import upload_parquet

SERVICE_TYPES = ["voice", "data", "SMS"]
SESSIONS_PER_SUBSCRIBER = 3


def load_towers() -> pd.DataFrame:
    with db_cursor() as cur:
        cur.execute("SELECT tower_id, cell_type FROM tower_master")
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["tower_id", "cell_type"])


def load_subscriber_ids(limit: int = None) -> list[str]:
    limit = limit or settings.subscriber_count
    with db_cursor() as cur:
        cur.execute("SELECT subscriber_id FROM subscriber_master LIMIT %s", (limit,))
        return [r[0] for r in cur.fetchall()]


def _tower_weights(towers: pd.DataFrame) -> np.ndarray:
    weights = towers["cell_type"].map({"urban": 3.0, "suburban": 2.0, "rural": 1.0}).fillna(1.5)
    return weights.values / weights.sum()


def generate_for_date(partition_date: date, seed: int = None) -> pd.DataFrame:
    seed = seed or settings.random_seed
    towers = load_towers()
    subscribers = load_subscriber_ids()
    if towers.empty or not subscribers:
        raise ValueError("tower_master or subscriber_master empty — run seed scripts first")

    rng = np.random.default_rng(seed + partition_date.toordinal() + 1000)
    tower_ids = towers["tower_id"].values
    weights = _tower_weights(towers)
    records = []

    for sub_id in subscribers:
        for _ in range(SESSIONS_PER_SUBSCRIBER):
            tower_id = rng.choice(tower_ids, p=weights)
            start_hour = int(rng.integers(0, 24))
            start_dt = datetime(partition_date.year, partition_date.month, partition_date.day) + timedelta(hours=start_hour)
            duration_min = float(rng.uniform(2, 120))
            end_dt = start_dt + timedelta(minutes=duration_min)
            service = rng.choice(SERVICE_TYPES, p=[0.2, 0.7, 0.1])
            bytes_xferred = int(rng.integers(1_000, 500_000_000)) if service == "data" else int(rng.integers(0, 1000))

            records.append({
                "subscriber_id": sub_id,
                "tower_id": tower_id,
                "session_start": start_dt,
                "session_end": end_dt,
                "session_duration_min": round(duration_min, 2),
                "service_type": service,
                "bytes_transferred": bytes_xferred,
            })

    return pd.DataFrame(records)


def run(partition_date: date) -> str:
    df = generate_for_date(partition_date)
    key = raw_subscriber_sessions_key(partition_date)
    upload_parquet(df, key)
    return key


def validate(partition_date: date) -> dict:
    from netpulse.storage import download_parquet
    from netpulse.paths import raw_subscriber_sessions_key

    df = download_parquet(raw_subscriber_sessions_key(partition_date))
    expected = settings.subscriber_count * SESSIONS_PER_SUBSCRIBER
    if len(df) < expected * 0.95:
        raise ValueError(f"Expected ~{expected} session rows, got {len(df)}")
    return {"row_count": len(df)}
