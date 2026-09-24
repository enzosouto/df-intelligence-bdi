/*
  Linhagem territorial das Regiões Administrativas.

  O PROBLEMA
  ----------
  Das 35 RAs atuais, apenas 19 existiam como subdistrito no Censo 2010. As
  outras 16 foram desmembradas de RAs preexistentes. Comparar os dois Censos
  por RA, ignorando isso, produz conclusões falsas:

      Ceilândia   402.729 (2010) → 287.023 (2022)   "−28,7%"
      Cruzeiro     81.075 (2010) →  25.741 (2022)   "−68,2%"

  Ninguém perdeu essa gente. O Sol Nascente/Pôr do Sol (101.866 hab.) saiu de
  Ceilândia; o Sudoeste/Octogonal (44.354 hab.) saiu do Cruzeiro.

  O QUE A EVIDÊNCIA PERMITE CONCLUIR
  ----------------------------------
  Verificação feita sobre os dados: **as 19 RAs que existiam em 2010 fazem
  fronteira com pelo menos uma RA criada depois.** Nenhuma delas manteve o
  território intacto entre os Censos.

  Portanto: **o crescimento populacional por RA entre 2010 e 2022 não é
  calculável com as fontes disponíveis.** `is_growth_comparable` é falso para
  todas as 35, e `dim_region` devolve `NULL` na variação. Esse resultado não é
  uma limitação do código — é a conclusão correta, e ela é publicada como
  insight (`POP_RA_NOT_COMPARABLE`).

  O crescimento do DF como um todo continua válido e vem da série anual do
  IBGE, em `fct_population_df`.

  POR QUE NÃO DÁ PARA RESOLVER
  ----------------------------
  Seria preciso a malha de subdistritos do IBGE de 2010 para reconstruir o
  território comparável. A API de malhas do IBGE não serve subdistrito em
  nenhum período (testado: `/malhas/subdistritos/{id}` → 404;
  `intrarregiao=subdistrito` → 400; `periodo=2010` → 500).

  A RA DE ORIGEM
  --------------
  `inferred_parent_region_id` é apenas DESCRITIVO — alimenta a frase "sua
  população em 2010 estava contabilizada em X" na página da região. É inferido
  pela fração do próprio contorno da RA nova que faz fronteira com uma RA
  preexistente, e só é preenchido quando essa fração passa de 50%. Usar
  quilômetros absolutos favoreceria RAs grandes e irregulares: o Plano Piloto
  aparecia como "origem" de Sobradinho II, que na verdade veio de Sobradinho.

  Abaixo do limiar, o campo fica nulo — a interface então diz "na RA de origem",
  sem nomear.
*/

{% set parent_border_share_threshold = 0.5 %}

with regions as (
    select
        stg.region_id,
        geo.perimeter_km,
        stg.neighbors
    from {{ ref('stg_regions') }} as stg
    inner join {{ source('raw', 'region_geo') }} as geo on geo.ra_code = stg.region_id
),

existed_in_2010 as (
    select
        regions.region_id,
        exists (
            select 1
            from {{ ref('stg_population_census') }} as census
            where census.region_id = regions.region_id
              and census.reference_year = 2010
        ) as existed_in_2010
    from regions
),

neighbor_pairs as (
    select
        regions.region_id,
        neighbor.value ->> 'ra_code'              as neighbor_region_id,
        (neighbor.value ->> 'shared_km')::numeric as shared_border_km,
        regions.perimeter_km
    from regions,
         lateral jsonb_array_elements(regions.neighbors) as neighbor
),

-- Toda RA que existia em 2010 e hoje faz fronteira com uma RA criada depois
-- teve o território redefinido no intervalo intercensitário.
lost_territory as (
    select distinct pairs.region_id
    from neighbor_pairs as pairs
    inner join existed_in_2010 as self_flag
        on self_flag.region_id = pairs.region_id
       and self_flag.existed_in_2010 is true
    inner join existed_in_2010 as neighbor_flag
        on neighbor_flag.region_id = pairs.neighbor_region_id
       and neighbor_flag.existed_in_2010 is false
),

-- Origem inferida das RAs novas — descritiva, com limiar de dominância.
inferred_parent as (
    select distinct on (pairs.region_id)
        pairs.region_id,
        pairs.neighbor_region_id                                     as inferred_parent_region_id,
        pairs.shared_border_km                                       as inferred_parent_shared_km,
        round((pairs.shared_border_km / nullif(pairs.perimeter_km, 0))::numeric, 3)
                                                                     as inferred_parent_border_share
    from neighbor_pairs as pairs
    inner join existed_in_2010 as self_flag
        on self_flag.region_id = pairs.region_id
       and self_flag.existed_in_2010 is false
    inner join existed_in_2010 as neighbor_flag
        on neighbor_flag.region_id = pairs.neighbor_region_id
       and neighbor_flag.existed_in_2010 is true
    where pairs.shared_border_km / nullif(pairs.perimeter_km, 0) >= {{ parent_border_share_threshold }}
    order by pairs.region_id, pairs.shared_border_km desc
)

select
    flags.region_id,
    flags.existed_in_2010,
    parent.inferred_parent_region_id,
    parent.inferred_parent_shared_km,
    parent.inferred_parent_border_share,
    (lost.region_id is not null) as lost_territory_after_2010,
    (
        flags.existed_in_2010
        and lost.region_id is null
    ) as is_growth_comparable
from existed_in_2010 as flags
left join inferred_parent as parent on parent.region_id = flags.region_id
left join lost_territory  as lost   on lost.region_id   = flags.region_id
