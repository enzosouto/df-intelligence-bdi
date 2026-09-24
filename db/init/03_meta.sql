-- ---------------------------------------------------------------------------
-- Camada META — observabilidade do pipeline.
--
-- Alimenta o KPI "última atualização dos dados" no frontend e serve de trilha
-- de auditoria: quem rodou, quando, quantas linhas entraram, deu erro?
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS meta.ingestion_run (
    run_id        bigserial PRIMARY KEY,
    source_key    text        NOT NULL,   -- 'regions', 'population', 'security', ...
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    status        text        NOT NULL DEFAULT 'RUNNING'
                  CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    rows_written  bigint      NOT NULL DEFAULT 0,
    requests_made integer     NOT NULL DEFAULT 0,
    error_message text
);

CREATE INDEX IF NOT EXISTS ix_ingestion_run_source
    ON meta.ingestion_run (source_key, started_at DESC);

-- Achados de qualidade gerados pela validação da ingestão (antes do dbt).
CREATE TABLE IF NOT EXISTS meta.data_quality_check (
    check_id    bigserial PRIMARY KEY,
    run_id      bigint REFERENCES meta.ingestion_run(run_id) ON DELETE CASCADE,
    check_name  text        NOT NULL,
    severity    text        NOT NULL CHECK (severity IN ('INFO', 'WARN', 'ERROR')),
    passed      boolean     NOT NULL,
    observed    text,
    expected    text,
    checked_at  timestamptz NOT NULL DEFAULT now()
);
