/*
  Regressão da inversão de códigos da SEEDF nas RAs 34/35.

  Escolas verificadas nos arquivos reais (coordenadas de 2023/2024):
    53047028  EC 01 DO ARAPOANGA   -15,640 / -47,636  → RA XXXIV (Arapoanga)
    53020154  EC DE AGUA QUENTE    -15,947 / -48,228  → RA XXXV  (Água Quente)

  A SEEDF declara a primeira sob o código 35 em todos os anos, e em 2025 ainda
  a nomeia "AGUA QUENTE". Se este teste falhar, a RA voltou a ser herdada da
  declaração em vez da coordenada.
*/

with expected (school_code, region_id) as (
    values (53047028::bigint, 'RA-XXXIV'), (53020154::bigint, 'RA-XXXV')
)

select expected.school_code, expected.region_id as expected_region, actual.region_id as actual_region
from expected
inner join {{ ref('int_education_school_region') }} as actual
    on actual.school_code = expected.school_code
where actual.region_id is distinct from expected.region_id
