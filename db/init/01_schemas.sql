-- ---------------------------------------------------------------------------
-- DF Intelligence — schemas
--
--   raw          : dado como veio da fonte, só com tipagem mínima e chave natural.
--   staging      : materializado pelo dbt (limpeza, normalização de RA).
--   intermediate : materializado pelo dbt (joins e enriquecimento).
--   marts        : materializado pelo dbt (tabelas que a API consome).
--   meta         : log de execução do pipeline.
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS meta;
