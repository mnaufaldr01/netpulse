"""Generate synthetic hourly tower telemetry anchored to tower_master."""

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from netpulse.config import settings
from netpulse.db import db_cursor
from netpulse.paths import raw_tower_telemetry_key
from netpulse.storage import upload_parquet


CELL_TYPE_BASELINE = {"urban": 0.55, "suburban": 0.45, "rural": 0.35}
RUSH_HOURS_WIB = (8, 9, 18, 19, 20)


def load_towers() -> pd.DataFrame:
    with db_cursor() as cur:
        cur.execute(
            "SELECT tower_id, cell_type, radio FROM tower_master ORDER BY tower_id"
        )
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["tower_id", "cell_type", "radio"])


def _hour_factor(hour_wib: int) -> float:
    if hour_wib in RUSH_HOURS_WIB:
        return 1.35
    if 0 <= hour_wib <= 5:
        return 0.65
    return 1.0


def generate_for_date(partition_date: date, seed: int = None) -> pd.DataFrame:
    seed = seed or settings.random_seed
    towers = load_towers()
    if towers.empty:
        raise ValueError("tower_master is empty — run seed_opencellid_local.py first")

    rng = np.random.default_rng(seed + partition_date.toordinal())
    records = []

    for _, tower in towers.iterrows():
        baseline = CELL_TYPE_BASELINE.get(tower["cell_type"], 0.45)
        for hour in range(24):
            event_dt = datetime(partition_date.year, partition_date.month, partition_date.day) + timedelta(hours=hour)
            hour_wib = (hour + 7) % 24  # UTC to WIB approximation
            factor = _hour_factor(hour_wib)

            prb = min(100.0, max(0.0, rng.normal(baseline * factor * 100, 12)))
            # Inject occasional sensor faults (~1%)
            if rng.random() < 0.01:
                prb = rng.uniform(100.5, 115.0)

            throughput = max(0.0, rng.normal(45 * factor, 10))
            latency = max(5.0, rng.normal(25 / factor, 8))
            dropped = max(0.0, min(5.0, rng.normal(0.3 * factor, 0.2)))
            handovers = max(0, int(rng.poisson(15 * factor)))
            subscribers = max(1, int(rng.poisson(80 * factor * baseline)))

            records.append({
                "tower_id": tower["tower_id"],
                "event_hour": event_dt,
                "prb_utilization": round(prb, 2),
                "throughput_mbps": round(throughput, 2),
                "latency_ms": round(latency, 2),
                "dropped_call_rate": round(dropped, 3),
                "handover_count": handovers,
                "connected_subscribers": subscribers,
            })

    return pd.DataFrame(records)


def run(partition_date: date) -> str:
    df = generate_for_date(partition_date)
    key = raw_tower_telemetry_key(partition_date)
    upload_parquet(df, key)
    return key


def validate(partition_date: date, expected_towers: int = None) -> dict:
    towers = load_towers()
    expected_towers = expected_towers or len(towers)
    expected_rows = expected_towers * 24
    from netpulse.storage import download_parquet
    from netpulse.paths import raw_tower_telemetry_key

    df = download_parquet(raw_tower_telemetry_key(partition_date))
    if len(df) != expected_rows:
        raise ValueError(f"Expected {expected_rows} telemetry rows, got {len(df)}")
    return {"row_count": len(df), "tower_count": df["tower_id"].nunique()}
