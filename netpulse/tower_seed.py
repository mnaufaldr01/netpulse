"""Shared tower_master / province_master seeding for local script and DAG 0."""

from __future__ import annotations

import pandas as pd

from netpulse.db import db_cursor


def upsert_tower_master(df: pd.DataFrame, *, truncate: bool = True) -> None:
    if truncate:
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


def upsert_province_master(df: pd.DataFrame) -> None:
    provinces = df[["province_name", "island_group"]].dropna(subset=["province_name"]).drop_duplicates()
    sql = """
        INSERT INTO province_master (province_name, island_group)
        VALUES (%s, %s)
        ON CONFLICT (province_name) DO UPDATE SET island_group = EXCLUDED.island_group
    """
    rows = [(r.province_name, r.island_group) for r in provinces.itertuples()]
    with db_cursor(commit=True) as cur:
        cur.executemany(sql, rows)


def validate_tower_master(expected_count: int) -> int:
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
    return count


def seed_towers_from_dataframe(df: pd.DataFrame, *, truncate: bool = True) -> int:
    """Upsert tower and province masters and validate row count."""
    upsert_tower_master(df, truncate=truncate)
    upsert_province_master(df)
    return validate_tower_master(len(df))
