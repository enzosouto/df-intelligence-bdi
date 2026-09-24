/*
  População do Distrito Federal, série anual.

  `yoy_change_pct` é calculado contra o ano anterior DISPONÍVEL, e
  `years_since_previous` diz qual é esse intervalo. Sem isso, a variação entre
  2021 e 2024 (há lacuna de dois anos na série do IBGE) apareceria como se
  fosse variação de um ano.
*/

with series as (
    select
        reference_year,
        population,
        source_url,
        lag(population)      over (order by reference_year) as previous_population,
        lag(reference_year)  over (order by reference_year) as previous_year
    from {{ ref('stg_population_df') }}
)

select
    reference_year,
    population,
    previous_year,
    (reference_year - previous_year)                 as years_since_previous,
    case
        when previous_population > 0
        then round(100.0 * (population - previous_population) / previous_population, 2)
    end                                              as change_pct_since_previous,
    'IBGE_ESTIMATIVAS'                               as source_id,
    source_url
from series
order by reference_year
