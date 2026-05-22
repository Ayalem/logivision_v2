"""Unit tests for services/qr_decoder/decoder.py — fully mocked, no Kafka or MinIO."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

from PIL import Image

from services.qr_decoder.decoder import (
    DecoderConfig,
    _crop_bbox,
    is_qr_detection,
    make_decode_payload,
    process_one,
)


def _png_bytes(width: int = 320, height: int = 240, color: tuple = (255, 255, 255)) -> bytes:
    """Helper: render a solid-colour PNG to bytes."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ---------- gating ----------------------------------------------------------


def test_is_qr_detection_matches_canonical_names() -> None:
    for name in ("qr_code", "QR_CODE", "qrcode", "barcode", "code128", "EAN13"):
        assert is_qr_detection({"class_name": name}), f"should accept {name}"


def test_is_qr_detection_rejects_non_qr_classes() -> None:
    for name in ("box", "person", "forklift", "pallet", ""):
        assert not is_qr_detection({"class_name": name}), f"should reject {name}"


def test_is_qr_detection_handles_missing_class_name() -> None:
    assert not is_qr_detection({})
    assert not is_qr_detection({"class_name": None})


# ---------- bbox cropping ---------------------------------------------------


def test_crop_bbox_returns_jpeg_bytes_within_image_bounds() -> None:
    img_bytes = _png_bytes(400, 300)
    out = _crop_bbox(img_bytes, (50.0, 60.0, 200.0, 250.0), padding_px=0)
    assert out  # non-empty
    # Round-trip: JPEG with same dims as the bbox.
    cropped = Image.open(io.BytesIO(out))
    assert cropped.size == (150, 190)


def test_crop_bbox_padding_extends_then_clamps_to_image() -> None:
    img_bytes = _png_bytes(100, 100)
    # bbox at the image corner; padding should clamp to (0, 0, 100, 100).
    out = _crop_bbox(img_bytes, (0.0, 0.0, 30.0, 30.0), padding_px=200)
    cropped = Image.open(io.BytesIO(out))
    assert cropped.size == (100, 100)  # clamped


def test_crop_bbox_degenerate_returns_1x1_not_raise() -> None:
    img_bytes = _png_bytes(100, 100)
    # x2 < x1 → degenerate, must NOT raise.
    out = _crop_bbox(img_bytes, (50.0, 50.0, 40.0, 40.0), padding_px=0)
    cropped = Image.open(io.BytesIO(out))
    assert cropped.size == (1, 1)


# ---------- payload shape ---------------------------------------------------


def test_make_decode_payload_carries_lineage() -> None:
    detection_msg = {
        "frame_id": "F1",
        "camera_id": "CAM01",
        "timestamp_ms": 1700000000000,
        "frame_uri": "s3://frames/CAM01/x.jpg",
    }
    detection = {
        "class_name": "qr_code",
        "track_id": 42,
        "x1": 10,
        "y1": 20,
        "x2": 110,
        "y2": 120,
    }
    decoded = {"payload": "ZONE_A1:CAT_RECEPTION", "type": "QRCODE"}
    out = make_decode_payload(detection_msg, detection, decoded, decoded_at_ms=1700000001000)

    assert out["frame_id"] == "F1"
    assert out["camera_id"] == "CAM01"
    assert out["track_id"] == 42
    assert out["bbox"] == {"x1": 10, "y1": 20, "x2": 110, "y2": 120}
    assert out["payload"] == "ZONE_A1:CAT_RECEPTION"
    assert out["code_type"] == "QRCODE"
    assert out["decoded_at_ms"] == 1700000001000
    assert out["decode_id"]  # uuid present


# ---------- process_one end-to-end (with mocks) -----------------------------


def _detection_msg(*, dets: list[dict]) -> dict:
    return {
        "frame_id": "F1",
        "camera_id": "CAM01",
        "timestamp_ms": 1700000000000,
        "frame_uri": "s3://frames/CAM01/x.jpg",
        "detections": dets,
    }


def test_process_one_emits_nothing_when_no_qr_class_in_message() -> None:
    msg = _detection_msg(dets=[{"class_name": "box", "x1": 0, "y1": 0, "x2": 50, "y2": 50}])
    decode = MagicMock(return_value=[{"payload": "ZONE", "type": "QRCODE"}])
    fetch = MagicMock(return_value=_png_bytes())
    out = process_one(msg, MagicMock(), fetch, decode, DecoderConfig())
    assert out == []
    # decode should not be called at all (gate filtered everything out).
    decode.assert_not_called()
    # fetch_frame should also not be called when there's nothing to decode.
    fetch.assert_not_called()


def test_process_one_emits_one_payload_per_decoded_code() -> None:
    msg = _detection_msg(
        dets=[
            {"class_name": "qr_code", "x1": 10, "y1": 10, "x2": 60, "y2": 60, "track_id": 7},
            {"class_name": "barcode", "x1": 70, "y1": 70, "x2": 120, "y2": 120, "track_id": 8},
            {"class_name": "box", "x1": 0, "y1": 0, "x2": 5, "y2": 5},  # should be skipped
        ]
    )
    decode = MagicMock(
        side_effect=[
            [{"payload": "ZONE_A1:CAT_BOX", "type": "QRCODE"}],
            [{"payload": "1234567890123", "type": "EAN13"}],
        ]
    )
    fetch = MagicMock(return_value=_png_bytes(200, 200))

    out = process_one(msg, MagicMock(), fetch, decode, DecoderConfig())
    assert len(out) == 2
    assert out[0]["payload"] == "ZONE_A1:CAT_BOX"
    assert out[0]["track_id"] == 7
    assert out[1]["payload"] == "1234567890123"
    assert out[1]["code_type"] == "EAN13"
    # Frame fetched ONCE even for multiple QR detections in the same frame.
    assert fetch.call_count == 1
    assert decode.call_count == 2


def test_process_one_returns_empty_when_decode_finds_nothing() -> None:
    msg = _detection_msg(dets=[{"class_name": "qr_code", "x1": 10, "y1": 10, "x2": 60, "y2": 60}])
    decode = MagicMock(return_value=[])  # pyzbar finds nothing
    fetch = MagicMock(return_value=_png_bytes())

    out = process_one(msg, MagicMock(), fetch, decode, DecoderConfig())
    assert out == []


def test_process_one_emits_two_when_one_bbox_has_two_barcodes() -> None:
    """A single QR detection bbox can encompass multiple physical codes.

    pyzbar can return more than one; we must emit one Kafka message per code.
    """
    msg = _detection_msg(dets=[{"class_name": "qr_code", "x1": 0, "y1": 0, "x2": 200, "y2": 100}])
    decode = MagicMock(
        return_value=[
            {"payload": "ZONE_A1", "type": "QRCODE"},
            {"payload": "9876543210987", "type": "EAN13"},
        ]
    )
    fetch = MagicMock(return_value=_png_bytes(400, 300))

    out = process_one(msg, MagicMock(), fetch, decode, DecoderConfig())
    assert len(out) == 2
    assert {o["code_type"] for o in out} == {"QRCODE", "EAN13"}


def test_process_one_fetch_failure_yields_no_decodes() -> None:
    """If the frame can't be fetched from MinIO, we skip it and continue."""
    msg = _detection_msg(dets=[{"class_name": "qr_code", "x1": 0, "y1": 0, "x2": 50, "y2": 50}])
    decode = MagicMock()  # should never be called
    fetch = MagicMock(side_effect=RuntimeError("MinIO connection refused"))

    out = process_one(msg, MagicMock(), fetch, decode, DecoderConfig())
    assert out == []
    decode.assert_not_called()
