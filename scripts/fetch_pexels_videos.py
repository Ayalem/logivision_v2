"""Fetch warehouse / logistics videos from the Pexels free API.

Pexels videos are CC0-equivalent (free for personal AND commercial use,
no attribution legally required — see https://www.pexels.com/license/).
This script uses the official REST API, NOT scraping — you need a free
API key from https://www.pexels.com/api/.

Usage:
    export PEXELS_API_KEY=...    # one-time, free key from pexels.com/api
    python scripts/fetch_pexels_videos.py --query warehouse --n 10 --output datasets/raw/videos

The script writes <output>/<id>.mp4 files and a `manifest.json` listing
each video's metadata (id, photographer, source URL, duration, resolution).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

PEXELS_API = "https://api.pexels.com/videos/search"
USER_AGENT = "logivision-data-fetcher/0.1 (academic project, +github.com/Ayalem/logivision_v2)"


@dataclass
class VideoEntry:
    id: int
    query: str
    duration_s: int
    width: int
    height: int
    photographer: str
    source_url: str
    download_url: str
    local_path: str


class PexelsError(Exception):
    """API or download error."""


def _http_get(url: str, headers: dict[str, str]) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (we control the URL)
        if resp.status != 200:
            raise PexelsError(f"HTTP {resp.status} for {url}")
        return resp.read()


def _pick_best_file(video_files: list[dict]) -> dict:
    """Pick a 'medium' quality mp4 to keep file sizes reasonable (~30-60 MB)."""
    mp4s = [f for f in video_files if f.get("file_type", "").lower() == "video/mp4"]
    if not mp4s:
        raise PexelsError("No mp4 variant in API response.")
    # Prefer hd (1280x720); fall back to sd then any.
    by_quality = {f.get("quality"): f for f in mp4s}
    for quality in ("hd", "sd"):
        if quality in by_quality:
            return by_quality[quality]
    return mp4s[0]


def search_and_download(
    query: str,
    n: int,
    output_dir: Path,
    api_key: str,
    per_page: int = 15,
) -> list[VideoEntry]:
    output_dir.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": api_key}
    entries: list[VideoEntry] = []
    page = 1
    while len(entries) < n:
        params = urllib.parse.urlencode(
            {"query": query, "per_page": per_page, "page": page, "orientation": "landscape"}
        )
        payload = json.loads(_http_get(f"{PEXELS_API}?{params}", headers=headers).decode())
        videos = payload.get("videos", [])
        if not videos:
            logger.info("No more results from Pexels for query %r.", query)
            break
        for v in videos:
            if len(entries) >= n:
                break
            best = _pick_best_file(v.get("video_files", []))
            local = output_dir / f"{v['id']}.mp4"
            if not local.is_file():
                logger.info(
                    "Downloading id=%s (%s x %s) ...",
                    v["id"],
                    best.get("width"),
                    best.get("height"),
                )
                local.write_bytes(_http_get(best["link"], headers={}))
            entries.append(
                VideoEntry(
                    id=v["id"],
                    query=query,
                    duration_s=int(v.get("duration", 0)),
                    width=int(best.get("width") or v.get("width", 0)),
                    height=int(best.get("height") or v.get("height", 0)),
                    photographer=v.get("user", {}).get("name", "unknown"),
                    source_url=v.get("url", ""),
                    download_url=best["link"],
                    local_path=str(local),
                )
            )
        page += 1
    (output_dir / "manifest.json").write_text(
        json.dumps([asdict(e) for e in entries], indent=2),
        encoding="utf-8",
    )
    return entries


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--query", default="warehouse", help="Pexels search query.")
    parser.add_argument("--n", type=int, default=10, help="How many videos to fetch.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/raw/videos"),
        help="Directory to write the mp4s + manifest.json into.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Pexels API key. Defaults to PEXELS_API_KEY env var.",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    api_key = args.api_key or os.environ.get("PEXELS_API_KEY")
    if not api_key:
        logger.error(
            "No Pexels API key. Get a free one at https://www.pexels.com/api/ "
            "and set it via PEXELS_API_KEY or --api-key."
        )
        return 1
    try:
        entries = search_and_download(args.query, args.n, args.output, api_key)
    except PexelsError as exc:
        logger.error("%s", exc)
        return 2
    logger.info("Wrote %d videos to %s", len(entries), args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
