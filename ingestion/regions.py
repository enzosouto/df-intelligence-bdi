"""Ingestão das Regiões Administrativas do DF.

Duas fontes, porque nenhuma sozinha resolve:

* **IBRAM / ONDA-DF (ArcGIS)** — geometria oficial 2025, código romano da RA
  (`RA-I`…`RA-XXXV`) e nome do GDF. É a espinha dorsal de `dim_region`.
* **IBGE / Localidades** — o `subdistrict_id`, que é a única chave aceita pela
  API do SIDRA para consultar população por RA.

A amarração entre as duas nomenclaturas NÃO é feita aqui. Ela é explícita, em
um seed versionado do dbt (`dbt/seeds/region_name_map.csv`), porque os nomes
divergem e adivinhar equivalência de região é exatamente o tipo de suposição
que este projeto não faz.
"""

from __future__ import annotations

import json
import logging

from pyproj import Geod
from shapely.geometry import shape

from .common import (
    connect,
    get_json,
    ingestion_run,
    PoliteSession,
    record_check,
    save_raw,
    settings,
    upsert,
    as_jsonb,
)

log = logging.getLogger("ingestion.regions")

ARCGIS_URL = (
    "https://onda.ibram.df.gov.br/server/rest/services/Territorio/"
    "Regioes_Administrativas_DF_2025/MapServer/0/query"
    "?where=1%3D1&outFields=*&returnGeometry=true&f=geojson"
)
IBGE_SUBDISTRICTS_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/municipios/5300108/subdistritos"
)

# Nº de RAs esperado nas duas fontes. Se mudar, o pipeline avisa em vez de
# aceitar em silêncio — o DF cria RAs por lei e isso precisa de revisão humana
# do mapeamento de nomes.
EXPECTED_REGION_COUNT = 35

_GEOD = Geod(ellps="WGS84")

# Fronteiras compartilhadas abaixo disso são contato de vértice / ruído
# cartográfico, não vizinhança real.
MIN_SHARED_BORDER_KM = 0.05


def _geodesic_area_km2(geom) -> float:
    """Área geodésica real, em km².

    O campo `st_area(shape)` devolvido pelo ArcGIS vem do CRS projetado do
    serviço e não bate com a área oficial da RA. Calcular a partir do polígono
    WGS84 é reprodutível e auditável.
    """
    area_m2, _ = _GEOD.geometry_area_perimeter(geom)
    return abs(area_m2) / 1_000_000.0


def _geodesic_perimeter_km(geom) -> float:
    _, perimeter_m = _GEOD.geometry_area_perimeter(geom)
    return abs(perimeter_m) / 1000.0


def _geodesic_length_km(geom) -> float:
    if geom.is_empty:
        return 0.0
    lines = getattr(geom, "geoms", [geom])
    total_m = 0.0
    for line in lines:
        coords = list(getattr(line, "coords", []))
        for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
            total_m += _GEOD.inv(lon1, lat1, lon2, lat2)[2]
    return total_m / 1000.0


def _neighbors(geometries: dict[str, object]) -> dict[str, list[dict]]:
    """Vizinhança de cada RA, com a extensão da fronteira compartilhada.

    Isso existe por um motivo analítico concreto: das 35 RAs atuais, apenas 19
    existiam como subdistrito no Censo 2010. As outras 16 foram desmembradas de
    RAs preexistentes. Sem saber disso, comparar população de 2010 com 2022 por
    RA produz absurdos — Ceilândia "perderia" 29% da população, quando na
    verdade o Sol Nascente/Pôr do Sol foi separado dela.

    A vizinhança é FATO GEOMÉTRICO: quem faz fronteira com quem, e por quantos
    quilômetros. O que se faz com ela (inferir origem, bloquear comparação) é
    decisão de modelagem e mora no dbt, em `int_region_lineage`.
    """
    codes = list(geometries)
    result: dict[str, list[dict]] = {code: [] for code in codes}
    for i, code_a in enumerate(codes):
        geom_a = geometries[code_a]
        for code_b in codes[i + 1 :]:
            geom_b = geometries[code_b]
            if not geom_a.intersects(geom_b):
                continue
            shared_km = _geodesic_length_km(
                geom_a.exterior.intersection(geom_b.exterior)
                if hasattr(geom_a, "exterior") and hasattr(geom_b, "exterior")
                else geom_a.boundary.intersection(geom_b.boundary)
            )
            if shared_km < MIN_SHARED_BORDER_KM:
                continue
            result[code_a].append({"ra_code": code_b, "shared_km": round(shared_km, 3)})
            result[code_b].append({"ra_code": code_a, "shared_km": round(shared_km, 3)})
    for code in codes:
        result[code].sort(key=lambda n: n["shared_km"], reverse=True)
    return result


