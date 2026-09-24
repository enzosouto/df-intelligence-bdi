"""Ingestão de educação: escolas e matrículas do Educacenso (SEEDF).

Fonte: portal de dados abertos da Secretaria de Educação do DF
(`data.se.df.gov.br`, CKAN), que republica o Censo Escolar do Inep para TODAS
as redes do DF — pública distrital, federal, conveniada e particular — com a
Região Administrativa de cada escola. Dois conjuntos são usados:

* **Série Histórica de Unidades Escolares** (2014–2025): uma linha por escola.
* **Série Histórica do Número de Matrículas** (2014–2025): uma linha por
  escola × idade × sexo × cor/raça (e nacionalidade em 2025) — ~80 mil linhas
  por ano, agregadas aqui para o grão escola × ano.

ARMADILHAS VERIFICADAS NOS ARQUIVOS REAIS (e tratadas aqui)

1. **O esquema muda entre anos.** Colunas trocam de nome (`CO_RA` → `RA`,
   `CO_ENTIDADE` → `Código INEP`, `ESC_EF_TOTAL` → `MAT_EF_TOTAL` → `Ensino
   fundamental - TOTAL`), a latitude vira `LATITUDE` em 2019 e some em 2025.
   Toda coluna é localizada pelo NOME normalizado, nunca pela posição.
2. **Linha-banner acima do cabeçalho** em 2025 ("EXTRAÍDO DO MICRODADOS…").
   O cabeçalho é a primeira linha que contém a coluna de ano.
3. **O ano sai do conteúdo** (`NU_ANO_CENSO`), não do nome do recurso no CKAN.
4. **Separador de milhar dentro de CSV com vírgula**: `"2,657"` são 2.657
   matrículas. Só são aceitos inteiros puros ou com milhar bem formado; outra
   coisa derruba a ingestão em vez de virar número errado.
5. **`NUL.L` é marcador de nulo** (2014). Vazio também é nulo — nunca zero.
6. **2024 não publica coluna de total.** Fica nulo; as etapas continuam.
7. **Códigos de RA 34/35 da SEEDF estão invertidos** em relação à numeração
   oficial (RA XXXIV = Arapoanga), e o NOME passou a vir trocado em 2025. Por
   isso a RA de cada escola vem da COORDENADA, por point-in-polygon contra a
   malha oficial — a mesma técnica da saúde. Ver `_resolve_locations`.
"""

from __future__ import annotations

import csv
import gzip
import io
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from shapely.geometry import Point

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

log = logging.getLogger("ingestion.education")

CKAN_API = "https://data.se.df.gov.br/api/3/action/package_show"
SCHOOLS_DATASET = "relacao-de-unidades-escolares-abrangendo-todas-as-redes-de-ensino-do-distrito-federal"
ENROLLMENT_DATASET = "quantidade-de-matriculas-das-modalidades-de-ensino-abrangendo-todas-as-redes-de-ensino-do-df"

# Caixa que envolve o DF com folga. Coordenada fora disso é erro de cadastro
# (lat/lon trocadas, sinal perdido), não escola fora do DF.
DF_BBOX = (-16.10, -48.35, -15.45, -47.25)  # (lat_min, lon_min, lat_max, lon_max)

# Mesma lógica da saúde: coordenada EXATA repetida por muitas escolas distintas
# é valor de preenchimento, não endereço. Escolas vizinhas de verdade (mesmo
# prédio, turnos diferentes) raramente passam de 3 ou 4.
PLACEHOLDER_MIN_SHARED = 10


# --------------------------------------------------------------------------- #
# Esquema: nome canônico -> nomes aceitos (já normalizados por `norm`)
# --------------------------------------------------------------------------- #
COMMON_COLUMNS: dict[str, tuple[str, ...]] = {
    "year": ("NU_ANO_CENSO", "ANO DO CENSO"),
    "network_code": ("CO_REDE", "REDE"),
    "network_name": ("NO_REDE", "NOME REDE"),
    "ra_code": ("CO_RA", "RA"),
    "ra_name": ("NO_RA", "NOME RA"),
    "location": ("LOCALIZACAO",),
    "school_code": ("CO_ENTIDADE", "CODIGO INEP"),
    "school_name": ("NO_ENTIDADE", "NOME DA ESCOLA"),
}
OPTIONAL_COMMON = {"location"}

