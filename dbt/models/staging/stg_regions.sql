/*
  Regiões Administrativas normalizadas.

  Junta a malha do GDF (geometria, código romano) com o identificador do IBGE
  pelo seed `region_name_map`, que é o registro explícito e versionado de qual
  nome do GDF corresponde a qual subdistrito do IBGE. O join NUNCA é por nome
  em tempo de execução: nomes divergem entre fontes e casar por string é
  exatamente o erro que este projeto se recusa a cometer.
*/

with mapping as (
    select * from {{ ref('region_name_map') }}
),

geo as (
    select * from {{ source('raw', 'region_geo') }}
)

select
    geo.ra_code                                as region_id,
    mapping.ra_number                          as region_number,
    mapping.region_name                        as region_name,
    mapping.region_name_gdf                    as region_name_gdf,
    mapping.ibge_subdistrict_id                as ibge_subdistrict_id,
    mapping.ibge_subdistrict_name              as ibge_subdistrict_name,
    mapping.name_match_method                  as name_match_method,
    nullif(mapping.note, '')                   as name_mapping_note,
    geo.area_km2                               as area_km2,
    geo.centroid_lat                           as centroid_lat,
    geo.centroid_lon                           as centroid_lon,
    geo.bbox_min_lon,
    geo.bbox_min_lat,
    geo.bbox_max_lon,
    geo.bbox_max_lat,
    geo.geometry                               as geometry,
    geo.neighbors                              as neighbors,
    geo.ra_monograph_url                       as monograph_url,
    geo._source_url                            as source_url
from geo
inner join mapping on mapping.ra_code = geo.ra_code
