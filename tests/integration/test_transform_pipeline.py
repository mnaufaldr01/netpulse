from datetime import date

import pandas as pd
import pytest

from netpulse.db import db_cursor
from netpulse.paths import raw_tower_telemetry_key
from netpulse.storage import get_s3_client, upload_parquet
from transforms.clean_tower_telemetry import clean, load_to_postgres


@pytest.mark.integration
def test_clean_and_load_telemetry_to_postgres(integration_env, seeded_database):
    partition_date = date(2025, 6, 29)
    raw_df = pd.DataFrame(
        [
            {
                "tower_id": "twr000000001",
                "event_hour": pd.Timestamp("2025-06-29 10:00:00"),
                "prb_utilization": 88.0,
                "throughput_mbps": 50.0,
                "latency_ms": 22.0,
                "dropped_call_rate": 0.3,
                "handover_count": 12,
                "connected_subscribers": 70,
            },
            {
                "tower_id": "unknown_tower",
                "event_hour": pd.Timestamp("2025-06-29 11:00:00"),
                "prb_utilization": 50.0,
                "throughput_mbps": 30.0,
                "latency_ms": 20.0,
                "dropped_call_rate": 0.1,
                "handover_count": 5,
                "connected_subscribers": 40,
            },
        ]
    )

    client = get_s3_client()
    key = raw_tower_telemetry_key(partition_date)
    upload_parquet(raw_df, key, client=client)

    cleaned = clean(raw_df, partition_date)
    assert len(cleaned) == 1
    load_to_postgres(cleaned, partition_date)

    with db_cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM staging.tower_telemetry_cleaned
            WHERE partition_date = %s AND tower_id = %s
            """,
            (partition_date, "twr000000001"),
        )
        count = cur.fetchone()[0]

    assert count == 1
