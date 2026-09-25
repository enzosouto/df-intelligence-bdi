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


def _prepare(conn) -> None:
    conn.set_session(readonly=True, autocommit=True)
    with conn.cursor() as probe:
        probe.execute("select 1")


@contextmanager
def cursor() -> Iterator[RealDictCursor]:
    if _pool is None:
        init_pool()
    assert _pool is not None
    conn = _pool.getconn()
    # Postgres gerenciado (Neon) desliga o computador ocioso e derruba as
    # conexões abertas; a do pool só descobre isso ao ser usada. Um `select 1`
    # antes de entregar troca a conexão morta por uma nova em vez de devolver
    # erro 500 para quem abriu o site depois de um tempo parado.
    try:
        _prepare(conn)
    except psycopg2.Error:
        _pool.putconn(conn, close=True)
        conn = _pool.getconn()
        _prepare(conn)
    try:
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
    return diagnose() is None


def diagnose() -> str | None:
    """None se o banco responde; senão, a CATEGORIA da falha.

    Serve ao health-check: com a API numa plataforma cujos logs nem sempre
    estão à mão (função serverless), saber se falta a variável, se a senha foi
    recusada ou se a rede não chega resolve metade do diagnóstico. Só a
    categoria sai — nunca a mensagem crua, que pode conter host e usuário.
    """
    if not os.getenv("DATABASE_URL"):
        return "DATABASE_URL não definida"
    try:
        with cursor() as cur:
            cur.execute("select 1")
            cur.fetchone()
        return None
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        for needle, category in (
            ("password authentication failed", "senha recusada"),
            ("role", "usuário inexistente"),
            ("could not translate host", "host não encontrado"),
            ("timeout", "tempo esgotado"),
            ("timed out", "tempo esgotado"),
            ("ssl", "falha de SSL"),
            ("does not exist", "banco inexistente"),
            ("invalid dsn", "URL mal formada"),
            ("invalid connection option", "URL mal formada"),
            ("connection refused", "conexão recusada"),
        ):
            if needle in message:
                return category
        return f"falha de conexão ({type(exc).__name__})"
