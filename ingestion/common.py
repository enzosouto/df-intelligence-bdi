"""Infraestrutura compartilhada pelos módulos de ingestão.

Concentra as cinco coisas que todo extractor precisa e que ninguém deveria
reimplementar: configuração, HTTP educado com retry, conexão com o Postgres,
upsert idempotente e registro da execução em `meta.ingestion_run`.
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence

import psycopg2
import requests
from psycopg2.extras import Json, execute_values
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:  # opcional: só facilita rodar fora do Docker
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
DDL_DIR = REPO_ROOT / "db" / "init"

LOG_FORMAT = "%(asctime)s  %(levelname)-7s  %(name)-22s  %(message)s"


def configure_logging(level: str | int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt="%H:%M:%S")
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Settings:
    database_url: str
    user_agent: str
    throttle_seconds: float
    weather_start_date: str
    security_start_year: int


def settings() -> Settings:
    url = os.getenv("DATABASE_URL")
    if not url:
        user = os.getenv("POSTGRES_USER", "df")
        pwd = os.getenv("POSTGRES_PASSWORD", "df_local_password_change_me")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_HOST_PORT", "55432")
        db = os.getenv("POSTGRES_DB", "df_intelligence")
        url = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
    return Settings(
        database_url=url,
        user_agent=os.getenv("HTTP_USER_AGENT", "DFIntelligence/1.0"),
        throttle_seconds=float(os.getenv("HTTP_THROTTLE_SECONDS", "0.4")),
        weather_start_date=os.getenv("WEATHER_START_DATE", "2018-01-01"),
        security_start_year=int(os.getenv("SECURITY_START_YEAR", "2014")),
    )


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class PoliteSession(requests.Session):
    """Session com retry exponencial, User-Agent de navegador e throttle.

    O User-Agent de navegador não é cosmético: o Liferay que serve
    `ssp.df.gov.br` devolve uma página de desafio JavaScript para clientes que
    se identificam como script. Já o throttle é cortesia com um servidor
    público — a ingestão de segurança faz ~300 downloads.
    """

    def __init__(self, user_agent: str, throttle_seconds: float) -> None:
        super().__init__()
        self._throttle = throttle_seconds
        self._last_call = 0.0
        self._requests_made = 0
        self.headers.update(
            {
                # UA de navegador é requisito dos portais Liferay do GDF.
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 "
                    f"{user_agent}"
                ),
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            }
        )
        retry = Retry(
            total=4,
            backoff_factor=1.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=8)
        self.mount("https://", adapter)
        self.mount("http://", adapter)

    @property
    def requests_made(self) -> int:
        return self._requests_made

    def request(self, method, url, **kwargs):  # type: ignore[override]
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._throttle:
            time.sleep(self._throttle - elapsed)
        kwargs.setdefault("timeout", 120)
        response = super().request(method, url, **kwargs)
        self._last_call = time.monotonic()
        self._requests_made += 1
        return response


def get_json(session: requests.Session, url: str, **kwargs: Any) -> Any:
    """GET + validação de que a resposta é realmente JSON.

    Portais do GDF respondem 200 com HTML de erro ou página de desafio. Tratar
    isso como JSON válido envenenaria o RAW silenciosamente.
    """
    response = session.get(url, **kwargs)
    response.raise_for_status()
    body = response.text.lstrip()
    if not body.startswith(("{", "[")):
        raise ValueError(
            f"Resposta não-JSON de {url} "
            f"(content-type={response.headers.get('content-type')!r}): {body[:160]!r}"
        )
    return response.json()


# --------------------------------------------------------------------------- #
# Persistência do RAW em disco (auditoria)
# --------------------------------------------------------------------------- #
def save_raw(source_key: str, filename: str, content: bytes | str) -> Path:
    """Grava o payload cru antes de qualquer transformação.

    Serve para auditar: se um número do dashboard for contestado, existe o
    arquivo exato que a fonte devolveu naquele dia.
    """
    target_dir = RAW_DIR / source_key / date.today().isoformat()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / filename
    mode, payload = ("wb", content) if isinstance(content, bytes) else ("w", content)
    with open(path, mode, encoding=None if isinstance(content, bytes) else "utf-8") as fh:
        fh.write(payload)
    return path


# --------------------------------------------------------------------------- #
# Banco
# --------------------------------------------------------------------------- #
def connect(autocommit: bool = False):
    conn = psycopg2.connect(settings().database_url)
    conn.autocommit = autocommit
    return conn


def bootstrap_schema(conn) -> None:
    """Aplica o DDL de `db/init/` no banco.

    O mesmo DDL roda pelo entrypoint do container do Postgres na primeira
    subida. Aplicá-lo de novo aqui é o que permite rodar a ingestão contra um
    Postgres que já existia (CI, banco gerenciado) sem passo manual.
    """
    with conn.cursor() as cur:
        for sql_file in sorted(DDL_DIR.glob("*.sql")):
            cur.execute(sql_file.read_text(encoding="utf-8"))
    conn.commit()


def upsert(
    conn,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    conflict_columns: Sequence[str],
    update_columns: Sequence[str] | None = None,
) -> int:
    """INSERT ... ON CONFLICT DO UPDATE em lote.

    É o que torna a ingestão idempotente: rodar o pipeline duas vezes no mesmo
    dia atualiza as mesmas linhas em vez de duplicá-las.
    """
    rows = [tuple(r) for r in rows]
    if not rows:
        return 0

    if update_columns is None:
        update_columns = [c for c in columns if c not in conflict_columns]

    assignments = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_columns)
    action = f"DO UPDATE SET {assignments}" if update_columns else "DO NOTHING"
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT ({', '.join(conflict_columns)}) {action}"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=1000)
    conn.commit()
    return len(rows)


def as_jsonb(value: Any) -> Json:
    return Json(value)


# --------------------------------------------------------------------------- #
# Registro de execução
# --------------------------------------------------------------------------- #
@contextmanager
def ingestion_run(conn, source_key: str):
    """Context manager que grava início, fim, linhas e erro em meta.ingestion_run."""
    log = logging.getLogger(f"ingestion.{source_key}")
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO meta.ingestion_run (source_key) VALUES (%s) RETURNING run_id",
            (source_key,),
        )
        run_id = cur.fetchone()[0]
    conn.commit()

    tracker = {"rows": 0, "requests": 0}
    started = time.monotonic()
    try:
        yield run_id, tracker
    except Exception as exc:
        # A falha pode ter abortado a transação corrente; sem rollback o
        # próprio registro do erro falharia com InFailedSqlTransaction.
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE meta.ingestion_run "
                "SET status='FAILED', finished_at=now(), error_message=%s, "
                "    rows_written=%s, requests_made=%s "
                "WHERE run_id=%s",
                (f"{type(exc).__name__}: {exc}"[:2000], tracker["rows"], tracker["requests"], run_id),
            )
        conn.commit()
        log.error("FALHOU após %.1fs: %s", time.monotonic() - started, exc)
        raise
    else:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE meta.ingestion_run "
                "SET status='SUCCESS', finished_at=now(), rows_written=%s, requests_made=%s "
                "WHERE run_id=%s",
                (tracker["rows"], tracker["requests"], run_id),
            )
        conn.commit()
        log.info(
            "OK — %s linhas, %s requisições, %.1fs",
            tracker["rows"],
            tracker["requests"],
            time.monotonic() - started,
        )


def record_check(
    conn,
    run_id: int | None,
    check_name: str,
    passed: bool,
    severity: str = "ERROR",
    observed: Any = None,
    expected: Any = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO meta.data_quality_check "
            "(run_id, check_name, severity, passed, observed, expected) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (run_id, check_name, severity, passed, _short(observed), _short(expected)),
        )
    conn.commit()


def _short(value: Any) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text[:500]
