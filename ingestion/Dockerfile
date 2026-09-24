# Container do pipeline: ingestão + dbt.
# Roda sob demanda, não como serviço:
#     docker compose run --rm pipeline
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

# Sem apt-get: a imagem slim já traz bash, e a conferência final do pipeline
# usa psycopg2 (não psql). Menos pacotes de sistema, menos pontos de falha.

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
