"""Atualização automática do banco, sem ninguém rodar nada.

Roda como serviço do Docker Compose (`updater`) e dispara o mesmo
`run_pipeline.sh` do uso manual, em dois ritmos:

* **todo dia** — só o clima (Open-Meteo publica dia a dia) e o dbt, para os
  marts refletirem o dia novo. Leve: uma requisição por RA.
* **uma vez por semana** — todas as fontes. SSP-DF e CNES publicam por mês,
  Censo Escolar e IDE-DF bem menos; baixar tudo todo dia só carregaria os
  portais do GDF para trazer o mesmo arquivo.

Por que não "tempo real": nenhuma das fontes publica em tempo real. O dado mais
fresco que existe é o clima de ontem; o crime é do mês passado. Atualizar mais
vezes do que a fonte publica não traz dado novo.

Banco vazio (primeira subida) → roda a carga completa na hora, sem esperar o
agendamento. Falha numa execução não derruba o serviço: fica no log e a
próxima execução tenta de novo.

Horário em Brasília (UTC−3 fixo; o DF não tem horário de verão desde 2019).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import psycopg2

BRASILIA = timezone(timedelta(hours=-3))
WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

UPDATE_HOUR = int(os.environ.get("UPDATE_HOUR", "6"))
FULL_UPDATE_WEEKDAY = int(os.environ.get("FULL_UPDATE_WEEKDAY", "0"))  # 0 = segunda
PIPELINE = ["bash", "/app/scripts/run_pipeline.sh"]


def log(message: str) -> None:
    now = datetime.now(BRASILIA).strftime("%d/%m/%Y %H:%M")
    print(f"[atualização {now}] {message}", flush=True)


def database_is_empty() -> bool:
    """Sem marts construídos, o site não tem o que mostrar."""
    try:
        with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
            cur.execute("select to_regclass('marts.dim_region') is null")
            return bool(cur.fetchone()[0])
    except psycopg2.Error as exc:
        log(f"banco indisponível ({exc.__class__.__name__}); tratando como vazio")
        return True


def next_run(now: datetime) -> datetime:
    target = now.replace(hour=UPDATE_HOUR, minute=0, second=0, microsecond=0)
    return target if target > now else target + timedelta(days=1)


def run(full: bool) -> None:
    # A validação de fontes fica só na carga completa: um portal do GDF fora do
    # ar não pode impedir o clima de ontem de entrar.
    args = PIPELINE if full else PIPELINE + ["--only", "weather", "--skip-validation"]
    log("carga completa (todas as fontes)" if full else "carga diária (clima + dbt)")
    started = time.monotonic()
    code = subprocess.call(args)
    minutes = (time.monotonic() - started) / 60
    if code == 0:
        log(f"concluída em {minutes:.1f} min")
    else:
        log(f"FALHOU (código {code}) após {minutes:.1f} min — nova tentativa no próximo horário")


def main() -> None:
    log(
        f"agendado: todo dia às {UPDATE_HOUR:02d}h (clima), carga completa às "
        f"{WEEKDAYS[FULL_UPDATE_WEEKDAY]}s"
    )
    if database_is_empty():
        log("banco sem dados — carga completa agora")
        run(full=True)

    while True:
        target = next_run(datetime.now(BRASILIA))
        log(f"próxima execução: {target:%d/%m/%Y %H:%M}")
        time.sleep(max(0.0, (target - datetime.now(BRASILIA)).total_seconds()))
        run(full=target.weekday() == FULL_UPDATE_WEEKDAY)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
