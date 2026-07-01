#!/usr/bin/env python3
"""Local-only: seed tower_master and province_master from OpenCelliD CSV."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from netpulse.config import settings
from netpulse.geo import (
    assign_provinces,
    build_tower_master_df,
    filter_indonesia_slice,
    load_opencellid_csv,
    sample_towers,
)
from netpulse.tower_seed import seed_towers_from_dataframe


def find_opencellid_csv() -> Path:
    data_dir = Path(settings.opencellid_data_path)
    if not data_dir.exists():
        raise FileNotFoundError(
            f"OpenCelliD data directory not found: {data_dir}. "
            "Download Indonesia slice and place CSV in data/opencellid/"
        )
    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    return csv_files[0]


def find_boundaries_geojson() -> Path:
    boundaries_dir = Path(settings.boundaries_data_path)
    if not boundaries_dir.exists():
        raise FileNotFoundError(
            f"Boundaries directory not found: {boundaries_dir}. "
            "Run: python scripts/download_boundaries.py"
        )
    geojson_files = list(boundaries_dir.glob("*.geojson")) + list(boundaries_dir.glob("*.json"))
    if not geojson_files:
        raise FileNotFoundError(f"No GeoJSON files found in {boundaries_dir}")
    return geojson_files[0]


def main():
    csv_path = find_opencellid_csv()
    geojson_path = find_boundaries_geojson()
    print(f"Loading OpenCelliD from {csv_path}")
    print(f"Loading boundaries from {geojson_path}")

    raw = load_opencellid_csv(csv_path)
    filtered = filter_indonesia_slice(raw)
    print(f"Indonesia slice (MCC 510): {len(filtered)} towers after filter")

    sampled = sample_towers(filtered)
    limit = settings.tower_sample_limit
    if limit is None:
        print(f"Seeding all {len(sampled)} towers (TOWER_SAMPLE_SIZE=0)")
    else:
        print(f"Seeding {len(sampled)} towers (TOWER_SAMPLE_SIZE={limit})")

    with_provinces = assign_provinces(sampled, geojson_path)
    tower_df = build_tower_master_df(with_provinces)

    count = seed_towers_from_dataframe(tower_df)
    print(f"Validated tower_master: {count} rows")
    print("Tower and province seeding complete.")


if __name__ == "__main__":
    main()
