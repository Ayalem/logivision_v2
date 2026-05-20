"""Train YOLOv8n on a warehouse dataset with MLflow tracking.

Usage:
    python -m ml.scripts.train --config ml/configs/yolov8n.yaml
    # On Colab / Kaggle:
    python -m ml.scripts.train --config ml/configs/yolov8n.yaml --device cuda

What gets logged to MLflow:
    params      — every hyperparameter
    tags        — git_commit, dvc_lock_hash, model_arch, framework, dataset_path
    metrics     — val_map50, val_map50_95, val_precision, val_recall
                  + per-epoch losses (from Ultralytics)
    artifacts   — best.pt / last.pt, args.yaml, confusion matrices, sample predictions
    model       — registered in `logivision-detector` (stage=None) unless `dry_register: true`
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mlflow
import yaml

logger = logging.getLogger(__name__)


@dataclass
class TrainResult:
    run_id: str
    map50: float
    map50_95: float
    output_dir: Path


def _get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _dataset_fingerprint(data_yaml_path: Path) -> str:
    """Stable hash of the dataset's data.yaml + every label file.

    Used as an MLflow tag so a run is reproducible to a specific data
    snapshot even when DVC pointers are not pushed.
    """
    h = hashlib.sha256()
    h.update(data_yaml_path.read_bytes())
    labels_root = data_yaml_path.parent / "labels"
    if labels_root.is_dir():
        for txt in sorted(labels_root.rglob("*.txt")):
            h.update(txt.relative_to(labels_root).as_posix().encode())
            h.update(txt.read_bytes())
    return h.hexdigest()[:16]


def _setup_mlflow(tracking_uri: str, experiment_name: str) -> None:
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)


def _flatten_metrics(d: dict[str, Any], prefix: str = "") -> dict[str, float]:
    """Ultralytics returns nested dicts; flatten to {dotted_key: float}."""
    out: dict[str, float] = {}
    for k, v in d.items():
        full = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(_flatten_metrics(v, full))
        elif isinstance(v, int | float):
            out[full.replace("/", ".")] = float(v)
    return out


def train(config: dict, override_device: str | None = None) -> TrainResult:
    """Run one training pass driven by `config`. Returns the MLflow run id."""
    from ultralytics import YOLO  # local import — keeps `--help` snappy

    data_yaml = Path(config["data"]["yaml_path"]).resolve()
    if not data_yaml.is_file():
        raise FileNotFoundError(
            f"data.yaml not found: {data_yaml}\n"
            "Hint: run `python -m ml.scripts.import_annotations --input ... "
            "--output datasets/processed/demo` first, or generate demo data with "
            "`python scripts/gen_synthetic_demo.py`."
        )

    _setup_mlflow(config["mlflow"]["tracking_uri"], config["mlflow"]["experiment"])

    hparams = dict(config["hyperparameters"])
    runtime = dict(config["runtime"])
    device = override_device or runtime.get("device", "cpu")

    with mlflow.start_run() as run:
        # 1. Log params + tags.
        mlflow.log_params(hparams)
        mlflow.set_tags(
            {
                "git_commit": _get_git_commit(),
                "dataset_path": str(data_yaml),
                "dataset_fingerprint": _dataset_fingerprint(data_yaml),
                "model_arch": config["model"]["arch"],
                "framework": "ultralytics",
                "device": device,
            }
        )

        # 2. Train.
        model = YOLO(config["model"]["weights"])
        output_dir = Path(runtime["output_dir"]).resolve()
        results = model.train(
            data=str(data_yaml),
            epochs=hparams["epochs"],
            imgsz=hparams["imgsz"],
            batch=hparams["batch"],
            patience=hparams["patience"],
            optimizer=hparams["optimizer"],
            lr0=hparams["lr0"],
            seed=hparams["seed"],
            mosaic=hparams.get("mosaic", 0.0),
            mixup=hparams.get("mixup", 0.0),
            hsv_h=hparams.get("hsv_h", 0.0),
            hsv_s=hparams.get("hsv_s", 0.0),
            hsv_v=hparams.get("hsv_v", 0.0),
            fliplr=hparams.get("fliplr", 0.5),
            flipud=hparams.get("flipud", 0.0),
            degrees=hparams.get("degrees", 0.0),
            device=device,
            project=str(output_dir),
            name=run.info.run_id,
            exist_ok=True,
            verbose=False,
        )

        # 3. Per-epoch metrics from Ultralytics' results dict.
        results_dict = getattr(results, "results_dict", {}) or {}
        for name, value in _flatten_metrics(results_dict).items():
            mlflow.log_metric(name, value)

        # 4. Final validation pass.
        val = model.val(data=str(data_yaml), verbose=False)
        map50 = float(val.box.map50)
        map50_95 = float(val.box.map)
        mlflow.log_metrics(
            {
                "val_map50": map50,
                "val_map50_95": map50_95,
                "val_precision": float(val.box.mp),
                "val_recall": float(val.box.mr),
            }
        )

        # 5. Artifacts — weights, args, training plots.
        run_dir = output_dir / run.info.run_id
        if run_dir.is_dir():
            mlflow.log_artifacts(str(run_dir), artifact_path="ultralytics-run")

        # 6. Register the model unless this is a dry run.
        if not runtime.get("dry_register", False):
            registered_name = config["mlflow"]["registered_model_name"]
            best_pt = run_dir / "weights" / "best.pt"
            if best_pt.is_file():
                mlflow.log_artifact(str(best_pt), artifact_path="model")
                model_uri = f"runs:/{run.info.run_id}/model/best.pt"
                try:
                    mlflow.register_model(model_uri=model_uri, name=registered_name)
                except (mlflow.exceptions.MlflowException, Exception) as exc:  # noqa: BLE001
                    logger.warning("Could not register model: %s", exc)
            else:
                logger.warning("best.pt not produced — skipping registry.")

        return TrainResult(
            run_id=run.info.run_id,
            map50=map50,
            map50_95=map50_95,
            output_dir=run_dir,
        )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, required=True, help="Path to a YAML config.")
    parser.add_argument(
        "--device",
        default=None,
        help="Override config.runtime.device (e.g. 'cuda', 'cpu').",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    result = train(config, override_device=args.device)
    logger.info("Run %s  map50=%.4f  map50_95=%.4f", result.run_id, result.map50, result.map50_95)
    logger.info("Artifacts under %s", result.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
