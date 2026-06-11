"""Fetch the TalTech synthetic-warehouse camera videos (Camera1..Camera5).

Source: "Synthetic dataset for warehouse equipment and pallet recognition —
Videos" record on the TalTech Data Repository (MIT licence):

    https://data.taltech.ee/records/e9wxe-qpv69

Each clip is a fixed CCTV-style viewpoint of the same warehouse scene
(~87-91 MB, 1080p), which makes the 5-camera dashboard coherent: one
warehouse, five angles, instead of unrelated stock footage. Camera3 was
already vendored; this script completes the set and writes a provenance
manifest (source record, licence, sizes, fetch date) so the article can
cite the footage precisely.

Usage:
    uv run python scripts/fetch_taltech_videos.py            # all missing
    uv run python scripts/fetch_taltech_videos.py --cameras 1 2
or via Makefile:
    make fetch-taltech-videos
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.request
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
TALTECH_DIR = REPO / "datasets" / "raw" / "taltech_videos"
MANIFEST = TALTECH_DIR / "manifest.json"

RECORD_URL = "https://data.taltech.ee/records/e9wxe-qpv69"
FILE_URL = RECORD_URL + "/files/Camera{n}.mp4?download=1"
LICENCE = "MIT"
CITATION = (
    "Synthetic dataset for warehouse equipment and pallet recognition (Videos), "
    "TalTech Data Repository, https://data.taltech.ee/records/e9wxe-qpv69"
)

CHUNK = 1 << 20  # 1 MiB


def _download(url: str, dest: Path) -> None:
    """Stream `url` to `dest` via a .part temp file (atomic on success)."""
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "logivision-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — fixed https host
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with part.open("wb") as fh:
            while chunk := resp.read(CHUNK):
                fh.write(chunk)
                done += len(chunk)
                if total:
                    pct = 100 * done / total
                    print(
                        f"\r  {dest.name}: {done / 1e6:6.1f} / {total / 1e6:.1f} MB ({pct:3.0f}%)",
                        end="",
                    )
    print()
    part.rename(dest)


def _update_manifest(fetched: list[str]) -> None:
    manifest: dict = {}
    if MANIFEST.is_file():
        try:
            manifest = json.loads(MANIFEST.read_text())
        except json.JSONDecodeError:
            logger.warning("Existing manifest unreadable; rewriting it.")
    manifest.setdefault("source", RECORD_URL)
    manifest.setdefault("license", LICENCE)
    manifest.setdefault("citation", CITATION)
    files = manifest.setdefault("files", {})
    for name in fetched:
        path = TALTECH_DIR / name
        files[name] = {
            "bytes": path.stat().st_size,
            "fetched": date.today().isoformat(),
            "url": FILE_URL.format(n=name[len("Camera") : -len(".mp4")]),
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    logger.info("Manifest updated: %s", MANIFEST.relative_to(REPO))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--cameras",
        nargs="*",
        type=int,
        default=[1, 2, 3, 4, 5],
        help="Camera numbers to fetch (default: all missing).",
    )
    parser.add_argument("--force", action="store_true", help="Re-download even if present.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    TALTECH_DIR.mkdir(parents=True, exist_ok=True)
    fetched: list[str] = []
    for n in args.cameras:
        name = f"Camera{n}.mp4"
        dest = TALTECH_DIR / name
        if dest.is_file() and not args.force:
            logger.info("%s already on disk (%.1f MB) — skipping.", name, dest.stat().st_size / 1e6)
            continue
        url = FILE_URL.format(n=n)
        logger.info("Downloading %s ...", url)
        try:
            _download(url, dest)
        except OSError as exc:
            logger.error("Failed to download %s: %s", name, exc)
            return 2
        fetched.append(name)

    # Manifest covers everything on disk, not just this run's downloads.
    on_disk = sorted(p.name for p in TALTECH_DIR.glob("Camera*.mp4"))
    _update_manifest(on_disk)
    logger.info("Done — %d downloaded, %d total on disk.", len(fetched), len(on_disk))
    return 0


if __name__ == "__main__":
    sys.exit(main())
