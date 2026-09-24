/*
  Cobertura real dos dados, por região e domínio.

  Este modelo existe porque a cobertura das fontes públicas é irregular e
  esconder isso seria desonesto. Exemplos reais encontrados:

  * A SSP-DF não publica o balanço de 2024 para 15 das 35 RAs — os links da
    página apontam para arquivos de outros anos.
  * O IBGE não publica população de 2022 para Arapoanga e Água Quente; conta
    essas populações dentro das RAs de origem.

  O frontend usa esta tabela para marcar lacunas em vez de desenhar zero.
*/

with regions as (
    select region_id, region_name from {{ ref('dim_region') }}
),

security as (
    select
        region_id,
        min(reference_year)                          as first_year,
        max(reference_year)                          as last_year,
        count(distinct reference_year)               as years_with_data,
        count(distinct (reference_year, reference_month)) as months_with_data
    from {{ ref('fct_security_monthly') }}
    group by region_id
),

security_expected_years as (
    select count(distinct reference_year) as total_years
    from {{ ref('fct_security_monthly') }}
),

security_missing as (
    select
        regions.region_id,
        array_agg(distinct all_years.reference_year order by all_years.reference_year)
            filter (
                where not exists (
                    select 1 from {{ ref('fct_security_monthly') }} as found
                    where found.region_id = regions.region_id
                      and found.reference_year = all_years.reference_year
                )
            ) as missing_years
    from regions
    cross join (
        select distinct reference_year from {{ ref('fct_security_monthly') }}
    ) as all_years
    group by regions.region_id
),

population as (
    select
        region_id,
        bool_or(reference_year = 2010) as has_census_2010,
        bool_or(reference_year = 2022) as has_census_2022
    from {{ ref('fct_population') }}
    group by region_id
),

weather as (
    select region_id, min(observed_on) as first_day, max(observed_on) as last_day, count(*) as days
    from {{ ref('fct_weather_daily') }}
    group by region_id
),

health as (
    select region_id, facilities_total from {{ ref('mart_health_region') }}
),

education as (
    select
        region_id,
        count(*) filter (where is_year_complete and enrollment_total is not null) as years_with_enrollment,
        max(schools_total) filter (
            where census_year = (select max(census_year) from {{ ref('mart_education_yearly') }})
        ) as schools_latest
    from {{ ref('mart_education_yearly') }}
    where scope = 'RA'
    group by region_id
)

select
    regions.region_id,
    regions.region_name,

    coalesce(population.has_census_2022, false)              as population_2022_available,
    coalesce(population.has_census_2010, false)              as population_2010_available,

    coalesce(security.years_with_data, 0)                    as security_years_with_data,
    (select total_years from security_expected_years)        as security_years_expected,
    security.first_year                                      as security_first_year,
    security.last_year                                       as security_last_year,
    coalesce(security.months_with_data, 0)                   as security_months_with_data,
    coalesce(security_missing.missing_years, array[]::int[]) as security_missing_years,

    coalesce(health.facilities_total, 0)                     as health_facilities,
    coalesce(education.schools_latest, 0)                    as education_schools,
    coalesce(education.years_with_enrollment, 0)             as education_years_with_enrollment,

    weather.first_day                                        as weather_first_day,
    weather.last_day                                         as weather_last_day,
    coalesce(weather.days, 0)                                as weather_days,

    (
        coalesce(population.has_census_2022, false)
        and coalesce(security.years_with_data, 0) > 0
        and coalesce(health.facilities_total, 0) > 0
        and coalesce(weather.days, 0) > 0
    ) as has_all_domains

from regions
left join population       on population.region_id       = regions.region_id
left join security         on security.region_id         = regions.region_id
left join security_missing on security_missing.region_id = regions.region_id
left join weather          on weather.region_id          = regions.region_id
left join health           on health.region_id           = regions.region_id
left join education        on education.region_id        = regions.region_id
