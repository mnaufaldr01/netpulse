import netpulse.opencellid_fetch as fetch_mod
from netpulse.config import get_settings


def test_get_api_token_from_env(monkeypatch):
    monkeypatch.setenv("OPENCELLID_API_KEY", "pk.test_token")
    get_settings.cache_clear()
    monkeypatch.setattr(fetch_mod, "settings", get_settings())
    assert fetch_mod.get_api_token() == "pk.test_token"
    get_settings.cache_clear()
