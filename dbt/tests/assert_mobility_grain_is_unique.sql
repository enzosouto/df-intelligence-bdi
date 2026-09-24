-- Um pedaço por trecho × RA. Duplicar aqui dobraria o km da RA.
select segment_id, region_id, count(*) as rows
from {{ ref('fct_mobility_bikeway') }}
group by segment_id, region_id
having count(*) > 1
