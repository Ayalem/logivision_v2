"""Real end-to-end training run.

Marked `integration` — opt-in. Requires the MLOps stack (`./scripts/bootstrap.sh`)
to be reachable on the URIs declared in `.env` (defaults: MLflow `:5050`,
MinIO `:9000`).

What it does:
    1. Generate a 20-frame synthetic CVAT export.
    2. Import it into a YOLO layout (5/15/15 split rounded for 20 frames).
    3. Run a real `ml.scripts.train.train()` for 1 epoch at imgsz=128 batch=2
       on yolov8n architecture trained from scratch (no pretrained download).
    4. Pull the resulting MLflow run via MlflowClient and assert the
       contract: status FINISHED, params logged, required tags present,
       at least one validation metric.

Total wall time on a recent laptop CPU: ~30-90 s.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _load_env_file() -> None:
    """Mirror tests/integration/conftest.py — best-effort .env loader."""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), os.path.expandvars(value.strip()))


_load_env_file()
MLFLOW_URI = os.environ.get(
    "MLFLOW_TRACKING_URI", f"http://localhost:{os.environ.get('MLFLOW_PORT', '5050')}"
)


def test_full_train_cycle_logs_run_to_mlflow(tmp_path: Path) -> None:
    pytest.importorskip("mlflow")
    pytest.importorskip("ultralytics")

    from mlflow.tracking import MlflowClient

    from ml.scripts.import_annotations import import_export
    from ml.scripts.train import train
    from scripts.gen_synthetic_demo import build_export

    # 1. Build a tiny synthetic CVAT export.
    archive = build_export(n_frames=20, output_zip=tmp_path / "annotations.zip", seed=7)
    assert archive.is_file()

    # 2. Import to YOLO layout.
    dataset_dir = tmp_path / "dataset"
    import_export(archive=archive, output_dir=dataset_dir, seed=7)
    data_yaml = dataset_dir / "data.yaml"
    assert data_yaml.is_file()

    # 3. Train one epoch on CPU at tiny size. `weights: yolov8n.yaml` avoids
    #    network access for the pretrained download.
    config = {
        "mlflow": {
            "tracking_uri": MLFLOW_URI,
            "experiment": "warehouse-detection-integration",
            "registered_model_name": "logivision-detector-integration",
        },
        "model": {"arch": "yolov8n", "weights": "yolov8n.yaml"},
        "data": {"yaml_path": str(data_yaml)},
        "hyperparameters": {
            "epochs": 1,
            "imgsz": 128,
            "batch": 2,
            "patience": 1,
            "optimizer": "AdamW",
            "lr0": 0.001,
            "seed": 42,
            "mosaic": 0.0,
            "mixup": 0.0,
            "fliplr": 0.0,
            "flipud": 0.0,
            "degrees": 0.0,
        },
        "runtime": {
            "device": "cpu",
            "output_dir": str(tmp_path / "runs"),
            "dry_register": True,
        },
    }

    result = train(config)

    # 4. Verify the run in MLflow.
    client = MlflowClient(tracking_uri=MLFLOW_URI)
    run = client.get_run(result.run_id)

    assert run.info.status == "FINISHED"
    assert run.data.params["epochs"] == "1"
    assert run.data.params["imgsz"] == "128"

    required_tags = {
        "git_commit",
        "dataset_path",
        "dataset_fingerprint",
        "model_arch",
        "framework",
        "device",
    }
    assert required_tags <= set(
        run.data.tags
    ), f"missing tags: {required_tags - set(run.data.tags)}"
    assert run.data.tags["model_arch"] == "yolov8n"
    assert run.data.tags["framework"] == "ultralytics"

    # The validation metrics must exist; values can be ~0 on 20 frames + 1 epoch.
    assert "val_map50" in run.data.metrics
    assert "val_map50_95" in run.data.metrics
    assert "val_precision" in run.data.metrics
    assert "val_recall" in run.data.metrics
