/*
  O km recortado por RA tem que bater com o comprimento de cada trecho, e o
  total geodésico tem que bater com o km declarado pela fonte.

  Verificado no pipeline real: 671,9 km declarados = 671,9 km geodésicos =
  671,9 km recortados. Folga de 1%: acima disso, ou o recorte perdeu pedaços
  (malha das RAs com buraco), ou a projeção foi lida errada (coordenada em
  UTM tratada como grau, por exemplo).
*/

with totals as (
    select
        (select sum(km) from {{ ref('fct_mobility_bikeway') }})              as clipped_km,
        (select sum(geodesic_km) from {{ ref('stg_mobility_bikeways') }})     as geodesic_km,
        (select sum(declared_km) from {{ ref('stg_mobility_bikeways') }})     as declared_km
)

select *
from totals
where clipped_km is not null
  and (abs(clipped_km - geodesic_km) > 0.01 * geodesic_km
       or abs(geodesic_km - declared_km) > 0.01 * declared_km)
