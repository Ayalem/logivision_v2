"""Extract object trajectories from video files (offline YOLO + ByteTrack).

Runs the same detector + tracker stack as the live inference worker over
local video files and writes one JSONL per video to
`data/processed/trajectories/`, plus a provenance `manifest.json`
(model version, confidence, fps, per-file record counts, extraction
date) so the article can state the exact extraction setup.

One JSONL record per (frame, confirmed track):
    {video, frame_idx, timestamp_ms, track_id, class_id, class_name,
     conf, cx, cy, w, h, frame_w, frame_h}

Timestamps are synthesised from frame_idx / fps — the trajectory features
only consume time *deltas*, so the absolute origin is irrelevant.

Usage:
    uv run python scripts/export_trajectories.py \\
        --videos datasets/raw/videos/Camera*.mp4 --fps 5 --conf 0.15
or via Makefile:
    make export-trajectories
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

logger = logging.getLogger(__name__)

OUT_DIR = REPO / "data" / "processed" / "trajectories"


def _resolve_model(weights_arg: str | None) -> tuple[str, str]:
    """Pick the detector weights: explicit path > MLflow Production > local runs."""
    if weights_arg:
        return weights_arg, f"local:{Path(weights_arg).name}"
    try:
        from services.model_server.service import resolve_model_weights

        return resolve_model_weights()
    except Exception as exc:  # noqa: BLE001 — MLflow may be down; use local runs
        logger.info("MLflow unavailable (%s); falling back to local run weights.", exc)
    for cand in (
        REPO / "ml" / "runs" / "two_phase" / "weights" / "best.pt",
        REPO / "yolov8n.pt",
    ):
        if cand.is_file():
            return str(cand), f"fallback:{cand.relative_to(REPO)}"
    raise SystemExit("No detector weights found — train a model or pass --weights.")


def export_video(
    video: Path, model, model_version: str, fps: float, conf: float
) -> tuple[Path, int, int]:
    """Run detector+tracker over one video; returns (jsonl, n_records, n_tracks)."""
    import cv2

    from services.inference_worker import worker

    # Fresh tracker per video so track ids never bleed across files.
    worker._TRACKERS.pop(f"offline:{video.stem}", None)
    camera_id = f"offline:{video.stem}"

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open {video}")
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    stride = max(1, round(native_fps / fps))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_path = OUT_DIR / f"{video.stem}.jsonl"
    n_records = 0
    track_ids: set[int] = set()
    with out_path.open("w") as fh:
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % stride == 0:
                timestamp_ms = int(idx / native_fps * 1000)
                results = model.predict(frame, conf=conf, verbose=False)[0]
                detections = []
                names = dict(getattr(model, "names", {}))
                if results.boxes is not None:
                    for box in results.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()
                        detections.append(
                            {
                                "class_id": int(box.cls.item()),
                                "class_name": names.get(int(box.cls.item()), "?"),
                                "confidence": float(box.conf.item()),
                                "x1": x1,
                                "y1": y1,
                                "x2": x2,
                                "y2": y2,
                            }
                        )
                tracked = worker.apply_tracker(detections, camera_id)
                for d in tracked:
                    tid = d.get("track_id")
                    if tid is None:  # unconfirmed — same rule as the live CEP
                        continue
                    track_ids.add(tid)
                    fh.write(
                        json.dumps(
                            {
                                "video": video.name,
                                "model_version": model_version,
                                "frame_idx": idx,
                                "timestamp_ms": timestamp_ms,
                                "track_id": tid,
                                "class_id": d["class_id"],
                                "class_name": d["class_name"],
                                "conf": round(d["confidence"], 4),
                                "cx": round((d["x1"] + d["x2"]) / 2, 2),
                                "cy": round((d["y1"] + d["y2"]) / 2, 2),
                                "w": round(d["x2"] - d["x1"], 2),
                                "h": round(d["y2"] - d["y1"], 2),
                                "frame_w": frame_w,
                                "frame_h": frame_h,
                            }
                        )
                        + "\n"
                    )
                    n_records += 1
            idx += 1
    cap.release()
    return out_path, n_records, len(track_ids)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--videos",
        nargs="+",
        type=Path,
        default=sorted((REPO / "datasets" / "raw" / "videos").glob("Camera*.mp4")),
        help="Video files to process (default: datasets/raw/videos/Camera*.mp4).",
    )
    parser.add_argument("--fps", type=float, default=5.0, help="Sampling rate (default 5).")
    parser.add_argument(
        "--conf",
        type=float,
        default=0.15,
        help="Detector confidence (default 0.15 — the first-iteration detector "
        "is weak on the deployment domain; ByteTrack's confirmation filter "
        "suppresses the extra noise).",
    )
    parser.add_argument("--weights", default=None, help="Explicit .pt path (else MLflow).")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    weights, model_version = _resolve_model(args.weights)
    from ultralytics import YOLO

    logger.info("Detector: %s (%s)", weights, model_version)
    model = YOLO(weights)

    # Merge into any existing manifest so the corpus can be assembled
    # over several runs (e.g. TalTech clips with the box detector, real
    # Pexels clips with the COCO detector) — provenance stays per-file.
    manifest_path = OUT_DIR / "manifest.json"
    manifest: dict = {"files": {}}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text())
            manifest.setdefault("files", {})
        except json.JSONDecodeError:
            logger.warning("Existing manifest unreadable; rewriting it.")
    for video in args.videos:
        video_path = video.resolve()
        out_path, n_records, n_tracks = export_video(
            video_path, model, model_version, args.fps, args.conf
        )
        logger.info("%s → %d records, %d tracks", video_path.name, n_records, n_tracks)
        manifest["files"][video_path.name] = {
            "jsonl": out_path.name,
            "records": n_records,
            "tracks": n_tracks,
            "model_version": model_version,
            "conf": args.conf,
            "fps": args.fps,
            "extracted": date.today().isoformat(),
        }

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    logger.info("Manifest: %s", (OUT_DIR / "manifest.json").relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
