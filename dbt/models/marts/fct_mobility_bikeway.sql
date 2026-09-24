/*
  Malha cicloviária por região. Grão: trecho × RA.

  Um trecho que cruza a divisa vira duas linhas, cada uma com o km que está
  dentro daquela RA (recorte geodésico feito na ingestão). É o que impede que
  os 35 trechos que atravessam divisas sejam contados inteiros na RA declarada
  — ou, pior, nas duas.
*/

select
    pieces.segment_id,
    pieces.ra_code                  as region_id,
    regions.region_name,
    round(pieces.km::numeric, 4)    as km,
    segments.typology,
    segments.typology_group,
    segments.road_type,
    segments.construction_year,
    segments.segment_name,
    'IDEDF_MOBILIDADE'              as source_id,
    segments.source_url
from {{ source('raw', 'mobility_bikeway_piece') }} as pieces
inner join {{ ref('stg_mobility_bikeways') }}     as segments on segments.segment_id = pieces.segment_id
left join {{ ref('dim_region') }}                 as regions  on regions.region_id   = pieces.ra_code
