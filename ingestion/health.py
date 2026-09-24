"""Ingestão de estabelecimentos de saúde (CNES / Ministério da Saúde).

Por que o CNES e não SIA/SIH/SINASC: o DF é um único município IBGE
(`5300108`). Todas as bases federais de *produção* de saúde param nesse código,
ou seja, no DF inteiro — não existe recorte por Região Administrativa nelas.

O CNES é a única base de saúde federal testada que traz latitude/longitude por
registro. Isso permite atribuir cada estabelecimento a uma RA por
*point-in-polygon* contra a malha oficial, criando de fato um indicador de
saúde com granularidade de RA.

Consequência honesta: este é um indicador de **infraestrutura** (quantos e que
tipo de serviços existem onde), **não** de produção (quantos atendimentos foram
feitos). A limitação está declarada na API e na interface.
"""

from __future__ import annotations

import json
import logging

from collections import Counter

from shapely.geometry import shape, Point
from shapely.strtree import STRtree

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

log = logging.getLogger("ingestion.health")

CNES_URL = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
CNES_UNIT_TYPES_URL = "https://apidadosabertos.saude.gov.br/cnes/tipounidades"
MUNICIPALITY_CODE = "530010"  # Brasília no padrão de 6 dígitos do CNES
PAGE_SIZE = 100
MAX_PAGES = 400  # trava de segurança: 40.000 registros

# Coordenadas de preenchimento ("placeholder") são detectadas pelos próprios
# dados, não por uma lista fixa: se dezenas de estabelecimentos distintos
# compartilham a coordenada EXATA, aquilo não é endereço, é valor padrão.
#
# No extrato atual do CNES em Brasília isso pega 274 registros em duas
# coordenadas — 232 em (-15.78, -47.93), o centro genérico da cidade.
#
# Tratá-los como localizados seria pior do que tratá-los como ausentes: eles
# se empilhariam todos na RA onde a coordenada falsa cai (Cruzeiro/Plano
# Piloto), inflando a rede de saúde dessas regiões e esvaziando as demais.
# Marcados como MISSING, eles caem na inferência por bairro.
PLACEHOLDER_MIN_SHARED = 20


def _load_region_index(conn):
    """Índice espacial das RAs a partir de raw.region_geo."""
    with conn.cursor() as cur:
        cur.execute("SELECT ra_code, geometry FROM raw.region_geo")
        records = cur.fetchall()
    if not records:
        raise RuntimeError(
            "raw.region_geo está vazia — rode `python -m ingestion.regions` primeiro."
        )
    codes = [row[0] for row in records]
    geometries = [shape(row[1]) for row in records]
    return codes, geometries, STRtree(geometries)


def _placeholder_coordinates(facilities: list[dict]) -> set[tuple[float, float]]:
    """Coordenadas compartilhadas por estabelecimentos demais para serem reais."""
    tally: Counter[tuple[float, float]] = Counter()
    for item in facilities:
        lat = _as_float(item.get("latitude_estabelecimento_decimo_grau"))
        lon = _as_float(item.get("longitude_estabelecimento_decimo_grau"))
        if lat is not None and lon is not None:
            tally[(lat, lon)] += 1
    return {coord for coord, count in tally.items() if count >= PLACEHOLDER_MIN_SHARED}


def _assign_region(lat, lon, codes, geometries, tree, placeholders) -> tuple[str | None, str]:
    if lat is None or lon is None:
        return None, "MISSING"
    if (lat, lon) in placeholders:
        # Coordenada de preenchimento não localiza nada. Vira ausência, e a
        # inferência por bairro decide — em vez de empilhar a rede toda numa RA.
        return None, "MISSING"

    point = Point(lon, lat)
    for index in tree.query(point):
        if geometries[index].covers(point):
            return codes[index], "OK"
    return None, "OUTSIDE_DF"


def _as_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().upper()
    if text in {"1", "S", "SIM", "TRUE", "T"}:
        return True
    if text in {"0", "N", "NAO", "NÃO", "FALSE", "F"}:
        return False
    return None


def _text(value):
    text = str(value).strip() if value is not None else ""
    return text or None


def _as_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number == 0 else number


