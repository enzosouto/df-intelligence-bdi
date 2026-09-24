/*
  Série mensal de segurança por região e categoria — a tabela que alimenta os
  gráficos temporais.

  Grão: região × mês × categoria (CVLI, CCP, OUTROS, PRODUTIVIDADE).

  `crimes_total` soma apenas `metric_type = 'CRIME'`. Produtividade policial
  fica em coluna própria: ela sobe quando a polícia apreende mais, não quando a
  região fica mais violenta, e misturar as duas coisas num "total de
  ocorrências" produz um número que não significa nada.
*/

select
    region_id,
    region_name,
    reference_month_start,
    reference_year,
    reference_month,
    category_code,
    category_name,
    metric_type,
    sum(occurrences)                                          as occurrences,
    sum(occurrences) filter (where is_violent)                as violent_occurrences,
    max(population_2022)                                      as population_2022,
    case
        when max(population_2022) > 0
        then round(10000.0 * sum(occurrences) / max(population_2022), 4)
    end                                                       as occurrences_per_10k,
    'SSP_DF_BALANCO'                                          as source_id
from {{ ref('fct_security_monthly') }}
group by
    region_id, region_name, reference_month_start, reference_year,
    reference_month, category_code, category_name, metric_type
