from unittest.mock import patch

from transforms.clean_tower_telemetry import clean


def test_clean_filters_invalid_towers_and_flags_sensor_fault(sample_telemetry_df, partition_date):
    valid_ids = {"twr000000001", "twr000000002"}

    with patch("transforms.clean_tower_telemetry.load_valid_tower_ids", return_value=valid_ids):
        result = clean(sample_telemetry_df, partition_date)

    assert len(result) == 2
    assert "invalid_tower" not in result["tower_id"].values
    assert result.loc[result["tower_id"] == "twr000000001", "is_sensor_fault"].iloc[0] == False
    assert result.loc[result["tower_id"] == "twr000000002", "is_sensor_fault"].iloc[0] == True
    assert (result["partition_date"] == partition_date).all()
    assert result["handover_count"].dtype.name in ("int32", "int64")
    assert result["connected_subscribers"].dtype.name in ("int32", "int64")
