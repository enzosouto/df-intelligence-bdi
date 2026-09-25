"""Reescreve os números do README a partir do banco.

Existe porque número escrito à mão em documentação apodrece: a cada execução do
pipeline as contagens mudam, e um README que afirma 70.035 ocorrências quando o
banco tem outra coisa é exatamente o tipo de dado inventado que este projeto se
propõe a não publicar.

Roda no fim do pipeline mensal (GitHub Actions) junto com as capturas de tela,
e o que mudar é commitado de volta. Localmente:

    python scripts/update_readme_stats.py            # reescreve
    python scripts/update_readme_stats.py --check     # só verifica (sai 1 se
                                                      # o README estiver velho)

Os trechos gerados ficam entre marcadores HTML no README. Fora deles, o texto é
escrito por gente e este script não encosta.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import psycopg2

README = Path(__file__).resolve().parent.parent / "README.md"

# Contagens da camada de marts. Cada uma é um `count(*)` — nada é derivado aqui,
# para que o README não possa discordar do banco por causa de uma conta local.
COUNTS = """
select
  (select count(*) from marts.dim_region)                          as regions,
  (select count(*) from marts.dim_source)                          as sources,
  (select count(*) from marts.fct_security_monthly)                as security_rows,
  (select min(reference_year) from marts.fct_security_monthly)     as security_from,
  (select max(reference_year) from marts.fct_security_monthly)     as security_to,
  (select count(*) from marts.fct_health_facility)                 as facilities,
  (select count(*) from marts.fct_population)                      as population_rows,
  (select count(*) from marts.fct_population_df)                   as population_df_rows,
  (select count(*) from marts.fct_education_enrollment)            as enrollment_rows,
  (select count(*) from marts.fct_mobility_bikeway)                as bikeway_rows,
  (select count(*) from marts.fct_mobility_station)                as station_rows,
  (select count(*) from marts.fct_weather_daily)                   as weather_rows,
  (select count(*) from marts.mart_insights)                       as insights,
  (select count(distinct census_year) from marts.mart_education_yearly
     where scope = 'DF')                                           as census_years,
  (select schools_total from marts.mart_education_yearly
     where scope = 'DF' order by census_year desc limit 1)          as schools_latest,
  (select max(census_year) from marts.mart_education_yearly
     where scope = 'DF')                                           as schools_year,
  (select round(sum(km)::numeric, 1) from marts.fct_mobility_bikeway) as bikeway_km
"""


def br(value: int | float, decimals: int = 0) -> str:
    """Formata no padrão pt-BR: ponto de milhar, vírgula decimal."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def blocks(row: dict) -> dict[str, str]:
    """Os trechos gerados, um por marcador."""
    resumo = (
        f"{row['regions']} Regiões Administrativas  ·  6 domínios  ·  "
        f"{row['sources']} fontes catalogadas\n"
        f"{br(row['security_rows'])} ocorrências criminais "
        f"({row['security_from']}–{row['security_to']})  ·  "
        f"{br(row['facilities'])} estabelecimentos de saúde\n"
        f"{br(row['schools_latest'])} escolas em {row['schools_year']}, "
        f"{row['census_years']} anos de Censo Escolar  ·  "
        f"{br(row['bikeway_km'], 1)} km de ciclovia"
    )

    tabela = "\n".join(
        f"| `{table}` | {grain} | {br(count)} |"
        for table, grain, count in [
            ("dim_region", "Região Administrativa", row["regions"]),
            ("fct_population", "região × ano censitário", row["population_rows"]),
            ("fct_population_df", "ano", row["population_df_rows"]),
            ("fct_security_monthly", "região × mês × natureza", row["security_rows"]),
            ("fct_health_facility", "estabelecimento", row["facilities"]),
            ("fct_education_enrollment", "escola × ano", row["enrollment_rows"]),
            ("fct_mobility_bikeway", "trecho cicloviário", row["bikeway_rows"]),
            ("fct_mobility_station", "estação de metrô", row["station_rows"]),
            ("fct_weather_daily", "região × dia", row["weather_rows"]),
            ("mart_insights", "achado calculado", row["insights"]),
        ]
    )

    return {"resumo": resumo, "tabela": tabela}


def apply(text: str, generated: dict[str, str]) -> str:
    for name, block in generated.items():
        pattern = re.compile(
            rf"(<!-- gerado:{name} -->\n).*?(\n<!-- /gerado:{name} -->)",
            re.DOTALL,
        )
        if not pattern.search(text):
            raise SystemExit(f"marcador `gerado:{name}` não encontrado no README")
        text = pattern.sub(lambda m: m.group(1) + block + m.group(2), text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="não escreve; sai 1 se desatualizado")
    args = parser.parse_args()

    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL não definida")

    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute(COUNTS)
        row = dict(zip([column.name for column in cur.description], cur.fetchone()))

    current = README.read_text(encoding="utf-8")
    updated = apply(current, blocks(row))

    if updated == current:
        print("README já está em dia com o banco.")
        return

    if args.check:
        print("README desatualizado: rode `python scripts/update_readme_stats.py`.", file=sys.stderr)
        sys.exit(1)

    README.write_text(updated, encoding="utf-8")
    print("README atualizado com os números do banco.")


if __name__ == "__main__":
    main()
