import pandas as pd
import pytest

from netpulse.storage import download_parquet, ensure_bucket, get_s3_client, object_exists, upload_parquet


@pytest.mark.integration
def test_minio_parquet_roundtrip(integration_env, seeded_database):
    client = get_s3_client()
    ensure_bucket(client)

    df = pd.DataFrame({"tower_id": ["twr000000001"], "value": [1.0]})
    key = "staging/ci_test/data.parquet"
    upload_parquet(df, key, client=client)

    assert object_exists(key, client=client)
    restored = download_parquet(key, client=client)
    pd.testing.assert_frame_equal(restored, df)
