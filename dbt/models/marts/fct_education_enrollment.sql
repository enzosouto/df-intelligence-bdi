/*
  Fato de educação. Grão: escola (código INEP) × ano de censo.

  A matrícula é contada ONDE A ESCOLA FICA, não onde o aluno mora. Por isso
  nenhuma taxa "matrículas por habitante da RA" é publicada: o Plano Piloto
  recebe alunos de todo o DF e teria uma taxa inflada que não descreve os
  moradores de lugar nenhum.
*/

select
    enrollment.census_year,
    enrollment.school_code,
    enrollment.school_name,
    school_region.region_id,
    regions.region_name,
    school_region.region_assignment,
    enrollment.network_code,
    enrollment.sector,
    enrollment.total_published,
    enrollment.daycare,
    enrollment.preschool,
    enrollment.early_childhood,
    enrollment.elementary,
    enrollment.high_school,
    enrollment.integrated_high_school,
    enrollment.high_school_all,
    enrollment.professional,
    enrollment.youth_adult,
    enrollment.special_exclusive,
    enrollment.special_total,
    coalesce(coverage.is_complete, false)      as is_sector_year_complete,
    coalesce(coverage.is_year_complete, false) as is_year_complete,
    'SEEDF_EDUCACENSO'                         as source_id,
    enrollment.source_url
from {{ ref('stg_education_enrollment') }}        as enrollment
left join {{ ref('int_education_school_region') }} as school_region
    on school_region.school_code = enrollment.school_code
left join {{ ref('dim_region') }}                  as regions
    on regions.region_id = school_region.region_id
left join {{ ref('mart_education_coverage') }}     as coverage
    on coverage.census_year = enrollment.census_year
   and coverage.sector      = enrollment.sector
