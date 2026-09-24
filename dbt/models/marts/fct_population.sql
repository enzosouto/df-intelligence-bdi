/*
  Fato de população por Região Administrativa.

  Grão: região × ano censitário. Só existem dois anos — 2010 e 2022 — porque só
  o Censo mede população abaixo do município no DF. A série anual do DF inteiro
  está em `fct_population_df`.
*/

select
    census.region_id,
    census.reference_year,
    census.population,
    census.density_per_km2,
    regions.area_km2,
    lineage.existed_in_2010,
    lineage.is_growth_comparable,
    'IBGE_CENSO_' || census.reference_year::text as source_id,
    census.source_url
from {{ ref('stg_population_census') }} as census
inner join {{ ref('stg_regions') }}        as regions on regions.region_id = census.region_id
left  join {{ ref('int_region_lineage') }} as lineage on lineage.region_id = census.region_id
