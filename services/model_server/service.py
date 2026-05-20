"""BentoML service that serves the LOGIVISION detector.

Model resolution priority at startup:
    1. MLflow Registry, latest version in `Production` (configurable via
       `MODEL_STAGE` env var).
    2. MLflow Registry, latest version in `Staging` if no Production exists.
    3. Local `yolov8n.pt` fallback (Ultralytics will download it on first use).

The chosen variant is recorded in `model_version` of every response so a
caller can attribute predictions to a specific run.

Run locally:
    uv run bentoml serve services.model_server.service:WarehouseDetector
Then:
    curl -F 'image=@frame.jpg' http://localhost:3000/detect
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path

import bentoml
import numpy as np
from PIL.Image import Image as PILImage
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = os.environ.get("MODEL_NAME", "logivision-detector")
DEFAULT_STAGE = os.environ.get("MODEL_STAGE", "Production")
DEFAULT_FALLBACK = os.environ.get("MODEL_FALLBACK", "yolov8n.pt")
DEFAULT_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5050")
DEFAULT_CONF = float(os.environ.get("DETECTION_CONF", "0.25"))


class Detection(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2] in pixel coords on the input image


class InferenceResponse(BaseModel):
    detections: list[Detection]
    inference_ms: float
    model_version: str


def resolve_model_weights(
    model_name: str = DEFAULT_MODEL_NAME,
    stage: str = DEFAULT_STAGE,
    fallback: str = DEFAULT_FALLBACK,
    tracking_uri: str = DEFAULT_TRACKING_URI,
    download_dir: Path | None = None,
) -> tuple[str, str]:
    """Return `(local_path, version_label)` for the model to serve."""
    try:
        from mlflow.tracking import MlflowClient
    except ImportError:
        logger.warning("mlflow not installed; using fallback %s", fallback)
        return fallback, f"fallback:{fallback}"

    try:
        client = MlflowClient(tracking_uri=tracking_uri)
        versions = client.search_model_versions(f"name='{model_name}'")
    except Exception as exc:  # noqa: BLE001
        logger.warning("MLflow unreachable (%s); using fallback %s", exc, fallback)
        return fallback, f"fallback:{fallback}"

    candidates = sorted(
        (v for v in versions if v.current_stage == stage),
        key=lambda v: int(v.version),
        reverse=True,
    )
    if not candidates and stage == "Production":
        # Soft fallback: Staging is acceptable if nothing is in Production yet.
        candidates = sorted(
            (v for v in versions if v.current_stage == "Staging"),
            key=lambda v: int(v.version),
            reverse=True,
        )
        if candidates:
            stage = "Staging"

    if not candidates:
        logger.warning(
            "No version of %r in stage %s; using fallback %s", model_name, stage, fallback
        )
        return fallback, f"fallback:{fallback}"

    mv = candidates[0]
    work = Path(download_dir or tempfile.mkdtemp(prefix="logivision-model-"))
    work.mkdir(parents=True, exist_ok=True)
    try:
        local_root = client.download_artifacts(run_id=mv.run_id, path="model", dst_path=str(work))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not download model/ for run %s (%s); fallback.", mv.run_id, exc)
        return fallback, f"fallback:{fallback}"

    pt = next(Path(local_root).rglob("best.pt"), None)
    if pt is None:
        logger.warning("best.pt not found under run %s; fallback.", mv.run_id)
        return fallback, f"fallback:{fallback}"

    return str(pt), f"{model_name}/v{mv.version}/{stage}"


@bentoml.service(
    name="warehouse_detector",
    resources={"cpu": "2"},
    traffic={"timeout": 10},
)
class WarehouseDetector:
    """YOLO detector served via BentoML. Loads the latest Production version on init."""

    def __init__(self) -> None:
        from ultralytics import YOLO

        weights, version_label = resolve_model_weights()
        logger.info("Loading model: %s (%s)", weights, version_label)
        self.model = YOLO(weights)
        self.model_version = version_label
        # Class id -> human-readable name (Ultralytics provides this on the model).
        self.class_names: dict[int, str] = dict(getattr(self.model, "names", {}))

    @bentoml.api
    def detect(self, image: PILImage, conf: float = DEFAULT_CONF) -> InferenceResponse:
        """Run detection on a single image. `conf` is the minimum confidence."""
        start = time.perf_counter()
        np_image = np.array(image.convert("RGB"))
        results = self.model.predict(np_image, conf=conf, verbose=False)
        detections: list[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None or boxes.xyxy is None:
                continue
            xyxy = boxes.xyxy.cpu().numpy().tolist()
            confs = boxes.conf.cpu().numpy().tolist()
            classes = boxes.cls.cpu().numpy().astype(int).tolist()
            for (x1, y1, x2, y2), c, cls_id in zip(xyxy, confs, classes, strict=False):
                detections.append(
                    Detection(
                        class_id=int(cls_id),
                        class_name=self.class_names.get(int(cls_id), str(cls_id)),
                        confidence=float(c),
                        bbox=[float(x1), float(y1), float(x2), float(y2)],
                    )
                )
        return InferenceResponse(
            detections=detections,
            inference_ms=(time.perf_counter() - start) * 1000.0,
            model_version=self.model_version,
        )

    @bentoml.api
    def health(self) -> dict:
        return {"status": "ok", "model_version": self.model_version}
