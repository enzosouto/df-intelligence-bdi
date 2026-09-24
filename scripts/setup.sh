#!/usr/bin/env bash
#
# Prepara o ambiente local: .env, ambiente virtual Python, dependências do
# frontend e o Postgres em container.
#
#   ./scripts/setup.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

# --- .env -------------------------------------------------------------------
if [[ -f .env ]]; then
  step ".env já existe — mantido"
else
  step "Criando .env a partir de .env.example"
  cp .env.example .env
  echo "    Revise a senha do Postgres antes de expor o serviço."
fi

# --- Python -----------------------------------------------------------------
step "Ambiente virtual Python"
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "${PYTHON_BIN}" >/dev/null 2>&1 || PYTHON_BIN=python
command -v "${PYTHON_BIN}" >/dev/null 2>&1 || PYTHON_BIN=py

if [[ ! -d .venv ]]; then
  "${PYTHON_BIN}" -m venv .venv
fi

if [[ -x .venv/Scripts/python.exe ]]; then
  VENV_PYTHON=.venv/Scripts/python.exe   # Windows
else
  VENV_PYTHON=.venv/bin/python           # Linux / macOS
fi

"${VENV_PYTHON}" -m pip install --quiet --upgrade pip
"${VENV_PYTHON}" -m pip install --quiet -r requirements.txt
"${VENV_PYTHON}" -m pip install --quiet -r api/requirements.txt
echo "    dependências instaladas em .venv"

# --- Frontend ---------------------------------------------------------------
if command -v npm >/dev/null 2>&1; then
  step "Dependências do frontend"
  (cd frontend && npm install --silent)
else
  step "npm não encontrado — pulando frontend (o container ainda funciona)"
fi

# --- Postgres ---------------------------------------------------------------
step "Subindo o PostgreSQL"
docker compose up -d postgres
docker compose exec -T postgres sh -c 'until pg_isready -q; do sleep 1; done'
echo "    banco pronto"

cat <<'EOF'

Ambiente pronto.

  1. Popular o banco (ingestão + dbt, ~12 min na primeira vez):
       ./scripts/run_pipeline.sh

  2. Subir a aplicação:
       docker compose up -d

  3. Abrir:
       http://localhost:5173   DF Intelligence
       http://localhost:8000/docs   documentação da API

EOF
