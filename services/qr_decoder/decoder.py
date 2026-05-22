"""QR / barcode decoder microservice.

Reads `detections` from Kafka, looks at every detection whose
`class_name` matches one of {qr_code, barcode}, downloads the frame
JPEG from MinIO, crops the bounding box, runs pyzbar on the crop, and
publishes the decoded payload to a new Kafka topic `qr-decodes`.

Downstream consumers (CEP, the dashboard's zone-label lookup) treat the
decoded payload as **authoritative** for that detection's
(zone_id, category_id), overriding the static `infra/zones.yaml`
mapping. That's how the operator can re-label a zone by physically
moving a printed QR code — no config change.

Message contract (JSON, same Avro upgrade path as the other topics):

    input  detections  (one message per frame, may contain multiple
                        detections; we only act on QR/barcode rows)
    output qr-decodes  {decode_id, frame_id, camera_id, timestamp_ms,
                        track_id, class_name, bbox, payload, decoded_at_ms}

Idempotency: keyed by `frame_id` so duplicate publishes land in the
same partition. CEP dedups on `decode_id`.

Usage:
    KAFKA_BOOTSTRAP=localhost:9092 python -m services.qr_decoder.decoder
"""

from __future__ import annotations

import io
import json
import logging
import os
import signal
import time
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Detections whose `class_name` matches one of these get fed to pyzbar.
# Kept as a module-level constant so tests can verify the gate.
QR_CLASS_NAMES: frozenset[str] = frozenset(
    {"qr_code", "qrcode", "barcode", "ean13", "ean8", "code128"}
)


@dataclass
class DecoderConfig:
    bootstrap_servers: str = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    input_topic: str = os.environ.get("KAFKA_DETECTIONS_TOPIC", "detections")
    output_topic: str = os.environ.get("KAFKA_QR_DECODES_TOPIC", "qr-decodes")
    consumer_group: str = os.environ.get("KAFKA_CONSUMER_GROUP", "qr-decoders")
    minio_endpoint: str = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
    minio_access_key: str = os.environ.get("AWS_ACCESS_KEY_ID", "logivision")
    minio_secret_key: str = os.environ.get(
        "AWS_SECRET_ACCESS_KEY", "change-me-in-local-minimum-8-chars"
    )
    # Pad the bbox before decoding — QR codes near a bbox edge are
    # frequently truncated, and pyzbar fails silently on truncated quiet zones.
    bbox_padding_px: int = int(os.environ.get("QR_BBOX_PADDING_PX", "8"))


def _crop_bbox(
    image_bytes: bytes, bbox: tuple[float, float, float, float], padding_px: int
) -> bytes:
    """Crop the given bbox (with optional padding) from a JPEG byte stream.

    Returned PIL image is RGB JPEG bytes ready for pyzbar.
    """
    from PIL import Image

    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = pil.size
    x1, y1, x2, y2 = bbox
    # Pad and clamp to image bounds.
    x1 = max(0, int(x1) - padding_px)
    y1 = max(0, int(y1) - padding_px)
    x2 = min(w, int(x2) + padding_px)
    y2 = min(h, int(y2) + padding_px)
    if x2 <= x1 or y2 <= y1:
        # Degenerate bbox; return an empty 1x1 image instead of raising,
        # so the caller's error path stays the same as "decode failed".
        out = io.BytesIO()
        Image.new("RGB", (1, 1)).save(out, format="JPEG")
        return out.getvalue()
    cropped = pil.crop((x1, y1, x2, y2))
    out = io.BytesIO()
    cropped.save(out, format="JPEG", quality=90)
    return out.getvalue()


def decode_qr_crop(crop_bytes: bytes) -> list[dict]:
    """Run pyzbar on the cropped image bytes.

    Returns a list of `{payload: str, type: str, polygon: [(x, y)]}` —
    pyzbar can find multiple barcodes per image. Empty list when nothing
    decodes. Errors from missing libzbar shared lib (macOS without
    `brew install zbar`) raise at *import* time, not at call time, so
    the test suite can monkeypatch this whole function.
    """
    from PIL import Image
    from pyzbar.pyzbar import decode as zbar_decode

    pil = Image.open(io.BytesIO(crop_bytes))
    raw = zbar_decode(pil)
    out: list[dict] = []
    for code in raw:
        payload = code.data.decode("utf-8", errors="replace") if code.data else ""
        out.append(
            {
                "payload": payload,
                "type": getattr(code, "type", "QRCODE"),
                "polygon": [(p.x, p.y) for p in (code.polygon or [])],
            }
        )
    return out


