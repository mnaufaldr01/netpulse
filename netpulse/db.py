from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
from psycopg2.extensions import connection as PgConnection

from netpulse.config import settings


def get_connection() -> PgConnection:
    return psycopg2.connect(settings.postgres_dsn)


@contextmanager
def db_cursor(commit: bool = False) -> Generator:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_query(sql: str, params: Optional[tuple] = None, fetch: bool = False):
    with db_cursor(commit=not fetch) as cur:
        cur.execute(sql, params)
        if fetch:
            return cur.fetchall()
    return None


def execute_many(sql: str, rows: list[tuple]):
    with db_cursor(commit=True) as cur:
        cur.executemany(sql, rows)
