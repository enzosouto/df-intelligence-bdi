/*
  Reconciliação: a soma da população das RAs tem que bater com o total do DF
  publicado pelo IBGE para o mesmo Censo.

  Este é o teste mais valioso do projeto, porque valida de uma vez o mapeamento
  RA↔subdistrito, a ingestão e a ausência de duplicata. Se ele passa, nenhuma
  RA foi contada duas vezes nem ficou de fora.

  Valores oficiais do IBGE para Brasília (município 5300108):
    Censo 2010: 2.570.160    Censo 2022: 2.817.381
*/

{% set official_totals = {'2010': 2570160, '2022': 2817381} %}

with sums as (
    select reference_year, sum(population) as population_sum
    from {{ ref('fct_population') }}
    group by reference_year
)

select
    reference_year,
    population_sum,
    case reference_year
        {% for year, total in official_totals.items() %}
        when {{ year }} then {{ total }}
        {% endfor %}
    end as official_total
from sums
where case reference_year
        {% for year, total in official_totals.items() %}
        when {{ year }} then population_sum <> {{ total }}
        {% endfor %}
        else false
      end
