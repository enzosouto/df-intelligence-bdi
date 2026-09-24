/*
  Fato de segurança pública.

  Grão: região × mês × natureza criminal.

  A normalização por população usa o Censo 2022 (único dado de população por RA
  disponível). Isso significa que a taxa de anos distantes de 2022 carrega o
  denominador de 2022 — está documentado em `data_quality.md` e exposto na API
  pelo campo `population_reference_year`.
*/

with occurrences as (
    select * from {{ ref('stg_security_occurrences') }}
),

population as (
    select region_id, population_2022
    from {{ ref('dim_region') }}
)

select
    occurrences.region_id,
    occurrences.region_name,
    occurrences.reference_year,
    occurrences.reference_month,
    occurrences.reference_month_start,
    occurrences.nature_key,
    occurrences.nature_name,
    occurrences.category_code,
    occurrences.category_name,
    occurrences.metric_type,
    occurrences.is_violent,
    occurrences.occurrences,
    population.population_2022,
    2022 as population_reference_year,
    case
        when population.population_2022 > 0
        then round(10000.0 * occurrences.occurrences / population.population_2022, 4)
    end as occurrences_per_10k,
    occurrences.axis_source,
    'SSP_DF_BALANCO' as source_id,
    occurrences.source_url
from occurrences
left join population on population.region_id = occurrences.region_id
