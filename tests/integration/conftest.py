"""Shared fixtures for integration tests.

Loads the project `.env` (if present) so tests pick up the same ports as
the running stack, then exposes them via the `endpoints` fixture.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"


def _load_env_file() -> None:
    if not _ENV_FILE.is_file():
        return
    for raw_line in _ENV_FILE.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = os.path.expandvars(value.strip().strip('"').strip("'"))
        os.environ.setdefault(key, value)


_load_env_file()


@pytest.fixture(scope="session")
def endpoints() -> dict[str, str | int]:
    """Service endpoints, overridable via env vars or `.env`."""
    mlflow_port = os.environ.get("MLFLOW_PORT", "5050")
    return {
        "postgres_host": os.environ.get("POSTGRES_HOST", "localhost"),
        "postgres_port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "minio_endpoint": os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        "mlflow_uri": os.environ.get("MLFLOW_TRACKING_URI", f"http://localhost:{mlflow_port}"),
    }
