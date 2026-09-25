"""Cria schemas e tabelas `raw`/`meta` num Postgres que não é o do Docker.

No Docker Compose, o Postgres roda `db/init/*.sql` sozinho na primeira subida.
Um banco gerenciado (Neon) não tem esse gancho, então o pipeline de produção
chama este script antes da ingestão. Todo o DDL é idempotente
(`IF NOT EXISTS`), então rodar de novo não altera nada.

Uso:
    DATABASE_URL=postgresql://... python scripts/init_db.py
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2

INIT_DIR = Path(__file__).resolve().parents[1] / "db" / "init"


def main() -> None:
    files = sorted(INIT_DIR.glob("*.sql"))
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        for path in files:
            cur.execute(path.read_text(encoding="utf-8"))
            print(f"  aplicado {path.name}")
    print(f"Schema pronto ({len(files)} arquivos).")


if __name__ == "__main__":
    main()
