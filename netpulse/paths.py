from datetime import date
from typing import Optional


def _format_partition(d: date) -> str:
    return f"{d.year:04d}/{d.month:02d}/{d.day:02d}"


def raw_tower_telemetry_key(partition_date: date, filename: str = "data.parquet") -> str:
    return f"raw/tower_telemetry/{_format_partition(partition_date)}/{filename}"


def raw_subscriber_sessions_key(partition_date: date, filename: str = "data.parquet") -> str:
    return f"raw/subscriber_sessions/{_format_partition(partition_date)}/{filename}"


def staging_tower_telemetry_key(partition_date: date, filename: str = "data.parquet") -> str:
    return f"staging/tower_telemetry_cleaned/{_format_partition(partition_date)}/{filename}"


def staging_subscriber_sessions_key(partition_date: date, filename: str = "data.parquet") -> str:
    return f"staging/subscriber_sessions_cleaned/{_format_partition(partition_date)}/{filename}"


def raw_opencellid_key(partition_date: Optional[date] = None, filename: str = "indonesia_slice.csv") -> str:
    if partition_date:
        return f"raw/opencellid/{_format_partition(partition_date)}/{filename}"
    return f"raw/opencellid/{filename}"


LAKE_ZONES = ("raw", "staging", "curated")
