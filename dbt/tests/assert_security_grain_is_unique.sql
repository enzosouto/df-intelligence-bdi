-- O grão declarado de fct_security_monthly é região × ano × mês × natureza.
-- Duplicata aqui significaria dupla contagem em todos os agregados acima.

select
    region_id,
    reference_year,
    reference_month,
    nature_key,
    count(*) as rows_found
from {{ ref('fct_security_monthly') }}
group by region_id, reference_year, reference_month, nature_key
having count(*) > 1
