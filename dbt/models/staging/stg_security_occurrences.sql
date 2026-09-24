/*
  Ocorrências criminais normalizadas.

  Três normalizações acontecem aqui:

  1. **Natureza canônica.** A SSP grafa a mesma natureza de formas diferentes
     entre anos (`TENTATIVA DE LATROCÍNIO` / `TENTATIVA DE LATROCINIO`). O seed
     `security_nature_map` colapsa as variações numa chave estável.

  2. **Categoria estável.** O eixo da SSP mudou ao longo do tempo — `ROUBO EM
     RESIDÊNCIA` saiu de "OUTROS CRIMES" para "C.C.P." em 2016. Usar o eixo
     bruto faria a série de cada categoria saltar por mudança de rótulo, não
     por mudança de realidade. A categoria vem do seed; o eixo original fica
     preservado em `axis_source` para auditoria.

  3. **Separação entre crime e atividade policial.** "Tráfico de drogas" e
     "Localização de veículo" são produtividade policial: sobem quando a
     polícia atua mais, não quando a região fica mais violenta. Somá-los a
     roubos produziria um indicador sem sentido. Ficam marcados como
     `metric_type = 'POLICE_ACTIVITY'` e são excluídos do total de crimes.

  Naturezas que aparecerem na fonte sem correspondência no seed são
  DESCARTADAS aqui e capturadas pelo teste `security_nature_unmapped`, que
  falha o pipeline — assim um tipo criminal novo é notado, não silenciado.
*/

with occurrences as (
    select * from {{ source('raw', 'security_occurrence') }}
),

natures as (
    select * from {{ ref('security_nature_map') }}
),

regions as (
    select region_id, region_name from {{ ref('stg_regions') }}
)

select
    occurrences.ra_code                         as region_id,
    regions.region_name                         as region_name,
    occurrences.reference_year                  as reference_year,
    occurrences.reference_month                 as reference_month,
    make_date(occurrences.reference_year, occurrences.reference_month, 1) as reference_month_start,
    natures.nature_key                          as nature_key,
    natures.nature_name                         as nature_name,
    natures.category_code                       as category_code,
    natures.category_name                       as category_name,
    natures.metric_type                         as metric_type,
    natures.is_violent                          as is_violent,
    occurrences.occurrences                     as occurrences,
    occurrences.axis_source                     as axis_source,
    occurrences.nature_source                   as nature_source,
    occurrences._source_url                     as source_url
from occurrences
inner join natures on natures.nature_source = occurrences.nature_source
inner join regions on regions.region_id = occurrences.ra_code
