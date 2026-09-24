/*
  Clima diário por Região Administrativa (Open-Meteo / ERA5).

  FONTE NÃO GOVERNAMENTAL. Reanálise ERA5 interpolada, não medição de estação
  do INMET. `grid_lat`/`grid_lon` expõem o ponto efetivamente consultado: RAs
  que compartilham a mesma célula compartilham a série, e a interface declara
  isso.

  `is_rainy_day` usa o limiar de 1,0 mm/dia, convenção da OMM para "dia com
  chuva" (abaixo disso o acumulado não é distinguível de orvalho/erro de
  modelo).
*/

select
    ra_code                     as region_id,
    observed_on,
    extract(year from observed_on)::int   as reference_year,
    extract(month from observed_on)::int  as reference_month,
    temp_max_c,
    temp_min_c,
    temp_mean_c,
    precipitation_mm,
    humidity_mean_pct,
    wind_max_kmh,
    (precipitation_mm >= 1.0)   as is_rainy_day,
    grid_lat,
    grid_lon,
    _source_url                 as source_url
from {{ source('raw', 'weather_daily') }}
where observed_on is not null
