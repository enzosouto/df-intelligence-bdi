#!/usr/bin/env bash
#
# Pipeline completo do DF Intelligence:
#   fontes → validação → ingestão → dbt → testes de qualidade
#
# Uso:
#   ./scripts/run_pipeline.sh                  # tudo
#   ./scripts/run_pipeline.sh --skip-ingestion # só dbt (itera em modelagem)
#   ./scripts/run_pipeline.sh --only security  # uma fonte
#
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

# --- .env -------------------------------------------------------------------
if [[ -f .env ]]; then
  set -a; source .env; set +a
elif [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERRO: não há .env nem DATABASE_URL no ambiente. Copie .env.example para .env." >&2
  exit 1
fi

PYTHON="${PYTHON:-python}"
if [[ -x "${REPO_ROOT}/.venv/Scripts/python.exe" ]]; then
  PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"      # Windows
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"              # Linux / macOS
fi

# --- DATABASE_URL é a única fonte de verdade de conexão ---------------------
# O dbt não sabe ler URL de conexão, então derivamos as partes para ele.
eval "$(
  "${PYTHON}" - <<'PY'
import os
from urllib.parse import urlparse, unquote

url = urlparse(os.environ["DATABASE_URL"])
parts = {
    "DBT_POSTGRES_HOST": url.hostname or "localhost",
    "DBT_POSTGRES_PORT": str(url.port or 5432),
    "DBT_POSTGRES_USER": unquote(url.username or "df"),
    "DBT_POSTGRES_PASSWORD": unquote(url.password or ""),
    "DBT_POSTGRES_DB": (url.path or "/df_intelligence").lstrip("/"),
}
for key, value in parts.items():
    print(f"export {key}='{value}'")
PY
)"
export DBT_PROFILES_DIR="${REPO_ROOT}/dbt"

# Chamar o dbt pelo MESMO interpretador da ingestão. Invocar `dbt` direto do
# PATH só funcionaria com o venv ativado — e o script precisa rodar tanto no
# terminal quanto no container, onde não há ativação.
dbt() { "${PYTHON}" -m dbt.cli.main "$@"; }

SKIP_INGESTION=0
ONLY_MODULES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-ingestion) SKIP_INGESTION=1; shift ;;
    --only)           ONLY_MODULES+=("$2"); shift 2 ;;
    *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

if [[ "${SKIP_INGESTION}" -eq 0 ]]; then
  # --- 1. As fontes ainda existem? ------------------------------------------
  # Só antes de ingerir: remodelar o que já está no banco não depende de rede,
  # e um portal do GDF fora do ar não pode travar o `dbt build`.
  step "Validando fontes"
  "${PYTHON}" -m ingestion.validate_sources

  # --- 2. Ingestão ----------------------------------------------------------
  step "Ingestão (fontes → schema raw)"
  "${PYTHON}" -m ingestion "${ONLY_MODULES[@]+"${ONLY_MODULES[@]}"}"
else
  step "Ingestão pulada (--skip-ingestion)"
fi

# --- 3. dbt -----------------------------------------------------------------
cd "${REPO_ROOT}/dbt"

step "dbt deps"
dbt deps --no-version-check || true

step "dbt seed (mapeamentos versionados)"
dbt seed --no-version-check

step "dbt build (modelos + testes de qualidade)"
dbt build --no-version-check

step "dbt docs generate"
dbt docs generate --no-version-check --static || true

cd "${REPO_ROOT}"

# --- 4. Prova de que o dado chegou ------------------------------------------
step "Conferindo o que entrou no banco"
"${PYTHON}" - <<'PY'
import os
import psycopg2

QUERIES = [
    ("Regiões Administrativas", "select count(*) from marts.dim_region"),
    ("População por RA (Censos)", "select count(*) from marts.fct_population"),
    ("População do DF (anos)", "select count(*) from marts.fct_population_df"),
    ("Ocorrências criminais", "select count(*) from marts.fct_security_monthly"),
    ("Estabelecimentos de saúde", "select count(*) from marts.fct_health_facility"),
    ("Dias de clima", "select count(*) from marts.fct_weather_daily"),
    ("Insights calculados", "select count(*) from marts.mart_insights"),
]

with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
    for label, sql in QUERIES:
        cur.execute(sql)
        count = cur.fetchone()[0]
        flag = "OK " if count > 0 else "VAZIO"
        print(f"  [{flag}] {label:32} {count:>9,}".replace(",", "."))
    cur.execute("select source_key, status, finished_at from marts.mart_pipeline_status order by source_key")
    print("\n  Última execução por fonte:")
    for source_key, status, finished_at in cur.fetchall():
        print(f"    {source_key:12} {status:8} {finished_at}")
PY

step "Pipeline concluído"
