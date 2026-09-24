"""DF Intelligence — API.

Camada de leitura sobre o schema `marts`. Não calcula indicador: devolve o que
o dbt materializou e testou, com os metadados que impedem leitura errada
(período de referência, cobertura, fonte e ressalva).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .schemas import (
    Coverage,
    EducationCoverage,
    EducationYear,
    BikewayYear,
    MobilityRegion,
    MobilityStation,
    GeoJSONFeatureCollection,
    HealthFacility,
    HealthSummary,
    Indicator,
    Insight,
    Overview,
    PipelineStatus,
    PopulationPoint,
    Region,
    RegionIndicators,
    SecurityPoint,
    Source,
    WeatherPoint,
)

DESCRIPTION = """
Camada analítica sobre dados públicos do Distrito Federal.

**Fontes**: IBGE (população e malha de subdistritos), IBRAM/ONDA-DF (limites das
Regiões Administrativas), SSP-DF (balanço criminal mensal por RA), CNES/Ministério
da Saúde (estabelecimentos de saúde), SEEDF/Educacenso (escolas e matrículas), IDE-DF
(malha cicloviária, metrô e terminais) e Open-Meteo/ERA5 (clima).

### Três coisas para saber antes de consumir

1. **O DF é um único município IBGE.** Bases federais de saúde e economia param
   no código `5300108`. Só existe granularidade de Região Administrativa em três
   lugares: subdistritos do IBGE, balanço criminal da SSP-DF e qualquer base com
   coordenada geográfica.

2. **Cobertura é irregular e está exposta.** O endpoint `/api/coverage` diz, por
   região e por domínio, o que existe e o que falta. Lacuna nunca vira zero.

3. **Clima não é fonte governamental do DF.** É reanálise ERA5 interpolada, não
   medição de estação do INMET.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_pool()
    yield
    db.close_pool()


