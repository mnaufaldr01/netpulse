#!/usr/bin/env python3
"""Download Indonesia province boundary GeoJSON for local seeding."""

import sys
from pathlib import Path

import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from netpulse.config import settings

# 38-province simplified boundaries (PRD-compatible; chmdznr hosts data on Google Drive)
BOUNDARIES_URL = (
    "https://raw.githubusercontent.com/denyherianto/"
    "indonesia-geojson-topojson-maps-with-38-provinces/main/"
    "GeoJSON/indonesia-38-provinces.geojson"
)
OUTPUT_NAME = "indonesia_provinces_simplified.geojson"


def main():
    out_dir = Path(settings.boundaries_data_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / OUTPUT_NAME

    print(f"Downloading province boundaries to {out_path} ...")
    urllib.request.urlretrieve(BOUNDARIES_URL, out_path)
    print(f"Saved {out_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
