"""Fetch the TOMIE (Tracking Of Multiple Industrial Entities) dataset.

TOMIE (TU Dortmund, EURASIP J. Image & Video Processing 2024) is a large,
peer-reviewed, DOI-citable benchmark of **photo-realistic rendered
industrial scenes with moving entities** — forklifts, pallets, load
carriers in motion. It replaces the un-citable Pexels stand-in footage and
gives the project:

  * camera footage with real *motion* (so the GRU-AE anomaly detector can be
    retrained on in-domain trajectories instead of over-firing), and
  * a proper tracking benchmark (MOTA / IDF1 / MOTP) for ByteTrack.

Source (CC-BY 4.0, DOI 10.5281/zenodo.7849183):
    https://zenodo.org/records/7849183
    paper: https://doi.org/10.1186/s13640-024-00623-6

The files are huge (5–8 GB each). This script downloads ONE scenario by
default (the smallest). Pick another with --scenario.

Usage:
    uv run python scripts/fetch_tomie.py                 # smallest scenario
    uv run python scripts/fetch_tomie.py --list          # show all scenarios
    uv run python scripts/fetch_tomie.py --scenario scenario_1_without_dist_LVL_0
or:
    make fetch-tomie

Heavy download — run it where you have ~10 GB free and a stable connection;
it validates the zip and resumes-by-retry on a dropped link.
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
TOMIE_DIR = REPO / "datasets" / "raw" / "tomie"
MANIFEST = TOMIE_DIR / "manifest.json"

ZENODO_RECORD = "7849183"
ZENODO_FILE_URL = "https://zenodo.org/api/records/%s/files/%s.zip/content"
SOURCE = "https://zenodo.org/records/7849183"
LICENSE = "CC-BY 4.0"
CITATION = (
    "M. Langer et al., 'Semi-automated computer vision-based tracking of "
    "multiple industrial entities,' EURASIP J. Image and Video Processing, "
    "2024, doi:10.1186/s13640-024-00623-6. Dataset: doi:10.5281/zenodo.7849183"
)

# Approx sizes (MB) from the Zenodo record — smallest first.
SCENARIOS = {
    "scenario_3_without_dist_LVL_0": 4992,
    "scenario_3_without_dist_LVL_3_2x2": 5136,
    "scenario_1_with_dist_LVL_0": 5776,
    "scenario_1_without_dist_LVL_0": 6391,
    "scenario_1_without_dist_LVL_3": 7927,
    "scenario_1_with_dist_LVL_3": 8071,
}
DEFAULT_SCENARIO = "scenario_3_without_dist_LVL_0"

CHUNK = 1 << 20  # 1 MiB


def _download(url: str, dest: Path) -> None:
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
                    print(
                        f"\r  {dest.name}: {done / 1e6:7.0f} / {total / 1e6:.0f} MB "
                        f"({100 * done / total:3.0f}%)",
                        end="",
                    )
    print()
    if total and done < total:
        part.unlink(missing_ok=True)
        raise OSError(f"truncated download: got {done} of {total} bytes")
    part.rename(dest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO, choices=list(SCENARIOS))
    parser.add_argument("--list", action="store_true", help="List scenarios + sizes and exit.")
    parser.add_argument("--force", action="store_true", help="Re-download even if present.")
    parser.add_argument("--keep-zip", action="store_true", help="Keep the zip after extracting.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.list:
        for name, mb in sorted(SCENARIOS.items(), key=lambda kv: kv[1]):
            print(f"  {name:38s} {mb / 1000:.1f} GB")
        return 0

    TOMIE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = TOMIE_DIR / f"{args.scenario}.zip"
    url = ZENODO_FILE_URL % (ZENODO_RECORD, args.scenario)

    if zip_path.is_file() and not args.force and zipfile.is_zipfile(zip_path):
        logger.info("%s present (%.0f MB) — skipping download.", zip_path.name, zip_path.stat().st_size / 1e6)
    else:
        logger.info("Downloading %s (~%.1f GB) from Zenodo ...", args.scenario, SCENARIOS[args.scenario] / 1000)
        for attempt in range(1, 4):
            try:
                _download(url, zip_path)
                break
            except OSError as exc:
                logger.warning("attempt %d/3 failed: %s", attempt, exc)
        else:
            logger.error("Download failed after 3 attempts. Re-run to resume.")
            return 2

    if not zipfile.is_zipfile(zip_path):
        zip_path.unlink(missing_ok=True)
        logger.error("Not a valid zip (partial/corrupt) — removed it; re-run to retry.")
        return 2

    out = TOMIE_DIR / args.scenario
    logger.info("Extracting into %s ...", out.relative_to(REPO))
    with zipfile.ZipFile(zip_path) as zf:
        n = len(zf.namelist())
        zf.extractall(out)

    MANIFEST.write_text(
        json.dumps(
            {
                "source": SOURCE,
                "license": LICENSE,
                "citation": CITATION,
                "doi": "10.5281/zenodo.7849183",
                "scenario": args.scenario,
                "members_extracted": n,
                "fetched": date.today().isoformat(),
                "note": "Industrial moving-entity sequences. Next: assemble camera "
                "video + re-export trajectories + retrain the GRU-AE (in-domain).",
            },
            indent=2,
        )
        + "\n"
    )
    logger.info("Extracted %d members. Manifest: %s", n, MANIFEST.relative_to(REPO))
    if not args.keep_zip:
        zip_path.unlink(missing_ok=True)
        logger.info("Removed the zip (pass --keep-zip to retain).")
    logger.info("Done. Inspect %s to wire cameras + trajectory export.", out.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
