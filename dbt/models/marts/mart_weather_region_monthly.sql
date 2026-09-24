/*
  Agregado climático mensal por região.

  `days_observed` acompanha cada linha: um mês em andamento tem menos dias e a
  precipitação acumulada dele não é comparável à de um mês fechado. O frontend
  usa esse campo para marcar o ponto como parcial em vez de desenhar uma queda
  que não existe.
*/

select
    region_id,
    reference_year,
    reference_month,
    make_date(reference_year, reference_month, 1)       as reference_month_start,
    count(*)                                            as days_observed,
    round(avg(temp_mean_c)::numeric, 2)                 as temp_mean_c,
    round(avg(temp_max_c)::numeric, 2)                  as temp_max_avg_c,
    round(avg(temp_min_c)::numeric, 2)                  as temp_min_avg_c,
    round(max(temp_max_c)::numeric, 2)                  as temp_max_absolute_c,
    round(min(temp_min_c)::numeric, 2)                  as temp_min_absolute_c,
    round(sum(precipitation_mm)::numeric, 2)            as precipitation_mm,
    count(*) filter (where is_rainy_day)                as rainy_days,
    round(avg(humidity_mean_pct)::numeric, 1)           as humidity_mean_pct,
    round(max(wind_max_kmh)::numeric, 1)                as wind_max_kmh,
    max(regions_sharing_cell)                           as regions_sharing_cell,
    'OPEN_METEO_ERA5'                                   as source_id
from {{ ref('fct_weather_daily') }}
group by region_id, reference_year, reference_month
