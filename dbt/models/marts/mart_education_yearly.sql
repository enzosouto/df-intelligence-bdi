/*
  Educação por região e ano — e o DF inteiro na linha com `region_id` nulo e
  `scope = 'DF'`. Grão: escopo × região × ano.

  REGRAS
  * Ano incompleto (ver `mart_education_coverage`) aparece com as métricas de
    matrícula NULAS e `is_year_complete = false`. É lacuna, não zero, e não
    some da série — o gráfico desenha a quebra.
  * `enrollment_total` só é preenchido quando TODAS as escolas do recorte têm
    total publicado. Em 2024 a fonte não publica total: fica nulo, e as etapas
    continuam disponíveis.
  * O número de escolas vem do CADASTRO, que é completo em todos os anos.
  * Escolas sem região determinada entram no DF, e em nenhuma RA.
*/

with enrollment as (
    select * from {{ ref('fct_education_enrollment') }}
),

registry as (
    select schools.census_year, schools.sector, school_region.region_id
    from {{ ref('stg_education_schools') }}           as schools
    left join {{ ref('int_education_school_region') }} as school_region
        on school_region.school_code = schools.school_code
),

years as (
    select distinct census_year, is_year_complete from {{ ref('mart_education_coverage') }}
),

{% set measures = ['early_childhood', 'daycare', 'preschool', 'elementary', 'high_school_all',
                   'professional', 'youth_adult', 'special_total'] %}

enrollment_by_region as (
    select
        'RA' as scope, region_id, census_year,
        {% for m in measures %}sum({{ m }}) as {{ m }},{% endfor %}
        case when count(*) filter (where total_published is null) = 0
             then sum(total_published) end                                   as enrollment_total,
        case when count(*) filter (where total_published is null) = 0
             then sum(total_published) filter (where sector = 'PÚBLICA') end as enrollment_public
    from enrollment
    where region_id is not null
    group by region_id, census_year

    union all

    select
        'DF', null, census_year,
        {% for m in measures %}sum({{ m }}),{% endfor %}
        case when count(*) filter (where total_published is null) = 0
             then sum(total_published) end,
        case when count(*) filter (where total_published is null) = 0
             then sum(total_published) filter (where sector = 'PÚBLICA') end
    from enrollment
    group by census_year
),

schools_by_region as (
    select 'RA' as scope, region_id, census_year,
           count(*) as schools_total,
           count(*) filter (where sector = 'PÚBLICA') as schools_public
    from registry
    where region_id is not null
    group by region_id, census_year

    union all

    select 'DF', null, census_year, count(*), count(*) filter (where sector = 'PÚBLICA')
    from registry
    group by census_year
)

select
    schools.scope,
    schools.region_id,
    schools.census_year,
    years.is_year_complete,
    schools.schools_total,
    schools.schools_public,
    {% for m in measures %}
    case when years.is_year_complete then enrollment.{{ m }} end as {{ m }},
    {% endfor %}
    case when years.is_year_complete then enrollment.enrollment_total end  as enrollment_total,
    case when years.is_year_complete then enrollment.enrollment_public end as enrollment_public,
    case when years.is_year_complete and enrollment.enrollment_total > 0
         then round(100.0 * enrollment.enrollment_public / enrollment.enrollment_total, 1)
    end                                                                     as enrollment_public_share_pct,
    'SEEDF_EDUCACENSO'                                                      as source_id
from schools_by_region as schools
inner join years on years.census_year = schools.census_year
left join enrollment_by_region as enrollment
    on enrollment.scope       = schools.scope
   and enrollment.census_year = schools.census_year
   and enrollment.region_id is not distinct from schools.region_id
