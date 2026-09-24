/*
  Estabelecimentos de saúde do CNES em Brasília.

  DUAS ARMADILHAS DO CNES TRATADAS AQUI

  1. **Público × privado NÃO sai de `descricao_esfera_administrativa`.**
     Esse campo diz quem *gerencia* o estabelecimento no SUS. No DF ele vale
     "ESTADUAL" para 2.407 dos 2.460 registros — inclusive para consultórios
     odontológicos particulares. Usá-lo como "setor" classificaria quase toda a
     rede privada como pública.

     O campo correto é a **natureza jurídica** (tabela CONCLA/IBGE), cujo
     primeiro dígito já separa os grandes grupos:
     `1` administração pública, `2` entidades empresariais,
     `3` entidades sem fins lucrativos, `4` pessoas físicas.

  2. **Os booleanos de serviço são quase todos `0`.**
     `estabelecimento_possui_atendimento_ambulatorial` é verdadeiro em apenas 21
     de 2.460 registros — eles têm um sentido estreito no CNES e não servem para
     agrupar a rede. O agrupamento sai da DESCRIÇÃO OFICIAL do tipo de unidade,
     que vem da própria API (`/cnes/tipounidades`), e não de uma lista de
     códigos digitada à mão.
*/

with facilities as (
    select * from {{ source('raw', 'health_facility') }}
),

unit_types as (
    select * from {{ source('raw', 'health_unit_type') }}
)

select
    facilities.cnes_code,
    nullif(trim(facilities.trade_name), '')     as facility_name,
    nullif(trim(facilities.legal_name), '')     as legal_name,
    facilities.unit_type_code,
    coalesce(unit_types.description, 'NÃO INFORMADO') as unit_type_name,

    case
        when unit_types.description is null then 'NÃO INFORMADO'
        when unit_types.description ~ 'HOSPITAL|PRONTO SOCORRO|UNIDADE MISTA'         then 'HOSPITALAR'
        when unit_types.description ~ 'PRONTO ATENDIMENTO|URGENCIA|EMERGENCIA'        then 'URGÊNCIA'
        when unit_types.description ~ 'APOIO DIAGNOSE|LABORATORIO|IMUNIZACAO|HEMOTERAPIA' then 'DIAGNÓSTICO E TERAPIA'
        when unit_types.description ~ 'CONSULTORIO|CLINICA|CENTRO DE SAUDE|POLICLINICA|SAUDE DA FAMILIA|ATENCAO|POSTO DE SAUDE|ATENCAO DOMICILIAR'
             then 'AMBULATORIAL'
        when unit_types.description ~ 'FARMACIA|CENTRAL|COOPERATIVA|TELESSAUDE|POLO|OFICINA|VIGILANCIA|GESTAO'
             then 'APOIO E GESTÃO'
        else 'OUTROS'
    end as service_group,

    facilities.legal_nature_code,
    case left(coalesce(facilities.legal_nature_code, ''), 1)
        when '1' then 'ADMINISTRAÇÃO PÚBLICA'
        when '2' then 'ENTIDADE EMPRESARIAL'
        when '3' then 'ENTIDADE SEM FINS LUCRATIVOS'
        when '4' then 'PESSOA FÍSICA'
        when '5' then 'ORGANIZAÇÃO INTERNACIONAL'
        else 'NÃO INFORMADO'
    end as legal_nature_group,
    case
        when left(coalesce(facilities.legal_nature_code, ''), 1) = '1' then 'PÚBLICO'
        when left(coalesce(facilities.legal_nature_code, ''), 1) = '3' then 'SEM FINS LUCRATIVOS'
        when left(coalesce(facilities.legal_nature_code, ''), 1) in ('2', '4', '5') then 'PRIVADO'
        else 'NÃO INFORMADO'
    end as sector,

    upper(coalesce(facilities.admin_sphere, 'NÃO INFORMADO')) as management_sphere,
    -- Nome preciso: o campo do CNES é especificamente sobre atendimento
    -- AMBULATORIAL pelo SUS, não sobre "atender pelo SUS" em geral.
    facilities.serves_sus_ambulatory,
    facilities.has_hospital_care,
    facilities.has_surgery_center,
    facilities.has_obstetric_center,
    facilities.has_neonatal_center,

    nullif(upper(trim(facilities.neighborhood)), '') as neighborhood,
    facilities.latitude,
    facilities.longitude,
    facilities.ra_code                           as region_id_geocoded,
    facilities.geocode_quality,
    facilities._source_url                       as source_url
from facilities
left join unit_types on unit_types.unit_type_code = facilities.unit_type_code
