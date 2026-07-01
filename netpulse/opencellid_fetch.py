"""Fetch OpenCelliD Indonesia (MCC 510) slice and land in S3 raw zone."""

from __future__ import annotations

import gzip
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netpulse.config import settings
from netpulse.paths import raw_opencellid_key
from netpulse.storage import get_s3_client

OPENCELLID_SSM_PARAM = "/netpulse/opencellid_api_key"

# Country-specific export URLs (OpenCelliD / Unwired Labs downloads API)
DOWNLOAD_URL_TEMPLATES = (
    "https://download.unwiredlabs.com/ocid/downloads?token={token}&type=mcc&mcc=510",
    "https://download.unwiredlabs.com/ocid/downloads?token={token}&mcc=510",
    "https://opencellid.org/downloads.php?token={token}&mcc=510",
)


def get_api_token() -> str:
    """Resolve OpenCelliD token from env (preferred) or SSM fallback."""
    if settings.opencellid_api_key:
        return settings.opencellid_api_key.strip()

    try:
        from netpulse.ssm import get_parameter

        return get_parameter(OPENCELLID_SSM_PARAM)
    except Exception as exc:
        raise RuntimeError(
            "OpenCelliD API token not configured. Set OPENCELLID_API_KEY in .env.cloud "
            f"(or {OPENCELLID_SSM_PARAM} in SSM)."
        ) from exc


def _download_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "netpulse/0.1"})
    with urlopen(request, timeout=120) as response:
        return response.read()


def download_indonesia_slice(token: Optional[str] = None) -> bytes:
    """Download raw Indonesia MCC 510 CSV bytes from OpenCelliD."""
    token = token or get_api_token()
    last_error: Exception | None = None
    for template in DOWNLOAD_URL_TEMPLATES:
        url = template.format(token=token)
        try:
            payload = _download_bytes(url)
            if payload and len(payload) > 100:
                return payload
        except HTTPError as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Failed to download OpenCelliD Indonesia slice: {last_error}")


def _maybe_decompress(payload: bytes) -> bytes:
    if payload[:2] == b"\x1f\x8b":
        return gzip.decompress(payload)
    return payload


def write_local_csv(payload: bytes, path: Path) -> Path:
    """Write decompressed CSV to a local path for pandas ingestion."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_maybe_decompress(payload))
    return path


def upload_raw_slice(
    payload: bytes,
    partition_date: Optional[date] = None,
    *,
    filename: str = "indonesia_slice.csv",
) -> str:
    """Upload raw CSV to S3; returns object key."""
    body = _maybe_decompress(payload)
    key = raw_opencellid_key(partition_date, filename=filename)
    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=body,
        ContentType="text/csv",
    )
    return key


def fetch_and_upload(partition_date: Optional[date] = None) -> str:
    """Download from OpenCelliD API and land raw CSV in S3."""
    payload = download_indonesia_slice()
    return upload_raw_slice(payload, partition_date)
