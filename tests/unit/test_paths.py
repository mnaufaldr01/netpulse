from datetime import date

from netpulse.paths import (
    raw_opencellid_key,
    raw_subscriber_sessions_key,
    raw_tower_telemetry_key,
    staging_subscriber_sessions_key,
    staging_tower_telemetry_key,
)


def test_raw_tower_telemetry_key():
    d = date(2025, 6, 28)
    assert raw_tower_telemetry_key(d) == "raw/tower_telemetry/2025/06/28/data.parquet"


def test_raw_subscriber_sessions_key():
    d = date(2025, 1, 5)
    assert raw_subscriber_sessions_key(d) == "raw/subscriber_sessions/2025/01/05/data.parquet"


def test_staging_tower_telemetry_key():
    d = date(2025, 12, 31)
    assert staging_tower_telemetry_key(d) == "staging/tower_telemetry_cleaned/2025/12/31/data.parquet"


def test_staging_subscriber_sessions_key():
    d = date(2025, 3, 15)
    assert staging_subscriber_sessions_key(d) == "staging/subscriber_sessions_cleaned/2025/03/15/data.parquet"


def test_raw_opencellid_key_with_and_without_date():
    d = date(2025, 6, 28)
    assert raw_opencellid_key(d) == "raw/opencellid/2025/06/28/indonesia_slice.csv"
    assert raw_opencellid_key() == "raw/opencellid/indonesia_slice.csv"
