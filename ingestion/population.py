"""Ingestão de população (IBGE / SIDRA).

Duas granularidades, porque só existem duas:

* **Por Região Administrativa** — Censos 2010 e 2022, via nível territorial
  `N11` (Subdistrito). São os únicos dois pontos no tempo em que o IBGE mede
  população abaixo do município no DF.
* **Do DF inteiro** — série anual estimada 2001–2026 (agregado 6579).

Armadilha documentada: o agregado 4709, o mais citado em tutoriais, **não**
aceita `N11`. A API responde `Parâmetro N11 (Nível territorial) incompatível
com a tabela`. Por isso usamos 9923 (2022) e 1309 (2010).
"""

from __future__ import annotations

import json
import logging

from .common import (
    connect,
    get_json,
    ingestion_run,
    PoliteSession,
    record_check,
    save_raw,
    settings,
    upsert,
)

log = logging.getLogger("ingestion.population")

SIDRA_BASE = "https://servicodados.ibge.gov.br/api/v3/agregados"

# (ano do censo, agregado, variável). Variável 93 = "População residente".
CENSUS_SOURCES = [
    (2010, 1309, 93),
    (2022, 9923, 93),
]

# O IBGE não publica os 35 subdistritos em todo Censo, e isso é propriedade da
# fonte, não falha da ingestão: em 2010 só 19 RAs existiam, e em 2022 duas
# (Arniqueira e Sol Nascente/Pôr do Sol como subdistritos próprios) não têm
# valor divulgado. Exigir 35 fazia a verificação falhar em toda execução, o que
# treina a gente a ignorar erro. O piso abaixo é o que uma regressão da fonte
# violaria de verdade.
CENSUS_EXPECTED_COVERAGE = {2010: 19, 2022: 33}

DF_ESTIMATE_URL = (
    f"{SIDRA_BASE}/6579/periodos/all/variaveis/9324?localidades=N6[5300108]"
)

# A API do SIDRA tem limite prático de URL; 35 ids cabem, mas lotes menores
# tornam a falha parcial mais barata de reexecutar.
BATCH_SIZE = 12


def _census_url(aggregate: int, year: int, variable: int, ids: list[int]) -> str:
    joined = ",".join(str(i) for i in ids)
    return (
        f"{SIDRA_BASE}/{aggregate}/periodos/{year}/variaveis/{variable}"
        f"?localidades=N11[{joined}]"
    )


def _total_series(payload: list) -> dict[str, str]:
    """Extrai {localidade_id: valor} do resultado cuja classificação é 'Total'.

    O SIDRA devolve um bloco por combinação de categorias. Sem parâmetro de
    classificação ele devolve só os totais, mas filtramos explicitamente para
    que uma mudança de contrato vire lista vazia (e falhe na checagem) em vez de
    somar categorias por engano.
    """
    out: dict[str, str] = {}
    for variable_block in payload:
        for result in variable_block.get("resultados", []):
            categories = result.get("classificacoes", [])
            if not all(
                "Total" in categoria["categoria"].values() for categoria in categories
            ):
                continue
            for serie in result.get("series", []):
                locality_id = serie["localidade"]["id"]
                for _, value in serie["serie"].items():
                    out[locality_id] = value
    return out


def _parse_int(value: str) -> int | None:
    """SIDRA usa '-', '..' e 'X' para ausência/sigilo. Ausência vira NULL, não 0."""
    if value is None:
        return None
    cleaned = str(value).strip().replace(".", "")
    if not cleaned or not cleaned.lstrip("-").isdigit():
        return None
    return int(cleaned)


def run() -> None:
    cfg = settings()
    session = PoliteSession(cfg.user_agent, cfg.throttle_seconds)
    conn = connect()

    with conn.cursor() as cur:
        cur.execute("SELECT subdistrict_id FROM raw.ibge_subdistrict ORDER BY subdistrict_id")
        subdistrict_ids = [row[0] for row in cur.fetchall()]

    if not subdistrict_ids:
        raise RuntimeError(
            "raw.ibge_subdistrict está vazia — rode `python -m ingestion.regions` primeiro."
        )

    with ingestion_run(conn, "population") as (run_id, tracker):
        # --- 1. Censos por RA ----------------------------------------------
        for year, aggregate, variable in CENSUS_SOURCES:
            collected: dict[str, str] = {}
            for start in range(0, len(subdistrict_ids), BATCH_SIZE):
                batch = subdistrict_ids[start : start + BATCH_SIZE]
                url = _census_url(aggregate, year, variable, batch)
                payload = get_json(session, url)
                save_raw(
                    "population",
                    f"censo_{year}_agregado{aggregate}_lote{start // BATCH_SIZE}.json",
                    json.dumps(payload, ensure_ascii=False),
                )
                collected.update(_total_series(payload))

            rows = []
            missing = []
            for locality_id, value in collected.items():
                population = _parse_int(value)
                if population is None:
                    missing.append(locality_id)
                    continue
                rows.append(
                    (
                        int(locality_id),
                        year,
                        population,
                        aggregate,
                        _census_url(aggregate, year, variable, subdistrict_ids),
                    )
                )

            expected_ras = CENSUS_EXPECTED_COVERAGE.get(year, len(subdistrict_ids))
            record_check(
                conn,
                run_id,
                f"population.census_{year}_coverage",
                passed=len(rows) >= expected_ras,
                severity="ERROR",
                observed=f"{len(rows)} RAs com valor; sem valor: {missing}",
                expected=f"≥ {expected_ras} RAs (o IBGE não divulga as demais em {year})",
            )

            tracker["rows"] += upsert(
                conn,
                "raw.population_census",
                ["subdistrict_id", "census_year", "population", "ibge_aggregate", "_source_url"],
                rows,
                conflict_columns=["subdistrict_id", "census_year"],
            )
            log.info("Censo %s: %s RAs gravadas", year, len(rows))

        # --- 2. Série anual do DF -------------------------------------------
        payload = get_json(session, DF_ESTIMATE_URL)
        save_raw("population", "df_estimativas.json", json.dumps(payload, ensure_ascii=False))

        estimates = []
        for variable_block in payload:
            for result in variable_block.get("resultados", []):
                for serie in result.get("series", []):
                    for year_str, value in serie["serie"].items():
                        population = _parse_int(value)
                        if population is not None:
                            estimates.append((int(year_str), population, DF_ESTIMATE_URL))

        # Anos de Censo/revisão metodológica não têm estimativa publicada.
        # Preservamos o buraco: interpolar aqui seria inventar dado.
        record_check(
            conn,
            run_id,
            "population.df_estimate_years",
            passed=len(estimates) >= 20,
            severity="WARN",
            observed=sorted(y for y, _, _ in estimates),
            expected="série anual 2001+ com lacunas nos anos de Censo",
        )

        tracker["rows"] += upsert(
            conn,
            "raw.population_df_estimate",
            ["reference_year", "population", "_source_url"],
            estimates,
            conflict_columns=["reference_year"],
        )
        log.info("Estimativas do DF: %s anos gravados", len(estimates))

        tracker["requests"] = session.requests_made

    conn.close()


if __name__ == "__main__":
    from .common import configure_logging

    configure_logging()
    run()
