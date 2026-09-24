/*
  Atribui uma Região Administrativa a cada estabelecimento do CNES.

  Cerca de 31% dos registros do CNES em Brasília não têm coordenada. Descartá-los
  subestimaria a rede de saúde justamente nas regiões com cadastro mais
  precário.

  A recuperação é feita SEM adivinhação: para cada bairro informado, olhamos
  onde caíram os estabelecimentos DAQUELE bairro que têm coordenada válida. Se
  há evidência suficiente (>= 3 estabelecimentos geolocalizados e >= 80% deles
  na mesma RA), o bairro herda essa RA. Caso contrário, o registro fica sem
  região e é contado como `UNRESOLVED` — visível no painel de cobertura, nunca
  empurrado para uma RA arbitrária.
*/

{% set min_evidence = 3 %}
{% set min_agreement = 0.8 %}

with facilities as (
    select * from {{ ref('stg_health_facilities') }}
),

neighborhood_votes as (
    select
        neighborhood,
        region_id_geocoded as region_id,
        count(*)           as votes,
        sum(count(*)) over (partition by neighborhood) as total_votes
    from facilities
    where region_id_geocoded is not null
      and neighborhood is not null
    group by neighborhood, region_id_geocoded
),

neighborhood_winner as (
    select distinct on (neighborhood)
        neighborhood,
        region_id as inferred_region_id,
        votes,
        total_votes,
        round(votes::numeric / total_votes, 3) as agreement
    from neighborhood_votes
    order by neighborhood, votes desc
),

trusted_neighborhood as (
    select *
    from neighborhood_winner
    where total_votes >= {{ min_evidence }}
      and agreement >= {{ min_agreement }}
)

select
    facilities.*,
    coalesce(facilities.region_id_geocoded, trusted.inferred_region_id) as region_id,
    case
        when facilities.region_id_geocoded is not null then facilities.geocode_quality
        when trusted.inferred_region_id is not null    then 'INFERRED_NEIGHBORHOOD'
        else 'UNRESOLVED'
    end as region_assignment,
    trusted.agreement as neighborhood_agreement
from facilities
left join trusted_neighborhood as trusted
    on trusted.neighborhood = facilities.neighborhood
   and facilities.region_id_geocoded is null
