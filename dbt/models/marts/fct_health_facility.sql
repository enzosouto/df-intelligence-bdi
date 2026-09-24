/*
  Fato de saúde. Grão: estabelecimento do CNES.

  É um fato de INFRAESTRUTURA — o que existe instalado e onde —, não de
  produção. O CNES não informa quantos atendimentos foram realizados.
*/

select
    facilities.cnes_code,
    facilities.region_id,
    regions.region_name,
    facilities.facility_name,
    facilities.unit_type_code,
    facilities.unit_type_name,
    facilities.service_group,
    facilities.sector,
    facilities.legal_nature_group,
    facilities.management_sphere,
    facilities.serves_sus_ambulatory,
    facilities.has_hospital_care,
    facilities.has_surgery_center,
    facilities.has_obstetric_center,
    facilities.has_neonatal_center,
    facilities.neighborhood,
    facilities.latitude,
    facilities.longitude,
    facilities.region_assignment,
    facilities.neighborhood_agreement,
    'CNES_ESTABELECIMENTOS' as source_id,
    facilities.source_url
from {{ ref('int_health_facility_region') }} as facilities
left join {{ ref('dim_region') }}            as regions on regions.region_id = facilities.region_id
