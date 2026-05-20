"""Unit tests for the BentoML serving layer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.model_server.service import (
    DEFAULT_FALLBACK,
    resolve_model_weights,
)


def _mock_version(version: str, stage: str, run_id: str) -> MagicMock:
    mv = MagicMock()
    mv.version = version
    mv.current_stage = stage
    mv.run_id = run_id
    return mv


def test_resolve_picks_latest_production_version(tmp_path: Path) -> None:
    client = MagicMock()
    client.search_model_versions.return_value = [
        _mock_version("1", "Production", "OLD"),
        _mock_version("3", "Production", "NEW"),
        _mock_version("2", "Staging", "STG"),
        _mock_version("4", "Archived", "ARCH"),
    ]
    client.download_artifacts.return_value = str(tmp_path / "art")
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "best.pt").write_bytes(b"FAKE")
    with patch("mlflow.tracking.MlflowClient", return_value=client):
        weights, label = resolve_model_weights(
            model_name="m", stage="Production", download_dir=tmp_path / "dl"
        )
    assert weights.endswith("best.pt")
    assert "v3" in label and "Production" in label
    client.download_artifacts.assert_called_once()
    assert client.download_artifacts.call_args.kwargs["run_id"] == "NEW"


def test_resolve_falls_back_to_staging_when_no_production(tmp_path: Path) -> None:
    client = MagicMock()
    client.search_model_versions.return_value = [
        _mock_version("1", "Staging", "STG"),
    ]
    client.download_artifacts.return_value = str(tmp_path)
    (tmp_path / "best.pt").write_bytes(b"FAKE")
    with patch("mlflow.tracking.MlflowClient", return_value=client):
        weights, label = resolve_model_weights(
            model_name="m", stage="Production", download_dir=tmp_path
        )
    assert "Staging" in label
    assert "v1" in label


def test_resolve_falls_back_when_no_matching_version() -> None:
    client = MagicMock()
    client.search_model_versions.return_value = []
    with patch("mlflow.tracking.MlflowClient", return_value=client):
        weights, label = resolve_model_weights(model_name="m", stage="Production")
    assert weights == DEFAULT_FALLBACK
    assert label.startswith("fallback:")


def test_resolve_falls_back_when_mlflow_unreachable() -> None:
    with patch("mlflow.tracking.MlflowClient", side_effect=ConnectionError("no MLflow")):
        weights, label = resolve_model_weights(model_name="m", stage="Production")
    # `search_model_versions` raises after client init; resolve catches it.
    # Either path lands on the fallback.
    assert weights == DEFAULT_FALLBACK
    assert label.startswith("fallback:")


def test_resolve_falls_back_when_download_fails(tmp_path: Path) -> None:
    client = MagicMock()
    client.search_model_versions.return_value = [_mock_version("2", "Production", "R")]
    client.download_artifacts.side_effect = RuntimeError("S3 down")
    with patch("mlflow.tracking.MlflowClient", return_value=client):
        weights, label = resolve_model_weights(
            model_name="m", stage="Production", download_dir=tmp_path
        )
    assert weights == DEFAULT_FALLBACK


@pytest.mark.parametrize(
    "stage,expect_match",
    [("Production", True), ("Staging", True), ("None", True), ("Archived", True)],
)
def test_resolve_handles_each_stage(stage: str, expect_match: bool, tmp_path: Path) -> None:
    client = MagicMock()
    client.search_model_versions.return_value = [_mock_version("1", stage, "R")]
    client.download_artifacts.return_value = str(tmp_path)
    (tmp_path / "best.pt").write_bytes(b"FAKE")
    with patch("mlflow.tracking.MlflowClient", return_value=client):
        weights, label = resolve_model_weights(model_name="m", stage=stage, download_dir=tmp_path)
    if expect_match:
        assert weights.endswith("best.pt")
        assert stage in label
