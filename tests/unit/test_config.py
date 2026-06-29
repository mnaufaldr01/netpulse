from netpulse.config import get_settings


def test_tower_sample_limit_zero_means_all(monkeypatch):
    monkeypatch.setenv("TOWER_SAMPLE_SIZE", "0")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.tower_sample_limit is None


def test_tower_sample_limit_positive(monkeypatch):
    monkeypatch.setenv("TOWER_SAMPLE_SIZE", "100")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.tower_sample_limit == 100


def test_postgres_dsn_from_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "db.example.com")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "mydb")
    monkeypatch.setenv("POSTGRES_USER", "user1")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    get_settings.cache_clear()
    settings = get_settings()
    assert "host=db.example.com" in settings.postgres_dsn
    assert "port=5433" in settings.postgres_dsn
    assert "dbname=mydb" in settings.postgres_dsn


def test_sqlalchemy_url_from_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "netpulse")
    monkeypatch.setenv("POSTGRES_PASSWORD", "netpulse_dev")
    monkeypatch.setenv("POSTGRES_DB", "netpulse")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.sqlalchemy_url == (
        "postgresql+psycopg2://netpulse:netpulse_dev@localhost:5432/netpulse"
    )
