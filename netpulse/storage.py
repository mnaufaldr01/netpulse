import hashlib
import io
from typing import Optional

import boto3
import pandas as pd
import pyarrow.parquet as pq
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from netpulse.config import settings


def get_s3_client() -> BaseClient:
    kwargs: dict = {
        "service_name": "s3",
        "region_name": settings.aws_default_region,
    }
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client(**kwargs)


def ensure_bucket(client: Optional[BaseClient] = None) -> None:
    client = client or get_s3_client()
    bucket = settings.s3_bucket
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)


def upload_parquet(df: pd.DataFrame, key: str, client: Optional[BaseClient] = None) -> str:
    client = client or get_s3_client()
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)
    client.put_object(Bucket=settings.s3_bucket, Key=key, Body=buffer.getvalue())
    return key


def download_parquet(key: str, client: Optional[BaseClient] = None) -> pd.DataFrame:
    client = client or get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket, Key=key)
    return pd.read_parquet(io.BytesIO(response["Body"].read()), engine="pyarrow")


def download_bytes(key: str, client: Optional[BaseClient] = None) -> bytes:
    client = client or get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read()


def parquet_row_count(key: str, client: Optional[BaseClient] = None) -> int:
    """Read row count from parquet metadata without loading a DataFrame."""
    client = client or get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket, Key=key)
    return pq.read_metadata(io.BytesIO(response["Body"].read())).num_rows


def object_exists(key: str, client: Optional[BaseClient] = None) -> bool:
    client = client or get_s3_client()
    try:
        client.head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except ClientError:
        return False


def put_marker(key: str, client: Optional[BaseClient] = None) -> None:
    """Write a zero-byte marker to verify prefix write access."""
    client = client or get_s3_client()
    client.put_object(Bucket=settings.s3_bucket, Key=key, Body=b"")
