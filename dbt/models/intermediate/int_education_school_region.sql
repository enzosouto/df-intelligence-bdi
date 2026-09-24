/*
  Atribui UMA Região Administrativa a cada escola (código INEP). Grão: escola.

  POR QUE NÃO USAR A RA QUE A SEEDF DECLARA
  ------------------------------------------
  Verificado nos arquivos de 2023, 2024 e 2025: as mesmas escolas aparecem
  sempre sob o mesmo código de RA, mas

      EC 01 DO ARAPOANGA (INEP 53047028)  código 35 — 2023/24 "ARAPOANGA", 2025 "AGUA QUENTE"
      EC DE AGUA QUENTE  (INEP 53020154)  código 34 — 2024 "AGUA QUENTE",   2025 "ARAPOANGA"

  Pela numeração oficial, RA XXXIV é Arapoanga. O código da SEEDF está
  invertido em todos os anos; o nome passou a vir invertido em 2025. Nem um
  nem outro serve de chave sozinho.

  A REGRA
  -------
  1. `COORDINATE` — a RA vem do point-in-polygon da coordenada da escola contra
     a malha oficial (feito na ingestão). A coordenada mais recente do código
     INEP vale para todos os anos: escola não muda de endereço sem mudar de
     código, e o arquivo de 2025 não traz coordenada.
  2. `DECLARED_VERIFIED` — sem coordenada, aceita-se a RA declarada somente se
     (a) o código E o nome apontam para a mesma RA oficial, e (b) o par
     (ano, código, nome) é CONFIÁVEL: entre as escolas desse par que têm
     coordenada, a maioria cai na RA que o par indica.

     A condição (b) existe porque (a) não basta. Em 2025, as escolas do
     Arapoanga vêm com código 35 E nome "AGUA QUENTE" — errados, mas
     coerentes entre si. No pipeline real, as 7 escolas desse par com
     coordenada estão todas na RA XXXIV: acerto 0%, par descartado. Nenhuma
     exceção escrita à mão para 34/35; a evidência decide.
  3. `UNRESOLVED` — o resto. Fica sem região, visível na cobertura, em vez de
     ser empurrado para uma RA arbitrária.

  CONSEQUÊNCIA ÚTIL
  -----------------
  Como a escola é um ponto, uma escola de 2014 é atribuída à RA que hoje contém
  o seu endereço. A série por RA fica em território CONSTANTE (malha de 2025)
  — ao contrário da população por RA, que não tem microdado e por isso não é
  comparável entre Censos (ver `int_region_lineage`).
*/

with regions as (
    select ra_code as region_id, ra_number, {{ norm_name('region_name_gdf') }} as name_norm
    from {{ ref('region_name_map') }}
),

name_lookup as (
    select name_norm as seedf_ra_name, region_id from regions
    union
    select seedf_ra_name, region_id from {{ ref('education_ra_alias') }}
),

declarations as (
    select school_code, census_year, declared_ra_code, declared_ra_name
    from {{ ref('stg_education_schools') }}
    union
    select school_code, census_year, declared_ra_code, declared_ra_name
    from {{ ref('stg_education_enrollment') }}
),

checked_declarations as (
    select
        declarations.*,
        by_name.region_id                         as region_by_name,
        by_code.region_id                         as region_by_code,
        by_name.region_id = by_code.region_id     as code_and_name_agree
    from declarations
    left join name_lookup as by_name on by_name.seedf_ra_name = declarations.declared_ra_name
    left join regions     as by_code on by_code.ra_number     = declarations.declared_ra_code
),

-- Confiabilidade de cada rótulo declarado, medida contra as coordenadas.
pair_reliability as (
    select
        checked.census_year,
        checked.declared_ra_code,
        checked.declared_ra_name,
        count(*)                                                      as geocoded_schools,
        avg((checked.region_by_name = location.ra_code)::int)         as agreement
    from checked_declarations as checked
    inner join {{ source('raw', 'education_school_location') }} as location
        on location.school_code = checked.school_code
       and location.ra_code is not null
    where checked.code_and_name_agree
    group by 1, 2, 3
),

latest_verified as (
    select distinct on (school_code)
        school_code,
        region_by_name as region_id,
        census_year    as declared_year
    from checked_declarations as checked
    left join pair_reliability as reliability
        using (census_year, declared_ra_code, declared_ra_name)
    where checked.code_and_name_agree
      -- Sem nenhuma escola geolocalizada no par, não há evidência contra ele.
      and coalesce(reliability.agreement >= 0.5, true)
    order by school_code, census_year desc
),

schools as (
    select distinct school_code from declarations
),

location as (
    select * from {{ source('raw', 'education_school_location') }}
)

select
    schools.school_code,
    coalesce(location.ra_code, latest_verified.region_id)       as region_id,
    case
        when location.ra_code is not null         then 'COORDINATE'
        when latest_verified.region_id is not null then 'DECLARED_VERIFIED'
        else 'UNRESOLVED'
    end                                                          as region_assignment,
    location.geocode_quality,
    location.latitude,
    location.longitude,
    location.coordinate_year,
    latest_verified.region_id                                    as declared_region_id,
    -- Controle de qualidade: onde há as duas evidências, elas concordam?
    case
        when location.ra_code is null or latest_verified.region_id is null then null
        else location.ra_code = latest_verified.region_id
    end                                                          as coordinate_agrees_with_declaration
from schools
left join location        on location.school_code        = schools.school_code
left join latest_verified on latest_verified.school_code = schools.school_code
