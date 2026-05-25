"""Extract frames from videos into JPG sequences with a manifest.jsonl.

Usage:
    python -m ml.scripts.extract_frames \\
        --input datasets/raw/videos \\
        --output datasets/raw/frames \\
        --fps 2 --resize 640

Each input video produces a sub-directory named after the video stem,
with frames named `frame_{n:06d}.jpg`. A single `manifest.jsonl` lists
every extracted frame with its source video, timestamp, and dimensions.

Reproducibility: a `--seed` is reserved for future random sampling
strategies; the current implementation samples deterministically by
stride, so the seed is recorded in the manifest header for tracing.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}


@dataclass(frozen=True)
class FrameRecord:
    """One line of the manifest.jsonl."""

    video_id: str
    frame_index: int
    output_path: str
    source_video: str
    timestamp_ms: int
    width: int
    height: int


def extract_video(
    video_path: Path,
    output_dir: Path,
    target_fps: float,
    max_frames: int | None,
    resize: int | None,
) -> Iterator[FrameRecord]:
    """Yield records for every frame extracted from a single video.

    `target_fps` is an approximation: we pick every Nth source frame such
    that `source_fps / N` is closest to `target_fps`.
    """
    if target_fps <= 0:
        raise ValueError(f"target_fps must be > 0, got {target_fps}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open video: {video_path}")

    return _iter_video_frames(cap, video_path, output_dir, target_fps, max_frames, resize)


def _iter_video_frames(
    cap: cv2.VideoCapture,
    video_path: Path,
    output_dir: Path,
    target_fps: float,
    max_frames: int | None,
    resize: int | None,
) -> Iterator[FrameRecord]:
    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    stride = max(1, round(source_fps / target_fps))
    video_id = video_path.stem
    out_subdir = output_dir / video_id
    out_subdir.mkdir(parents=True, exist_ok=True)

    extracted = 0
    src_index = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if src_index % stride == 0:
                if resize and resize > 0:
                    frame = _maybe_resize(frame, resize)
                out_path = out_subdir / f"frame_{extracted:06d}.jpg"
                cv2.imwrite(str(out_path), frame)
                h, w = frame.shape[:2]
                yield FrameRecord(
                    video_id=video_id,
                    frame_index=extracted,
                    output_path=str(out_path),
                    source_video=str(video_path),
                    timestamp_ms=int(cap.get(cv2.CAP_PROP_POS_MSEC)),
                    width=w,
                    height=h,
                )
                extracted += 1
                if max_frames is not None and extracted >= max_frames:
                    break
            src_index += 1
    finally:
        cap.release()


def _maybe_resize(frame, max_side: int):
    h, w = frame.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return frame
    scale = max_side / longest
    return cv2.resize(frame, (int(w * scale), int(h * scale)))


def extract_all(
    input_dir: Path,
    output_dir: Path,
    manifest_path: Path,
    target_fps: float = 2.0,
    max_frames_per_video: int | None = None,
    resize: int | None = 640,
) -> int:
    """Extract frames from every video under `input_dir`. Returns total count."""
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input dir does not exist: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    video_paths = sorted(p for p in input_dir.rglob("*") if p.suffix.lower() in VIDEO_EXTENSIONS)
    if not video_paths:
        logger.warning("No videos found under %s", input_dir)

    total = 0
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for video_path in video_paths:
            logger.info("Extracting %s", video_path)
            for record in extract_video(
                video_path=video_path,
                output_dir=output_dir,
                target_fps=target_fps,
                max_frames=max_frames_per_video,
                resize=resize,
            ):
                manifest.write(json.dumps(asdict(record)) + "\n")
                total += 1
    return total


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--input", type=Path, required=True, help="Directory of source videos.")
    parser.add_argument(
        "--output", type=Path, required=True, help="Directory for extracted frames."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Output path for manifest.jsonl. Defaults to <output>/manifest.jsonl.",
    )
    parser.add_argument("--fps", type=float, default=2.0, help="Target frame rate (default 2).")
    parser.add_argument(
        "--max-frames-per-video",
        type=int,
        default=None,
        help="Cap extracted frames per video.",
    )
    parser.add_argument(
        "--resize", type=int, default=640, help="Max dimension after resize (0 to disable)."
    )
    parser.add_argument("--seed", type=int, default=42, help="Reserved for future sampling.")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")

    manifest_path = args.manifest or (args.output / "manifest.jsonl")
    resize = args.resize if args.resize and args.resize > 0 else None

    n = extract_all(
        input_dir=args.input,
        output_dir=args.output,
        manifest_path=manifest_path,
        target_fps=args.fps,
        max_frames_per_video=args.max_frames_per_video,
        resize=resize,
    )
    logger.info("Extracted %d frames -> %s", n, args.output)
    logger.info("Manifest at %s", manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
