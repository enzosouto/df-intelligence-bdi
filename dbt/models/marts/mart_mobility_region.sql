/*
  Infraestrutura de mobilidade por região. Grão: RA (as 35, inclusive as sem
  nenhuma infraestrutura — ali o zero é verdadeiro, porque as camadas cobrem o
  DF inteiro).

  Km por 10 mil habitantes usa o Censo 2022; fica nulo onde o IBGE não publica
  população (Arapoanga e Água Quente), em vez de dividir por um denominador
  inventado.
*/

with regions as (
    select region_id, population_2022 from {{ ref('dim_region') }}
),

bikeways as (
    select
        region_id,
        sum(km)                                                          as bikeway_km,
        sum(km) filter (where typology_group = 'CICLOVIA')               as bikeway_km_segregated,
        sum(km) filter (where typology_group = 'CICLOFAIXA')             as bikeway_km_painted,
        sum(km) filter (where typology_group = 'CALÇADA COMPARTILHADA')  as bikeway_km_shared,
        sum(km) filter (where typology_group = 'OUTROS')                 as bikeway_km_other,
        min(construction_year)                                           as bikeway_first_year,
        max(construction_year)                                           as bikeway_last_year
    from {{ ref('fct_mobility_bikeway') }}
    group by region_id
),

stations as (
    select
        region_id,
        count(*) filter (where station_kind = 'METRO' and is_operating)       as metro_stations,
        count(*) filter (where station_kind = 'METRO' and not is_operating)   as metro_stations_building,
        count(*) filter (where station_kind = 'BUS_TERMINAL' and is_operating) as bus_terminals
    from {{ ref('fct_mobility_station') }}
    where region_id is not null
    group by region_id
)

select
    regions.region_id,
    round(coalesce(bikeways.bikeway_km, 0), 1)             as bikeway_km,
    round(coalesce(bikeways.bikeway_km_segregated, 0), 1)  as bikeway_km_segregated,
    round(coalesce(bikeways.bikeway_km_painted, 0), 1)     as bikeway_km_painted,
    round(coalesce(bikeways.bikeway_km_shared, 0), 1)      as bikeway_km_shared,
    round(coalesce(bikeways.bikeway_km_other, 0), 1)       as bikeway_km_other,
    case when regions.population_2022 > 0
         then round(10000.0 * coalesce(bikeways.bikeway_km, 0) / regions.population_2022, 2)
    end                                                    as bikeway_km_per_10k,
    bikeways.bikeway_first_year,
    bikeways.bikeway_last_year,
    coalesce(stations.metro_stations, 0)                   as metro_stations,
    coalesce(stations.metro_stations_building, 0)          as metro_stations_building,
    coalesce(stations.bus_terminals, 0)                    as bus_terminals,
    'IDEDF_MOBILIDADE'                                     as source_id
from regions
left join bikeways on bikeways.region_id = regions.region_id
left join stations on stations.region_id = regions.region_id
