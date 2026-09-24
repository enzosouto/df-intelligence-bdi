/*
  Todo nome de RA que a SEEDF usa precisa ser reconhecido — pelo nome oficial
  do GDF (normalizado) ou pelo seed `education_ra_alias`. Um nome novo (RA
  criada, grafia nova) falha aqui em vez de virar escola sem região.
*/

with known as (
    select {{ norm_name('region_name_gdf') }} as name from {{ ref('region_name_map') }}
    union
    select seedf_ra_name from {{ ref('education_ra_alias') }}
),

declared as (
    select distinct declared_ra_name as name from {{ ref('stg_education_schools') }}
    union
    select distinct declared_ra_name from {{ ref('stg_education_enrollment') }}
)

select declared.name
from declared
left join known on known.name = declared.name
where declared.name is not null
  and known.name is null
