from unittest.mock import patch

from transforms.clean_subscriber_sessions import clean


def test_clean_dedupes_and_filters_invalid_ids(sample_sessions_df, partition_date):
    valid_towers = {"twr000000001"}
    valid_subscribers = {"sub000001"}

    with patch(
        "transforms.clean_subscriber_sessions.load_valid_ids",
        return_value=(valid_towers, valid_subscribers),
    ):
        result = clean(sample_sessions_df, partition_date)

    assert len(result) == 1
    assert result.iloc[0]["tower_id"] == "twr000000001"
    assert result.iloc[0]["subscriber_id"] == "sub000001"
    assert (result["partition_date"] == partition_date).all()
