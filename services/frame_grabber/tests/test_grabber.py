"""Unit tests for the frame-grabber — Kafka + MinIO + OpenCV mocked."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from services.frame_grabber.grabber import (
    GrabberConfig,
    build_frame_uri,
    make_raw_frame_message,
    run,
)


def test_build_frame_uri_uses_camera_and_date() -> None:
    when = datetime(2026, 5, 20, tzinfo=UTC)
    assert (
        build_frame_uri("frames", "CAM03", "abc-1", when=when)
        == "s3://frames/CAM03/20260520/abc-1.jpg"
    )


def test_make_raw_frame_message_shape() -> None:
    msg = make_raw_frame_message(
        camera_id="CAM01",
        frame_id="F1",
        timestamp_ms=1234,
        width=640,
        height=480,
        frame_uri="s3://frames/CAM01/20260520/F1.jpg",
    )
    assert set(msg.keys()) == {
        "frame_id",
        "camera_id",
        "timestamp_ms",
        "width",
        "height",
        "frame_uri",
    }
    assert msg["frame_id"] == "F1"
    assert msg["camera_id"] == "CAM01"


def test_run_publishes_one_frame_per_iterated_image(tmp_path) -> None:
    """End-to-end with cv2 / boto3 / confluent_kafka mocked."""
    import numpy as np

    fake_frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(3)]

    mock_cv2 = MagicMock()
    mock_cv2.imencode.return_value = (True, np.array([0xFF, 0xD8, 0xFF], dtype=np.uint8))
    mock_cv2.IMWRITE_JPEG_QUALITY = 1

    mock_s3 = MagicMock()
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3

    mock_producer_cls = MagicMock()
    mock_producer = MagicMock()
    mock_producer_cls.return_value = mock_producer

    with (
        patch.dict("sys.modules", {"cv2": mock_cv2}),
        patch.dict("sys.modules", {"boto3": mock_boto3}),
        patch("services.frame_grabber.grabber._iter_video_frames", return_value=iter(fake_frames)),
        patch("services.frame_grabber.grabber._iter_dir_frames", return_value=iter(fake_frames)),
        patch("confluent_kafka.Producer", mock_producer_cls),
    ):
        cfg = GrabberConfig(
            source=str(tmp_path / "video.mp4"),  # not a dir → triggers video path
            camera_id="CAM01",
            target_fps=10.0,
            max_frames=None,
        )
        n = run(cfg)

    assert n == 3
    assert mock_s3.put_object.call_count == 3
    assert mock_producer.produce.call_count == 3
    # For each iteration the Kafka key (frame_id) must match the S3 Key suffix.
    for producer_call, s3_call in zip(
        mock_producer.produce.call_args_list,
        mock_s3.put_object.call_args_list,
        strict=False,
    ):
        kafka_frame_id = producer_call.kwargs["key"].decode()
        s3_key: str = s3_call.kwargs["Key"]
        assert kafka_frame_id in s3_key
        assert s3_key.endswith(".jpg")


def test_run_caps_at_max_frames(tmp_path) -> None:
    import numpy as np

    fake_frames = [np.zeros((10, 10, 3), dtype=np.uint8) for _ in range(20)]
    mock_cv2 = MagicMock()
    mock_cv2.imencode.return_value = (True, np.array([0xFF, 0xD8], dtype=np.uint8))
    mock_cv2.IMWRITE_JPEG_QUALITY = 1
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = MagicMock()
    mock_producer_cls = MagicMock()
    mock_producer_cls.return_value = MagicMock()

    with (
        patch.dict("sys.modules", {"cv2": mock_cv2, "boto3": mock_boto3}),
        patch("services.frame_grabber.grabber._iter_video_frames", return_value=iter(fake_frames)),
        patch("confluent_kafka.Producer", mock_producer_cls),
    ):
        n = run(
            GrabberConfig(
                source=str(tmp_path / "v.mp4"),
                camera_id="C",
                target_fps=30.0,
                max_frames=5,
            )
        )
    assert n == 5


@pytest.mark.parametrize(
    "bucket,camera,frame_id",
    [("frames", "CAM01", "abc"), ("custom", "CAM-FOO", "def-ghi")],
)
def test_frame_uri_round_trip(bucket: str, camera: str, frame_id: str) -> None:
    uri = build_frame_uri(bucket, camera, frame_id)
    assert uri.startswith(f"s3://{bucket}/{camera}/")
    assert uri.endswith(f"{frame_id}.jpg")
