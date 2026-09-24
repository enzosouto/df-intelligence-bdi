"""Verificação de disponibilidade e contrato das fontes.

Roda antes da ingestão (localmente e no CI). Faz uma requisição real e barata a
cada fonte e confere que a resposta ainda tem o formato esperado.

O objetivo é falhar cedo e alto: é melhor o pipeline parar dizendo "a SSP mudou
o layout da página" do que gravar zero linha no banco e o dashboard mostrar uma
queda que não existe.

    python -m ingestion.validate_sources
"""

from __future__ import annotations

import logging
import sys
from datetime import date, timedelta

from .common import PoliteSession, configure_logging, get_json, settings

log = logging.getLogger("ingestion.validate")


def check_regions(session) -> str:
    payload = get_json(
        session,
        "https://onda.ibram.df.gov.br/server/rest/services/Territorio/"
        "Regioes_Administrativas_DF_2025/MapServer/0/query"
        "?where=1%3D1&outFields=ra_codigo,ra_nome&returnGeometry=false&f=geojson",
    )
    features = payload.get("features", [])
    assert features, "sem features"
    assert "ra_codigo" in features[0]["properties"], "campo ra_codigo sumiu"
    return f"{len(features)} Regiões Administrativas"


def check_ibge_subdistricts(session) -> str:
    payload = get_json(
        session,
        "https://servicodados.ibge.gov.br/api/v1/localidades/municipios/5300108/subdistritos",
    )
    assert isinstance(payload, list) and payload, "lista vazia"
    assert "id" in payload[0] and "nome" in payload[0], "contrato mudou"
    return f"{len(payload)} subdistritos"


def check_census(session) -> str:
    payload = get_json(
        session,
        "https://servicodados.ibge.gov.br/api/v3/agregados/9923/periodos/2022/"
        "variaveis/93?localidades=N11[53001080506]",
    )
    serie = payload[0]["resultados"][0]["series"][0]["serie"]
    assert serie.get("2022"), "Censo 2022 sem valor para o Plano Piloto"
    return f"Plano Piloto 2022 = {serie['2022']} pessoas"


def check_df_estimates(session) -> str:
    payload = get_json(
        session,
        "https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/all/"
        "variaveis/9324?localidades=N6[5300108]",
    )
    serie = payload[0]["resultados"][0]["series"][0]["serie"]
    assert len(serie) > 15, "série anual muito curta"
    return f"{len(serie)} anos ({min(serie)}–{max(serie)})"


def check_ssp(session) -> str:
    response = session.get("https://www.ssp.df.gov.br/dados-por-regiao-administrativa/")
    response.raise_for_status()
    page = response.text
    assert 'id="RAs"' in page, "âncora 'RAs' sumiu — layout da página mudou"
    import re

    section = page[page.find('id="RAs"') :]
    links = {h for h in re.findall(r'href="([^"]+)"', section) if "xls" in h.lower()}
    assert len(links) > 100, f"apenas {len(links)} planilhas encontradas"
    return f"{len(links)} planilhas por RA"


def check_cnes(session) -> str:
    payload = get_json(
        session,
        "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
        "?codigo_municipio=530010&limit=1",
    )
    item = payload["estabelecimentos"][0]
    assert "latitude_estabelecimento_decimo_grau" in item, "campo de latitude sumiu"
    return f"CNES {item['codigo_cnes']} — {item.get('nome_fantasia')}"


def check_open_meteo(session) -> str:
    end = date.today() - timedelta(days=7)
    start = end - timedelta(days=2)
    payload = get_json(
        session,
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude=-15.78&longitude=-47.93&start_date={start}&end_date={end}"
        "&daily=temperature_2m_max,precipitation_sum&timezone=America/Sao_Paulo",
    )
    daily = payload["daily"]
    assert daily["time"], "sem dias na resposta"
    return f"{len(daily['time'])} dias, última máx = {daily['temperature_2m_max'][-1]}°C"


CHECKS = {
    "Regiões Administrativas (IBRAM/ONDA-DF)": check_regions,
    "Subdistritos (IBGE Localidades)": check_ibge_subdistricts,
    "População por RA (IBGE Censo 2022)": check_census,
    "População do DF (IBGE estimativas)": check_df_estimates,
    "Balanço Criminal (SSP-DF)": check_ssp,
    "Estabelecimentos de saúde (CNES)": check_cnes,
    "Clima histórico (Open-Meteo/ERA5)": check_open_meteo,
}


def main() -> int:
    configure_logging()
    cfg = settings()
    session = PoliteSession(cfg.user_agent, cfg.throttle_seconds)

    failures = 0
    for name, check in CHECKS.items():
        try:
            detail = check(session)
        except Exception as exc:
            failures += 1
            log.error("FALHOU  %-42s  %s: %s", name, type(exc).__name__, exc)
        else:
            log.info("OK      %-42s  %s", name, detail)

    if failures:
        log.error("%s de %s fontes indisponíveis ou com contrato alterado.", failures, len(CHECKS))
        return 1
    log.info("Todas as %s fontes respondendo conforme documentado.", len(CHECKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
