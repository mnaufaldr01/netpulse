import pandas as pd

from netpulse.geo import (
    classify_cell_type,
    filter_indonesia_slice,
    generate_tower_id,
    get_island_group,
    sample_towers,
)


def test_generate_tower_id_is_deterministic():
    a = generate_tower_id("LTE", 510, 1, 100, 1)
    b = generate_tower_id("LTE", 510, 1, 100, 1)
    assert a == b
    assert len(a) == 12


def test_generate_tower_id_differs_by_cell():
    a = generate_tower_id("LTE", 510, 1, 100, 1)
    b = generate_tower_id("LTE", 510, 1, 100, 2)
    assert a != b


def test_classify_cell_type():
    assert classify_cell_type(None) == "suburban"
    assert classify_cell_type(0) == "suburban"
    assert classify_cell_type(999) == "urban"
    assert classify_cell_type(1000) == "suburban"
    assert classify_cell_type(5000) == "suburban"
    assert classify_cell_type(5001) == "rural"


def test_filter_indonesia_slice(sample_opencellid_df):
    filtered = filter_indonesia_slice(sample_opencellid_df)
    assert len(filtered) == 2
    assert (filtered["mcc"] == 510).all()
    assert filtered.iloc[0]["updated"] >= filtered.iloc[1]["updated"]


def test_sample_towers_full_slice(sample_opencellid_df, monkeypatch):
    monkeypatch.setenv("TOWER_SAMPLE_SIZE", "0")
    get_settings = __import__("netpulse.config", fromlist=["get_settings"]).get_settings
    get_settings.cache_clear()

    indonesia = filter_indonesia_slice(sample_opencellid_df)
    result = sample_towers(indonesia, n=0)
    assert len(result) == 2


def test_sample_towers_capped(sample_opencellid_df, monkeypatch):
    monkeypatch.setenv("TOWER_SAMPLE_SIZE", "1")
    get_settings = __import__("netpulse.config", fromlist=["get_settings"]).get_settings
    get_settings.cache_clear()

    indonesia = filter_indonesia_slice(sample_opencellid_df)
    result = sample_towers(indonesia, n=1, seed=42)
    assert len(result) == 1


def test_get_island_group():
    assert get_island_group("DKI Jakarta") == "Jawa"
    assert get_island_group("Unknown Province") is None
