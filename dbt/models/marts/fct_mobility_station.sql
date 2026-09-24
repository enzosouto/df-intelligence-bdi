/*
  Estações de metrô e terminais de ônibus. Grão: estação.

  A RA vem da geometria, não do nome: a "Estação Arniqueiras" fica, pelo
  polígono oficial, em Águas Claras.
*/

select
    stations.station_kind,
    stations.feature_id,
    stations.station_name,
    upper(stations.status)                                          as status,
    case
        when stations.station_kind = 'METRO'
        then upper(stations.status) = 'EM OPERAÇÃO'
        else upper(stations.status) = 'ATIVO'
    end                                                             as is_operating,
    stations.station_number,
    stations.latitude,
    stations.longitude,
    stations.ra_code                                                as region_id,
    regions.region_name,
    'IDEDF_MOBILIDADE'                                              as source_id,
    stations._source_url                                            as source_url
from {{ source('raw', 'mobility_station') }} as stations
left join {{ ref('dim_region') }}           as regions on regions.region_id = stations.ra_code
