/*
  Matrículas do Educacenso por escola × ano (agregadas na ingestão a partir do
  grão idade × sexo × cor/raça).

  DUAS COMPOSIÇÕES DERIVADAS, E POR QUÊ

  * `early_childhood` = creche + pré-escola. As duas partes existem em todos os
    anos; o total de educação infantil publicado vem vazio em parte de 2025.

  * `high_school_all` = ensino médio + ensino médio integrado (EMI). Em 2025 a
    SEEDF passou a classificar boa parte do médio como integrado: o EM sozinho
    cai de 100.541 para 89.098, enquanto o EMI sobe de 3.928 para 15.917. A
    soma fica estável (104.469 → 105.015). Publicar o EM sozinho mostraria uma
    queda de 11% que é reclassificação, não perda de alunos.

  `total_published` é o total que a própria fonte publica. Não é recalculado:
  2024 não tem coluna de total e fica NULL. A soma das etapas só fecha
  exatamente com o total em 2023 e 2025 — nos demais anos falta entre 0,04% e
  0,4% —, então ela não pode substituí-lo.
*/

select
    census_year,
    school_code,
    network_code,
    case
        when network_code in (1, 2, 5) then 'PÚBLICA'
        when network_code = 3          then 'CONVENIADA'
        when network_code = 4          then 'PARTICULAR'
        else 'NÃO INFORMADO'
    end                                               as sector,
    nullif(trim(declared_ra_code), '')::int           as declared_ra_code,
    {{ norm_name('declared_ra_name') }}               as declared_ra_name,
    nullif(trim(school_name), '')                     as school_name,
    total_published,
    daycare,
    preschool,
    case when daycare is null and preschool is null then null
         else coalesce(daycare, 0) + coalesce(preschool, 0) end               as early_childhood,
    elementary,
    high_school,
    integrated_high_school,
    case when high_school is null and integrated_high_school is null then null
         else coalesce(high_school, 0) + coalesce(integrated_high_school, 0) end as high_school_all,
    professional,
    youth_adult,
    special_exclusive,
    special_total,
    source_rows,
    _source_url                                        as source_url
from {{ source('raw', 'education_enrollment') }}
