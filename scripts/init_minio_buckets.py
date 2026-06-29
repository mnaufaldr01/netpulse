#!/usr/bin/env python3
"""Create netpulse-lake bucket and verify write access to raw/staging prefixes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from netpulse.config import settings
from netpulse.paths import LAKE_ZONES
from netpulse.storage import ensure_bucket, get_s3_client, put_marker


def main():
    client = get_s3_client()
    ensure_bucket(client)
    print(f"Bucket '{settings.s3_bucket}' ready.")

    for zone in LAKE_ZONES:
        marker_key = f"{zone}/.init"
        put_marker(marker_key, client)
        print(f"  Verified write: s3://{settings.s3_bucket}/{marker_key}")

    print("MinIO lake initialization complete.")


if __name__ == "__main__":
    main()
