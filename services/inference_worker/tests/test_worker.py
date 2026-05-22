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


# ---------- ByteTrack integration ---------------------------------------


def _make_det(x1: float, y1: float, x2: float, y2: float, cls: int = 0, conf: float = 0.85) -> dict:
    return {
        "class_id": cls,
        "class_name": "box",
        "confidence": conf,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
    }


def test_apply_tracker_empty_input_returns_empty(monkeypatch) -> None:
    """Zero detections → zero output, no tracker created."""
    from services.inference_worker.worker import _TRACKERS, apply_tracker

    monkeypatch.setattr(
        "services.inference_worker.worker._TRACKERS", _TRACKERS.copy(), raising=True
    )
    assert apply_tracker([], "CAM_EMPTY") == []


def test_apply_tracker_assigns_persistent_track_id_across_frames() -> None:
    """A detection at almost the same position 3 frames in a row keeps the SAME track_id."""
    from services.inference_worker.worker import _TRACKERS, apply_tracker

    cam = "CAM_TRACKER_TEST"
    _TRACKERS.pop(cam, None)  # fresh state for the test

    # Three frames, same object barely moving — tracker should give one ID.
    track_ids: list[int] = []
    for x_off in (0, 2, 4):
        result = apply_tracker([_make_det(100 + x_off, 100, 200 + x_off, 200, conf=0.9)], cam)
        if result and "track_id" in result[0]:
            track_ids.append(result[0]["track_id"])

    # ByteTrack needs ≥ 2 hits to confirm a track. After 3 frames at least
    # 2 of the rows must have the same track_id.
    assert len(track_ids) >= 2, f"tracker dropped too many frames: {track_ids}"
    assert track_ids[0] == track_ids[-1], f"track_id changed across frames: {track_ids}"


def test_apply_tracker_isolates_state_per_camera() -> None:
    """Two cameras can't share track IDs — they are independent ByteTrack instances."""
    from services.inference_worker.worker import _TRACKERS, apply_tracker

    _TRACKERS.pop("CAM_A", None)
    _TRACKERS.pop("CAM_B", None)

    # Same bbox on two different cameras 3 frames each.
    for _ in range(3):
        apply_tracker([_make_det(50, 50, 150, 150)], "CAM_A")
        apply_tracker([_make_det(50, 50, 150, 150)], "CAM_B")

    assert "CAM_A" in _TRACKERS
    assert "CAM_B" in _TRACKERS
    # Each tracker is a different object (independent state).
    assert _TRACKERS["CAM_A"] is not _TRACKERS["CAM_B"]


def test_apply_tracker_preserves_class_info() -> None:
    """The tracker must not drop class_id / class_name / confidence."""
    from services.inference_worker.worker import _TRACKERS, apply_tracker

    cam = "CAM_PRESERVE"
    _TRACKERS.pop(cam, None)

    # Warm up the tracker (needs ≥ 2 frames to confirm).
    for _ in range(3):
        out = apply_tracker([_make_det(10, 10, 50, 50, cls=2, conf=0.91)], cam)

    assert out, "no detections came back from the tracker"
    d = out[0]
    assert d["class_id"] == 2
    assert d["class_name"] == "box"
    assert d["confidence"] == 0.91
    assert "track_id" in d
    assert isinstance(d["track_id"], int)