GEO_COLUMNS: dict[str, tuple[str, ...]] = {
    "latitude": ("NU_LATITUDE", "LATITUDE"),
    "longitude": ("NU_LONGITUDE", "LONGITUDE"),
    "neighborhood": ("NO_BAIRRO",),
}

ENROLLMENT_COLUMNS: dict[str, tuple[str, ...]] = {
    "total_published": ("MATRICULA", "TOTAL GERAL (MATRICULAS DE ESCOLARIZACAO)"),
    "daycare": ("MAT_CRECHE", "EDUCACAO INFANTIL - CRECHE"),
    "preschool": ("MAT_PRE", "EDUCACAO INFANTIL - PRE-ESCOLA"),
    "elementary": ("ESC_EF_TOTAL", "MAT_EF_TOTAL", "ENSINO FUNDAMENTAL - TOTAL"),
    "high_school": ("MAT_EM_TOTAL", "ENSINO MEDIO - TOTAL (EM EMM)", "ENSINO MEDIO - TOTAL"),
    "integrated_high_school": ("MAT_EMI", "ENSINO MEDIO INTEGRADO (EMI) - TOTAL"),
    "professional": ("MAT_EP_TOTAL", "EDUCACAO PROFISSIONAL - TOTAL (EMI CT FIC EJAI EAD)"),
    "youth_adult": ("MAT_EJA_TOTAL", "EJA - TOTAL ( EF EM EAD )"),
    "special_exclusive": ("MAT_EE_CE", "EDUCACAO ESPECIAL - CLASSE EXCLUSIVA"),
    "special_total": ("MAT_EE_TOTAL", "EDUCACAO ESPECIAL - TOTAL"),
}
# 2024 não tem coluna de total. Qualquer outra ausência é mudança de contrato.
OPTIONAL_ENROLLMENT = {"total_published"}
STAGE_FIELDS = [k for k in ENROLLMENT_COLUMNS if k != "total_published"]

NULL_MARKERS = {"", "NUL.L", "NULL", "-", "..."}
_PLAIN_INT = re.compile(r"^\d+$")
_THOUSANDS_INT = re.compile(r"^\d{1,3}([.,]\d{3})+$")


