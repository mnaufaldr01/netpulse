import pytest

from dashboard.queries import window_interval


def test_window_interval_valid():
    assert window_interval("24h") == "1 day"
    assert window_interval("7d") == "7 days"
    assert window_interval("30d") == "30 days"


def test_window_interval_invalid():
    with pytest.raises(ValueError, match="Unknown window"):
        window_interval("90d")
