"""Ingestão de mobilidade: malha cicloviária, metrô e terminais (IDE-DF).

Fonte: FeatureServer público da Infraestrutura de Dados Espaciais do DF
(`geoservicos.ide.df.gov.br`, serviço `Publico/IDEDF`), mantido pela SEDUH.

Por que a IDE-DF e não a SEMOB ou o DETRAN: o GeoServer da SEMOB
(`geoserver.semob.df.gov.br`) não aceita conexão a partir de fora do Brasil
(ConnectTimeout), e os portais da SEMOB, do DETRAN e o `dados.df.gov.br`
estouram 30 s sem responder. A IDE-DF responde em ~1 s. Ver
`docs/data_sources.md`.

TRÊS CAMADAS, TRÊS DECISÕES (verificadas nos dados reais)

1. **Sistema Cicloviário (camada 218)** — 2.293 trechos, 671,9 km. O trecho
   traz a RA declarada (`cvia_ra`), mas 35 trechos cruzam divisa e 47 declaram
   uma RA diferente da que contém a maior parte da geometria. O comprimento por
   RA vem do RECORTE geométrico: cada trecho é intersectado com os polígonos
   oficiais e medido de forma geodésica (elipsoide WGS84). O km declarado
   (`cvia_km`) fica guardado só para reconciliação.

2. **Estação de Metrô (camada 140)** — 29 estações, com situação ("EM
   OPERAÇÃO" / "EM CONSTRUÇÃO"). É a fonte única do metrô.

3. **Estações e Terminais (camada 127)** — mistura três coisas. Dela só entram
   os terminais de ônibus:
   * as 17 "ESTAÇÃO METRÔ" DUPLICAM parte da camada 140 (que tem 27 em
     operação). Somar as duas contaria estação duas vezes;
   * as 5 "ESTAÇÃO BRT" vêm sem nome e não dá para verificar a contagem.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter

from pyproj import Geod
from shapely.geometry import shape

from .common import (
    connect,
    get_json,
    ingestion_run,
    load_region_index,
    PoliteSession,
    record_check,
    save_raw,
    settings,
    upsert,
)

log = logging.getLogger("ingestion.mobility")

FEATURE_SERVER = "https://www.geoservicos.ide.df.gov.br/arcgis/rest/services/Publico/IDEDF/FeatureServer"
BIKEWAY_LAYER = 218
METRO_LAYER = 140
TERMINAL_LAYER = 127
PAGE_SIZE = 1000  # maxRecordCount do serviço
MAX_PAGES = 50

GEOD = Geod(ellps="WGS84")

# Pedaço de trecho menor que isto numa RA é ruído de divisa (vértice encostado
# no limite), não infraestrutura naquela RA.
MIN_PIECE_KM = 0.001

TERMINAL_TYPE = "TERMINAIS DFTRANS"


# --------------------------------------------------------------------------- #
# Funções puras (testadas em tests/test_mobility.py)
# --------------------------------------------------------------------------- #
def geodesic_km(geometry) -> float:
    """Comprimento geodésico em km. A geometria vem em lon/lat (EPSG:4326)."""
    return GEOD.geometry_length(geometry) / 1000.0


def split_by_region(line, codes, geometries, tree) -> dict[str, float]:
    """Km de um trecho dentro de cada RA que ele atravessa."""
    pieces: dict[str, float] = {}
    for index in tree.query(line):
        inside = line.intersection(geometries[index])
        if inside.is_empty:
            continue
        km = geodesic_km(inside)
        if km >= MIN_PIECE_KM:
            pieces[codes[index]] = pieces.get(codes[index], 0.0) + km
    return pieces


def region_of_point(point, codes, geometries, tree) -> str | None:
    for index in tree.query(point):
        if geometries[index].covers(point):
            return codes[index]
    return None


def parse_year(value) -> int | None:
    """Ano de construção como inteiro, ou nulo. Nunca adivinha século."""
    text = str(value or "").strip()
    return int(text) if re.fullmatch(r"(19|20)\d{2}", text) else None


def clean(value) -> str | None:
    text = " ".join(str(value or "").split())
    return text or None


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def _layer_features(session: PoliteSession, layer: int) -> list[dict]:
    """Todas as feições da camada, em lon/lat, paginando por `objectid`.

    A paginação ordenada é obrigatória: sem `orderByFields`, o ArcGIS não
    garante que duas páginas não se sobreponham.
    """
    features: list[dict] = []
    for page in range(MAX_PAGES):
        payload = get_json(
            session,
            f"{FEATURE_SERVER}/{layer}/query",
            params={
                "where": "1=1",
                "outFields": "*",
                "outSR": 4326,
                "f": "geojson",
                "orderByFields": "objectid",
                "resultOffset": page * PAGE_SIZE,
                "resultRecordCount": PAGE_SIZE,
            },
        )
        batch = payload.get("features") or []
        features.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    else:
        raise RuntimeError(f"camada {layer}: mais de {MAX_PAGES} páginas — revise o limite")

    ids = [feature["properties"]["objectid"] for feature in features]
    if len(ids) != len(set(ids)):
        raise ValueError(f"camada {layer}: objectid repetido entre páginas")
    save_raw("mobility", f"idedf_layer_{layer}.geojson", json.dumps(features, ensure_ascii=False))
    return features


def _expected_count(session: PoliteSession, layer: int) -> int:
    payload = get_json(
        session,
        f"{FEATURE_SERVER}/{layer}/query",
        params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
    )
    return int(payload["count"])


# --------------------------------------------------------------------------- #
# Execução
# --------------------------------------------------------------------------- #
def run() -> None:
    cfg = settings()
    session = PoliteSession(cfg.user_agent, cfg.throttle_seconds)
    conn = connect()
    codes, geometries, tree = load_region_index(conn)
    layer_url = f"{FEATURE_SERVER}/{{}}"

    with ingestion_run(conn, "mobility") as (run_id, tracker):
        # --- Malha cicloviária -------------------------------------------------
        bikeways = _layer_features(session, BIKEWAY_LAYER)
        expected = _expected_count(session, BIKEWAY_LAYER)
        record_check(
            conn, run_id, "mobility.bikeway_count", passed=len(bikeways) == expected,
            severity="ERROR", observed=len(bikeways), expected=f"{expected} trechos (returnCountOnly)",
        )

        segment_rows, piece_rows = [], []
        declared_total = geometric_total = 0.0
        crossing = 0
        for feature in bikeways:
            props = feature["properties"]
            if not feature.get("geometry"):
                continue
            line = shape(feature["geometry"])
            length = geodesic_km(line)
            pieces = split_by_region(line, codes, geometries, tree)
            crossing += len(pieces) > 1
            declared_total += props.get("cvia_km") or 0.0
            geometric_total += length
            segment_rows.append(
                (
                    props["objectid"],
                    clean(props.get("cvia_ra")),
                    props.get("cvia_km"),
                    round(length, 5),
                    parse_year(props.get("cvia_ano_construcao")),
                    clean(props.get("cvia_ano_construcao")),
                    clean(props.get("cvia_tipologia")),
                    clean(props.get("cvia_tipo_via")),
                    clean(props.get("cvia_nome_trecho")),
                    clean(props.get("cvia_nome_rodovia")),
                    layer_url.format(BIKEWAY_LAYER),
                )
            )
            piece_rows.extend(
                (props["objectid"], ra_code, round(km, 5), layer_url.format(BIKEWAY_LAYER))
                for ra_code, km in pieces.items()
            )

        log.info(
            "%s trechos cicloviários: %.1f km declarados, %.1f km geodésicos, %s cruzam divisa",
            len(segment_rows), declared_total, geometric_total, crossing,
        )
        record_check(
            conn, run_id, "mobility.bikeway_km_reconciles",
            passed=abs(geometric_total - declared_total) <= 0.02 * max(declared_total, 1),
            severity="WARN", observed=f"{geometric_total:.1f} km geodésicos",
            expected=f"{declared_total:.1f} km declarados ± 2%",
        )

        tracker["rows"] += upsert(
            conn,
            "raw.mobility_bikeway_segment",
            [
                "segment_id", "declared_ra_name", "declared_km", "geodesic_km",
                "construction_year", "construction_year_raw", "typology", "road_type",
                "segment_name", "highway_name", "_source_url",
            ],
            segment_rows,
            conflict_columns=["segment_id"],
        )
        # Recorte refeito do zero: se a malha oficial mudar, um pedaço antigo
        # numa RA errada não pode sobreviver ao upsert.
        with conn.cursor() as cur:
            cur.execute("DELETE FROM raw.mobility_bikeway_piece")
        conn.commit()
        tracker["rows"] += upsert(
            conn,
            "raw.mobility_bikeway_piece",
            ["segment_id", "ra_code", "km", "_source_url"],
            piece_rows,
            conflict_columns=["segment_id", "ra_code"],
        )

        # --- Metrô e terminais -------------------------------------------------
        station_rows = []
        kinds: Counter[str] = Counter()
        for feature in _layer_features(session, METRO_LAYER):
            props = feature["properties"]
            point = shape(feature["geometry"])
            station_rows.append(
                (
                    "METRO", props["objectid"], clean(props.get("mto_nome_estac")),
                    clean(props.get("mto_situacao")), clean(props.get("mto_num_estaca")),
                    point.y, point.x, region_of_point(point, codes, geometries, tree),
                    layer_url.format(METRO_LAYER),
                )
            )
            kinds["METRO"] += 1

        ignored: Counter[str] = Counter()
        for feature in _layer_features(session, TERMINAL_LAYER):
            props = feature["properties"]
            kind = clean(props.get("let_tipo"))
            if kind != TERMINAL_TYPE:
                ignored[kind or "SEM TIPO"] += 1
                continue
            point = shape(feature["geometry"])
            station_rows.append(
                (
                    "BUS_TERMINAL", props["objectid"], clean(props.get("let_nome_estac")),
                    clean(props.get("let_situacao")), None,
                    point.y, point.x, region_of_point(point, codes, geometries, tree),
                    layer_url.format(TERMINAL_LAYER),
                )
            )
            kinds["BUS_TERMINAL"] += 1
        log.info("Estações gravadas: %s. Ignoradas da camada %s: %s", dict(kinds), TERMINAL_LAYER, dict(ignored))

        tracker["rows"] += upsert(
            conn,
            "raw.mobility_station",
            ["station_kind", "feature_id", "station_name", "status", "station_number",
             "latitude", "longitude", "ra_code", "_source_url"],
            station_rows,
            conflict_columns=["station_kind", "feature_id"],
        )
        unlocated = sum(1 for row in station_rows if row[7] is None)
        record_check(
            conn, run_id, "mobility.stations_located", passed=unlocated == 0, severity="WARN",
            observed=unlocated, expected="0 estações fora das RAs",
        )
        tracker["requests"] = session.requests_made

    conn.close()


if __name__ == "__main__":
    from .common import configure_logging

    configure_logging()
    run()
