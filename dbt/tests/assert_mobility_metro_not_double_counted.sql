/*
  O metrô vem SÓ da camada 140. A camada 127 repete 17 estações de metrô com
  outro objectid — se elas entrarem como estação, o metrô é contado duas vezes.
*/

select station_name, count(*) as rows
from {{ ref('fct_mobility_station') }}
where station_kind = 'METRO'
group by station_name
having count(*) > 1
