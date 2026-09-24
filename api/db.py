"""Acesso ao Postgres.

A API é estritamente de leitura sobre o schema `marts`. Ela não calcula
indicador nem aplica regra de negócio: tudo que ela devolve já foi materializado
e testado pelo dbt. Se um número está errado, o lugar de corrigir é o modelo —
nunca aqui.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

_pool: ThreadedConnectionPool | None = None


def init_pool() -> None:
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=int(os.getenv("DB_POOL_MAX", "10")),
            dsn=os.environ["DATABASE_URL"],
        )


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def cursor() -> Iterator[RealDictCursor]:
    if _pool is None:
        init_pool()
    assert _pool is not None
    conn = _pool.getconn()
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
    finally:
        _pool.putconn(conn)


def fetch_all(sql: str, params: Sequence[Any] | dict | None = None) -> list[dict]:
    with cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def fetch_one(sql: str, params: Sequence[Any] | dict | None = None) -> dict | None:
    with cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None


def ping() -> bool:
    try:
        with cursor() as cur:
            cur.execute("select 1")
            return cur.fetchone() is not None
    except psycopg2.Error:
        return False
