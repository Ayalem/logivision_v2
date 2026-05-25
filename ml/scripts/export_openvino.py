"""Export an MLflow-registered model to OpenVINO IR (FP32 + INT8).

Pipeline:
    1. Resolve the run (via --run-id or --stage <Production|Staging>).
    2. Download `best.pt` from the run's artifacts.
    3. Call `model.export(format="openvino")` → FP32 IR.
    4. Build a calibration dataset (200 frames sampled with seed from the
       `dataset_path` tag of the run).
    5. Quantize FP32 → INT8 via NNCF.
    6. Validate both on the val split, compare mAP50.
    7. If `delta_map50 > 0.05`, abort with exit code 2 and DO NOT log anything.
    8. Otherwise log both directories back to the same MLflow run as
       artifacts under `openvino-fp32/` and `openvino-int8/`.

Usage:
    python -m ml.scripts.export_openvino --run-id <RUN>
    python -m ml.scripts.export_openvino --stage Production
"""

from __future__ import annotations

import argparse
import logging
import random
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    run_id: str
    fp32_dir: Path
    int8_dir: Path
    map50_fp32: float
    map50_int8: float
    delta_map50: float
    aborted: bool


class ExportError(Exception):
    """Raised when the export cannot proceed."""


def _resolve_run_id(client, model_name: str, run_id: str | None, stage: str | None) -> str:
    if run_id:
        return run_id
    if stage is None:
        raise ExportError("Pass either --run-id or --stage.")
    versions = client.search_model_versions(f"name='{model_name}'")
    matching = [v for v in versions if v.current_stage == stage]
    if not matching:
        raise ExportError(f"No version of {model_name!r} is in stage {stage!r}.")
    # Highest version number wins in case of ties.
    latest = max(matching, key=lambda v: int(v.version))
    return latest.run_id


