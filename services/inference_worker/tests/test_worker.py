"""Unit tests for the inference worker — Kafka + MinIO mocked."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.inference_worker.worker import (
    _parse_s3_uri,
    fetch_frame_bytes,
    make_detection_payload,
)


def test_parse_s3_uri_splits_bucket_and_key() -> None:
    bucket, key = _parse_s3_uri("s3://frames/cam01/2026-05-20/abc.jpg")
    assert bucket == "frames"
    assert key == "cam01/2026-05-20/abc.jpg"


@pytest.mark.parametrize("bad", ["http://x", "s3://only-bucket", "frames/x", ""])
def test_parse_s3_uri_rejects_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        _parse_s3_uri(bad)


def test_fetch_frame_bytes_calls_boto_get_object() -> None:
    s3 = MagicMock()
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"BYTES")}
    out = fetch_frame_bytes(s3, "s3://frames/cam01/x.jpg")
    s3.get_object.assert_called_once_with(Bucket="frames", Key="cam01/x.jpg")
    assert out == b"BYTES"


def test_make_detection_payload_shape() -> None:
    raw = {
        "frame_id": "F1",
        "camera_id": "C1",
        "timestamp_ms": 1234567890,
        "frame_uri": "s3://frames/C1/2026-05-20/F1.jpg",
    }
    detections = [
        {
            "class_id": 0,
            "class_name": "box",
            "confidence": 0.8,
            "x1": 1.0,
            "y1": 2.0,
            "x2": 50.0,
            "y2": 60.0,
        }
    ]
    payload = make_detection_payload(raw, detections, "v3/Production", 12.5)
    assert payload["frame_id"] == "F1"
    assert payload["camera_id"] == "C1"
    assert payload["model_version"] == "v3/Production"
    assert payload["inference_ms"] == 12.5
    assert payload["frame_uri"] == raw["frame_uri"]
    assert payload["detections"] == detections


def test_detect_on_image_bytes_handles_no_detections() -> None:
    """Empty results dict from YOLO → empty detections list."""
    from services.inference_worker.worker import detect_on_image_bytes

    fake_model = MagicMock()
    fake_model.names = {0: "box"}
    fake_model.predict.return_value = []

    # Provide a real PNG byte-stream so PIL.Image.open() doesn't fail.
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(0, 0, 0)).save(buf, format="PNG")

    out = detect_on_image_bytes(fake_model, buf.getvalue(), conf=0.1)
    assert out == []
    fake_model.predict.assert_called_once()
