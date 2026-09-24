/*
  Uma linha por Região Administrativa, com todos os indicadores de topo.
  É o que a página de região e o mapa consomem.

  Regra de janela: os indicadores de segurança usam o ÚLTIMO ANO COMPLETO
  disponível PARA AQUELA REGIÃO (12 meses de dados), não o ano corrente. Um ano
  em andamento sempre pareceria mais seguro do que é, e o ano completo mais
  recente varia entre regiões porque a SSP não publicou 2024 para todas.
  `security_reference_year` acompanha o número para que a comparação entre
  regiões nunca seja cega.
*/

with regions as (
    select * from {{ ref('dim_region') }}
),

security_complete_years as (
    select region_id, reference_year
    from {{ ref('fct_security_monthly') }}
    group by region_id, reference_year
    having count(distinct reference_month) = 12
),

security_reference as (
    select region_id, max(reference_year) as reference_year
    from security_complete_years
    group by region_id
),

security_metrics as (
    select
        facts.region_id,
        facts.reference_year,
        sum(facts.occurrences) filter (where facts.metric_type = 'CRIME')            as crimes_total,
        sum(facts.occurrences) filter (where facts.category_code = 'CVLI')           as cvli_total,
        sum(facts.occurrences) filter (where facts.category_code = 'CCP')            as property_crimes_total,
        sum(facts.occurrences) filter (where facts.metric_type = 'POLICE_ACTIVITY')  as police_activity_total,
        sum(facts.occurrences) filter (where facts.is_violent)                       as violent_total
    from {{ ref('fct_security_monthly') }} as facts
    inner join security_reference as window_year
        on window_year.region_id = facts.region_id
       and window_year.reference_year = facts.reference_year
    group by facts.region_id, facts.reference_year
),

weather_normals as (
    -- Normais do período disponível, calculadas só sobre meses fechados.
    select
        region_id,
        round(avg(temp_mean_c), 1)                             as temp_mean_c,
        round(avg(temp_max_avg_c), 1)                          as temp_max_avg_c,
        round(avg(temp_min_avg_c), 1)                          as temp_min_avg_c,
        round(sum(precipitation_mm) / nullif(count(distinct reference_year), 0), 0)
                                                               as precipitation_mm_per_year,
        round(sum(rainy_days)::numeric / nullif(count(distinct reference_year), 0), 0)
                                                               as rainy_days_per_year,
        min(reference_year)                                    as weather_first_year,
        max(reference_year)                                    as weather_last_year,
        max(regions_sharing_cell)                              as weather_regions_sharing_cell
    from {{ ref('mart_weather_region_monthly') }}
    where days_observed >= 28
    group by region_id
),

health as (
    select * from {{ ref('mart_health_region') }}
),

-- Último ano de censo escolar completo E com total publicado (2024 não tem).
education_reference as (
    select max(census_year) as census_year
    from {{ ref('mart_education_yearly') }}
    where scope = 'DF' and is_year_complete and enrollment_total is not null
),

mobility as (
    select * from {{ ref('mart_mobility_region') }}
),

education as (
    select yearly.*
    from {{ ref('mart_education_yearly') }} as yearly
    inner join education_reference on education_reference.census_year = yearly.census_year
    where yearly.scope = 'RA'
)

select
    regions.region_id,
    regions.region_number,
    regions.region_name,
    regions.area_km2,
    regions.centroid_lat,
    regions.centroid_lon,
    regions.monograph_url,

    regions.population_2022,
    regions.population_2010,
    regions.density_2022_per_km2,
    regions.existed_in_2010,
    regions.is_growth_comparable,
    regions.inferred_parent_region_id,
    regions.lost_territory_after_2010,
    regions.population_change_pct_2010_2022,
    regions.population_cagr_pct_2010_2022,

    security_metrics.reference_year          as security_reference_year,
    security_metrics.crimes_total,
    security_metrics.cvli_total,
    security_metrics.property_crimes_total,
    security_metrics.violent_total,
    security_metrics.police_activity_total,
    case
        when regions.population_2022 > 0
        then round(10000.0 * security_metrics.crimes_total / regions.population_2022, 2)
    end                                      as crimes_per_10k,
    case
        when regions.population_2022 > 0
        then round(100000.0 * security_metrics.cvli_total / regions.population_2022, 2)
    end                                      as cvli_per_100k,

    coalesce(health.facilities_total, 0)     as health_facilities,
    coalesce(health.facilities_public, 0)    as health_facilities_public,
    coalesce(health.facilities_sus_ambulatory, 0) as health_facilities_sus_ambulatory,
    coalesce(health.facilities_hospital, 0)  as health_facilities_hospital,
    case
        when regions.population_2022 > 0
        then round(10000.0 * coalesce(health.facilities_total, 0) / regions.population_2022, 2)
    end                                      as health_facilities_per_10k,

    education_reference.census_year          as education_reference_year,
    -- Escola é contada onde fica. Sem escola cadastrada na RA, o número é 0
    -- de verdade (o cadastro é completo); a matrícula, não: fica NULL.
    coalesce(education.schools_total, 0)     as education_schools,
    coalesce(education.schools_public, 0)    as education_schools_public,
    education.enrollment_total               as education_enrollment,
    education.enrollment_public_share_pct    as education_enrollment_public_share_pct,

    mobility.bikeway_km,
    mobility.bikeway_km_per_10k,
    mobility.metro_stations,
    mobility.bus_terminals,

    weather_normals.temp_mean_c,
    weather_normals.temp_max_avg_c,
    weather_normals.temp_min_avg_c,
    weather_normals.precipitation_mm_per_year,
    weather_normals.rainy_days_per_year,
    weather_normals.weather_first_year,
    weather_normals.weather_last_year,
    weather_normals.weather_regions_sharing_cell

from regions
left join security_metrics on security_metrics.region_id = regions.region_id
left join weather_normals  on weather_normals.region_id  = regions.region_id
left join health           on health.region_id           = regions.region_id
left join mobility         on mobility.region_id         = regions.region_id
cross join education_reference
left join education        on education.region_id        = regions.region_id
