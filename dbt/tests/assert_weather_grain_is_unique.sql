-- O grão declarado de fct_weather_daily é região × dia.

select
    region_id,
    observed_on,
    count(*) as rows_found
from {{ ref('fct_weather_daily') }}
group by region_id, observed_on
having count(*) > 1
