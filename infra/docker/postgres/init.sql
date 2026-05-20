-- Bootstrap databases used by the MLOps stack.
-- The default ${POSTGRES_DB} (`logivision`) is created by the postgres image itself.
-- This script adds the `mlflow` database used by the MLflow tracking server.

CREATE DATABASE mlflow;
GRANT ALL PRIVILEGES ON DATABASE mlflow TO logivision;
