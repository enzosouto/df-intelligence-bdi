/*
  Extensão da malha cicloviária ATUAL por ano de construção, por RA e para o
  DF (`scope = 'DF'`, `region_id` nulo). Grão: escopo × região × ano.

  O QUE ESTA SÉRIE É, E O QUE NÃO É
  ---------------------------------
  É: quantos km dos trechos que existem hoje foram construídos em cada ano, e
  o acumulado. Não é: a malha que existia em cada ano. Trecho removido ou
  reconstruído não aparece — a camada da IDE-DF é um retrato do presente.
  Por isso o nome das colunas diz `current_network`.
*/

with pieces as (
    select region_id, construction_year, km
    from {{ ref('fct_mobility_bikeway') }}
    where construction_year is not null
),

span as (
    select min(construction_year) as first_year, max(construction_year) as last_year from pieces
),

years as (
    select generate_series(span.first_year, span.last_year) as construction_year from span
),

scopes as (
    select 'RA' as scope, region_id from {{ ref('dim_region') }}
    union all
    select 'DF', null
),

built as (
    select 'RA' as scope, region_id, construction_year, sum(km) as km
    from pieces group by region_id, construction_year
    union all
    select 'DF', null, construction_year, sum(km)
    from pieces group by construction_year
)

select
    scopes.scope,
    scopes.region_id,
    years.construction_year,
    round(coalesce(built.km, 0), 2)                                           as current_network_km_built,
    round(sum(coalesce(built.km, 0)) over (
        partition by scopes.scope, scopes.region_id order by years.construction_year
    ), 2)                                                                     as current_network_km_cumulative,
    'IDEDF_MOBILIDADE'                                                        as source_id
from scopes
cross join years
left join built
    on built.scope = scopes.scope
   and built.region_id is not distinct from scopes.region_id
   and built.construction_year = years.construction_year