def _download_best_weights(client, run_id: str, dest_dir: Path) -> Path:
    """Pull every artifact under `model/` and return the local best.pt path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    local_root = client.download_artifacts(run_id=run_id, path="model", dst_path=str(dest_dir))
    candidates = list(Path(local_root).rglob("best.pt"))
    if not candidates:
        raise ExportError(
            f"best.pt not found under run {run_id}'s model/ artifacts. "
            "Re-train with dry_register=False so the weights are logged."
        )
    return candidates[0]


def _sample_calibration_images(data_yaml: Path, n: int, seed: int = 42) -> list[Path]:
    """Pick `n` JPGs from the data.yaml's train split. Returns absolute paths."""
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    root = Path(data.get("path", data_yaml.parent)).resolve()
    train_dir = root / data["train"]
    images = sorted(
        p for p in train_dir.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if not images:
        raise ExportError(f"No images found in {train_dir}.")
    rng = random.Random(seed)
    rng.shuffle(images)
    return images[: min(n, len(images))]


def _export_fp32(weights: Path, imgsz: int = 640) -> Path:
    """Ultralytics writes `<weights-stem>_openvino_model/`. Return that dir."""
    from ultralytics import YOLO

    model = YOLO(str(weights))
    out = model.export(format="openvino", imgsz=imgsz, half=False)
    # `out` is the path to the .xml in recent ultralytics; the directory is its parent.
    fp32_dir = Path(out).parent if Path(out).suffix == ".xml" else Path(out)
    return fp32_dir.resolve()


def _quantize_int8(fp32_dir: Path, calibration_images: list[Path], imgsz: int = 640) -> Path:
    """Run NNCF post-training quantization. Returns directory containing best_int8.xml."""
    import cv2
    import nncf
    import numpy as np
    import openvino as ov

    xml_files = list(fp32_dir.glob("*.xml"))
    if not xml_files:
        raise ExportError(f"No .xml file in {fp32_dir}.")
    fp32_xml = xml_files[0]

    core = ov.Core()
    fp32_model = core.read_model(str(fp32_xml))

    def transform(image_path: Path) -> np.ndarray:
        img = cv2.imread(str(image_path))
        img = cv2.resize(img, (imgsz, imgsz))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.transpose(2, 0, 1).astype(np.float32) / 255.0  # CHW, [0,1]
        return np.expand_dims(img, axis=0)

    calib_dataset = nncf.Dataset(calibration_images, transform_fn=transform)
    int8_model = nncf.quantize(
        fp32_model,
        calib_dataset,
        subset_size=min(len(calibration_images), 200),
    )

    int8_dir = fp32_dir.parent / (fp32_dir.name.replace("_openvino_model", "_int8_openvino_model"))
    if int8_dir == fp32_dir:
        int8_dir = fp32_dir.parent / f"{fp32_dir.name}_int8"
    int8_dir.mkdir(parents=True, exist_ok=True)
    ov.save_model(int8_model, str(int8_dir / fp32_xml.name))
    return int8_dir.resolve()


def _measure_map50(weights_pt_or_xml: Path, data_yaml: Path, imgsz: int = 640) -> float:
    """Use Ultralytics' YOLO(...) wrapper which handles both .pt and OpenVINO dirs."""
    from ultralytics import YOLO

    model = YOLO(str(weights_pt_or_xml))
    results = model.val(data=str(data_yaml), imgsz=imgsz, verbose=False)
    return float(results.box.map50)


def export(
    run_id: str | None,
    stage: str | None,
    model_name: str,
    calib_size: int = 200,
    imgsz: int = 640,
    delta_map50_abort: float = 0.05,
    tracking_uri: str | None = None,
) -> ExportResult:
    import mlflow
    from mlflow.tracking import MlflowClient

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    resolved_run_id = _resolve_run_id(client, model_name, run_id, stage)
    run = client.get_run(resolved_run_id)
    data_yaml_str = run.data.tags.get("dataset_path")
    if not data_yaml_str:
        raise ExportError(
            f"Run {resolved_run_id} has no `dataset_path` tag — cannot locate val/train data."
        )
    data_yaml = Path(data_yaml_str)
    if not data_yaml.is_file():
        raise ExportError(f"Tagged data.yaml not found locally: {data_yaml}")

    with tempfile.TemporaryDirectory() as tmp:
        work_root = Path(tmp)
        weights = _download_best_weights(client, resolved_run_id, work_root / "weights")
        logger.info("Downloaded weights: %s", weights)

        fp32_dir = _export_fp32(weights, imgsz=imgsz)
        logger.info("FP32 export: %s", fp32_dir)

        calib_images = _sample_calibration_images(data_yaml, n=calib_size)
        int8_dir = _quantize_int8(fp32_dir, calib_images, imgsz=imgsz)
        logger.info("INT8 export: %s", int8_dir)

        map50_fp32 = _measure_map50(fp32_dir, data_yaml, imgsz=imgsz)
        map50_int8 = _measure_map50(int8_dir, data_yaml, imgsz=imgsz)
        delta = map50_fp32 - map50_int8
        logger.info("mAP50  fp32=%.4f  int8=%.4f  delta=%.4f", map50_fp32, map50_int8, delta)

        if delta > delta_map50_abort:
            return ExportResult(
                run_id=resolved_run_id,
                fp32_dir=fp32_dir,
                int8_dir=int8_dir,
                map50_fp32=map50_fp32,
                map50_int8=map50_int8,
                delta_map50=delta,
                aborted=True,
            )

        # Log artifacts back to the same MLflow run.
        with mlflow.start_run(run_id=resolved_run_id):
            mlflow.log_artifacts(str(fp32_dir), artifact_path="openvino-fp32")
            mlflow.log_artifacts(str(int8_dir), artifact_path="openvino-int8")
            mlflow.log_metric("openvino_fp32_map50", map50_fp32)
            mlflow.log_metric("openvino_int8_map50", map50_int8)
            mlflow.log_metric("openvino_int8_delta_map50", delta)

        # Persist the FP32 + INT8 dirs OUTSIDE the temp dir so the caller can use them.
        persist_root = data_yaml.parent.parent / "openvino" / resolved_run_id
        persist_root.mkdir(parents=True, exist_ok=True)
        final_fp32 = persist_root / "fp32"
        final_int8 = persist_root / "int8"
        if final_fp32.exists():
            shutil.rmtree(final_fp32)
        if final_int8.exists():
            shutil.rmtree(final_int8)
        shutil.copytree(fp32_dir, final_fp32)
        shutil.copytree(int8_dir, final_int8)

        return ExportResult(
            run_id=resolved_run_id,
            fp32_dir=final_fp32,
            int8_dir=final_int8,
            map50_fp32=map50_fp32,
            map50_int8=map50_int8,
            delta_map50=delta,
            aborted=False,
        )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--run-id", help="MLflow run to export.")
    src.add_argument(
        "--stage", choices=["Staging", "Production"], help="Pick latest in this stage."
    )
    parser.add_argument("--model-name", default="logivision-detector")
    parser.add_argument("--calib-size", type=int, default=200)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument(
        "--delta-map50-abort",
        type=float,
        default=0.05,
        help="Abort if FP32 mAP50 minus INT8 mAP50 exceeds this value.",
    )
    parser.add_argument("--tracking-uri", default=None)
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    try:
        result = export(
            run_id=args.run_id,
            stage=args.stage,
            model_name=args.model_name,
            calib_size=args.calib_size,
            imgsz=args.imgsz,
            delta_map50_abort=args.delta_map50_abort,
            tracking_uri=args.tracking_uri,
        )
    except ExportError as exc:
        logger.error("%s", exc)
        return 1
    if result.aborted:
        logger.error(
            "INT8 mAP50 regression too large (delta=%.4f > %.4f). Aborting; nothing logged.",
            result.delta_map50,
            args.delta_map50_abort,
        )
        return 2
    logger.info(
        "Export OK. fp32=%s  int8=%s  delta_map50=%.4f",
        result.fp32_dir,
        result.int8_dir,
        result.delta_map50,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
