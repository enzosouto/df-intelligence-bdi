/*
  Série mensal de segurança do DF inteiro. Grão: mês × categoria.

  Existia como SOMA feita dentro da API; foi movida para cá porque indicador
  se calcula no dbt, onde é testado. `regions_reporting` acompanha cada mês: a
  cobertura da SSP-DF varia entre RAs e anos, e um total do DF sem essa
  informação esconderia que o mês é mais "baixo" só porque menos RAs
  publicaram.
*/

select
    'DF'                                    as region_id,
    null::text                              as region_name,
    reference_month_start,
    reference_year,
    reference_month,
    category_code,
    max(category_name)                      as category_name,
    max(metric_type)                        as metric_type,
    sum(occurrences)::int                   as occurrences,
    sum(violent_occurrences)::int           as violent_occurrences,
    null::numeric                           as occurrences_per_10k,
    count(distinct region_id)               as regions_reporting,
    'SSP_DF_BALANCO'                        as source_id
from {{ ref('mart_security_region_monthly') }}
group by reference_month_start, reference_year, reference_month, category_code