def run() -> None:
    cfg = settings()
    session = PoliteSession(cfg.user_agent, cfg.throttle_seconds)
    conn = connect()

    with ingestion_run(conn, "regions") as (run_id, tracker):
        # --- 1. Geometria (IBRAM / ONDA-DF) --------------------------------
        log.info("Baixando malha das RAs (IBRAM/ONDA-DF)...")
        payload = get_json(session, ARCGIS_URL)
        save_raw("regions", "ra_2025.geojson", json.dumps(payload, ensure_ascii=False))

        features = payload.get("features") or []
        record_check(
            conn,
            run_id,
            "regions.feature_count",
            passed=len(features) == EXPECTED_REGION_COUNT,
            severity="WARN",
            observed=len(features),
            expected=EXPECTED_REGION_COUNT,
        )
        if not features:
            raise ValueError("Malha das RAs voltou vazia — fonte indisponível ou contrato mudou.")

        geometries: dict[str, object] = {}
        by_code: dict[str, dict] = {}
        for feature in features:
            props = feature["properties"]
            ra_code = (props.get("ra_codigo") or "").strip().upper()
            if not ra_code:
                raise ValueError(f"Feature sem ra_codigo: {props.get('ra_nome')!r}")
            if ra_code in geometries:
                raise ValueError(f"ra_codigo duplicado na fonte: {ra_code}")

            geom = shape(feature["geometry"])
            if not geom.is_valid:
                geom = geom.buffer(0)  # conserta auto-interseções da cartografia
            geometries[ra_code] = geom
            by_code[ra_code] = feature

        neighbors = _neighbors(geometries)

        rows = []
        for ra_code, feature in by_code.items():
            props = feature["properties"]
            geom = geometries[ra_code]
            inner_point = geom.representative_point()  # garantidamente DENTRO do polígono
            min_lon, min_lat, max_lon, max_lat = geom.bounds
            rows.append(
                (
                    ra_code,
                    int(props["ra_cira"]),
                    (props.get("ra_nome") or "").strip(),
                    props.get("ra_path"),
                    round(_geodesic_area_km2(geom), 4),
                    round(_geodesic_perimeter_km(geom), 4),
                    round(inner_point.y, 6),
                    round(inner_point.x, 6),
                    min_lon,
                    min_lat,
                    max_lon,
                    max_lat,
                    as_jsonb(feature["geometry"]),
                    as_jsonb(neighbors[ra_code]),
                    ARCGIS_URL,
                )
            )

        tracker["rows"] += upsert(
            conn,
            "raw.region_geo",
            [
                "ra_code",
                "ra_cira",
                "ra_name_source",
                "ra_monograph_url",
                "area_km2",
                "perimeter_km",
                "centroid_lat",
                "centroid_lon",
                "bbox_min_lon",
                "bbox_min_lat",
                "bbox_max_lon",
                "bbox_max_lat",
                "geometry",
                "neighbors",
                "_source_url",
            ],
            rows,
            conflict_columns=["ra_code"],
        )
        log.info("%s Regiões Administrativas gravadas em raw.region_geo", len(rows))

        # --- 2. Subdistritos IBGE ------------------------------------------
        log.info("Baixando subdistritos do IBGE...")
        subdistricts = get_json(session, IBGE_SUBDISTRICTS_URL)
        save_raw("regions", "ibge_subdistritos.json", json.dumps(subdistricts, ensure_ascii=False))

        record_check(
            conn,
            run_id,
            "regions.ibge_subdistrict_count",
            passed=len(subdistricts) == EXPECTED_REGION_COUNT,
            severity="WARN",
            observed=len(subdistricts),
            expected=EXPECTED_REGION_COUNT,
        )

        tracker["rows"] += upsert(
            conn,
            "raw.ibge_subdistrict",
            [
                "subdistrict_id",
                "subdistrict_name",
                "district_id",
                "municipality_id",
                "_source_url",
            ],
            [
                (
                    int(s["id"]),
                    s["nome"].strip(),
                    int(s["distrito"]["id"]),
                    int(s["distrito"]["municipio"]["id"]),
                    IBGE_SUBDISTRICTS_URL,
                )
                for s in subdistricts
            ],
            conflict_columns=["subdistrict_id"],
        )
        log.info("%s subdistritos gravados em raw.ibge_subdistrict", len(subdistricts))

        tracker["requests"] = session.requests_made

    conn.close()


if __name__ == "__main__":
    from .common import configure_logging

    configure_logging()
    run()
