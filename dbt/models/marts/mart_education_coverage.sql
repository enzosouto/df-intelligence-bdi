/*
  Cobertura do arquivo de matrículas contra o cadastro de escolas.
  Grão: ano × setor.

  POR QUE EXISTE
  --------------
  Os arquivos de matrículas da SEEDF omitem escolas ATIVAS do cadastro (que
  oferecem etapas e tinham matrícula no ano anterior) em 8 dos 12 anos:
  particulares de 2015 a 2020 e 2022 (15% a 29% delas) e, em 2023, 664 das
  1.264 escolas. Verificado no pipeline real: das 102 escolas ausentes do
  arquivo de 2015, 87 tinham 26.844 matrículas em 2014 — 94% da "queda" de
  2014 para 2015.

  Em vez de uma lista de anos escrita à mão, a completude é MEDIDA para todo
  ano e setor: fração das escolas do cadastro que aparecem no arquivo de
  matrículas. Abaixo do limiar em qualquer rede, o ano não é publicado.
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