def run() -> None:
    cfg = settings()
    session = PoliteSession(cfg.user_agent, cfg.throttle_seconds)
    conn = connect()
    codes, geometries, tree = _load_region_index(conn)

    with ingestion_run(conn, "health") as (run_id, tracker):
        # --- Domínio: tipos de unidade --------------------------------------
        unit_types = get_json(session, f"{CNES_UNIT_TYPES_URL}?limit=200")["tipos_unidade"]
        save_raw("health", "cnes_tipounidades.json", json.dumps(unit_types, ensure_ascii=False))
        tracker["rows"] += upsert(
            conn,
            "raw.health_unit_type",
            ["unit_type_code", "description", "_source_url"],
            [
                (int(t["codigo_tipo_unidade"]), t["descricao_tipo_unidade"], CNES_UNIT_TYPES_URL)
                for t in unit_types
            ],
            conflict_columns=["unit_type_code"],
        )
        log.info("%s tipos de unidade CNES gravados", len(unit_types))

        # --- Estabelecimentos -----------------------------------------------
        facilities: list[dict] = []
        for page in range(MAX_PAGES):
            url = f"{CNES_URL}?codigo_municipio={MUNICIPALITY_CODE}&limit={PAGE_SIZE}&offset={page * PAGE_SIZE}"
            payload = get_json(session, url)
            batch = payload.get("estabelecimentos") or []
            if not batch:
                break
            facilities.extend(batch)
            if page % 20 == 0:
                log.info("... %s estabelecimentos baixados", len(facilities))
        else:
            log.warning("Limite de %s páginas atingido — pode haver mais dados.", MAX_PAGES)

        save_raw("health", "cnes_estabelecimentos.json", json.dumps(facilities, ensure_ascii=False))
        log.info("%s estabelecimentos no CNES para Brasília", len(facilities))

        record_check(
            conn,
            run_id,
            "health.facility_count",
            passed=len(facilities) > 1000,
            severity="ERROR",
            observed=len(facilities),
            expected="> 1.000 estabelecimentos",
        )

        placeholders = _placeholder_coordinates(facilities)
        if placeholders:
            log.info("%s coordenadas de preenchimento detectadas: %s", len(placeholders), sorted(placeholders))

        rows = []
        quality_tally: dict[str, int] = {}
        for item in facilities:
            lat = _as_float(item.get("latitude_estabelecimento_decimo_grau"))
            lon = _as_float(item.get("longitude_estabelecimento_decimo_grau"))
            ra_code, quality = _assign_region(lat, lon, codes, geometries, tree, placeholders)
            quality_tally[quality] = quality_tally.get(quality, 0) + 1

            rows.append(
                (
                    int(item["codigo_cnes"]),
                    item.get("nome_fantasia"),
                    item.get("nome_razao_social"),
                    item.get("codigo_tipo_unidade"),
                    item.get("descricao_esfera_administrativa"),
                    item.get("tipo_gestao"),
                    _text(item.get("descricao_natureza_juridica_estabelecimento")),
                    item.get("bairro_estabelecimento"),
                    item.get("codigo_cep_estabelecimento"),
                    lat,
                    lon,
                    _as_bool(item.get("estabelecimento_possui_centro_cirurgico")),
                    _as_bool(item.get("estabelecimento_possui_centro_obstetrico")),
                    _as_bool(item.get("estabelecimento_possui_centro_neonatal")),
                    _as_bool(item.get("estabelecimento_possui_atendimento_hospitalar")),
                    _as_bool(item.get("estabelecimento_possui_atendimento_ambulatorial")),
                    _as_bool(item.get("estabelecimento_faz_atendimento_ambulatorial_sus")),
                    item.get("descricao_turno_atendimento"),
                    item.get("data_atualizacao"),
                    ra_code,
                    quality,
                    CNES_URL,
                )
            )

        log.info("Qualidade da geolocalização: %s", quality_tally)
        localized = quality_tally.get("OK", 0) + quality_tally.get("LOW", 0)
        record_check(
            conn,
            run_id,
            "health.geocode_coverage",
            passed=localized >= len(rows) * 0.9,
            severity="WARN",
            observed=quality_tally,
            expected=">= 90% dos estabelecimentos atribuídos a uma RA",
        )

        tracker["rows"] += upsert(
            conn,
            "raw.health_facility",
            [
                "cnes_code",
                "trade_name",
                "legal_name",
                "unit_type_code",
                "admin_sphere",
                "management_type",
                "legal_nature_code",
                "neighborhood",
                "postal_code",
                "latitude",
                "longitude",
                "has_surgery_center",
                "has_obstetric_center",
                "has_neonatal_center",
                "has_hospital_care",
                "has_ambulatory_care",
                "serves_sus_ambulatory",
                "shift_description",
                "source_updated_at",
                "ra_code",
                "geocode_quality",
                "_source_url",
            ],
            rows,
            conflict_columns=["cnes_code"],
        )
        tracker["requests"] = session.requests_made

    conn.close()


if __name__ == "__main__":
    from .common import configure_logging

    configure_logging()
    run()
