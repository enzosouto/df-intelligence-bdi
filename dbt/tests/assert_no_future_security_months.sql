/*
  As planilhas do ano corrente trazem 0 nos meses que ainda não aconteceram.
  A ingestão trunca no último mês com ocorrência; este teste garante que a
  truncagem funcionou e que nenhum mês futuro entrou no banco.
*/

select
    region_id,
    reference_year,
    reference_month,
    sum(occurrences) as occurrences
from {{ ref('fct_security_monthly') }}
where make_date(reference_year, reference_month, 1) > date_trunc('month', current_date)
group by region_id, reference_year, reference_month
