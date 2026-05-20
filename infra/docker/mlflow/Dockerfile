FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
        mlflow==2.17.0 \
        psycopg2-binary==2.9.10 \
        boto3==1.35.50

WORKDIR /mlflow
EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=10 \
    CMD curl -fsS http://localhost:5000/health || exit 1

# Default command is overridden by docker-compose with full flags.
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000"]
