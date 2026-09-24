/*
  Estado da última execução de cada fonte. Alimenta o KPI "última atualização
  dos dados" e a página de transparência do produto.
*/

with last_run as (
    select distinct on (source_key)
        source_key,
        run_id,
        started_at,
        finished_at,
        status,
        rows_written,
        requests_made,
        error_message
    from {{ source('meta', 'ingestion_run') }}
    order by source_key, started_at desc
),

failed_checks as (
    select
        runs.source_key,
        count(*) filter (where not checks.passed and checks.severity = 'ERROR') as failed_errors,
        count(*) filter (where not checks.passed and checks.severity = 'WARN')  as failed_warnings
    from {{ source('meta', 'data_quality_check') }} as checks
    inner join last_run as runs on runs.run_id = checks.run_id
    group by runs.source_key
)

select
    last_run.source_key,
    last_run.status,
    last_run.started_at,
    last_run.finished_at,
    extract(epoch from (last_run.finished_at - last_run.started_at))::int as duration_seconds,
    last_run.rows_written,
    last_run.requests_made,
    last_run.error_message,
    coalesce(failed_checks.failed_errors, 0)   as failed_error_checks,
    coalesce(failed_checks.failed_warnings, 0) as failed_warning_checks
from last_run
left join failed_checks on failed_checks.source_key = last_run.source_key
