-- Uma linha por mês × categoria na série do DF.
select reference_month_start, category_code, count(*) as rows
from {{ ref('mart_security_df_monthly') }}
group by reference_month_start, category_code
having count(*) > 1
