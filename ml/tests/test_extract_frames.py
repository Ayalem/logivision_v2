"""Tests for ml.scripts.extract_frames."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from ml.scripts.extract_frames import extract_all, extract_video


def _make_synthetic_video(path: Path, n_frames: int = 10, fps: float = 10.0) -> Path:
    """Write an `n_frames`-frame AVI of solid-color frames (320x240)."""
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (320, 240))
    if not writer.isOpened():
        raise RuntimeError("Could not open VideoWriter; codec missing in test env.")
    palette = [
        (0, 0, 255),
        (0, 255, 0),
        (255, 0, 0),
        (0, 255, 255),
        (255, 0, 255),
        (255, 255, 0),
        (0, 0, 128),
        (0, 128, 0),
        (128, 0, 0),
        (128, 128, 128),
    ]
    for i in range(n_frames):
        frame = np.full((240, 320, 3), palette[i % len(palette)], dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture
def synthetic_video_dir(tmp_path: Path) -> Path:
    """Directory containing one 10-frame synthetic video."""
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    _make_synthetic_video(videos_dir / "synthetic.avi", n_frames=10, fps=10.0)
    return videos_dir


def test_extracts_at_target_fps(synthetic_video_dir: Path, tmp_path: Path) -> None:
    """Half the source fps → stride 2 → 5 frames extracted from 10."""
    out_dir = tmp_path / "frames"
    manifest = tmp_path / "manifest.jsonl"

    n = extract_all(
        input_dir=synthetic_video_dir,
        output_dir=out_dir,
        manifest_path=manifest,
        target_fps=5.0,
        max_frames_per_video=None,
        resize=None,
    )

    assert n == 5
    extracted = sorted((out_dir / "synthetic").glob("frame_*.jpg"))
    assert len(extracted) == 5
    assert extracted[0].name == "frame_000000.jpg"
    assert extracted[-1].name == "frame_000004.jpg"


def test_manifest_has_one_record_per_frame(synthetic_video_dir: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "frames"
    manifest = tmp_path / "manifest.jsonl"

    n = extract_all(
        input_dir=synthetic_video_dir,
        output_dir=out_dir,
        manifest_path=manifest,
        target_fps=5.0,
        max_frames_per_video=None,
        resize=None,
    )

    records = [json.loads(line) for line in manifest.read_text().splitlines()]
    assert len(records) == n
    required_keys = {
        "video_id",
        "frame_index",
        "output_path",
        "source_video",
        "timestamp_ms",
        "width",
        "height",
    }
    for rec in records:
        assert required_keys <= rec.keys()
        assert Path(rec["output_path"]).is_file()
        assert rec["width"] == 320
        assert rec["height"] == 240
        assert rec["video_id"] == "synthetic"


def test_max_frames_per_video_caps_output(synthetic_video_dir: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "frames"
    manifest = tmp_path / "manifest.jsonl"
    n = extract_all(
        input_dir=synthetic_video_dir,
        output_dir=out_dir,
        manifest_path=manifest,
        target_fps=10.0,
        max_frames_per_video=3,
        resize=None,
    )
    assert n == 3


def test_resize_caps_longest_side(synthetic_video_dir: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "frames"
    manifest = tmp_path / "manifest.jsonl"
    extract_all(
        input_dir=synthetic_video_dir,
        output_dir=out_dir,
        manifest_path=manifest,
        target_fps=10.0,
        max_frames_per_video=2,
        resize=160,  # half of 320
    )
    frames = sorted((out_dir / "synthetic").glob("frame_*.jpg"))
    assert frames
    img = cv2.imread(str(frames[0]))
    assert max(img.shape[:2]) <= 160


def test_extract_video_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Could not open"):
        extract_video(
            video_path=tmp_path / "nonexistent.mp4",
            output_dir=tmp_path / "frames",
            target_fps=2.0,
            max_frames=None,
            resize=None,
        )


def test_extract_all_raises_on_missing_input_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        extract_all(
            input_dir=tmp_path / "nope",
            output_dir=tmp_path / "frames",
            manifest_path=tmp_path / "m.jsonl",
        )


def test_invalid_target_fps_rejected(synthetic_video_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="target_fps"):
        extract_video(
            video_path=next(synthetic_video_dir.glob("*.avi")),
            output_dir=tmp_path / "frames",
            target_fps=0.0,
            max_frames=None,
            resize=None,
        )
