"""MJPEG live-video streaming for the dashboard camera tiles.

How this works under the hood
-----------------------------
We expose `GET /api/cameras/{camera_id}/stream.mjpg` as a Motion-JPEG stream
over HTTP (`multipart/x-mixed-replace; boundary=frame`). Each "frame" is an
independent JPEG; the browser's `<img>` tag handles the demuxing natively,
which means **no WebSocket, no MediaSource API, no codec licensing** — it
just works in every browser.

Why MJPEG (and not HLS / WebRTC)?
    * MJPEG: zero infrastructure, latency ≈ one frame, perfect for a demo.
    * HLS: needs a segmenter + manifest, latency ≥ 4 s.
    * WebRTC: needs a SFU and STUN — overkill for a single-node demo.

Source selection
----------------
For the academic demo we don't have real RTSP cameras, so each camera ID
is mapped deterministically to a video file under `datasets/raw/videos/`.
The mapping is stable across restarts (`hash(camera_id) % len(videos)`)
so the same camera always shows the same scene.

When a real `frame_grabber` is feeding MinIO + Kafka, the production
upgrade is to replace `_open_camera_source()` with a MinIO/RTSP reader —
the streaming endpoint stays identical.

Frame loop
----------
We loop the file on EOF so the tile never goes black. We throttle to the
camera's `fps_target` from `infra/cameras.yaml` so we don't burn CPU.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cameras", tags=["stream"])

REPO_ROOT = Path(__file__).resolve().parents[3]
VIDEO_DIR = Path(os.environ.get("LOGIVISION_VIDEO_DIR", REPO_ROOT / "datasets" / "raw" / "videos"))
CAMERAS_FILE = Path(
    os.environ.get("LOGIVISION_CAMERAS", REPO_ROOT / "infra" / "cameras.example.yaml")
)
JPEG_QUALITY = int(os.environ.get("LOGIVISION_STREAM_JPEG_QUALITY", "75"))
DEFAULT_FPS = float(os.environ.get("LOGIVISION_STREAM_DEFAULT_FPS", "12"))


def _list_videos() -> list[Path]:
    """Return ALL .mp4 / .mov / .avi files in deterministic order.

    The Pexels videos here were curated by the user with a warehouse search
    query — they're intentional stand-ins for the TalTech footage we don't
    have on disk yet. Don't filter them.
    """
    if not VIDEO_DIR.is_dir():
        return []
    return sorted(p for p in VIDEO_DIR.iterdir() if p.suffix.lower() in {".mp4", ".mov", ".avi"})


def _camera_config(camera_id: str) -> dict:
    """Look up a camera's YAML entry, or return defaults if unknown."""
    if not CAMERAS_FILE.is_file():
        return {"id": camera_id, "fps_target": DEFAULT_FPS}
    raw = yaml.safe_load(CAMERAS_FILE.read_text(encoding="utf-8")) or {}
    for entry in raw.get("cameras", []) or []:
        if entry.get("id") == camera_id:
            return entry
    return {"id": camera_id, "fps_target": DEFAULT_FPS}


_CAMERA_NUM_RE = re.compile(r"^CAM0?(\d+)$", re.IGNORECASE)


def _source_for_camera(camera_id: str) -> str | int | None:
    """Resolve the OpenCV-openable source for a camera.

    Priority order:
      1. Explicit `source:` field in cameras.yaml — any URL, file path, or
         integer device index. `0`/`1`/... become webcam indices (live).
         `rtsp://...`, `http://...` → live network stream.
      2. Convention `CAM0N` ↔ `CameraN.mp4` under `data/raw/videos/`
         (or its legacy `datasets/raw/videos/` location).
      3. Deterministic hash across all available video files so unmapped
         cameras still show *some* warehouse scene rather than a black tile.

    Returns either a `Path` (file), a string (RTSP/HTTP URL), or an int
    (webcam device index). `None` only when *zero* sources are reachable.
    """
    cfg = _camera_config(camera_id)
    src = cfg.get("source")
    if src is not None:
        if isinstance(src, int) or (isinstance(src, str) and str(src).isdigit()):
            return int(src)
        if isinstance(src, str) and (src.startswith(("rtsp://", "http://", "https://"))):
            return src
        candidate = Path(src)
        if not candidate.is_absolute():
            candidate = (REPO_ROOT / src).resolve()
        if candidate.is_file():
            return candidate
        logger.warning("camera %s: configured source %r unreachable; falling back", camera_id, src)

    # Filename convention fallback
    videos = _list_videos()
    if not videos:
        return None
    m = _CAMERA_NUM_RE.match(camera_id)
    if m:
        n = m.group(1)
        for v in videos:
            if v.name.lower() == f"camera{n}.mp4":
                return v
    idx = int(hashlib.md5(camera_id.encode()).hexdigest(), 16) % len(videos)
    return videos[idx]


