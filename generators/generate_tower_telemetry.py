"""Generate synthetic hourly tower telemetry anchored to tower_master."""

from datetime import date

import numpy as np
import pandas as pd

from netpulse.config import settings
from netpulse.db import db_cursor
from netpulse.paths import raw_tower_telemetry_key
from netpulse.storage import parquet_row_count, upload_parquet

CELL_TYPE_BASELINE = {"urban": 0.55, "suburban": 0.45, "rural": 0.35}
RUSH_HOURS_WIB = np.array([8, 9, 18, 19, 20])


def load_towers() -> pd.DataFrame:
    with db_cursor() as cur:
        cur.execute(
            "SELECT tower_id, cell_type, radio FROM tower_master ORDER BY tower_id"
        )
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["tower_id", "cell_type", "radio"])


def _hour_factors(hours_utc: np.ndarray) -> np.ndarray:
    hours_wib = (hours_utc + 7) % 24
    factors = np.ones_like(hours_wib, dtype=float)
    factors[np.isin(hours_wib, RUSH_HOURS_WIB)] = 1.35
    factors[(hours_wib >= 0) & (hours_wib <= 5)] = 0.65
    return factors


def generate_for_date(partition_date: date, seed: int = None) -> pd.DataFrame:
    seed = seed or settings.random_seed
    towers = load_towers()
    if towers.empty:
        raise ValueError("tower_master is empty — run seed_opencellid_local.py first")

    rng = np.random.default_rng(seed + partition_date.toordinal())
    n_towers = len(towers)
    hours = np.tile(np.arange(24), n_towers)
    factors = _hour_factors(hours)

    baselines = towers["cell_type"].map(CELL_TYPE_BASELINE).fillna(0.45).values
    baselines = np.repeat(baselines, 24)

    prb = np.clip(rng.normal(baselines * factors * 100, 12), 0.0, 100.0)
    fault_mask = rng.random(len(prb)) < 0.01
    prb[fault_mask] = rng.uniform(100.5, 115.0, size=fault_mask.sum())

    throughput = np.clip(rng.normal(45 * factors, 10), 0.0, None)
    latency = np.clip(rng.normal(25 / factors, 8), 5.0, None)
    dropped = np.clip(rng.normal(0.3 * factors, 0.2), 0.0, 5.0)
    handovers = rng.poisson(15 * factors).astype(int)
    subscribers = np.maximum(1, rng.poisson(80 * factors * baselines).astype(int))

    event_hours = pd.to_datetime(partition_date) + pd.to_timedelta(hours, unit="h")

    return pd.DataFrame({
        "tower_id": np.repeat(towers["tower_id"].values, 24),
        "event_hour": event_hours,
        "prb_utilization": np.round(prb, 2),
        "throughput_mbps": np.round(throughput, 2),
        "latency_ms": np.round(latency, 2),
        "dropped_call_rate": np.round(dropped, 3),
        "handover_count": handovers,
        "connected_subscribers": subscribers,
    })


def run(partition_date: date) -> str:
    df = generate_for_date(partition_date)
    key = raw_tower_telemetry_key(partition_date)
    upload_parquet(df, key)
    return key


def validate(partition_date: date, expected_towers: int = None) -> dict:
    towers = load_towers()
    expected_towers = expected_towers or len(towers)
    expected_rows = expected_towers * 24
    key = raw_tower_telemetry_key(partition_date)
    actual = parquet_row_count(key)
    if actual != expected_rows:
        raise ValueError(f"Expected {expected_rows} telemetry rows, got {actual}")
    return {"row_count": actual, "tower_count": expected_towers}
