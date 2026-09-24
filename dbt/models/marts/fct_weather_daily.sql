/*
  Fato de clima. Grão: região × dia.

  Fonte NÃO governamental (Open-Meteo/ERA5). `grid_lat`/`grid_lon` mostram o
  ponto efetivamente consultado; RAs que caem na mesma célula têm série
  idêntica, e `regions_sharing_cell` deixa isso explícito para a interface.
*/

with weather as (
    select * from {{ ref('stg_weather_daily') }}
),

cell_sharing as (
    select
        grid_lat,
        grid_lon,
        count(distinct region_id) as regions_sharing_cell
    from weather
    group by grid_lat, grid_lon
)

select
    weather.region_id,
    weather.observed_on,
    weather.reference_year,
    weather.reference_month,
    weather.temp_max_c,
    weather.temp_min_c,
    weather.temp_mean_c,
    weather.precipitation_mm,
    weather.humidity_mean_pct,
    weather.wind_max_kmh,
    weather.is_rainy_day,
    weather.grid_lat,
    weather.grid_lon,
    cell_sharing.regions_sharing_cell,
    'OPEN_METEO_ERA5' as source_id,
    weather.source_url
from weather
left join cell_sharing
    on cell_sharing.grid_lat = weather.grid_lat
   and cell_sharing.grid_lon = weather.grid_lon
