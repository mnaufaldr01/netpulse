"""Helpers for integration tests against Postgres and MinIO."""

import time
from pathlib import Path

import psycopg2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INIT_SQL = REPO_ROOT / "sql" / "init"
SEED_SQL = REPO_ROOT / "tests" / "fixtures" / "seed_ci.sql"


def wait_for_postgres(host: str, port: int, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname="netpulse",
                user="netpulse",
                password="netpulse_dev",
            )
            conn.close()
            return
        except psycopg2.OperationalError:
            time.sleep(1)
    raise RuntimeError(f"Postgres not ready at {host}:{port}")


def apply_sql_file(dsn_parts: dict, path: Path) -> None:
    conn = psycopg2.connect(**dsn_parts)
    try:
        with conn.cursor() as cur:
            cur.execute(path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def bootstrap_database(host: str = "localhost", port: int = 5432) -> None:
    wait_for_postgres(host, port)
    dsn = {
        "host": host,
        "port": port,
        "dbname": "netpulse",
        "user": "netpulse",
        "password": "netpulse_dev",
    }
    apply_sql_file(dsn, INIT_SQL / "01_schemas.sql")
    apply_sql_file(dsn, INIT_SQL / "02_grants.sql")
    apply_sql_file(dsn, SEED_SQL)


@pytest.fixture(scope="module")
def seeded_database(integration_env):
    from netpulse.config import get_settings

    settings = get_settings()
    bootstrap_database(settings.postgres_host, settings.postgres_port)
    yield settings
