"""Read frames from a source (file / RTSP / dir) → upload to MinIO → publish to Kafka.

The source can be:
    - a single .mp4 / .avi file (most reliable for local testing)
    - an RTSP URL (`rtsp://host:port/stream`) — pulled via OpenCV
    - a directory of JPGs (each file becomes one frame, useful for replays)

Per frame:
    1. JPEG-encode at `quality` (default 85) and upload to MinIO under
       `s3://frames/<camera_id>/<YYYYMMDD>/<frame_id>.jpg`
    2. Publish a `RawFrame`-shaped JSON message to Kafka `raw-frames`,
       partition key = `frame_id` so a single frame always lands on the
       same partition (Flink can dedup on frame_id).

Throughput-control:
    --fps N    target N frames / second (drop the rest, never block)
    --max M    cap total frames emitted (useful for smoke tests)

Usage:
    python -m services.frame_grabber.grabber \\
        --source datasets/raw/videos/Camera3.mp4 \\
        --camera-id CAM03 --fps 2 --max 50
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GrabberConfig:
    source: str
    camera_id: str
    target_fps: float = 2.0
    max_frames: int | None = None
    jpeg_quality: int = 85
    bootstrap_servers: str = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    output_topic: str = os.environ.get("KAFKA_RAW_FRAMES_TOPIC", "raw-frames")
    minio_endpoint: str = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
    minio_bucket: str = os.environ.get("BUCKET_FRAMES", "frames")
    minio_access_key: str = os.environ.get("AWS_ACCESS_KEY_ID", "logivision")
    minio_secret_key: str = os.environ.get(
        "AWS_SECRET_ACCESS_KEY", "change-me-in-local-minimum-8-chars"
    )


def _iter_video_frames(source: str, target_fps: float) -> Any:
    """Yield (np.ndarray BGR, source_fps) from a video file or RTSP url."""
    import cv2

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {source}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    stride = max(1, round(src_fps / target_fps)) if target_fps > 0 else 1
    idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % stride == 0:
                yield frame
            idx += 1
    finally:
        cap.release()


def _iter_dir_frames(source: str) -> Any:
    """Yield JPGs from a directory in sorted order."""
    import cv2

    root = Path(source)
    if not root.is_dir():
        raise RuntimeError(f"Not a directory: {source}")
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            img = cv2.imread(str(path))
            if img is not None:
                yield img


def build_frame_uri(
    bucket: str, camera_id: str, frame_id: str, when: datetime | None = None
) -> str:
    """`s3://<bucket>/<camera-id>/YYYYMMDD/<frame_id>.jpg`."""
    when = when or datetime.now(UTC)
    return f"s3://{bucket}/{camera_id}/{when.strftime('%Y%m%d')}/{frame_id}.jpg"


def make_raw_frame_message(
    *,
    camera_id: str,
    frame_id: str,
    timestamp_ms: int,
    width: int,
    height: int,
    frame_uri: str,
) -> dict:
    return {
        "frame_id": frame_id,
        "camera_id": camera_id,
        "timestamp_ms": timestamp_ms,
        "width": width,
        "height": height,
        "frame_uri": frame_uri,
    }


def _ensure_bucket(s3_client: Any, bucket: str) -> None:
    try:
        s3_client.head_bucket(Bucket=bucket)
    except Exception:  # noqa: BLE001
        try:
            s3_client.create_bucket(Bucket=bucket)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not auto-create bucket %s: %s", bucket, exc)


def run(config: GrabberConfig) -> int:
    """Push frames through the pipeline. Returns the number of frames published."""
    import boto3
    import cv2
    from confluent_kafka import Producer

    s3 = boto3.client(
        "s3",
        endpoint_url=config.minio_endpoint,
        aws_access_key_id=config.minio_access_key,
        aws_secret_access_key=config.minio_secret_key,
    )
    _ensure_bucket(s3, config.minio_bucket)
    producer = Producer({"bootstrap.servers": config.bootstrap_servers})

    iterator = (
        _iter_dir_frames(config.source)
        if Path(config.source).is_dir()
        else _iter_video_frames(config.source, config.target_fps)
    )

    published = 0
    target_interval = 1.0 / config.target_fps if config.target_fps > 0 else 0.0
    last_emit = 0.0
    for frame in iterator:
        if config.max_frames and published >= config.max_frames:
            break
        # Throttle when reading from a dir (no native fps).
        if Path(config.source).is_dir() and target_interval > 0:
            now = time.perf_counter()
            elapsed = now - last_emit
            if last_emit and elapsed < target_interval:
                time.sleep(target_interval - elapsed)
            last_emit = time.perf_counter()

        frame_id = str(uuid.uuid4())
        timestamp_ms = int(time.time() * 1000)
        height, width = frame.shape[:2]
        ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), config.jpeg_quality])
        if not ok:
            logger.warning("JPEG encode failed for %s", frame_id)
            continue
        frame_uri = build_frame_uri(config.minio_bucket, config.camera_id, frame_id)
        key = frame_uri[len(f"s3://{config.minio_bucket}/") :]
        s3.put_object(
            Bucket=config.minio_bucket,
            Key=key,
            Body=jpg.tobytes(),
            ContentType="image/jpeg",
        )
        message = make_raw_frame_message(
            camera_id=config.camera_id,
            frame_id=frame_id,
            timestamp_ms=timestamp_ms,
            width=int(width),
            height=int(height),
            frame_uri=frame_uri,
        )
        producer.produce(
            config.output_topic,
            key=frame_id.encode(),
            value=json.dumps(message).encode(),
        )
        producer.poll(0)
        published += 1
        if published % 10 == 0:
            logger.info("published %d frames", published)
    producer.flush(timeout=5.0)
    return published


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--source", required=True, help="Video file, RTSP URL, or directory of JPGs."
    )
    parser.add_argument("--camera-id", default="CAM01")
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--max", type=int, default=None, help="Cap total frames emitted.")
    parser.add_argument("--jpeg-quality", type=int, default=85)
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    cfg = GrabberConfig(
        source=args.source,
        camera_id=args.camera_id,
        target_fps=args.fps,
        max_frames=args.max,
        jpeg_quality=args.jpeg_quality,
    )
    logger.info("starting frame-grabber for %s -> %s", cfg.source, cfg.output_topic)
    n = run(cfg)
    logger.info("published %d frames", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
