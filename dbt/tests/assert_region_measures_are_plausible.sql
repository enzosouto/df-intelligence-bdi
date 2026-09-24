/*
  Faixas de plausibilidade para as medidas geográficas e demográficas das RAs.

  Os limites vêm da realidade física do DF: o território inteiro tem ~5.760 km²,
  a menor RA (Varjão) tem menos de 3 km² e a maior (Planaltina) passa de
  1.500 km². Centroides precisam cair dentro do retângulo que contém o DF.

  Serve como rede de segurança contra o erro clássico de geoprocessamento:
  trocar latitude por longitude, ou ler área em m² como se fosse km².
*/

with regions as (
    select * from {{ ref('dim_region') }}
),

bad_area as (
    select region_id, 'área fora da faixa plausível (0,5–2.000 km²)' as problem,
           area_km2::text as observed
    from regions
    where area_km2 is null or area_km2 < 0.5 or area_km2 > 2000
),

bad_centroid as (
    select region_id, 'centroide fora do retângulo do DF' as problem,
           centroid_lat::text || ', ' || centroid_lon::text as observed
    from regions
    where centroid_lat not between -16.10 and -15.45
       or centroid_lon not between -48.35 and -47.30
),

bad_population as (
    select region_id, 'população do Censo 2022 fora da faixa plausível' as problem,
           population_2022::text as observed
    from regions
    where population_2022 is not null
      and (population_2022 <= 0 or population_2022 > 1000000)
),

total_area as (
    select
        'TOTAL' as region_id,
        'soma das áreas das RAs distante da área do DF (~5.760 km²)' as problem,
        round(sum(area_km2)::numeric, 1)::text as observed
    from regions
    having sum(area_km2) not between 5000 and 6500
)

select * from bad_area
union all select * from bad_centroid
union all select * from bad_population
union all select * from total_area
