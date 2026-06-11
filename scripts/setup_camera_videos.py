"""Map physical cameras to source videos via Camera1.mp4 .. Camera5.mp4 symlinks.

Why this script exists
----------------------
`services/api/routers/stream.py` looks for a video named `CameraN.mp4`
under `datasets/raw/videos/` whenever a request comes in for `CAM0N`.
The convention is intentional — it lets the operator swap a physical
camera by physically renaming a file, no code change, no config reload.

We have:
  * `datasets/raw/taltech_videos/Camera{1..5}.mp4` — the TalTech
    synthetic-warehouse clips (1080p, MIT, ~90 MB each) — five fixed
    CCTV angles on the SAME warehouse. Fetched by
    `scripts/fetch_taltech_videos.py` (`make fetch-taltech-videos`).
  * `datasets/raw/pexels_warehouse/*.mp4`          — 15 Pexels stock
    clips kept on disk as a last-resort fallback for any TalTech
    camera that hasn't been downloaded yet.

This script creates the 5 `CameraN.mp4` symlinks in
`datasets/raw/videos/` so the streaming endpoint can find them all.
Run:
    uv run python scripts/setup_camera_videos.py
or via Makefile:
    make camera-videos
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VIDEOS_DIR = REPO / "datasets" / "raw" / "videos"
TALTECH_DIR = REPO / "datasets" / "raw" / "taltech_videos"
PEXELS_DIR = REPO / "datasets" / "raw" / "pexels_warehouse"

# Camera → role mapping (matches infra/cameras.example.yaml).
# Each entry: (camera_index, role_description, source_chain)
# `source_chain` is tried in order: "taltech" resolves to the matching
# CameraN.mp4 under taltech_videos/; "pexels:<size_rank>" picks a stock
# clip by size (rank 0 = biggest). TalTech is always preferred — five
# coherent CCTV angles on the same warehouse beat unrelated stock clips.
ROLES = [
    (1, "Entrée Principale (Porte A)", ["taltech", "pexels:0"]),
    (2, "Quai d'Expédition (Porte B)", ["taltech", "pexels:1"]),
    (3, "Allée Stockage A1-A2", ["taltech", "pexels:2"]),
    (4, "Allée Stockage A3-A4", ["taltech", "pexels:3"]),
    (5, "Allée Restreinte (Couloir tech.)", ["taltech", "pexels:4"]),
]


def main() -> int:
    if not VIDEOS_DIR.is_dir():
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    pexels_by_size: list[Path] = sorted(
        (p for p in PEXELS_DIR.glob("*.mp4") if not p.is_symlink()),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )

    print(f"Camera videos directory: {VIDEOS_DIR.relative_to(REPO)}")
    print(f"Pexels archive          : {len(pexels_by_size)} files")
    print(f"TalTech archive         : {len(list(TALTECH_DIR.glob('Camera*.mp4')))} files")
    print()

    for idx, role, chain in ROLES:
        link = VIDEOS_DIR / f"Camera{idx}.mp4"
        target: Path | None = None

        for source in chain:
            if source == "taltech":
                cand = TALTECH_DIR / f"Camera{idx}.mp4"
                if cand.is_file():
                    target = Path("..") / "taltech_videos" / cand.name
                    break
                print(
                    f"⚠  CAM0{idx}: TalTech Camera{idx}.mp4 not on disk "
                    f"(run `make fetch-taltech-videos`); trying fallback"
                )
            elif source.startswith("pexels:"):
                rank = int(source.split(":", 1)[1])
                if rank < len(pexels_by_size):
                    target = Path("..") / "pexels_warehouse" / pexels_by_size[rank].name
                    break

        if target is None:
            print(f"❌ CAM0{idx} ({role}): no source available")
            continue

        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target)
        print(f"  CAM0{idx} ({role:38s}) -> {target}")

    print("\nDone. The dashboard now resolves each CAM0N to its CameraN.mp4 symlink.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
