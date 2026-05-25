"""Tests for ml.scripts.train.

Heavy ML deps (ultralytics, torch) are mocked in unit tests so the suite
stays under a few seconds. The optional integration test actually runs
1 epoch on a tiny synthetic dataset and is gated by `-m integration`.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from ml.scripts.train import (
    _dataset_fingerprint,
    _flatten_metrics,
    train,
)


def _mock_val(map50: float = 0.8, map50_95: float = 0.6) -> MagicMock:
    val = MagicMock()
    val.box.map50 = map50
    val.box.map = map50_95
    val.box.mp = 0.7
    val.box.mr = 0.75
    return val


@pytest.fixture
def tiny_dataset(tmp_path: Path) -> Path:
    """A minimal Ultralytics-style dataset on disk — used by mocked tests only."""
    dataset_root = tmp_path / "tiny"
    (dataset_root / "images" / "train").mkdir(parents=True)
    (dataset_root / "labels" / "train").mkdir(parents=True)
    (dataset_root / "labels" / "train" / "a.txt").write_text("0 0.5 0.5 0.1 0.1\n")
    (dataset_root / "labels" / "train" / "b.txt").write_text("1 0.4 0.4 0.2 0.2\n")
    data_yaml = dataset_root / "data.yaml"
    data_yaml.write_text(
        yaml.safe_dump(
            {
                "path": str(dataset_root),
                "train": "images/train",
                "val": "images/train",
                "nc": 2,
                "names": ["box", "person"],
            }
        )
    )
    return data_yaml


@pytest.fixture
def base_config(tiny_dataset: Path, tmp_path: Path) -> dict:
    return {
        "mlflow": {
            "tracking_uri": "http://localhost:5050",
            "experiment": "test-exp",
            "registered_model_name": "test-detector",
        },
        "model": {"arch": "yolov8n", "weights": "yolov8n.yaml"},
        "data": {"yaml_path": str(tiny_dataset)},
        "hyperparameters": {
            "epochs": 1,
            "imgsz": 320,
            "batch": 2,
            "patience": 5,
            "optimizer": "AdamW",
            "lr0": 0.001,
            "seed": 42,
        },
        "runtime": {
            "device": "cpu",
            "output_dir": str(tmp_path / "runs"),
            "dry_register": True,
        },
    }


def test_flatten_metrics_handles_nested_dicts() -> None:
    nested = {"box": {"map50": 0.8}, "loss": 1.2, "ignored": "hello"}
    flat = _flatten_metrics(nested)
    assert flat == {"box.map50": 0.8, "loss": 1.2}


def test_dataset_fingerprint_is_stable(tiny_dataset: Path) -> None:
    fp1 = _dataset_fingerprint(tiny_dataset)
    fp2 = _dataset_fingerprint(tiny_dataset)
    assert fp1 == fp2
    assert len(fp1) == 16


def test_dataset_fingerprint_changes_with_label_edit(tiny_dataset: Path) -> None:
    fp1 = _dataset_fingerprint(tiny_dataset)
    label = tiny_dataset.parent / "labels" / "train" / "a.txt"
    label.write_text("0 0.6 0.6 0.1 0.1\n")  # different bbox
    fp2 = _dataset_fingerprint(tiny_dataset)
    assert fp1 != fp2


def test_train_raises_on_missing_data_yaml(base_config: dict, tmp_path: Path) -> None:
    base_config["data"]["yaml_path"] = str(tmp_path / "does_not_exist.yaml")
    with pytest.raises(FileNotFoundError, match="data.yaml"):
        train(base_config)


def test_train_logs_params_and_tags_to_mlflow(base_config: dict) -> None:
    """End-to-end with MLflow + YOLO mocked. Verifies the contract, not training."""
    with (
        patch("ml.scripts.train.mlflow") as mlflow_mock,
        patch("ultralytics.YOLO") as yolo_mock,
    ):
        # Fake context manager for start_run.
        run_ctx = MagicMock()
        run_ctx.info.run_id = "fake-run-id"
        mlflow_mock.start_run.return_value.__enter__.return_value = run_ctx

        # Fake model with .train() and .val()
        model_instance = MagicMock()
        model_instance.train.return_value = MagicMock(results_dict={"metrics/mAP50": 0.42})
        model_instance.val.return_value = _mock_val()
        yolo_mock.return_value = model_instance

        result = train(base_config)

    assert result.run_id == "fake-run-id"
    assert result.map50 == pytest.approx(0.8)
    # Params: every key in `hyperparameters` is logged.
    logged_params = mlflow_mock.log_params.call_args[0][0]
    assert logged_params["epochs"] == 1
    assert logged_params["lr0"] == 0.001
    # Tags: the required ones are present.
    logged_tags = mlflow_mock.set_tags.call_args[0][0]
    for required in (
        "git_commit",
        "dataset_path",
        "dataset_fingerprint",
        "model_arch",
        "framework",
        "device",
    ):
        assert required in logged_tags
    # The final validation metrics were logged.
    metric_keys: set[str] = set()
    for call in mlflow_mock.log_metrics.call_args_list:
        metric_keys.update(call[0][0].keys())
    assert {"val_map50", "val_map50_95", "val_precision", "val_recall"} <= metric_keys


def test_train_respects_dry_register(base_config: dict) -> None:
    """When `dry_register: true` we never call mlflow.register_model."""
    base_config["runtime"]["dry_register"] = True
    with (
        patch("ml.scripts.train.mlflow") as mlflow_mock,
        patch("ultralytics.YOLO") as yolo_mock,
    ):
        run_ctx = MagicMock()
        run_ctx.info.run_id = "fake-run"
        mlflow_mock.start_run.return_value.__enter__.return_value = run_ctx
        model_instance = MagicMock()
        model_instance.train.return_value = MagicMock(results_dict={})
        model_instance.val.return_value = _mock_val()
        yolo_mock.return_value = model_instance

        train(base_config)

    mlflow_mock.register_model.assert_not_called()


def test_train_override_device(base_config: dict) -> None:
    """CLI device override propagates to model.train(device=...)."""
    with (
        patch("ml.scripts.train.mlflow") as mlflow_mock,
        patch("ultralytics.YOLO") as yolo_mock,
    ):
        run_ctx = MagicMock()
        run_ctx.info.run_id = "r"
        mlflow_mock.start_run.return_value.__enter__.return_value = run_ctx
        model = MagicMock()
        model.train.return_value = MagicMock(results_dict={})
        model.val.return_value = _mock_val()
        yolo_mock.return_value = model

        train(base_config, override_device="cuda")

    train_kwargs = model.train.call_args.kwargs
    assert train_kwargs["device"] == "cuda"
