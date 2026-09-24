"""Executor da ingestão.

    python -m ingestion                  # tudo, na ordem correta
    python -m ingestion regions weather  # apenas os módulos indicados
    python -m ingestion --continue-on-error

`regions` roda primeiro sempre, porque as demais fontes dependem das chaves que
ele cria.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import education, health, population, regions, security, weather
from .common import bootstrap_schema, configure_logging, connect

MODULES = {
    "regions": regions,
    "population": population,
    "security": security,
    "health": health,
    "education": education,
    "weather": weather,
}

log = logging.getLogger("ingestion")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ingestion")
    # Sem `choices=`: com nargs="*", o argparse valida a própria lista default
    # contra as escolhas quando nenhum argumento é passado, e rejeita a execução
    # completa. A validação é feita à mão logo abaixo.
    parser.add_argument(
        "modules",
        nargs="*",
        default=[],
        metavar="MODULO",
        help=f"módulos a executar ({', '.join(MODULES)}). Sem argumento, roda todos.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="não aborta se uma fonte falhar (útil quando um portal está fora do ar)",
    )
    args = parser.parse_args(argv)
    configure_logging()

    unknown = [name for name in args.modules if name not in MODULES]
    if unknown:
        parser.error(
            f"módulo desconhecido: {', '.join(unknown)}. Disponíveis: {', '.join(MODULES)}"
        )

    selected = args.modules or list(MODULES)
    # regions precede todo mundo: ele cria as chaves usadas pelas outras fontes.
    ordered = [name for name in MODULES if name in selected]

    conn = connect()
    bootstrap_schema(conn)
    conn.close()
    log.info("Schema aplicado. Módulos: %s", ", ".join(ordered))

    failed: list[str] = []
    for name in ordered:
        log.info("=" * 70)
        log.info(">>> %s", name)
        try:
            MODULES[name].run()
        except Exception as exc:
            failed.append(name)
            log.error("Módulo %s falhou: %s", name, exc, exc_info=True)
            if not args.continue_on_error:
                return 1

    if failed:
        log.error("Concluído com falhas em: %s", ", ".join(failed))
        return 1
    log.info("Ingestão concluída com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
