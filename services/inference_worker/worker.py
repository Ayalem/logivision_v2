"""Consume `raw-frames`, run inference, publish to `detections`.

This is a thin async wrapper around the existing BentoML detector logic
(re-uses `services.model_server.service.resolve_model_weights`). The
worker is designed to scale horizontally — N workers all in consumer
group `inference-workers`, Kafka partitioning gives ordering per frame.

Message contract (JSON for now; Avro upgrade in T2.0):
    input  raw-frames   {frame_id, camera_id, timestamp_ms, width, height, frame_uri}
    output detections   {frame_id, camera_id, timestamp_ms, model_version,
                         inference_ms, frame_uri, detections: [{class_id, class_name,
                         confidence, x1, y1, x2, y2}]}

Idempotency: the producer uses `frame_id` as the Kafka key so any duplicate
publish lands in the same partition; downstream (Flink) dedups on frame_id.

Usage:
    KAFKA_BOOTSTRAP=localhost:9092 \\
    MLFLOW_TRACKING_URI=http://localhost:5050 \\
    python -m services.inference_worker.worker
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    bootstrap_servers: str = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    input_topic: str = os.environ.get("KAFKA_INPUT_TOPIC", "raw-frames")
    output_topic: str = os.environ.get("KAFKA_OUTPUT_TOPIC", "detections")
    consumer_group: str = os.environ.get("KAFKA_CONSUMER_GROUP", "inference-workers")
    minio_endpoint: str = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
    minio_access_key: str = os.environ.get("AWS_ACCESS_KEY_ID", "logivision")
    minio_secret_key: str = os.environ.get(
        "AWS_SECRET_ACCESS_KEY", "change-me-in-local-minimum-8-chars"
    )
    detection_conf: float = float(os.environ.get("DETECTION_CONF", "0.25"))


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    """`s3://bucket/key/path` → ('bucket', 'key/path')."""
    if not uri.startswith("s3://"):
        raise ValueError(f"Expected s3:// URI, got {uri!r}")
    body = uri[len("s3://") :]
    bucket, _, key = body.partition("/")
    if not bucket or not key:
        raise ValueError(f"Malformed s3 URI: {uri!r}")
    return bucket, key


def fetch_frame_bytes(s3_client: Any, frame_uri: str) -> bytes:
    bucket, key = _parse_s3_uri(frame_uri)
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def make_detection_payload(
    raw: dict, detections: list[dict], model_version: str, inference_ms: float
) -> dict:
    return {
        "frame_id": raw["frame_id"],
        "camera_id": raw["camera_id"],
        "timestamp_ms": raw["timestamp_ms"],
        "model_version": model_version,
        "inference_ms": inference_ms,
        "frame_uri": raw["frame_uri"],
        "detections": detections,
    }


def detect_on_image_bytes(model: Any, image_bytes: bytes, conf: float) -> list[dict]:
    """Run YOLO inference on raw bytes and return YOLO-shape detections.

    Each detection is a dict with class_id / class_name / confidence /
    bounding-box. **No tracking here** — tracking is a separate step in
    `apply_tracker()` so that the two concerns stay testable in isolation.
    """
    import io

    import numpy as np
    from PIL import Image

    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    np_image = np.array(pil)
    results = model.predict(np_image, conf=conf, verbose=False)
    out: list[dict] = []
    names = dict(getattr(model, "names", {}))
    for result in results:
        boxes = result.boxes
        if boxes is None or boxes.xyxy is None:
            continue
        xyxy = boxes.xyxy.cpu().numpy().tolist()
        confs = boxes.conf.cpu().numpy().tolist()
        classes = boxes.cls.cpu().numpy().astype(int).tolist()
        for (x1, y1, x2, y2), c, cls_id in zip(xyxy, confs, classes, strict=False):
            out.append(
                {
                    "class_id": int(cls_id),
                    "class_name": names.get(int(cls_id), str(cls_id)),
                    "confidence": float(c),
                    "x1": float(x1),
                    "y1": float(y1),
                    "x2": float(x2),
                    "y2": float(y2),
                }
            )
    return out


# Per-camera ByteTrack state. Each camera_id gets its own tracker so that
# track_ids stay locally consistent without single-camera sequences bleeding
# into one another. Reset on worker restart (acceptable — Kafka rebalance
# will reassign partitions and the next frames seed new tracks anyway).
_TRACKERS: dict[str, Any] = {}


def _get_tracker(camera_id: str):
    """Lazy-init one `trackers.ByteTrackTracker` per camera.

    The `trackers` package (Roboflow, replaces deprecated supervision.ByteTrack)
    keeps its own internal state — we instantiate one per camera_id so a
    forklift at camera A never collides with a forklift at camera B in
    the ID assignment.
    """
    if camera_id in _TRACKERS:
        return _TRACKERS[camera_id]
    from trackers import ByteTrackTracker

    # Defaults tuned for our 5 fps warehouse stream:
    #   track_activation_threshold = 0.25  → match D-conf threshold
    #   lost_track_buffer          = 30    → tolerate ~6 s of occlusion
    #   minimum_consecutive_frames = 2     → confirm a track after 2 hits
    #   minimum_iou_threshold      = 0.1   → loose IoU for slow-moving boxes
    #   frame_rate                 = 5     → our nominal grabber FPS
    _TRACKERS[camera_id] = ByteTrackTracker(
        track_activation_threshold=0.25,
        lost_track_buffer=30,
        minimum_consecutive_frames=2,
        minimum_iou_threshold=0.1,
        frame_rate=5,
    )
    return _TRACKERS[camera_id]


def apply_tracker(detections: list[dict], camera_id: str) -> list[dict]:
    """Add a persistent integer `track_id` to each detection via ByteTrack.

    Detections that ByteTrack hasn't (yet) confirmed as a track keep no
    `track_id` key. CEP downstream uses its presence/absence to decide
    whether to run stateful rules (stationary, fall) on that detection.

    Empty input → empty output. Side effect: updates per-camera tracker
    state in `_TRACKERS`.
    """
    if not detections:
        return detections

    import numpy as np
    import supervision as sv

    xyxy = np.array([[d["x1"], d["y1"], d["x2"], d["y2"]] for d in detections], dtype=np.float32)
    conf = np.array([d["confidence"] for d in detections], dtype=np.float32)
    cls = np.array([d["class_id"] for d in detections], dtype=int)

    sv_dets = sv.Detections(xyxy=xyxy, confidence=conf, class_id=cls)
    tracked = _get_tracker(camera_id).update(sv_dets)

    # Re-match tracked rows back to our original dict objects by xyxy.
    # Rounding to one decimal keeps a small tolerance against float drift
    # the tracker may introduce.
    by_xyxy: dict[tuple, dict] = {
        tuple(round(v, 1) for v in (d["x1"], d["y1"], d["x2"], d["y2"])): d for d in detections
    }
    out: list[dict] = []
    for i in range(len(tracked.xyxy)):
        key = tuple(round(float(v), 1) for v in tracked.xyxy[i])
        original = by_xyxy.get(key)
        if original is None:
            # Tracker returned a row we cannot reconcile — drop it rather
            # than guess. Avoids assigning the wrong class to a track.
            continue
        clean = dict(original)
        tid_raw = tracked.tracker_id[i] if tracked.tracker_id is not None else None
        if tid_raw is not None and int(tid_raw) >= 0:
            clean["track_id"] = int(tid_raw)
        out.append(clean)
    return out


def run(config: WorkerConfig, stop_after: int | None = None) -> int:
    """Main worker loop. Returns the number of frames processed.

    `stop_after` is mostly for tests — when set, the loop exits after that
    many successful inferences.
    """
    # Local imports to keep `--help` fast.
    import boto3
    from confluent_kafka import Consumer, Producer

    from services.model_server.service import resolve_model_weights

    weights, model_version = resolve_model_weights(
        tracking_uri=os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5050"),
    )
    from ultralytics import YOLO

    logger.info("Loading model: %s (%s)", weights, model_version)
    model = YOLO(weights)

    s3 = boto3.client(
        "s3",
        endpoint_url=config.minio_endpoint,
        aws_access_key_id=config.minio_access_key,
        aws_secret_access_key=config.minio_secret_key,
    )

    consumer = Consumer(
        {
            "bootstrap.servers": config.bootstrap_servers,
            "group.id": config.consumer_group,
            # `earliest` so a freshly-started worker replays any frames
            # already in the topic. Production deployments may flip to
            # `latest` once a fleet of workers is steady-state.
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([config.input_topic])
    producer = Producer({"bootstrap.servers": config.bootstrap_servers})

    processed = 0
    running = True

    def _shutdown(*_signum: int) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while running:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                logger.warning("consumer error: %s", msg.error())
                continue
            try:
                raw = json.loads(msg.value().decode("utf-8"))
                image_bytes = fetch_frame_bytes(s3, raw["frame_uri"])
                started = time.perf_counter()
                detections = detect_on_image_bytes(model, image_bytes, config.detection_conf)
                # ByteTrack step: detections gain a persistent `track_id`.
                # Done after detection so the function stays single-purpose
                # and the tracker can be unit-tested without a model.
                detections = apply_tracker(detections, raw.get("camera_id", "UNKNOWN"))
                payload = make_detection_payload(
                    raw, detections, model_version, (time.perf_counter() - started) * 1000.0
                )
                producer.produce(
                    config.output_topic,
                    key=raw["frame_id"].encode(),
                    value=json.dumps(payload).encode(),
                )
                producer.poll(0)
                consumer.commit(msg, asynchronous=False)
                processed += 1
                if processed % 10 == 0:
                    logger.info("processed %d frames", processed)
                if stop_after is not None and processed >= stop_after:
                    break
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to process message: %s", exc)
                # Skip the bad message — its offset is NOT committed so it
                # will be retried; production should send to a DLQ instead.
    finally:
        producer.flush(timeout=5.0)
        consumer.close()
    return processed


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001 — reserved for argparse later
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = WorkerConfig()
    logger.info(
        "starting inference worker: bootstrap=%s group=%s in=%s out=%s",
        config.bootstrap_servers,
        config.consumer_group,
        config.input_topic,
        config.output_topic,
    )
    n = run(config)
    logger.info("processed %d frames before shutdown", n)
    return 0


# Re-export for type-checkers.
__all__ = [
    "WorkerConfig",
    "make_detection_payload",
    "detect_on_image_bytes",
    "fetch_frame_bytes",
    "run",
]


# Silence unused-import warnings.
_ = Path


if __name__ == "__main__":
    sys.exit(main())
