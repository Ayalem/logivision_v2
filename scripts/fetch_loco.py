"""Fetch the LOCO (Logistics Objects in Context) dataset.

LOCO is the first scene-understanding dataset for logistics: real photos
captured while walking through five operating warehouse / logistics
environments. 5,593 manually annotated images (152,421 annotations, COCO
format) across five logistics-specific classes:

    pallet, small_load_carrier, forklift, stillage, pallet_truck

Source (TU München, FML chair), public-domain (CC0) dedication:

    https://github.com/tum-fml/loco
    annotated set → https://go.mytum.de/239870  (dataset.zip, ~769 MB)

This replaces the Kaggle aerial delivery-box set with REAL warehouse
imagery — the model now learns the objects a warehouse monitor actually
cares about (pallets, forklifts, load carriers), not just generic boxes.

Usage:
    uv run python scripts/fetch_loco.py            # download + extract
    uv run python scripts/fetch_loco.py --force    # re-download
or via the Makefile:
    make fetch-loco

The download + COCO→YOLO conversion (scripts/prepare_loco.py) + retraining
are heavy steps — run the training on Colab/Kaggle GPU, not local CPU.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
LOCO_DIR = REPO / "datasets" / "raw" / "loco"
ZIP_PATH = LOCO_DIR / "dataset.zip"
MANIFEST = LOCO_DIR / "manifest.json"

# Stable TUM short-link; 302-redirects to the webdisk attachment. urllib
# follows the redirect automatically, so we keep the stable link here
# rather than the ephemeral token URL it resolves to.
DOWNLOAD_URL = "https://go.mytum.de/239870"
SOURCE = "https://github.com/tum-fml/loco"
LICENSE = "CC0 1.0 (public domain dedication)"
CITATION = (
    "Mayershofer et al., 'LOCO: Logistics Objects in Context', "
    "IEEE ICMLA 2020. Dataset: https://github.com/tum-fml/loco"
)

CHUNK = 1 << 20  # 1 MiB


def _download(url: str, dest: Path) -> None:
    """Stream `url` to `dest` via a .part temp file (atomic on success)."""
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "logivision-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 — fixed https host
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


def _extract(zip_path: Path, dest: Path) -> int:
    """Extract the archive; return the number of members written."""
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        zf.extractall(dest)
    return len(members)


def _write_manifest(n_members: int) -> None:
    MANIFEST.write_text(
        json.dumps(
            {
                "source": SOURCE,
                "license": LICENSE,
                "citation": CITATION,
                "download_url": DOWNLOAD_URL,
                "archive": ZIP_PATH.name,
                "archive_bytes": ZIP_PATH.stat().st_size if ZIP_PATH.is_file() else None,
                "members_extracted": n_members,
                "fetched": date.today().isoformat(),
                "note": "Real warehouse/logistics imagery (COCO format). Convert "
                "to YOLO with scripts/prepare_loco.py.",
            },
            indent=2,
        )
        + "\n"
    )
    logger.info("Manifest written: %s", MANIFEST.relative_to(REPO))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true", help="Re-download even if present.")
    parser.add_argument(
        "--keep-zip", action="store_true", help="Keep dataset.zip after extracting."
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    LOCO_DIR.mkdir(parents=True, exist_ok=True)

    if ZIP_PATH.is_file() and not args.force:
        logger.info(
            "%s already on disk (%.1f MB) — skipping download.",
            ZIP_PATH.name,
            ZIP_PATH.stat().st_size / 1e6,
        )
    else:
        logger.info("Downloading LOCO annotated set from %s ...", DOWNLOAD_URL)
        try:
            _download(DOWNLOAD_URL, ZIP_PATH)
        except OSError as exc:
            logger.error("Download failed: %s", exc)
            return 2

    logger.info("Extracting %s ...", ZIP_PATH.name)
    n = _extract(ZIP_PATH, LOCO_DIR)
    logger.info("Extracted %d members into %s", n, LOCO_DIR.relative_to(REPO))
    _write_manifest(n)

    if not args.keep_zip:
        ZIP_PATH.unlink(missing_ok=True)
        logger.info("Removed %s (pass --keep-zip to retain).", ZIP_PATH.name)

    logger.info("Done. Next: uv run python scripts/prepare_loco.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
