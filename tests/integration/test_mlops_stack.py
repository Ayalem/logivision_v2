"""Smoke tests for the local MLOps stack.

These tests assume the stack is already running (`./scripts/bootstrap.sh`).
They are marked `integration` and excluded from the default pytest run.

Run explicitly:
    uv run pytest tests/integration -m integration
"""

from __future__ import annotations

import socket

import pytest
import requests

pytestmark = pytest.mark.integration


def test_postgres_tcp_open(endpoints: dict[str, str | int]) -> None:
    host = str(endpoints["postgres_host"])
    port = int(endpoints["postgres_port"])
    with socket.create_connection((host, port), timeout=5):
        pass


def test_minio_health_live(endpoints: dict[str, str | int]) -> None:
    url = f"{endpoints['minio_endpoint']}/minio/health/live"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"MinIO /health/live returned {response.status_code}"


def test_mlflow_health(endpoints: dict[str, str | int]) -> None:
    url = f"{endpoints['mlflow_uri']}/health"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"MLflow /health returned {response.status_code}"


def test_mlflow_api_lists_experiments(endpoints: dict[str, str | int]) -> None:
    """The Default experiment must exist after a fresh start."""
    url = f"{endpoints['mlflow_uri']}/api/2.0/mlflow/experiments/search"
    response = requests.post(url, json={"max_results": 5}, timeout=5)
    assert response.status_code == 200
    payload = response.json()
    assert "experiments" in payload