# Back-compat alias — older code in this module called the helper
# `_video_for_camera`. Keep the name working so nothing breaks.
def _video_for_camera(camera_id: str) -> Path | None:
    src = _source_for_camera(camera_id)
    return src if isinstance(src, Path) else None


def _open_source(source: Path | str | int):
    """Open any OpenCV-compatible source — file Path, URL string, or int index.

    - Path  → file (looped on EOF in the generator).
    - str   → RTSP/HTTP URL (`rtsp://`, `http://`, `https://`).
    - int   → webcam device index (`0`, `1`, ...). macOS prompts for
              Camera permission on first attempt.
    """
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover
        raise HTTPException(503, "opencv-python-headless not installed") from e
    handle = source if isinstance(source, int | str) else str(source)
    cap = cv2.VideoCapture(handle)
    if not cap.isOpened():
        raise HTTPException(500, f"cannot open source {source!r}")
    return cap, cv2


def _mjpeg_generator(camera_id: str):
    """Yield multipart MJPEG chunks for the given camera, looping on EOF."""
    source = _source_for_camera(camera_id)
    if source is None:
        raise HTTPException(
            404,
            f"no source resolved for camera={camera_id!r}. Either set "
            f"`source:` in {CAMERAS_FILE.name} or drop a video into {VIDEO_DIR}",
        )

    cap, cv2 = _open_source(source)
    # File sources loop on EOF; live sources (webcam, RTSP, HTTP) don't —
    # they reconnect on transient read failures instead.
    is_live = not isinstance(source, Path)
    cfg = _camera_config(camera_id)
    target_fps = float(cfg.get("fps_target") or DEFAULT_FPS)
    frame_interval = 1.0 / max(1.0, target_fps)
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    boundary = b"--frame"

    src_label = (
        source.name
        if isinstance(source, Path)
        else f"device:{source}"
        if isinstance(source, int)
        else source
    )
    logger.info(
        "mjpeg stream started camera=%s source=%s fps=%.1f live=%s",
        camera_id,
        src_label,
        target_fps,
        is_live,
    )

    try:
        last_emit = 0.0
        while True:
            ok, frame = cap.read()
            if not ok:
                if is_live:
                    # Live source: transient read failure → brief backoff,
                    # don't try to seek (RTSP/webcam have no rewindable buffer).
                    time.sleep(0.05)
                    continue
                # File source: loop so the tile is never blank.
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            # Throttle without busy-waiting.
            now = time.monotonic()
            wait = frame_interval - (now - last_emit)
            if wait > 0:
                time.sleep(wait)
            last_emit = time.monotonic()
            ok, buf = cv2.imencode(".jpg", frame, encode_params)
            if not ok:
                continue
            jpeg = buf.tobytes()
            yield (
                boundary
                + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(jpeg)).encode()
                + b"\r\n\r\n"
                + jpeg
                + b"\r\n"
            )
    except GeneratorExit:
        # The browser closed the <img> connection (tab hidden, refresh, etc).
        logger.info("mjpeg stream stopped camera=%s", camera_id)
    finally:
        cap.release()


@router.get("/{camera_id}/stream.mjpg")
def stream_camera(camera_id: str) -> StreamingResponse:
    """Live MJPEG feed for the named camera.

    Drop into `<img src="/api/cameras/CAM01/stream.mjpg">` — the browser
    decodes the multipart stream as a live image and updates in place.
    """
    return StreamingResponse(
        _mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/{camera_id}/source")
def camera_source(camera_id: str) -> dict:
    """Introspection helper — which video file backs this camera."""
    video = _video_for_camera(camera_id)
    return {
        "camera_id": camera_id,
        "video": video.name if video else None,
        "video_dir": str(VIDEO_DIR),
        "available_videos": [p.name for p in _list_videos()][:10],
    }