app = FastAPI(
    title="DF Intelligence API",
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Regiões", "description": "Regiões Administrativas e seus indicadores."},
        {"name": "População", "description": "Censos 2010/2022 por RA e série anual do DF."},
        {"name": "Segurança", "description": "Balanço criminal mensal da SSP-DF."},
        {"name": "Saúde", "description": "Rede instalada do CNES. Infraestrutura, não produção."},
        {"name": "Clima", "description": "Série climática por RA (Open-Meteo/ERA5)."},
        {"name": "Análise", "description": "Insights calculados, catálogo de indicadores e fontes."},
        {"name": "Transparência", "description": "Cobertura dos dados e estado do pipeline."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("API_CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Infra
# --------------------------------------------------------------------------- #
@app.get("/api/health-check", tags=["Transparência"], summary="Liveness da API")
def health_check() -> dict:
    """Checagem de vida usada pelo Docker. Não confundir com `/api/health`,
    que serve os dados de saúde do DF."""
    if not db.ping():
        raise HTTPException(status_code=503, detail="Banco indisponível")
    return {"status": "ok"}


@app.get("/api/overview", response_model=Overview, tags=["Análise"], summary="KPIs do dashboard")
def overview() -> dict:
    population = db.fetch_one(
        "select reference_year, population from marts.fct_population_df "
        "order by reference_year desc limit 1"
    )
    census_years = db.fetch_one(
        "select max(reference_year) as last_census from marts.fct_population"
    )
    regions = db.fetch_one(
        "select count(*) as total, count(*) filter (where has_all_domains) as complete "
        "from marts.mart_data_coverage"
    )
    security = db.fetch_one("select max(reference_month_start) as last_month from marts.fct_security_monthly")
    weather = db.fetch_one("select max(observed_on) as last_day from marts.fct_weather_daily")
    pipeline = db.fetch_one("select max(finished_at) as last_run from marts.mart_pipeline_status")
    sources = db.fetch_one(
        "select count(*) as total, count(*) filter (where is_df_government) as government "
        "from marts.dim_source"
    )
    indicators = _indicator_catalog()

    last_census = (census_years or {}).get("last_census")
    return {
        "population_df_latest": population["population"],
        "population_df_latest_year": population["reference_year"],
        # Depois do último Censo, a série do IBGE é projeção.
        "population_df_is_projection": bool(
            last_census and population["reference_year"] > last_census
        ),
        "regions_total": regions["total"],
        "regions_with_all_domains": regions["complete"],
        "indicators_monitored": len(indicators),
        "security_last_month": security["last_month"],
        "weather_last_day": weather["last_day"],
        "data_last_updated_at": pipeline["last_run"],
        "sources_total": sources["total"],
        "government_sources_total": sources["government"],
    }


# --------------------------------------------------------------------------- #
# Regiões
# --------------------------------------------------------------------------- #
@app.get("/api/regions", response_model=list[Region], tags=["Regiões"], summary="Lista as 35 RAs")
def list_regions() -> list[dict]:
    return db.fetch_all(
        """
        select region_id, region_number, region_name, area_km2,
               centroid_lat, centroid_lon, population_2022,
               density_2022_per_km2, monograph_url
        from marts.dim_region
        order by region_number
        """
    )


@app.get(
    "/api/regions/geojson",
    response_model=GeoJSONFeatureCollection,
    tags=["Regiões"],
    summary="Malha das RAs em GeoJSON",
)
def regions_geojson() -> dict:
    """Geometria oficial das RAs com os indicadores de topo em `properties` —
    o mapa do frontend é desenhado direto daqui, sem segunda requisição."""
    rows = db.fetch_all(
        """
        select
            dim.region_id, dim.region_name, dim.region_number, dim.geometry,
            dim.area_km2, dim.population_2022, dim.density_2022_per_km2,
            overview.crimes_per_10k, overview.security_reference_year,
            overview.health_facilities, overview.temp_mean_c
        from marts.dim_region as dim
        left join marts.mart_region_overview as overview using (region_id)
        order by dim.region_number
        """
    )
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": row["region_id"],
                "geometry": row.pop("geometry"),
                "properties": row,
            }
            for row in rows
        ],
    }


