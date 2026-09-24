/*
  Trechos da malha cicloviária do DF (IDE-DF). Grão: trecho.

  A tipologia é agrupada porque o que importa para quem pedala é o grau de
  separação do tráfego: ciclovia (segregada) ≠ ciclofaixa (pintada na pista) ≠
  calçada compartilhada (com pedestre). Parques, ciclorrotas e zonas 30 são
  poucos trechos (69 de 2.293) e ficam em OUTROS.

  O ano é o de CONSTRUÇÃO do trecho que existe hoje. Não é a malha que existia
  em cada ano: trecho removido não aparece na camada.
*/

select
    segment_id,
    {{ norm_name('declared_ra_name') }}           as declared_ra_name,
    declared_km,
    geodesic_km,
    construction_year,
    upper(typology)                               as typology,
    case upper(coalesce(typology, ''))
        when 'CICLOVIA'              then 'CICLOVIA'
        when 'CICLOFAIXA'            then 'CICLOFAIXA'
        when 'CALÇADA COMPARTILHADA' then 'CALÇADA COMPARTILHADA'
        else 'OUTROS'
    end                                           as typology_group,
    upper(road_type)                              as road_type,
    segment_name,
    highway_name,
    _source_url                                   as source_url
from {{ source('raw', 'mobility_bikeway_segment') }}
