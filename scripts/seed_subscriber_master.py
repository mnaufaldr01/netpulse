#!/usr/bin/env python3
"""Generate synthetic subscriber_master records."""

import sys
import uuid
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from netpulse.config import settings
from netpulse.db import db_cursor

PLAN_TIERS = ["basic", "standard", "premium"]
REGIONS = ["Jawa", "Sumatera", "Kalimantan", "Sulawesi", "Bali Nusa", "Papua", "Maluku"]


def generate_subscribers(n: int, seed: int) -> list[tuple]:
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        sub_id = f"SUB-{uuid.uuid4().hex[:10].upper()}"
        plan = rng.choice(PLAN_TIERS, p=[0.4, 0.4, 0.2])
        region = rng.choice(REGIONS)
        rows.append((sub_id, plan, region))
    return rows


def main():
    n = settings.subscriber_count
    seed = settings.random_seed
    rows = generate_subscribers(n, seed)

    with db_cursor(commit=True) as cur:
        cur.execute("TRUNCATE subscriber_master")
        cur.executemany(
            "INSERT INTO subscriber_master (subscriber_id, plan_tier, home_region) VALUES (%s, %s, %s)",
            rows,
        )
        cur.execute("SELECT COUNT(*) FROM subscriber_master")
        count = cur.fetchone()[0]

    print(f"Seeded {count} subscribers into subscriber_master")


if __name__ == "__main__":
    main()