@app.get(
    "/api/regions/{region_id}",
    response_model=Region,
    tags=["Regiões"],
    summary="Detalhe de uma RA",
)
def get_region(region_id: str = Path(description="Código da RA, ex.: `RA-IX`.")) -> dict:
    row = db.fetch_one(
        """
        select region_id, region_number, region_name, area_km2,
               centroid_lat, centroid_lon, population_2022,
               density_2022_per_km2, monograph_url
        from marts.dim_region where region_id = %s
        """,
        (region_id.upper(),),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Região {region_id!r} não encontrada")
    return row


@app.get(
    "/api/regions/{region_id}/indicators",
    response_model=RegionIndicators,
    tags=["Regiões"],
    summary="Todos os indicadores de uma RA",
)
def get_region_indicators(region_id: str) -> dict:
    row = db.fetch_one(
        "select * from marts.mart_region_overview where region_id = %s",
        (region_id.upper(),),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Região {region_id!r} não encontrada")
    return row


@app.get(
    "/api/indicators",
    response_model=list[RegionIndicators],
    tags=["Análise"],
    summary="Indicadores de todas as RAs",
)
def list_indicators(
    order_by: str = Query(
        "region_number",
        description="Coluna de ordenação. Use `crimes_per_10k`, `population_2022`, `density_2022_per_km2`…",
    ),
    descending: bool = Query(False),
) -> list[dict]:
    allowed = _overview_columns()
    if order_by not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"order_by inválido. Colunas disponíveis: {sorted(allowed)}",
        )
    direction = "desc nulls last" if descending else "asc nulls last"
    return db.fetch_all(f"select * from marts.mart_region_overview order by {order_by} {direction}")


# --------------------------------------------------------------------------- #
# População
# --------------------------------------------------------------------------- #
@app.get(
    "/api/population",
    response_model=list[PopulationPoint],
    tags=["População"],
    summary="População por RA ou série do DF",
)
def get_population(
    region_id: str | None = Query(None, description="Filtra por RA."),
    scope: str = Query(
        "region",
        description=(
            "`region` devolve os Censos 2010/2022 por RA. `df` devolve a série "
            "anual estimada do Distrito Federal inteiro."
        ),
    ),
) -> list[dict]:
    if scope == "df":
        return db.fetch_all(
            """
            select null::text as region_id, null::text as region_name,
                   reference_year, population, null::numeric as density_per_km2,
                   change_pct_since_previous, years_since_previous, source_id
            from marts.fct_population_df order by reference_year
            """
        )
    if scope != "region":
        raise HTTPException(status_code=400, detail="scope deve ser 'region' ou 'df'")

    sql = """
        select facts.region_id, dim.region_name, facts.reference_year, facts.population,
               facts.density_per_km2, null::numeric as change_pct_since_previous,
               null::int as years_since_previous, facts.source_id
        from marts.fct_population as facts
        join marts.dim_region as dim using (region_id)
        {where}
        order by dim.region_number, facts.reference_year
    """
    if region_id:
        return db.fetch_all(sql.format(where="where facts.region_id = %s"), (region_id.upper(),))
    return db.fetch_all(sql.format(where=""))


# --------------------------------------------------------------------------- #
# Segurança
# --------------------------------------------------------------------------- #
@app.get(
    "/api/security",
    response_model=list[SecurityPoint],
    tags=["Segurança"],
    summary="Série mensal de ocorrências",
)
def get_security(
    region_id: str | None = Query(None),
    category_code: str | None = Query(None, description="`CVLI`, `CCP`, `OUTROS` ou `PRODUTIVIDADE`."),
    metric_type: str | None = Query(
        None,
        description="`CRIME` ou `POLICE_ACTIVITY`. Somar os dois produz um total sem significado.",
    ),
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
    limit: int = Query(5000, le=50000),
) -> list[dict]:
    conditions: list[str] = []
    params: list = []
    if region_id:
        conditions.append("region_id = %s")
        params.append(region_id.upper())
    if category_code:
        conditions.append("category_code = %s")
        params.append(category_code.upper())
    if metric_type:
        conditions.append("metric_type = %s")
        params.append(metric_type.upper())
    if year_from:
        conditions.append("reference_year >= %s")
        params.append(year_from)
    if year_to:
        conditions.append("reference_year <= %s")
        params.append(year_to)

    where = f"where {' and '.join(conditions)}" if conditions else ""
    params.append(limit)
    return db.fetch_all(
        f"""
        select region_id, region_name, reference_month_start, reference_year,
               reference_month, category_code, category_name, metric_type,
               occurrences, violent_occurrences, occurrences_per_10k
        from marts.mart_security_region_monthly
        {where}
        order by reference_month_start, region_id, category_code
        limit %s
        """,
        params,
    )


@app.get(
    "/api/security/summary",
    response_model=list[SecurityPoint],
    tags=["Segurança"],
    summary="Série mensal agregada (DF inteiro ou uma RA)",
)
def get_security_summary(
    region_id: str | None = Query(None, description="Omitido, agrega todas as RAs."),
    year_from: int | None = Query(None),
) -> list[dict]:
    """Soma por mês e categoria, para o gráfico temporal do dashboard.

    Agregar no banco evita mandar dezenas de milhares de linhas para o
    navegador só para ele somar.

    `region_id` nulo agrega o DF inteiro — mas note que a cobertura da SSP-DF
    varia entre RAs e anos, então o total do DF reflete quem publicou naquele
    mês. Use `/api/coverage` para saber quem está faltando.
    """
    conditions: list[str] = []
    params: list = []
    if region_id:
        conditions.append("region_id = %s")
        params.append(region_id.upper())
    if year_from:
        conditions.append("reference_year >= %s")
        params.append(year_from)
    where = f"where {' and '.join(conditions)}" if conditions else ""

    return db.fetch_all(
        f"""
        select
            coalesce(%s, 'DF')            as region_id,
            null::text                    as region_name,
            reference_month_start,
            reference_year,
            reference_month,
            category_code,
            max(category_name)            as category_name,
            max(metric_type)              as metric_type,
            sum(occurrences)::int         as occurrences,
            sum(violent_occurrences)::int as violent_occurrences,
            null::numeric                 as occurrences_per_10k
        from marts.mart_security_region_monthly
        {where}
        group by reference_month_start, reference_year, reference_month, category_code
        order by reference_month_start, category_code
        """,
        [region_id.upper() if region_id else None, *params],
    )


# --------------------------------------------------------------------------- #
# Saúde
# --------------------------------------------------------------------------- #
@app.get(
    "/api/health",
    response_model=list[HealthSummary],
    tags=["Saúde"],
    summary="Rede de saúde instalada por RA",
)
def get_health(region_id: str | None = Query(None)) -> list[dict]:
    """Infraestrutura cadastrada no CNES, **não** produção de atendimentos.

    A linha com `region_id` nulo agrupa os estabelecimentos cuja RA não foi
    possível determinar — eles não são distribuídos entre as demais regiões.
    """
    sql = """
        select
            summary.region_id, dim.region_name, summary.facilities_total,
            summary.facilities_public, summary.facilities_private, summary.facilities_sus_ambulatory,
            summary.facilities_hospital, summary.facilities_ambulatory, summary.facilities_support, summary.facilities_nonprofit, summary.facilities_urgent_care, summary.facilities_diagnostics,
            summary.facilities_with_surgery_center, summary.facilities_with_obstetric_center,
            summary.assigned_by_coordinates, summary.assigned_by_neighborhood,
            case when dim.population_2022 > 0
                 then round(10000.0 * summary.facilities_total / dim.population_2022, 2)
            end as facilities_per_10k
        from marts.mart_health_region as summary
        left join marts.dim_region as dim on dim.region_id = summary.region_id
        {where}
        order by summary.facilities_total desc
    """
    if region_id:
        return db.fetch_all(sql.format(where="where summary.region_id = %s"), (region_id.upper(),))
    return db.fetch_all(sql.format(where=""))


@app.get(
    "/api/health/facilities",
    response_model=list[HealthFacility],
    tags=["Saúde"],
    summary="Estabelecimentos individuais do CNES",
)
def get_health_facilities(
    region_id: str | None = Query(None),
    service_group: str | None = Query(None, description="`HOSPITALAR`, `AMBULATORIAL`, `APOIO E GESTÃO`."),
    only_sus: bool = Query(False),
    limit: int = Query(500, le=5000),
) -> list[dict]:
    conditions: list[str] = []
    params: list = []
    if region_id:
        conditions.append("region_id = %s")
        params.append(region_id.upper())
    if service_group:
        conditions.append("service_group = %s")
        params.append(service_group.upper())
    if only_sus:
        conditions.append("serves_sus_ambulatory is true")
    where = f"where {' and '.join(conditions)}" if conditions else ""
    params.append(limit)
    return db.fetch_all(
        f"""
        select cnes_code, facility_name, region_id, region_name, unit_type_name,
               service_group, sector, serves_sus_ambulatory, latitude, longitude, region_assignment
        from marts.fct_health_facility
        {where}
        order by service_group, facility_name
        limit %s
        """,
        params,
    )


# --------------------------------------------------------------------------- #
# Educação
# --------------------------------------------------------------------------- #
@app.get(
    "/api/education",
    response_model=list[EducationYear],
    tags=["Educação"],
    summary="Escolas e matrículas por ano",
)
def get_education(
    region_id: str | None = Query(None, description="Sem RA, devolve a série do DF inteiro."),
) -> list[dict]:
    """Série anual do Censo Escolar (todas as redes).

    Matrícula é contada **onde a escola fica**, não onde o aluno mora. Anos com
    arquivo de matrículas incompleto vêm com `is_year_complete = false` e
    matrículas nulas — lacuna, não zero.
    """
    sql = """
        select yearly.*, dim.region_name
        from marts.mart_education_yearly as yearly
        left join marts.dim_region as dim on dim.region_id = yearly.region_id
        where {where}
        order by yearly.census_year
    """
    if region_id:
        return db.fetch_all(sql.format(where="yearly.scope = 'RA' and yearly.region_id = %s"), (region_id.upper(),))
    return db.fetch_all(sql.format(where="yearly.scope = 'DF'"))


@app.get(
    "/api/education/coverage",
    response_model=list[EducationCoverage],
    tags=["Transparência"],
    summary="Completude do arquivo de matrículas por ano e rede",
)
def get_education_coverage() -> list[dict]:
    return db.fetch_all("select * from marts.mart_education_coverage order by census_year, sector")


# --------------------------------------------------------------------------- #
# Mobilidade
# --------------------------------------------------------------------------- #
@app.get(
    "/api/mobility",
    response_model=list[MobilityRegion],
    tags=["Mobilidade"],
    summary="Malha cicloviária, metrô e terminais por RA",
)
def get_mobility(region_id: str | None = Query(None)) -> list[dict]:
    """Infraestrutura instalada, com o km de cada trecho recortado pela divisa
    das RAs. Mede presença e extensão, não qualidade nem uso."""
    sql = """
        select mobility.*, dim.region_name
        from marts.mart_mobility_region as mobility
        left join marts.dim_region as dim on dim.region_id = mobility.region_id
        {where}
        order by mobility.bikeway_km desc
    """
    if region_id:
        return db.fetch_all(sql.format(where="where mobility.region_id = %s"), (region_id.upper(),))
    return db.fetch_all(sql.format(where=""))


@app.get(
    "/api/mobility/bikeways/yearly",
    response_model=list[BikewayYear],
    tags=["Mobilidade"],
    summary="Malha cicloviária atual por ano de construção",
)
def get_bikeway_yearly(
    region_id: str | None = Query(None, description="Sem RA, devolve o DF inteiro."),
) -> list[dict]:
    """Km dos trechos que existem hoje, por ano de construção. **Não** é a
    malha histórica: trechos removidos não aparecem na fonte."""
    if region_id:
        return db.fetch_all(
            "select * from marts.mart_mobility_bikeway_yearly "
            "where scope = 'RA' and region_id = %s order by construction_year",
            (region_id.upper(),),
        )
    return db.fetch_all(
        "select * from marts.mart_mobility_bikeway_yearly where scope = 'DF' order by construction_year"
    )


@app.get(
    "/api/mobility/stations",
    response_model=list[MobilityStation],
    tags=["Mobilidade"],
    summary="Estações de metrô e terminais de ônibus",
)
def get_mobility_stations(region_id: str | None = Query(None)) -> list[dict]:
    sql = """
        select station_kind, station_name, status, is_operating, latitude, longitude, region_id, region_name
        from marts.fct_mobility_station
        {where}
        order by station_kind, station_name
    """
    if region_id:
        return db.fetch_all(sql.format(where="where region_id = %s"), (region_id.upper(),))
    return db.fetch_all(sql.format(where=""))


# --------------------------------------------------------------------------- #
# Clima
# --------------------------------------------------------------------------- #
@app.get(
    "/api/weather",
    response_model=list[WeatherPoint],
    tags=["Clima"],
    summary="Série climática mensal por RA",
)
def get_weather(
    region_id: str | None = Query(None),
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
    limit: int = Query(2000, le=20000),
) -> list[dict]:
    """Fonte NÃO governamental do DF: reanálise ERA5 via Open-Meteo.

    `regions_sharing_cell > 1` significa que a série é idêntica à de outras RAs
    — elas caem na mesma célula de amostragem do modelo.
    """
    conditions: list[str] = []
    params: list = []
    if region_id:
        conditions.append("region_id = %s")
        params.append(region_id.upper())
    if year_from:
        conditions.append("reference_year >= %s")
        params.append(year_from)
    if year_to:
        conditions.append("reference_year <= %s")
        params.append(year_to)
    where = f"where {' and '.join(conditions)}" if conditions else ""
    params.append(limit)
    return db.fetch_all(
        f"""
        select region_id, reference_year, reference_month, reference_month_start,
               days_observed, temp_mean_c, temp_max_avg_c, temp_min_avg_c,
               temp_max_absolute_c, temp_min_absolute_c, precipitation_mm,
               rainy_days, humidity_mean_pct, regions_sharing_cell
        from marts.mart_weather_region_monthly
        {where}
        order by reference_month_start, region_id
        limit %s
        """,
        params,
    )


@app.get(
    "/api/weather/summary",
    response_model=list[WeatherPoint],
    tags=["Clima"],
    summary="Série climática média do DF",
)
def get_weather_summary(year_from: int | None = Query(None)) -> list[dict]:
    """Média das 35 RAs por mês. Como o ERA5 tem resolução menor que uma RA, a
    média do DF é o recorte com significado físico mais claro."""
    where = "where reference_year >= %s" if year_from else ""
    params = [year_from] if year_from else []
    return db.fetch_all(
        f"""
        select
            'DF'                                  as region_id,
            reference_year,
            reference_month,
            reference_month_start,
            round(avg(days_observed))::int        as days_observed,
            round(avg(temp_mean_c), 1)            as temp_mean_c,
            round(avg(temp_max_avg_c), 1)         as temp_max_avg_c,
            round(avg(temp_min_avg_c), 1)         as temp_min_avg_c,
            round(max(temp_max_absolute_c), 1)    as temp_max_absolute_c,
            round(min(temp_min_absolute_c), 1)    as temp_min_absolute_c,
            round(avg(precipitation_mm), 1)       as precipitation_mm,
            round(avg(rainy_days))::int           as rainy_days,
            round(avg(humidity_mean_pct), 1)      as humidity_mean_pct,
            null::int                             as regions_sharing_cell
        from marts.mart_weather_region_monthly
        {where}
        group by reference_year, reference_month, reference_month_start
        order by reference_month_start
        """,
        params,
    )


# --------------------------------------------------------------------------- #
# Análise e transparência
# --------------------------------------------------------------------------- #
@app.get("/api/insights", response_model=list[Insight], tags=["Análise"], summary="Insights calculados")
def get_insights(domain: str | None = Query(None)) -> list[dict]:
    """Achados derivados dos dados, cada um com período, método, fonte e ressalva.

    Nenhum texto é redigido à mão: se o dado mudar, o texto muda; se o dado
    sumir, o insight some.
    """
    if domain:
        return db.fetch_all(
            "select * from marts.mart_insights where domain = %s order by insight_id", (domain,)
        )
    return db.fetch_all("select * from marts.mart_insights order by domain, insight_id")


@app.get("/api/sources", response_model=list[Source], tags=["Análise"], summary="Catálogo de fontes")
def get_sources() -> list[dict]:
    return db.fetch_all("select * from marts.dim_source order by domain, source_id")


@app.get("/api/coverage", response_model=list[Coverage], tags=["Transparência"], summary="Cobertura dos dados")
def get_coverage() -> list[dict]:
    """O que existe e o que falta, por região e domínio. Lacuna nunca vira zero."""
    return db.fetch_all(
        "select * from marts.mart_data_coverage order by region_id"
    )


@app.get(
    "/api/pipeline",
    response_model=list[PipelineStatus],
    tags=["Transparência"],
    summary="Estado da última ingestão",
)
def get_pipeline_status() -> list[dict]:
    return db.fetch_all("select * from marts.mart_pipeline_status order by source_key")


@app.get(
    "/api/indicators/catalog",
    response_model=list[Indicator],
    tags=["Análise"],
    summary="O que cada indicador mede",
)
def get_indicator_catalog() -> list[dict]:
    return _indicator_catalog()


# --------------------------------------------------------------------------- #
# Auxiliares
# --------------------------------------------------------------------------- #
def _overview_columns() -> set[str]:
    rows = db.fetch_all(
        "select column_name from information_schema.columns "
        "where table_schema = 'marts' and table_name = 'mart_region_overview'"
    )
    return {row["column_name"] for row in rows}


def _indicator_catalog() -> list[dict]:
    """Catálogo declarativo do que o produto monitora.

    Fica no código, e não no banco, porque descreve a intenção analítica do
    projeto — não é dado observado.
    """
    return [
        {
            "indicator_id": "population_total",
            "domain": "population",
            "name": "População residente",
            "unit": "pessoas",
            "granularity": "Região Administrativa (Censo) / DF (anual)",
            "source_id": "IBGE_CENSO_2022",
            "description": "População residente por RA nos Censos 2010 e 2022, e série anual estimada do DF.",
            "caveat": "Só o Censo mede população abaixo do município no DF. Não há série anual por RA.",
        },
        {
            "indicator_id": "population_density",
            "domain": "population",
            "name": "Densidade demográfica",
            "unit": "hab/km²",
            "granularity": "Região Administrativa",
            "source_id": "IBGE_CENSO_2022",
            "description": "População do Censo 2022 sobre a área geodésica do polígono oficial.",
            "caveat": "A área inclui zonas rurais e de preservação, o que reduz a densidade de RAs extensas.",
        },
        {
            "indicator_id": "population_growth",
            "domain": "population",
            "name": "Crescimento populacional 2010–2022",
            "unit": "%",
            "granularity": "Região Administrativa",
            "source_id": "IBGE_CENSO_2022",
            "description": "Variação intercensitária, total e anualizada.",
            "caveat": "Publicado apenas para RAs que existiam em 2010 e não cederam território depois.",
        },
        {
            "indicator_id": "security_crimes",
            "domain": "security",
            "name": "Crimes registrados",
            "unit": "ocorrências",
            "granularity": "Região Administrativa × mês × natureza",
            "source_id": "SSP_DF_BALANCO",
            "description": "Soma das naturezas classificadas como crime, excluindo produtividade policial.",
            "caveat": "Registros administrativos de ocorrência policial, sujeitos a subnotificação.",
        },
        {
            "indicator_id": "security_cvli",
            "domain": "security",
            "name": "Crimes Violentos Letais Intencionais",
            "unit": "ocorrências",
            "granularity": "Região Administrativa × mês",
            "source_id": "SSP_DF_BALANCO",
            "description": "Homicídio, latrocínio e lesão corporal seguida de morte.",
            "caveat": "Indicador menos sujeito a subnotificação, por envolver morte e perícia.",
        },
        {
            "indicator_id": "security_rate",
            "domain": "security",
            "name": "Ocorrências por 10 mil habitantes",
            "unit": "por 10 mil hab.",
            "granularity": "Região Administrativa",
            "source_id": "SSP_DF_BALANCO",
            "description": "Ocorrências normalizadas pela população do Censo 2022.",
            "caveat": "Regiões com grande fluxo de não residentes têm taxa inflada pelo denominador residente.",
        },
        {
            "indicator_id": "security_police_activity",
            "domain": "security",
            "name": "Produtividade policial",
            "unit": "ocorrências",
            "granularity": "Região Administrativa × mês",
            "source_id": "SSP_DF_BALANCO",
            "description": "Tráfico e uso de drogas, porte de arma e recuperação de veículos.",
            "caveat": "Mede atuação policial, não violência. Nunca é somado ao total de crimes.",
        },
        {
            "indicator_id": "health_facilities",
            "domain": "health",
            "name": "Estabelecimentos de saúde",
            "unit": "estabelecimentos",
            "granularity": "Região Administrativa",
            "source_id": "CNES_ESTABELECIMENTOS",
            "description": "Rede cadastrada no CNES, por tipo, esfera e atendimento ao SUS.",
            "caveat": "Infraestrutura instalada, não produção de atendimentos. Inclui consultórios privados.",
        },
        {
            "indicator_id": "health_facilities_rate",
            "domain": "health",
            "name": "Estabelecimentos por 10 mil habitantes",
            "unit": "por 10 mil hab.",
            "granularity": "Região Administrativa",
            "source_id": "CNES_ESTABELECIMENTOS",
            "description": "Oferta instalada normalizada pela população do Censo 2022.",
            "caveat": "Oferta na região não equivale a acesso da população da região.",
        },
        {
            "indicator_id": "education_schools",
            "domain": "education",
            "name": "Escolas",
            "unit": "escolas",
            "granularity": "Região Administrativa × ano",
            "source_id": "SEEDF_EDUCACENSO",
            "description": "Unidades escolares de todas as redes, localizadas na RA pela coordenada.",
            "caveat": "A RA vem da coordenada, não do código declarado pela SEEDF (invertido nas RAs 34 e 35).",
        },
        {
            "indicator_id": "education_enrollment",
            "domain": "education",
            "name": "Matrículas por etapa",
            "unit": "matrículas",
            "granularity": "Região Administrativa × ano",
            "source_id": "SEEDF_EDUCACENSO",
            "description": "Educação infantil, fundamental, médio (com integrado), profissional, EJA e especial.",
            "caveat": "Contadas onde a escola fica, não onde o aluno mora. Anos com arquivo incompleto ficam nulos; 2024 sem total.",
        },
        {
            "indicator_id": "mobility_bikeway",
            "domain": "mobility",
            "name": "Malha cicloviária",
            "unit": "km / km por 10 mil hab.",
            "granularity": "Região Administrativa",
            "source_id": "IDEDF_MOBILIDADE",
            "description": "Ciclovia, ciclofaixa e calçada compartilhada, com o trecho recortado pela divisa das RAs.",
            "caveat": "Retrato do presente. A série por ano de construção não é a malha histórica.",
        },
        {
            "indicator_id": "mobility_transit",
            "domain": "mobility",
            "name": "Estações de metrô e terminais de ônibus",
            "unit": "estações",
            "granularity": "Região Administrativa",
            "source_id": "IDEDF_MOBILIDADE",
            "description": "Estações de metrô em operação e terminais de ônibus ativos, localizados pela geometria.",
            "caveat": "Presença na RA não é acessibilidade a pé. Estações de BRT não entram (camada sem nome).",
        },
        {
            "indicator_id": "weather_temperature",
            "domain": "weather",
            "name": "Temperatura",
            "unit": "°C",
            "granularity": "Região Administrativa × dia",
            "source_id": "OPEN_METEO_ERA5",
            "description": "Máxima, mínima e média diárias, agregadas por mês.",
            "caveat": "Reanálise ERA5 interpolada. Fonte não governamental do DF.",
        },
        {
            "indicator_id": "weather_precipitation",
            "domain": "weather",
            "name": "Precipitação e dias de chuva",
            "unit": "mm / dias",
            "granularity": "Região Administrativa × dia",
            "source_id": "OPEN_METEO_ERA5",
            "description": "Acumulado mensal e contagem de dias com 1 mm ou mais.",
            "caveat": "Limiar de dia chuvoso segue a convenção da OMM (≥ 1,0 mm).",
        },
    ]
