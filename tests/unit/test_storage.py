import boto3
import pandas as pd
import pytest
from moto import mock_aws

from netpulse.config import get_settings
import netpulse.storage as storage_mod
from netpulse.storage import download_parquet, object_exists, upload_parquet


@pytest.fixture
def mock_s3_env(monkeypatch):
    monkeypatch.setenv("S3_ENDPOINT_URL", "")
    monkeypatch.setenv("S3_BUCKET", "netpulse-test-bucket")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    get_settings.cache_clear()
    monkeypatch.setattr(storage_mod, "settings", get_settings())


@mock_aws
def test_upload_download_parquet_roundtrip(mock_s3_env):
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="netpulse-test-bucket")

    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    key = "staging/test/data.parquet"
    upload_parquet(df, key, client=client)

    assert object_exists(key, client=client)
    restored = download_parquet(key, client=client)
    pd.testing.assert_frame_equal(restored, df)


@mock_aws
def test_object_exists_false_for_missing_key(mock_s3_env):
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="netpulse-test-bucket")
    assert object_exists("missing/key.parquet", client=client) is False
