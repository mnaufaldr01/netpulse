"""Shared pytest fixtures."""

from datetime import date, datetime

import pandas as pd
import pytest

from netpulse.config import get_settings


@pytest.fixture(autouse=True)
def reset_settings_cache(monkeypatch):
    """Clear cached settings so env overrides apply per test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def integration_env():
    """Use env / .env for service endpoints; CI sets vars in the workflow."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def sample_opencellid_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "radio": "LTE",
                "mcc": 510,
                "net": 1,
                "area": 100,
                "cell": 1,
                "unit": 0,
                "lon": 106.8456,
                "lat": -6.2088,
                "range": 500,
                "samples": 5,
                "changeable": 1,
                "created": 1600000000,
                "updated": 1700000000,
                "averageSignal": -85,
            },
            {
                "radio": "LTE",
                "mcc": 510,
                "net": 8,
                "area": 100,
                "cell": 2,
                "unit": 0,
                "lon": 107.0,
                "lat": -6.5,
                "range": 3000,
                "samples": 3,
                "changeable": 1,
                "created": 1600000000,
                "updated": 1690000000,
                "averageSignal": -90,
            },
            {
                "radio": "GSM",
                "mcc": 404,
                "net": 1,
                "area": 1,
                "cell": 1,
                "unit": 0,
                "lon": 77.0,
                "lat": 28.0,
                "range": 1000,
                "samples": 10,
                "changeable": 1,
                "created": 1600000000,
                "updated": 1700000000,
                "averageSignal": -80,
            },
        ]
    )


@pytest.fixture
def sample_telemetry_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "tower_id": "twr000000001",
                "event_hour": datetime(2025, 6, 28, 8, 0, 0),
                "prb_utilization": 75.0,
                "throughput_mbps": 40.0,
                "latency_ms": 30.0,
                "dropped_call_rate": 0.5,
                "handover_count": 10,
                "connected_subscribers": 50,
            },
            {
                "tower_id": "twr000000002",
                "event_hour": datetime(2025, 6, 28, 8, 0, 0),
                "prb_utilization": 105.0,
                "throughput_mbps": 20.0,
                "latency_ms": 25.0,
                "dropped_call_rate": 0.2,
                "handover_count": 5,
                "connected_subscribers": 30,
            },
            {
                "tower_id": "invalid_tower",
                "event_hour": datetime(2025, 6, 28, 9, 0, 0),
                "prb_utilization": 50.0,
                "throughput_mbps": 30.0,
                "latency_ms": 20.0,
                "dropped_call_rate": 0.1,
                "handover_count": 3,
                "connected_subscribers": 20,
            },
        ]
    )


@pytest.fixture
def sample_sessions_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "subscriber_id": "sub000001",
                "tower_id": "twr000000001",
                "session_start": datetime(2025, 6, 28, 8, 0, 0),
                "session_end": datetime(2025, 6, 28, 9, 0, 0),
                "session_duration_min": 60.0,
                "service_type": "data",
                "bytes_transferred": 1024,
            },
            {
                "subscriber_id": "sub000001",
                "tower_id": "twr000000001",
                "session_start": datetime(2025, 6, 28, 8, 0, 0),
                "session_end": datetime(2025, 6, 28, 9, 0, 0),
                "session_duration_min": 60.0,
                "service_type": "voice",
                "bytes_transferred": 0,
            },
            {
                "subscriber_id": "sub000002",
                "tower_id": "bad_tower",
                "session_start": datetime(2025, 6, 28, 10, 0, 0),
                "session_end": datetime(2025, 6, 28, 11, 0, 0),
                "session_duration_min": 30.0,
                "service_type": "data",
                "bytes_transferred": 512,
            },
        ]
    )


@pytest.fixture
def partition_date() -> date:
    return date(2025, 6, 28)
