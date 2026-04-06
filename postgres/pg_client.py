from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, Optional

import psycopg
from psycopg.rows import dict_row

from config import PG_DBNAME, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def get_connection():
    return psycopg.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DBNAME,
        user=PG_USER,
        password=PG_PASSWORD,
        row_factory=dict_row,
    )


@contextmanager
def get_cursor(commit: bool = False):
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


def execute_sql(sql: str, params: Optional[Iterable[Any]] = None, commit: bool = False) -> None:
    with get_cursor(commit=commit) as cur:
        cur.execute(sql, params or ())


def fetch_all(sql: str, params: Optional[Iterable[Any]] = None) -> list[dict]:
    with get_cursor(commit=False) as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def fetch_one(sql: str, params: Optional[Iterable[Any]] = None) -> Optional[dict]:
    with get_cursor(commit=False) as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()
def execute(sql: str, params=None) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()