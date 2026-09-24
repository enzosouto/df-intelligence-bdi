/*
  Cobertura do arquivo de matrículas contra o cadastro de escolas.
  Grão: ano × setor.

  POR QUE EXISTE
  --------------
  O arquivo de matrículas de 2023 publicado pela SEEDF está incompleto: traz
  600 escolas e 385.801 matrículas, contra ~1.150 escolas e ~620 mil matrículas
  nos anos vizinhos (creche: 177 matrículas, contra ~33 mil). Somado
  ingenuamente, ele fabricaria uma "queda de 38% nas matrículas do DF".

  Em vez de uma exceção escrita à mão para 2023, a completude é MEDIDA para
  todo ano e setor: fração das escolas do cadastro que aparecem no arquivo de
  matrículas. Abaixo do limiar, o ano×setor não é publicado — vira lacuna.
*/

{% set min_coverage = 0.95 %}

with registry as (
    select census_year, sector, school_code from {{ ref('stg_education_schools') }}
),

enrolled as (
    select census_year, sector, school_code from {{ ref('stg_education_enrollment') }}
),

by_sector as (
    select
        registry.census_year,
        registry.sector,
        count(*)                                 as schools_in_registry,
        count(enrolled.school_code)              as schools_in_enrollment_file,
        round(count(enrolled.school_code)::numeric / count(*), 3) as coverage
    from registry
    left join enrolled
        on enrolled.census_year = registry.census_year
       and enrolled.school_code = registry.school_code
    group by registry.census_year, registry.sector
)

select
    census_year,
    sector,
    schools_in_registry,
    schools_in_enrollment_file,
    coverage,
    coverage >= {{ min_coverage }}                                   as is_complete,
    bool_and(coverage >= {{ min_coverage }}) over (partition by census_year) as is_year_complete
from by_sector
