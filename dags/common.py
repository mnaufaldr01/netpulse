"""Shared DAG defaults and helpers."""

from datetime import datetime, timedelta

DEFAULT_ARGS = {
    "owner": "netpulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

PIPELINE_START_DATE = datetime(2025, 5, 25)