# --------------------------------------------------------------------------- #
# Parsing puro (testado em tests/test_education_parser.py)
# --------------------------------------------------------------------------- #
def norm(text: str) -> str:
    """Normaliza um nome de coluna ou de RA: sem acento, maiúsculo, `/` vira
    espaço e espaços repetidos colapsam. `'Ensino médio - TOTAL  (EM/EMM)'` →
    `'ENSINO MEDIO - TOTAL (EM EMM)'`."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return " ".join(text.upper().replace("/", " ").split())


def parse_count(value: str | None) -> int | None:
    """Contagem inteira ou nulo. Nunca adivinha.

    `"2,657"` e `"2.657"` → 2657 (milhar bem formado). `"12.5"` ou `"1,2"` não
    são contagens: levantam erro, porque aceitá-los exigiria escolher entre
    decimal e milhar — foi exatamente essa escolha que fez `12.0` virar `120` no
    parser da SSP.
    """
    text = (value or "").strip()
    if text.upper() in NULL_MARKERS:
        return None
    if _PLAIN_INT.match(text):
        return int(text)
    if _THOUSANDS_INT.match(text):
        return int(re.sub(r"[.,]", "", text))
    raise ValueError(f"contagem inválida: {value!r}")


def parse_coordinate(value: str | None) -> float | None:
    text = (value or "").strip().replace(",", ".")
    if text.upper() in NULL_MARKERS:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return None if number == 0 else number


def inside_df_bbox(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    lat_min, lon_min, lat_max, lon_max = DF_BBOX
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def read_table(text: str) -> tuple[list[str], list[list[str]]]:
    """Devolve (cabeçalho normalizado, linhas de dados).

    O cabeçalho é a primeira linha, entre as 5 primeiras, que contém a coluna de
    ano. Isso descarta a linha-banner de 2025 sem depender de posição fixa.
    """
    sample = text[:5000]
    delimiter = max(",;\t", key=sample.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    year_names = set(COMMON_COLUMNS["year"])
    for index, row in enumerate(rows[:5]):
        header = [norm(cell) for cell in row]
        if year_names & set(header):
            data = [r for r in rows[index + 1 :] if any(cell.strip() for cell in r)]
            return header, data
    raise ValueError("cabeçalho com a coluna de ano não encontrado nas 5 primeiras linhas")


def locate_columns(
    header: list[str], spec: dict[str, tuple[str, ...]], optional: set[str]
) -> dict[str, int | None]:
    """Mapeia nome canônico -> índice, pelo primeiro alias presente."""
    located: dict[str, int | None] = {}
    missing = []
    for canonical, aliases in spec.items():
        index = next((header.index(alias) for alias in aliases if alias in header), None)
        if index is None and canonical not in optional:
            missing.append(f"{canonical} ({' | '.join(aliases)})")
        located[canonical] = index
    if missing:
        raise ValueError("colunas obrigatórias ausentes: " + "; ".join(missing))
    return located


def _cell(row: list[str], index: int | None) -> str | None:
    if index is None or index >= len(row):
        return None
    return row[index].strip()


def file_year(rows: list[list[str]], year_index: int) -> int:
    """O ano declarado DENTRO do arquivo. Um arquivo com dois anos é recusado."""
    years = {_cell(row, year_index) for row in rows} - {None, ""}
    if len(years) != 1:
        raise ValueError(f"arquivo deveria conter um único ano de censo; contém {sorted(years)}")
    return int(years.pop())


@dataclass
class SchoolYear:
    """Uma escola em um ano, agregada a partir das linhas do arquivo."""

    year: int
    school_code: int
    network_code: int | None
    network_name: str | None
    ra_code: str | None
    ra_name: str | None
    location: str | None
    school_name: str | None
    neighborhood: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    counts: dict[str, int | None] = field(default_factory=dict)
    source_rows: int = 0
    conflicting_ra: bool = False


def parse_file(text: str, with_enrollment: bool) -> tuple[int, dict[int, SchoolYear]]:
    """Lê um arquivo de escolas ou de matrículas e devolve (ano, escolas).

    Com `with_enrollment`, as contagens das várias linhas da mesma escola
    (idade × sexo × cor/raça) são somadas. Uma etapa sem nenhum valor
    publicado para a escola fica nula; com pelo menos um valor, é a soma dos
    valores publicados.
    """
    header, rows = read_table(text)
    cols = locate_columns(header, COMMON_COLUMNS, OPTIONAL_COMMON)
    geo = locate_columns(header, GEO_COLUMNS, set(GEO_COLUMNS))
    counts_cols = (
        locate_columns(header, ENROLLMENT_COLUMNS, OPTIONAL_ENROLLMENT) if with_enrollment else {}
    )
    year = file_year(rows, cols["year"])

    schools: dict[int, SchoolYear] = {}
    for row in rows:
        code_text = _cell(row, cols["school_code"])
        if not code_text or not code_text.isdigit():
            continue
        code = int(code_text)
        ra_code = _cell(row, cols["ra_code"]) or None
        item = schools.get(code)
        if item is None:
            network = _cell(row, cols["network_code"])
            item = SchoolYear(
                year=year,
                school_code=code,
                network_code=int(network) if network and network.isdigit() else None,
                network_name=_cell(row, cols["network_name"]) or None,
                ra_code=ra_code,
                ra_name=" ".join((_cell(row, cols["ra_name"]) or "").split()) or None,
                location=_cell(row, cols["location"]) or None,
                school_name=_cell(row, cols["school_name"]) or None,
                neighborhood=_cell(row, geo["neighborhood"]) or None,
                latitude=parse_coordinate(_cell(row, geo["latitude"])),
                longitude=parse_coordinate(_cell(row, geo["longitude"])),
                counts={key: None for key in counts_cols},
            )
            schools[code] = item
        elif ra_code != item.ra_code:
            item.conflicting_ra = True

        item.source_rows += 1
        for key, index in counts_cols.items():
            value = parse_count(_cell(row, index))
            if value is not None:
                item.counts[key] = (item.counts[key] or 0) + value
    return year, schools


# --------------------------------------------------------------------------- #
# Localização: uma coordenada por escola, válida para todos os anos
# --------------------------------------------------------------------------- #
def best_coordinates(
    observations: list[tuple[int, int, float | None, float | None]],
) -> tuple[dict[int, tuple[float, float, int]], set[tuple[float, float]]]:
    """Escolhe a coordenada mais RECENTE e válida de cada escola.

    `observations` = (código INEP, ano, lat, lon), vindos dos dois conjuntos e
    de todos os anos. Escola não muda de endereço com o código INEP — e o
    arquivo de 2025 não traz coordenada —, então a coordenada de um ano vale
    para os demais. Coordenadas de preenchimento (repetidas por muitas escolas
    distintas) são descartadas.
    """
    schools_at: dict[tuple[float, float], set[int]] = defaultdict(set)
    for code, _year, lat, lon in observations:
        if inside_df_bbox(lat, lon):
            schools_at[(lat, lon)].add(code)
    placeholders = {coord for coord, codes in schools_at.items() if len(codes) >= PLACEHOLDER_MIN_SHARED}

    best: dict[int, tuple[float, float, int]] = {}
    for code, year, lat, lon in observations:
        if not inside_df_bbox(lat, lon) or (lat, lon) in placeholders:
            continue
        if code not in best or year > best[code][2]:
            best[code] = (lat, lon, year)
    return best, placeholders


def assign_region(lat: float, lon: float, codes, geometries, tree) -> str | None:
    point = Point(lon, lat)
    for index in tree.query(point):
        if geometries[index].covers(point):
            return codes[index]
    return None


# --------------------------------------------------------------------------- #
# Execução
# --------------------------------------------------------------------------- #
def _csv_resources(session: PoliteSession, dataset: str) -> list[dict]:
    package = get_json(session, f"{CKAN_API}?id={dataset}")["result"]
    resources = [
        resource
        for resource in package["resources"]
        if (resource.get("format") or "").upper() == "CSV"
        and "DICION" not in norm(resource.get("name") or "") + norm(resource["url"])
    ]
    if len(resources) < 10:
        raise ValueError(f"{dataset}: apenas {len(resources)} CSVs — o conjunto mudou")
    return resources


def _download_all(session, dataset: str, with_enrollment: bool, label: str):
    """Baixa e parseia todos os CSVs do conjunto. Um ano repetido é erro."""
    by_year: dict[int, tuple[dict[int, SchoolYear], str]] = {}
    for resource in _csv_resources(session, dataset):
        url = resource["url"]
        response = session.get(url)
        response.raise_for_status()
        year, schools = parse_file(decode(response.content), with_enrollment)
        save_raw("education", f"{label}_{year}.csv.gz", gzip.compress(response.content))
        if year in by_year:
            raise ValueError(f"{label}: dois arquivos declaram o ano {year} ({by_year[year][1]} e {url})")
        by_year[year] = (schools, url)
        log.info("%s %s: %s escolas (%s)", label, year, len(schools), url.rsplit("/", 1)[-1])
    return by_year


def run() -> None:
    cfg = settings()
    session = PoliteSession(cfg.user_agent, cfg.throttle_seconds)
    conn = connect()
    region_codes, geometries, tree = load_region_index(conn)

    with ingestion_run(conn, "education") as (run_id, tracker):
        registry = _download_all(session, SCHOOLS_DATASET, with_enrollment=False, label="escolas")
        enrollment = _download_all(session, ENROLLMENT_DATASET, with_enrollment=True, label="matriculas")

        # --- Escolas (cadastro) -------------------------------------------------
        school_rows = []
        conflicts = 0
        for year, (schools, url) in sorted(registry.items()):
            for item in schools.values():
                conflicts += item.conflicting_ra
                school_rows.append(
                    (
                        year, item.school_code, item.network_code, item.network_name,
                        item.ra_code, item.ra_name, item.location, item.school_name,
                        item.neighborhood, item.latitude, item.longitude, url,
                    )
                )
        tracker["rows"] += upsert(
            conn,
            "raw.education_school",
            [
                "census_year", "school_code", "network_code", "network_name",
                "declared_ra_code", "declared_ra_name", "location_type", "school_name",
                "neighborhood", "latitude", "longitude", "_source_url",
            ],
            school_rows,
            conflict_columns=["census_year", "school_code"],
        )

        # --- Matrículas, agregadas por escola × ano ---------------------------
        enrollment_rows = []
        for year, (schools, url) in sorted(enrollment.items()):
            for item in schools.values():
                conflicts += item.conflicting_ra
                enrollment_rows.append(
                    (
                        year, item.school_code, item.network_code, item.ra_code, item.ra_name,
                        item.school_name, *[item.counts.get(key) for key in ENROLLMENT_COLUMNS],
                        item.source_rows, url,
                    )
                )
        tracker["rows"] += upsert(
            conn,
            "raw.education_enrollment",
            [
                "census_year", "school_code", "network_code", "declared_ra_code",
                "declared_ra_name", "school_name", *ENROLLMENT_COLUMNS, "source_rows", "_source_url",
            ],
            enrollment_rows,
            conflict_columns=["census_year", "school_code"],
        )
        record_check(
            conn, run_id, "education.single_ra_per_school_file", passed=conflicts == 0,
            severity="WARN", observed=conflicts, expected="0 escolas com duas RAs no mesmo arquivo",
        )

        # --- Cobertura do arquivo de matrículas contra o cadastro -------------
        coverage = {}
        for year, (schools, _url) in registry.items():
            enrolled = set(enrollment.get(year, ({}, ""))[0])
            coverage[year] = round(len(enrolled & set(schools)) / max(len(schools), 1), 3)
        log.info("Cobertura das matrículas sobre o cadastro, por ano: %s", coverage)
        record_check(
            conn, run_id, "education.enrollment_file_coverage",
            passed=all(value >= 0.9 for value in coverage.values()), severity="WARN",
            observed=coverage, expected=">= 90% das escolas do cadastro presentes no arquivo de matrículas",
        )

        # --- Localização: coordenada -> RA oficial ----------------------------
        observations = [
            (item.school_code, year, item.latitude, item.longitude)
            for dataset in (registry, enrollment)
            for year, (schools, _url) in dataset.items()
            for item in schools.values()
        ]
        best, placeholders = best_coordinates(observations)
        if placeholders:
            log.info("Coordenadas de preenchimento descartadas: %s", sorted(placeholders))

        all_codes = {obs[0] for obs in observations}
        location_rows = []
        quality: Counter[str] = Counter()
        for code in sorted(all_codes):
            if code in best:
                lat, lon, coordinate_year = best[code]
                ra_code = assign_region(lat, lon, region_codes, geometries, tree)
                status = "OK" if ra_code else "OUTSIDE_DF"
            else:
                lat = lon = coordinate_year = ra_code = None
                status = "MISSING"
            quality[status] += 1
            location_rows.append((code, lat, lon, coordinate_year, ra_code, status, SCHOOLS_DATASET))

        tracker["rows"] += upsert(
            conn,
            "raw.education_school_location",
            ["school_code", "latitude", "longitude", "coordinate_year", "ra_code", "geocode_quality", "_source_url"],
            location_rows,
            conflict_columns=["school_code"],
        )
        log.info("Localização das %s escolas: %s", len(all_codes), dict(quality))
        record_check(
            conn, run_id, "education.geocode_coverage",
            passed=quality["OK"] >= 0.9 * len(all_codes), severity="WARN",
            observed=dict(quality), expected=">= 90% das escolas com RA pela coordenada",
        )
        tracker["requests"] = session.requests_made

    conn.close()


if __name__ == "__main__":
    from .common import configure_logging

    configure_logging()
    run()
