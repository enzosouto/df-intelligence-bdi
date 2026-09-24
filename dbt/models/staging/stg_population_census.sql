/*
  População por Região Administrativa nos Censos 2010 e 2022.

  Cuidado analítico embutido aqui: em 2010 o IBGE reconhecia 19 subdistritos no
  DF; em 2022, 35. As 16 RAs restantes foram desmembradas de RAs preexistentes.
  Esta camada só padroniza; a decisão sobre o que é comparável no tempo mora em
  `int_region_lineage`.
*/

with census as (
    select * from {{ source('raw', 'population_census') }}
),

regions as (
    select * from {{ ref('stg_regions') }}
)

select
    regions.region_id                as region_id,
    regions.region_name              as region_name,
    census.census_year               as reference_year,
    census.population                as population,
    round(
        census.population::numeric / nullif(regions.area_km2::numeric, 0),
        2
    )                                as density_per_km2,
    census.ibge_aggregate            as ibge_aggregate,
    census._source_url               as source_url
from census
inner join regions on regions.ibge_subdistrict_id = census.subdistrict_id
