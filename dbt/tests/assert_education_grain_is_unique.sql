-- Uma linha por escola × ano. Duplicar aqui dobraria as matrículas da escola.
select school_code, census_year, count(*) as rows
from {{ ref('fct_education_enrollment') }}
group by school_code, census_year
having count(*) > 1
