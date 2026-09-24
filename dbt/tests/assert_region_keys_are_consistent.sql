/*
  Toda RA precisa existir nas duas nomenclaturas, com mapeamento 1:1.

  Falha se: uma RA do GDF não tem subdistrito IBGE, um subdistrito IBGE é usado
  por mais de uma RA, ou o número da RA não bate com o código romano.
*/

with mapping as (
    select * from {{ ref('region_name_map') }}
),

duplicated_subdistricts as (
    select
        'subdistrito IBGE usado por mais de uma RA' as problem,
        ibge_subdistrict_id::text                   as offending_value
    from mapping
    group by ibge_subdistrict_id
    having count(*) > 1
),

regions_without_mapping as (
    select
        'RA do GDF sem mapeamento IBGE' as problem,
        geo.ra_code                     as offending_value
    from {{ source('raw', 'region_geo') }} as geo
    left join mapping on mapping.ra_code = geo.ra_code
    where mapping.ra_code is null
),

mapping_without_region as (
    select
        'mapeamento aponta para RA inexistente na malha' as problem,
        mapping.ra_code                                  as offending_value
    from mapping
    left join {{ source('raw', 'region_geo') }} as geo on geo.ra_code = mapping.ra_code
    where geo.ra_code is null
)

select * from duplicated_subdistricts
union all select * from regions_without_mapping
union all select * from mapping_without_region
