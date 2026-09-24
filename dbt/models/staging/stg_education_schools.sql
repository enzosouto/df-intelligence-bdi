/*
  Cadastro de escolas do Educacenso, como a SEEDF publica. Grão: escola × ano.

  O setor sai do CÓDIGO DA REDE, não do nome da escola nem da CRE:
    1 federal, 2 SEEDF, 5 pública não vinculada à SEEDF  → PÚBLICA
    3 particular conveniada                              → CONVENIADA
    4 particular                                         → PARTICULAR

  A conveniada fica separada: é escola privada com vagas pagas pelo GDF
  (sobretudo creches). Juntá-la a qualquer um dos lados distorceria a
  participação da rede pública na educação infantil.
*/

select
    census_year,
    school_code,
    network_code,
    nullif(trim(network_name), '')              as network_name,
    case
        when network_code in (1, 2, 5) then 'PÚBLICA'
        when network_code = 3          then 'CONVENIADA'
        when network_code = 4          then 'PARTICULAR'
        else 'NÃO INFORMADO'
    end                                          as sector,
    nullif(trim(declared_ra_code), '')::int      as declared_ra_code,
    {{ norm_name('declared_ra_name') }}          as declared_ra_name,
    nullif(trim(location_type), '')              as location_type,
    nullif(trim(school_name), '')                as school_name,
    nullif(upper(trim(neighborhood)), '')        as neighborhood,
    latitude,
    longitude,
    _source_url                                  as source_url
from {{ source('raw', 'education_school') }}
