/*
  As etapas precisam fechar com o total publicado — com a folga medida nos
  arquivos reais.

  Identidade verificada: creche + pré + fundamental + médio + profissional +
  EJA + educação especial em classe exclusiva = total. Fecha EXATAMENTE em 2023
  e 2025; de 2014 a 2022 as etapas somam entre 99,6% e 99,96% do total. Fora
  da faixa [99%, 100%], alguma coluna foi lida errada (etapa trocada, milhar
  virando decimal, linha duplicada).
*/

with df as (
    select
        census_year,
        sum(total_published) as total,
        sum(coalesce(early_childhood, 0) + coalesce(elementary, 0) + coalesce(high_school, 0)
            + coalesce(professional, 0) + coalesce(youth_adult, 0) + coalesce(special_exclusive, 0)) as parts
    from {{ ref('fct_education_enrollment') }}
    group by census_year
    having count(*) filter (where total_published is null) = 0
)

select census_year, total, parts, round(parts::numeric / total, 4) as ratio
from df
where parts > total or parts < 0.99 * total
