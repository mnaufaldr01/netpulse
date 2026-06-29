"""Generate synthetic subscriber session records for a partition date."""

from datetime import date

import numpy as np
import pandas as pd

from netpulse.config import settings
from netpulse.db import db_cursor
from netpulse.paths import raw_subscriber_sessions_key
from netpulse.storage import parquet_row_count, upload_parquet

SERVICE_TYPES = np.array(["voice", "data", "SMS"])
SERVICE_WEIGHTS = np.array([0.2, 0.7, 0.1])
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

    n_subs = len(subscribers)
    n_sessions = n_subs * SESSIONS_PER_SUBSCRIBER

    subscriber_col = np.repeat(np.asarray(subscribers, dtype=object), SESSIONS_PER_SUBSCRIBER)
    chosen_towers = rng.choice(tower_ids, size=n_sessions, p=weights)
    start_hours = rng.integers(0, 24, size=n_sessions)
    duration_min = rng.uniform(2, 120, size=n_sessions)

    session_starts = pd.to_datetime(partition_date) + pd.to_timedelta(start_hours, unit="h")
    session_ends = session_starts + pd.to_timedelta(duration_min, unit="m")
    service_types = rng.choice(SERVICE_TYPES, size=n_sessions, p=SERVICE_WEIGHTS)

    is_data = service_types == "data"
    bytes_xferred = np.where(
        is_data,
        rng.integers(1_000, 500_000_000, size=n_sessions),
        rng.integers(0, 1_000, size=n_sessions),
    )

    return pd.DataFrame({
        "subscriber_id": subscriber_col,
        "tower_id": chosen_towers,
        "session_start": session_starts,
        "session_end": session_ends,
        "session_duration_min": np.round(duration_min, 2),
        "service_type": service_types,
        "bytes_transferred": bytes_xferred,
    })


def run(partition_date: date) -> str:
    df = generate_for_date(partition_date)
    key = raw_subscriber_sessions_key(partition_date)
    upload_parquet(df, key)
    return key


def validate(partition_date: date) -> dict:
    subscriber_count = len(load_subscriber_ids())
    key = raw_subscriber_sessions_key(partition_date)
    expected = subscriber_count * SESSIONS_PER_SUBSCRIBER
    actual = parquet_row_count(key)
    if actual < expected * 0.95:
        raise ValueError(f"Expected ~{expected} session rows, got {actual}")
    return {"row_count": actual}