def is_qr_detection(detection: dict) -> bool:
    """Gate: should we attempt to decode this detection?

    Match is case-insensitive. Centralised here so the CEP-side filter
    and the worker-side filter can never drift apart.
    """
    name = (detection.get("class_name") or "").lower().strip()
    return name in QR_CLASS_NAMES


def make_decode_payload(
    detection_msg: dict, detection: dict, decoded: dict, decoded_at_ms: int
) -> dict:
    """Shape the `qr-decodes` message. Keeps lineage to the frame + track."""
    return {
        "decode_id": str(uuid.uuid4()),
        "frame_id": detection_msg["frame_id"],
        "camera_id": detection_msg["camera_id"],
        "timestamp_ms": detection_msg["timestamp_ms"],
        "track_id": detection.get("track_id"),
        "class_name": detection.get("class_name"),
        "bbox": {
            "x1": detection["x1"],
            "y1": detection["y1"],
            "x2": detection["x2"],
            "y2": detection["y2"],
        },
        "payload": decoded.get("payload", ""),
        "code_type": decoded.get("type", "QRCODE"),
        "decoded_at_ms": decoded_at_ms,
    }


def process_one(
    detection_msg: dict,
    s3_client: Any,
    fetch_frame: Any,
    decode_fn: Any,
    config: DecoderConfig,
) -> list[dict]:
    """Pure (testable) function: take one `detections` message, return all
    `qr-decodes` payloads it generates.

    Arguments are injected so tests can pass mocks for `s3_client`,
    `fetch_frame`, and `decode_fn`. The Kafka loop in `run()` calls this
    with real implementations.
    """
    out: list[dict] = []
    qr_dets = [d for d in detection_msg.get("detections", []) if is_qr_detection(d)]
    if not qr_dets:
        return out

    try:
        image_bytes = fetch_frame(s3_client, detection_msg["frame_uri"])
    except Exception:  # noqa: BLE001
        logger.exception("Failed to fetch frame %s for QR decode", detection_msg.get("frame_id"))
        return out

    for d in qr_dets:
        crop = _crop_bbox(
            image_bytes,
            (d["x1"], d["y1"], d["x2"], d["y2"]),
            padding_px=config.bbox_padding_px,
        )
        decoded_list = decode_fn(crop)
        if not decoded_list:
            continue
        # If a bbox contains multiple codes, emit one message per code.
        for dc in decoded_list:
            out.append(make_decode_payload(detection_msg, d, dc, int(time.time() * 1000)))
    return out


def run(config: DecoderConfig, stop_after: int | None = None) -> int:
    """Main Kafka consumer loop. Returns the number of decodes published."""
    import boto3
    from confluent_kafka import Consumer, Producer

    from services.inference_worker.worker import fetch_frame_bytes  # reuse helper

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
            "auto.offset.reset": "latest",  # don't replay history
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([config.input_topic])
    producer = Producer({"bootstrap.servers": config.bootstrap_servers})

    running = True
    n_decodes = 0

    def _shutdown(*_a: int) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info(
        "qr-decoder started: in=%s out=%s gate_classes=%s",
        config.input_topic,
        config.output_topic,
        sorted(QR_CLASS_NAMES),
    )

    try:
        while running:
            msg = consumer.poll(timeout=1.0)
            if msg is None or msg.error():
                continue
            try:
                detection_msg = json.loads(msg.value().decode("utf-8"))
                decodes = process_one(detection_msg, s3, fetch_frame_bytes, decode_qr_crop, config)
                for d in decodes:
                    producer.produce(
                        config.output_topic,
                        key=d["frame_id"].encode(),
                        value=json.dumps(d).encode(),
                    )
                    n_decodes += 1
                if decodes:
                    producer.poll(0)
                consumer.commit(msg, asynchronous=False)
                if stop_after is not None and n_decodes >= stop_after:
                    break
            except Exception:  # noqa: BLE001
                logger.exception("Failed to process detection message")
    finally:
        producer.flush(timeout=5.0)
        consumer.close()
    return n_decodes


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return 0 if run(DecoderConfig()) >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
