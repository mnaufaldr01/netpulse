#!/usr/bin/env python3
"""Local-only: seed tower_master and province_master from OpenCelliD CSV."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from netpulse.config import settings
from netpulse.db import db_cursor
from netpulse.geo import (
    assign_provinces,
    build_tower_master_df,
    filter_indonesia_slice,
    load_opencellid_csv,
    sample_towers,
)


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
            "Download simplified GeoJSON from chmdznr/indonesia-geojson"
        )
    geojson_files = list(boundaries_dir.glob("*.geojson")) + list(boundaries_dir.glob("*.json"))
    if not geojson_files:
        raise FileNotFoundError(f"No GeoJSON files found in {boundaries_dir}")
    return geojson_files[0]


def upsert_tower_master(df):
    with db_cursor(commit=True) as cur:
        cur.execute("TRUNCATE tower_master")
    sql = """
        INSERT INTO tower_master (
            tower_id, radio, mcc, mnc, area, cell, lon, lat, range_m,
            samples, changeable, cell_type, province_name, island_group, last_updated
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (tower_id) DO UPDATE SET
            province_name = EXCLUDED.province_name,
            island_group = EXCLUDED.island_group,
            cell_type = EXCLUDED.cell_type
    """
    rows = [
        (
            r.tower_id, r.radio, r.mcc, r.mnc, r.area, r.cell,
            r.lon, r.lat, r.range_m, r.samples, r.changeable,
            r.cell_type, r.province_name, r.island_group, r.last_updated,
        )
        for r in df.itertuples()
    ]
    with db_cursor(commit=True) as cur:
        cur.executemany(sql, rows)


def upsert_province_master(df):
    provinces = df[["province_name", "island_group"]].dropna(subset=["province_name"]).drop_duplicates()
    sql = """
        INSERT INTO province_master (province_name, island_group)
        VALUES (%s, %s)
        ON CONFLICT (province_name) DO UPDATE SET island_group = EXCLUDED.island_group
    """
    rows = [(r.province_name, r.island_group) for r in provinces.itertuples()]
    with db_cursor(commit=True) as cur:
        cur.executemany(sql, rows)


def validate_tower_master(expected_count: int):
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tower_master")
        count = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM tower_master WHERE lat IS NULL OR lon IS NULL OR cell_type IS NULL"
        )
        invalid = cur.fetchone()[0]
    if count != expected_count:
        raise ValueError(f"Expected {expected_count} towers, got {count}")
    if invalid > 0:
        raise ValueError(f"{invalid} towers have missing required fields")
    print(f"Validated tower_master: {count} rows")


def main():
    csv_path = find_opencellid_csv()
    geojson_path = find_boundaries_geojson()
    print(f"Loading OpenCelliD from {csv_path}")
    print(f"Loading boundaries from {geojson_path}")

    raw = load_opencellid_csv(csv_path)
    filtered = filter_indonesia_slice(raw)
    sampled = sample_towers(filtered)
    with_provinces = assign_provinces(sampled, geojson_path)
    tower_df = build_tower_master_df(with_provinces)

    upsert_tower_master(tower_df)
    upsert_province_master(tower_df)
    validate_tower_master(settings.tower_sample_size)
    print("Tower and province seeding complete.")


if __name__ == "__main__":
    main()
