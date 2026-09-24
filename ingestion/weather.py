"""Ingestão de clima diário por Região Administrativa (Open-Meteo / ERA5).

ATENÇÃO — ESTA NÃO É UMA FONTE GOVERNAMENTAL DO DISTRITO FEDERAL.

Open-Meteo é um serviço aberto europeu que serve a reanálise ERA5 (ECMWF). Os
valores são saída de modelo interpolada para o ponto consultado, **não** leitura
de estação do INMET. Como as 35 RAs cabem em poucas células da grade ERA5, a
variação entre RAs é pequena: leia como microclima aproximado, não como medição
local. Essa ressalva é propagada até o frontend.

O ponto consultado por RA é o `representative_point()` do polígono — um ponto
garantidamente dentro da região (o centroide geométrico pode cair fora em RAs
de formato côncavo).

A ingestão é incremental: busca a partir do último dia já gravado (com 3 dias
de sobreposição, porque o ERA5 revisa os dias mais recentes).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta

from .common import (
    connect,
    ingestion_run,
    PoliteSession,
    record_check,
    save_raw,
    settings,
    upsert,
)

log = logging.getLogger("ingestion.weather")

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "relative_humidity_2m_mean",
    "wind_speed_10m_max",
]
TIMEZONE = "America/Sao_Paulo"

# O arquivo ERA5 tem latência de ~5 dias. Pedimos até D-6 para não receber
# páginas de nulos.
ARCHIVE_LAG_DAYS = 6

# Sobreposição ao retomar: o ERA5 revisa os dias mais recentes.
REFETCH_DAYS = 3

# Célula de amostragem, em graus. A grade do ERA5 é de 0,25° (~28 km) e a do
# ERA5-Land, 0,1° (~11 km) — ou seja, MENOR resolução do que 35 polígonos
# dentro de 5.760 km². Consultar 35 pontos distintos gastaria cota da API para
# receber a mesma série várias vezes.
#
# Agrupamos as RAs por célula de 0,1° e consultamos uma vez por célula. RAs na
# mesma célula recebem a mesma série — que é o que a fonte tem a dizer. A
# coordenada consultada fica gravada em `grid_lat`/`grid_lon` para que a
# interface possa declarar isso ao usuário.
GRID_DEGREES = 0.1

# A API pública aplica cota diária. Em 429, esperar e tentar de novo custa
# menos do que perder a ingestão inteira.
RATE_LIMIT_SLEEP_SECONDS = 70
RATE_LIMIT_MAX_RETRIES = 3


def _regions(conn) -> list[tuple[str, float, float]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ra_code, centroid_lat, centroid_lon FROM raw.region_geo ORDER BY ra_code"
        )
        return cur.fetchall()


def _resume_date(conn, default_start: str) -> date:
    with conn.cursor() as cur:
        cur.execute("SELECT max(observed_on) FROM raw.weather_daily")
        last = cur.fetchone()[0]
    if last is None:
        return datetime.strptime(default_start, "%Y-%m-%d").date()
    return last - timedelta(days=REFETCH_DAYS)


def _as_float(value):
    return None if value is None else float(value)


def _grid_cells(regions: list[tuple[str, float, float]]) -> dict[tuple[float, float], list[str]]:
    """Agrupa RAs por célula de amostragem. Chave = coordenada consultada."""
    cells: dict[tuple[float, float], list[str]] = {}
    for ra_code, lat, lon in regions:
        key = (
            round(round(lat / GRID_DEGREES) * GRID_DEGREES, 4),
            round(round(lon / GRID_DEGREES) * GRID_DEGREES, 4),
        )
        cells.setdefault(key, []).append(ra_code)
    return cells


def _fetch_cell(session, lat: float, lon: float, start: date, end: date) -> dict:
    """GET com tratamento explícito de 429 (cota diária da API pública)."""
    url = (
        f"{ARCHIVE_URL}?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&start_date={start}&end_date={end}"
        f"&daily={','.join(DAILY_VARIABLES)}&timezone={TIMEZONE}"
    )
    for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
        response = session.get(url)
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()
        if attempt == RATE_LIMIT_MAX_RETRIES:
            break
        log.warning(
            "Open-Meteo devolveu 429 (cota). Aguardando %ss — tentativa %s/%s",
            RATE_LIMIT_SLEEP_SECONDS, attempt + 1, RATE_LIMIT_MAX_RETRIES,
        )
        time.sleep(RATE_LIMIT_SLEEP_SECONDS)
    raise RuntimeError(
        "Open-Meteo esgotou a cota diária gratuita. Reduza WEATHER_START_DATE ou "
        "reexecute amanhã — a ingestão é incremental e retoma de onde parou."
    )


def run() -> None:
    cfg = settings()
    session = PoliteSession(cfg.user_agent, cfg.throttle_seconds)
    conn = connect()

    regions = _regions(conn)
    if not regions:
        raise RuntimeError(
            "raw.region_geo está vazia — rode `python -m ingestion.regions` primeiro."
        )

    start = _resume_date(conn, cfg.weather_start_date)
    end = date.today() - timedelta(days=ARCHIVE_LAG_DAYS)
    if start > end:
        log.info("Clima já está atualizado até %s — nada a fazer.", end)
        return

    log.info("Buscando clima de %s a %s para %s RAs", start, end, len(regions))

    cells = _grid_cells(regions)
    log.info("%s RAs agrupadas em %s células de %s°", len(regions), len(cells), GRID_DEGREES)

    with ingestion_run(conn, "weather") as (run_id, tracker):
        rows: list[tuple] = []
        for position, ((lat, lon), ra_codes) in enumerate(cells.items(), start=1):
            payload = _fetch_cell(session, lat, lon, start, end)
            daily = payload["daily"]
            if not daily.get("time"):
                raise ValueError(f"Open-Meteo devolveu série vazia para {lat},{lon}")

            for ra_code in ra_codes:
                for index, day in enumerate(daily["time"]):
                    rows.append(
                        (
                            ra_code,
                            day,
                            _as_float(daily["temperature_2m_max"][index]),
                            _as_float(daily["temperature_2m_min"][index]),
                            _as_float(daily["temperature_2m_mean"][index]),
                            _as_float(daily["precipitation_sum"][index]),
                            _as_float(daily["relative_humidity_2m_mean"][index]),
                            _as_float(daily["wind_speed_10m_max"][index]),
                            payload.get("latitude", lat),
                            payload.get("longitude", lon),
                            ARCHIVE_URL,
                        )
                    )
            log.info("... célula %s/%s (%s RAs)", position, len(cells), len(ra_codes))

        save_raw(
            "weather",
            f"open_meteo_{start}_{end}.json",
            json.dumps({"rows": len(rows), "start": str(start), "end": str(end)}),
        )

        expected = len(regions) * ((end - start).days + 1)
        record_check(
            conn,
            run_id,
            "weather.row_count",
            passed=abs(len(rows) - expected) <= len(regions),
            severity="WARN",
            observed=len(rows),
            expected=expected,
        )

        tracker["rows"] += upsert(
            conn,
            "raw.weather_daily",
            [
                "ra_code",
                "observed_on",
                "temp_max_c",
                "temp_min_c",
                "temp_mean_c",
                "precipitation_mm",
                "humidity_mean_pct",
                "wind_max_kmh",
                "grid_lat",
                "grid_lon",
                "_source_url",
            ],
            rows,
            conflict_columns=["ra_code", "observed_on"],
        )
        log.info("%s linhas diárias gravadas", len(rows))
        tracker["requests"] = session.requests_made

    conn.close()


if __name__ == "__main__":
    from .common import configure_logging

    configure_logging()
    run()
