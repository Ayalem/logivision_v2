"""Unit tests for ml.scripts.export_openvino — heavy deps mocked."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from ml.scripts.export_openvino import (
    ExportError,
    _resolve_run_id,
    _sample_calibration_images,
)


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    root = tmp_path / "ds"
    train_dir = root / "images" / "train"
    train_dir.mkdir(parents=True)
    for i in range(50):
        (train_dir / f"frame_{i:03d}.jpg").write_bytes(b"\xff\xd8\xff\xe0FAKE")
    data_yaml = root / "data.yaml"
    data_yaml.write_text(
        yaml.safe_dump(
            {
                "path": str(root),
                "train": "images/train",
                "val": "images/train",
                "nc": 2,
                "names": ["box", "person"],
            }
        )
    )
    return data_yaml


def test_resolve_run_id_explicit_run_id() -> None:
    assert _resolve_run_id(MagicMock(), "m", "RUN-A", None) == "RUN-A"


def test_resolve_run_id_picks_latest_in_stage() -> None:
    client = MagicMock()
    v1 = MagicMock(version="1", current_stage="Production", run_id="OLD")
    v3 = MagicMock(version="3", current_stage="Production", run_id="NEW")
    v2 = MagicMock(version="2", current_stage="Staging", run_id="STAGING")
    client.search_model_versions.return_value = [v1, v3, v2]
    assert _resolve_run_id(client, "m", None, "Production") == "NEW"


def test_resolve_run_id_raises_when_no_match() -> None:
    client = MagicMock()
    client.search_model_versions.return_value = []
    with pytest.raises(ExportError, match="No version"):
        _resolve_run_id(client, "m", None, "Production")


def test_resolve_run_id_raises_when_no_input() -> None:
    with pytest.raises(ExportError, match="--run-id or --stage"):
        _resolve_run_id(MagicMock(), "m", None, None)


def test_sample_calibration_images_is_deterministic(dataset: Path) -> None:
    a = _sample_calibration_images(dataset, n=10, seed=42)
    b = _sample_calibration_images(dataset, n=10, seed=42)
    assert [p.name for p in a] == [p.name for p in b]
    assert len(a) == 10


def test_sample_calibration_images_caps_at_available(dataset: Path) -> None:
    images = _sample_calibration_images(dataset, n=10000, seed=42)
    assert len(images) == 50  # the fixture has 50 frames


def test_sample_calibration_images_raises_on_empty_dir(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    (root / "images" / "train").mkdir(parents=True)
    data_yaml = root / "data.yaml"
    data_yaml.write_text(
        yaml.safe_dump(
            {
                "path": str(root),
                "train": "images/train",
                "val": "images/train",
                "nc": 1,
                "names": ["x"],
            }
        )
    )
    with pytest.raises(ExportError, match="No images"):
        _sample_calibration_images(data_yaml, n=5)


@contextmanager
def _patched_mlflow(client: MagicMock):
    with (
        patch("mlflow.tracking.MlflowClient", return_value=client),
        patch("mlflow.set_tracking_uri"),
        patch("mlflow.start_run"),
        patch("mlflow.log_artifacts"),
        patch("mlflow.log_metric"),
    ):
        yield


def test_export_aborts_on_large_int8_regression(dataset: Path, tmp_path: Path) -> None:
    """If FP32 - INT8 > delta_map50_abort, return aborted=True and skip logging."""
    from ml.scripts.export_openvino import export

    client = MagicMock()
    run = MagicMock()
    run.data.tags = {"dataset_path": str(dataset)}
    client.get_run.return_value = run

    version = MagicMock(version="1", current_stage="None", run_id="RUN")
    client.search_model_versions.return_value = [version]

    fake_weights = tmp_path / "fake_best.pt"
    fake_weights.write_bytes(b"FAKE")
    client.download_artifacts.return_value = str(fake_weights.parent)

    fake_fp32 = tmp_path / "fp32_openvino_model"
    fake_fp32.mkdir()
    (fake_fp32 / "best.xml").write_text("<xml/>")
    fake_int8 = tmp_path / "fp32_int8_openvino_model"
    fake_int8.mkdir()
    (fake_int8 / "best.xml").write_text("<xml/>")

    with (
        _patched_mlflow(client),
        patch("ml.scripts.export_openvino._download_best_weights", return_value=fake_weights),
        patch("ml.scripts.export_openvino._export_fp32", return_value=fake_fp32),
        patch("ml.scripts.export_openvino._quantize_int8", return_value=fake_int8),
        patch(
            "ml.scripts.export_openvino._measure_map50",
            side_effect=[0.80, 0.50],  # fp32=0.80, int8=0.50 → delta=0.30 → ABORT
        ),
    ):
        result = export(
            run_id="RUN",
            stage=None,
            model_name="m",
            delta_map50_abort=0.05,
        )

    assert result.aborted is True
    assert result.map50_fp32 == 0.80
    assert result.map50_int8 == 0.50
    assert result.delta_map50 == pytest.approx(0.30, abs=1e-6)


def test_export_logs_when_int8_is_within_tolerance(dataset: Path, tmp_path: Path) -> None:
    from ml.scripts.export_openvino import export

    client = MagicMock()
    run = MagicMock()
    run.data.tags = {"dataset_path": str(dataset)}
    client.get_run.return_value = run
    client.search_model_versions.return_value = [
        MagicMock(version="1", current_stage="None", run_id="RUN")
    ]

    fake_weights = tmp_path / "best.pt"
    fake_weights.write_bytes(b"FAKE")
    fake_fp32 = tmp_path / "fp32"
    fake_fp32.mkdir()
    (fake_fp32 / "best.xml").write_text("<xml/>")
    fake_int8 = tmp_path / "int8"
    fake_int8.mkdir()
    (fake_int8 / "best.xml").write_text("<xml/>")

    log_artifacts_mock = MagicMock()
    log_metric_mock = MagicMock()
    with (
        patch("mlflow.tracking.MlflowClient", return_value=client),
        patch("mlflow.set_tracking_uri"),
        patch("mlflow.start_run"),
        patch("mlflow.log_artifacts", log_artifacts_mock),
        patch("mlflow.log_metric", log_metric_mock),
        patch("ml.scripts.export_openvino._download_best_weights", return_value=fake_weights),
        patch("ml.scripts.export_openvino._export_fp32", return_value=fake_fp32),
        patch("ml.scripts.export_openvino._quantize_int8", return_value=fake_int8),
        patch(
            "ml.scripts.export_openvino._measure_map50",
            side_effect=[0.80, 0.78],  # delta = 0.02 → OK
        ),
    ):
        result = export(
            run_id="RUN",
            stage=None,
            model_name="m",
            delta_map50_abort=0.05,
        )

    assert result.aborted is False
    assert log_artifacts_mock.call_count == 2  # fp32 + int8
    metric_names = {call.args[0] for call in log_metric_mock.call_args_list}
    assert {
        "openvino_fp32_map50",
        "openvino_int8_map50",
        "openvino_int8_delta_map50",
    } <= metric_names
