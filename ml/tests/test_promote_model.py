"""Unit tests for ml.scripts.promote_model — MLflow client mocked."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from ml.scripts.promote_model import (
    PromotionError,
    _check_metrics,
    promote,
)


@pytest.fixture
def thresholds_file(tmp_path: Path) -> Path:
    f = tmp_path / "thresholds.yaml"
    f.write_text(
        yaml.safe_dump(
            {
                "policy_version": 1,
                "staging_thresholds": {
                    "val_map50": 0.65,
                    "val_map50_95": 0.40,
                    "val_precision": 0.60,
                    "val_recall": 0.60,
                },
                "production_thresholds": {
                    "val_map50": 0.75,
                    "val_map50_95": 0.50,
                    "val_precision": 0.70,
                    "val_recall": 0.70,
                },
            }
        )
    )
    return f


def _mock_client(metrics: dict[str, float], current_stage: str) -> MagicMock:
    """Build a MagicMock that mimics the MlflowClient calls we use."""
    client = MagicMock()
    run = MagicMock()
    run.data.metrics = metrics
    client.get_run.return_value = run

    version = MagicMock()
    version.run_id = "RUN"
    version.version = "3"
    version.current_stage = current_stage
    client.search_model_versions.return_value = [version]
    return client


@contextmanager
def _patched(client: MagicMock):
    """Patch MlflowClient where `promote` actually imports it from."""
    with (
        patch("mlflow.tracking.MlflowClient", return_value=client),
        patch("mlflow.set_tracking_uri"),
    ):
        yield


def test_check_metrics_pass() -> None:
    assert (
        _check_metrics(
            {"val_map50": 0.8, "val_map50_95": 0.5},
            {"val_map50": 0.7, "val_map50_95": 0.4},
        )
        == []
    )


def test_check_metrics_reports_missing_and_low() -> None:
    failures = _check_metrics(
        {"val_map50": 0.5},
        {"val_map50": 0.7, "val_map50_95": 0.4},
    )
    assert any("val_map50 (0.5000" in f for f in failures)
    assert any("val_map50_95 (missing)" in f for f in failures)


def test_none_to_staging_passes(thresholds_file: Path) -> None:
    client = _mock_client(
        metrics={
            "val_map50": 0.8,
            "val_map50_95": 0.5,
            "val_precision": 0.7,
            "val_recall": 0.7,
        },
        current_stage="None",
    )
    with _patched(client):
        result = promote(
            run_id="RUN",
            model_name="logivision-detector",
            thresholds_path=thresholds_file,
        )
    assert result.promoted is True
    assert result.new_stage == "Staging"
    called = client.transition_model_version_stage.call_args.kwargs
    assert called["stage"] == "Staging"
    assert called["archive_existing_versions"] is False


def test_none_to_staging_fails_when_threshold_unmet(thresholds_file: Path) -> None:
    client = _mock_client(
        metrics={
            "val_map50": 0.50,
            "val_map50_95": 0.50,
            "val_precision": 0.7,
            "val_recall": 0.7,
        },
        current_stage="None",
    )
    with _patched(client), pytest.raises(PromotionError, match="val_map50"):
        promote(run_id="RUN", model_name="m", thresholds_path=thresholds_file)
    client.transition_model_version_stage.assert_not_called()


def test_staging_needs_approve_for_production(thresholds_file: Path) -> None:
    client = _mock_client(
        metrics={
            "val_map50": 0.9,
            "val_map50_95": 0.8,
            "val_precision": 0.85,
            "val_recall": 0.85,
        },
        current_stage="Staging",
    )
    with _patched(client):
        result = promote(
            run_id="RUN", model_name="m", thresholds_path=thresholds_file, approve=False
        )
    assert result.promoted is False
    assert result.new_stage == "Staging"
    client.transition_model_version_stage.assert_not_called()


def test_staging_to_production_with_approve(thresholds_file: Path) -> None:
    client = _mock_client(
        metrics={
            "val_map50": 0.9,
            "val_map50_95": 0.8,
            "val_precision": 0.85,
            "val_recall": 0.85,
        },
        current_stage="Staging",
    )
    with _patched(client):
        result = promote(
            run_id="RUN", model_name="m", thresholds_path=thresholds_file, approve=True
        )
    assert result.promoted is True
    assert result.new_stage == "Production"
    called = client.transition_model_version_stage.call_args.kwargs
    assert called["stage"] == "Production"
    assert called["archive_existing_versions"] is True


def test_staging_to_production_fails_when_threshold_unmet(thresholds_file: Path) -> None:
    client = _mock_client(
        metrics={
            "val_map50": 0.70,
            "val_map50_95": 0.45,
            "val_precision": 0.7,
            "val_recall": 0.7,
        },
        current_stage="Staging",
    )
    with _patched(client), pytest.raises(PromotionError, match="val_map50"):
        promote(
            run_id="RUN",
            model_name="m",
            thresholds_path=thresholds_file,
            approve=True,
        )
    client.transition_model_version_stage.assert_not_called()


def test_already_production_is_noop(thresholds_file: Path) -> None:
    client = _mock_client(
        metrics={
            "val_map50": 0.9,
            "val_map50_95": 0.8,
            "val_precision": 0.85,
            "val_recall": 0.85,
        },
        current_stage="Production",
    )
    with _patched(client):
        result = promote(
            run_id="RUN", model_name="m", thresholds_path=thresholds_file, approve=True
        )
    assert result.promoted is False
    assert result.previous_stage == "Production"
    client.transition_model_version_stage.assert_not_called()


def test_unknown_run_for_model_raises(thresholds_file: Path) -> None:
    client = MagicMock()
    run = MagicMock()
    run.data.metrics = {}
    client.get_run.return_value = run
    client.search_model_versions.return_value = []
    with _patched(client), pytest.raises(PromotionError, match="No version"):
        promote(run_id="RUN", model_name="m", thresholds_path=thresholds_file)
