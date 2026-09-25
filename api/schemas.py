"""Contratos de resposta da API.

Cada campo que pode enganar carrega o aviso no próprio schema — é o que aparece
na documentação automática do FastAPI e o que impede que alguém consuma
`crimes_total` sem saber de que ano ele é.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Region(BaseModel):
    region_id: str = Field(description="Código romano da RA, ex.: `RA-IX`.", examples=["RA-IX"])
    region_number: int = Field(description="Número da RA, de 1 a 35.")
    region_name: str = Field(description="Nome oficial na grafia do IBGE.")
    area_km2: float = Field(description="Área geodésica em km², calculada do polígono oficial.")
    centroid_lat: float
    centroid_lon: float
    population_2022: int | None = Field(
        description=(
            "População do Censo 2022. Nula para Arapoanga e Água Quente: o IBGE "
            "não publica esses subdistritos separadamente e conta a população "
            "deles dentro das RAs de origem."
        )
    )
    density_2022_per_km2: float | None = None
    monograph_url: str | None = Field(
        default=None, description="Monografia oficial da RA publicada pelo GDF."
    )


class RegionIndicators(BaseModel):
    region_id: str
    region_name: str
    area_km2: float
    centroid_lat: float
    centroid_lon: float

    population_2022: int | None
    population_2010: int | None
    density_2022_per_km2: float | None
    existed_in_2010: bool | None
    is_growth_comparable: bool | None = Field(
        description=(
            "Só quando `true` o crescimento populacional é publicado. RAs que "
            "cederam território a RAs criadas depois de 2010 têm comparação "
            "inválida entre os dois Censos."
        )
    )
    inferred_parent_region_id: str | None = Field(
        default=None,
        description=(
            "Para RAs criadas após 2010, a RA de origem inferida pela fronteira "
            "compartilhada mais longa. É heurística e serve apenas para excluir "
            "regiões de métricas de crescimento."
        ),
    )
    population_change_pct_2010_2022: float | None
    population_cagr_pct_2010_2022: float | None

    security_reference_year: int | None = Field(
        description="Último ano COMPLETO (12 meses) publicado pela SSP-DF para esta RA."
    )
    crimes_total: int | None
    cvli_total: int | None
    property_crimes_total: int | None
    violent_total: int | None
    police_activity_total: int | None = Field(
        description="Tráfico, porte de arma e recuperação de veículo. Mede atuação policial, não violência."
    )
    crimes_per_10k: float | None
    cvli_per_100k: float | None

    health_facilities: int
    health_facilities_public: int
    health_facilities_sus_ambulatory: int
    health_facilities_hospital: int
    health_facilities_per_10k: float | None

    education_reference_year: int | None = Field(
        default=None,
        description="Último ano do Censo Escolar com arquivo de matrículas completo e total publicado.",
    )
    education_schools: int = Field(default=0, description="Escolas de todas as redes localizadas na RA.")
    education_schools_public: int = 0
    education_enrollment: int | None = Field(
        default=None,
        description=(
            "Matrículas de escolarização nas escolas situadas na RA — contadas onde a "
            "escola fica, não onde o aluno mora. Por isso não há taxa por habitante."
        ),
    )
    education_enrollment_public_share_pct: float | None = None

    bikeway_km: float | None = Field(
        default=None, description="Km de ciclovia, ciclofaixa e calçada compartilhada dentro da RA (recorte geodésico)."
    )
    bikeway_km_per_10k: float | None = Field(
        default=None, description="Km por 10 mil habitantes (Censo 2022). Nulo onde o IBGE não publica população."
    )
    metro_stations: int | None = Field(default=None, description="Estações de metrô em operação na RA.")

    temp_mean_c: float | None
    temp_max_avg_c: float | None
    temp_min_avg_c: float | None
    precipitation_mm_per_year: float | None
    rainy_days_per_year: float | None
    weather_first_year: int | None
    weather_last_year: int | None
    weather_regions_sharing_cell: int | None = Field(
        default=None,
        description=(
            "Quantas RAs compartilham a mesma célula de amostragem do ERA5. "
            "Maior que 1 significa série climática idêntica entre elas."
        ),
    )


class PopulationPoint(BaseModel):
    region_id: str | None = Field(default=None, description="Nulo nas séries do DF inteiro.")
    region_name: str | None = None
    reference_year: int
    population: int
    density_per_km2: float | None = None
    change_pct_since_previous: float | None = None
    years_since_previous: int | None = Field(
        default=None,
        description="Intervalo real até o ano anterior disponível — a série do IBGE tem lacunas.",
    )
    source_id: str


class SecurityPoint(BaseModel):
    region_id: str
    region_name: str | None = None
    reference_month_start: date
    reference_year: int
    reference_month: int
    category_code: str
    category_name: str
    metric_type: Literal["CRIME", "POLICE_ACTIVITY"]
    occurrences: int
    violent_occurrences: int | None = None
    occurrences_per_10k: float | None = Field(
        default=None, description="Denominador é sempre a população do Censo 2022."
    )


class WeatherPoint(BaseModel):
    region_id: str
    reference_year: int
    reference_month: int
    reference_month_start: date
    days_observed: int = Field(
        description="Menos de 28 indica mês parcial — não compare o acumulado com meses fechados."
    )
    temp_mean_c: float | None
    temp_max_avg_c: float | None
    temp_min_avg_c: float | None
    temp_max_absolute_c: float | None
    temp_min_absolute_c: float | None
    precipitation_mm: float | None
    rainy_days: int
    humidity_mean_pct: float | None
    regions_sharing_cell: int | None = None


class HealthSummary(BaseModel):
    region_id: str | None = Field(
        description="Nulo agrupa os estabelecimentos cuja RA não foi possível determinar."
    )
    region_name: str | None = None
    facilities_total: int
    facilities_public: int = Field(
        description=(
            "Natureza jurídica de administração pública. NÃO use a esfera "
            "administrativa do CNES para isso: no DF ela vale 'ESTADUAL' para "
            "quase toda a rede, inclusive consultórios particulares."
        )
    )
    facilities_private: int
    facilities_nonprofit: int
    facilities_sus_ambulatory: int = Field(
        description="Faz atendimento AMBULATORIAL pelo SUS — não é o total de unidades que atendem SUS."
    )
    facilities_hospital: int
    facilities_ambulatory: int
    facilities_urgent_care: int
    facilities_diagnostics: int
    facilities_support: int
    facilities_with_surgery_center: int
    facilities_with_obstetric_center: int
    assigned_by_coordinates: int
    assigned_by_neighborhood: int
    facilities_per_10k: float | None = None


class HealthFacility(BaseModel):
    cnes_code: int
    facility_name: str | None
    region_id: str | None
    region_name: str | None
    unit_type_name: str
    service_group: str
    sector: str
    serves_sus_ambulatory: bool | None
    latitude: float | None
    longitude: float | None
    region_assignment: str


class Insight(BaseModel):
    insight_id: str
    domain: Literal["population", "security", "health", "education", "mobility", "weather", "quality"]
    title: str
    finding: str = Field(description="Texto gerado a partir dos dados, não redigido à mão.")
    value_numeric: float | None
    unit: str | None
    period_start: int | None
    period_end: int | None
    method: str = Field(description="Como o número foi calculado.")
    source_id: str
    caveat: str | None = Field(description="Limitação metodológica conhecida deste achado.")


class Source(BaseModel):
    source_id: str
    source_name: str
    organization: str
    domain: str
    url: str
    access_type: str
    granularity: str
    update_frequency: str
    is_df_government: bool
    temporal_coverage: str
    caveat: str | None


class Coverage(BaseModel):
    region_id: str
    region_name: str
    population_2022_available: bool
    population_2010_available: bool
    security_years_with_data: int
    security_years_expected: int
    security_first_year: int | None
    security_last_year: int | None
    security_months_with_data: int
    security_missing_years: list[int]
    health_facilities: int
    education_schools: int = 0
    education_years_with_enrollment: int = 0
    mobility_bikeway_km: float = 0
    mobility_metro_stations: int = 0
    weather_first_day: date | None
    weather_last_day: date | None
    weather_days: int
    # Quantos dos seis domínios publicados têm dado para esta RA (0 a 6).
    domains_with_data: int = 0
    has_all_domains: bool


class EducationYear(BaseModel):
    scope: Literal["RA", "DF"] = Field(description="`DF` é o Distrito Federal inteiro, com `region_id` nulo.")
    region_id: str | None = None
    region_name: str | None = None
    census_year: int
    is_year_complete: bool = Field(
        description=(
            "Falso quando o arquivo de matrículas da SEEDF não cobre ao menos 95% das "
            "escolas do cadastro em alguma rede (8 dos 12 anos). As matrículas desse ano vêm nulas."
        )
    )
    schools_total: int = Field(description="Escolas no cadastro do Censo Escolar, todas as redes.")
    schools_public: int
    enrollment_total: int | None = Field(
        description="Total publicado pela fonte. Nulo em 2024 (a SEEDF não publica total nesse ano) e em anos incompletos."
    )
    enrollment_public: int | None
    enrollment_public_share_pct: float | None
    early_childhood: int | None = Field(description="Creche + pré-escola.")
    daycare: int | None
    preschool: int | None
    elementary: int | None
    high_school_all: int | None = Field(
        description=(
            "Ensino médio + ensino médio integrado. Em 2025 parte do médio foi "
            "reclassificada como integrado; a soma mantém a série comparável."
        )
    )
    professional: int | None
    youth_adult: int | None = Field(description="Educação de Jovens e Adultos (EJA).")
    special_total: int | None
    source_id: str


class MobilityRegion(BaseModel):
    region_id: str
    region_name: str | None = None
    bikeway_km: float = Field(description="Km dentro da RA, com trechos que cruzam a divisa recortados.")
    bikeway_km_segregated: float = Field(description="Ciclovia (segregada do tráfego).")
    bikeway_km_painted: float = Field(description="Ciclofaixa (pintada na pista).")
    bikeway_km_shared: float = Field(description="Calçada compartilhada com pedestres.")
    bikeway_km_other: float = Field(description="Infraestrutura em parques, ciclorrotas e zonas 30.")
    bikeway_km_per_10k: float | None
    bikeway_first_year: int | None
    bikeway_last_year: int | None
    metro_stations: int = Field(description="Estações de metrô em operação.")
    metro_stations_building: int = Field(description="Estações de metrô registradas como em construção.")
    source_id: str


class BikewayYear(BaseModel):
    scope: Literal["RA", "DF"]
    region_id: str | None = None
    construction_year: int
    current_network_km_built: float = Field(
        description="Km dos trechos QUE EXISTEM HOJE construídos neste ano. Não é a malha que existia no ano."
    )
    current_network_km_cumulative: float
    source_id: str


class MobilityStation(BaseModel):
    station_kind: Literal["METRO"]
    station_name: str | None
    status: str | None
    is_operating: bool
    latitude: float
    longitude: float
    region_id: str | None
    region_name: str | None = None


class EducationCoverage(BaseModel):
    census_year: int
    sector: str
    schools_in_registry: int
    schools_in_enrollment_file: int
    coverage: float
    is_complete: bool
    is_year_complete: bool


class PipelineStatus(BaseModel):
    source_key: str
    status: Literal["RUNNING", "SUCCESS", "FAILED"]
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: int | None
    rows_written: int
    requests_made: int
    error_message: str | None
    failed_error_checks: int
    failed_warning_checks: int


class Overview(BaseModel):
    """KPIs do topo do dashboard."""

    population_df_latest: int
    population_df_latest_year: int
    population_df_is_projection: bool = Field(
        description="True quando o último ano da série é projeção do IBGE, não contagem censitária."
    )
    regions_total: int
    regions_with_all_domains: int
    indicators_monitored: int
    security_last_month: date | None
    weather_last_day: date | None
    data_last_updated_at: datetime | None
    sources_total: int
    government_sources_total: int


class Indicator(BaseModel):
    """Catálogo dos indicadores disponíveis, com o que cada um mede e de onde vem."""

    indicator_id: str
    domain: str
    name: str
    unit: str
    granularity: str
    source_id: str
    description: str
    caveat: str | None = None


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[dict[str, Any]]
