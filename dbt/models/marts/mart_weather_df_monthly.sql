/*
  Clima mensal do DF: média das RAs. Grão: mês.

  Existia como MÉDIA feita dentro da API; foi movida para cá (indicador se
  calcula no dbt). Como o ERA5 tem resolução menor que uma RA, a média do DF
  é o recorte com significado físico mais claro. Extremos usam o máximo e o
  mínimo entre as RAs, não a média.
*/

select
    'DF'                                        as region_id,
    reference_year,
    reference_month,
    reference_month_start,
    round(avg(days_observed))::int              as days_observed,
    round(avg(temp_mean_c), 1)                  as temp_mean_c,
    round(avg(temp_max_avg_c), 1)               as temp_max_avg_c,
    round(avg(temp_min_avg_c), 1)               as temp_min_avg_c,
    round(max(temp_max_absolute_c), 1)          as temp_max_absolute_c,
    round(min(temp_min_absolute_c), 1)          as temp_min_absolute_c,
    round(avg(precipitation_mm), 1)             as precipitation_mm,
    round(avg(rainy_days))::int                 as rainy_days,
    round(avg(humidity_mean_pct), 1)            as humidity_mean_pct,
    null::int                                   as regions_sharing_cell,
    'OPEN_METEO_ERA5'                           as source_id
from {{ ref('mart_weather_region_monthly') }}
group by reference_year, reference_month, reference_month_start
