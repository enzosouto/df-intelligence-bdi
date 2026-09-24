/*
  Rede de saúde instalada por região.

  Indicador de infraestrutura, não de produção. Quem tem hospital, quantos
  estabelecimentos atendem pelo SUS, quantos por 10 mil habitantes.

  `facilities_unresolved` (região não determinada) aparece como uma linha com
  `region_id` nulo — em vez de ser diluída nas demais, o que inflaria a rede de
  todas as regiões.

  A taxa por 10 mil habitantes é calculada AQUI, e não na API: indicador que
  sai errado se corrige no modelo que o produz. Nula onde o IBGE não publica
  população (Arapoanga, Água Quente) e na linha sem região.
*/

with facilities as (
    select * from {{ ref('fct_health_facility') }}
),

by_region as (
select
    region_id,
    count(*)                                                    as facilities_total,
    count(*) filter (where sector = 'PÚBLICO')                  as facilities_public,
    count(*) filter (where sector = 'PRIVADO')                  as facilities_private,
    count(*) filter (where sector = 'SEM FINS LUCRATIVOS')      as facilities_nonprofit,
    count(*) filter (where serves_sus_ambulatory)               as facilities_sus_ambulatory,
    count(*) filter (where service_group = 'HOSPITALAR')        as facilities_hospital,
    count(*) filter (where service_group = 'AMBULATORIAL')      as facilities_ambulatory,
    count(*) filter (where service_group = 'URGÊNCIA')          as facilities_urgent_care,
    count(*) filter (where service_group = 'DIAGNÓSTICO E TERAPIA') as facilities_diagnostics,
    count(*) filter (where service_group = 'APOIO E GESTÃO')    as facilities_support,
    count(*) filter (where has_surgery_center)                  as facilities_with_surgery_center,
    count(*) filter (where has_obstetric_center)                as facilities_with_obstetric_center,
    count(*) filter (where region_assignment = 'OK')            as assigned_by_coordinates,
    count(*) filter (where region_assignment = 'LOW')           as assigned_by_low_quality_coordinates,
    count(*) filter (where region_assignment = 'INFERRED_NEIGHBORHOOD') as assigned_by_neighborhood,
    'CNES_ESTABELECIMENTOS'                                     as source_id
from facilities
group by region_id
)

select
    by_region.*,
    case when regions.population_2022 > 0
         then round(10000.0 * by_region.facilities_total / regions.population_2022, 2)
    end as facilities_per_10k
from by_region
left join {{ ref('dim_region') }} as regions on regions.region_id = by_region.region_id
