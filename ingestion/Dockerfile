# Container do pipeline: ingestão + dbt.
# Roda sob demanda, não como serviço:
#     docker compose run --rm pipeline
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

# postgresql-client: o passo final do pipeline confere o que entrou no banco.
# bash: o script usa arrays e `set -o pipefail`.
RUN apt-get update \
    && apt-get install --no-install-recommends -y bash postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ingestion/ /app/ingestion/
COPY dbt/       /app/dbt/
COPY db/        /app/db/
COPY scripts/   /app/scripts/

RUN chmod +x /app/scripts/*.sh && mkdir -p /app/data/raw

ENV DBT_PROFILES_DIR=/app/dbt

CMD ["bash", "/app/scripts/run_pipeline.sh"]
