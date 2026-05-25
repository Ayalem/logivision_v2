"""Fetch a Kaggle dataset using the `kaggle` CLI under the hood.

Auth: this script reads `KAGGLE_USERNAME` and `KAGGLE_KEY` from the
environment (or `.env`) and writes a temporary `~/.kaggle/kaggle.json`
just for this run, then removes it. You can also pre-populate
`~/.kaggle/kaggle.json` yourself and skip the env-vars step.

Get the credentials at https://www.kaggle.com/settings → "Create New Token".

Usage:
    export KAGGLE_USERNAME=...
    export KAGGLE_KEY=...
    python scripts/fetch_kaggle.py \\
        --dataset zoya77/warehouse-delivery-box-detection-dataset \\
        --output datasets/raw/external/kaggle_warehouse_box
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Best-effort .env loader so the script works from `make` subshells."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), os.path.expandvars(value.strip()))


_load_env_file()


def _ensure_credentials(username: str | None, key: str | None) -> Path | None:
    """Write a temporary kaggle.json if both are provided. Return its parent dir, or None."""
    if not username or not key:
        return None
    tmp = Path(tempfile.mkdtemp(prefix="logivision-kaggle-"))
    cred_file = tmp / "kaggle.json"
    cred_file.write_text(json.dumps({"username": username, "key": key}))
    cred_file.chmod(0o600)
    return tmp


def fetch(
    dataset_slug: str,
    output_dir: Path,
    unzip: bool = True,
    username: str | None = None,
    key: str | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    tmp_dir = _ensure_credentials(username, key)
    if tmp_dir is not None:
        env["KAGGLE_CONFIG_DIR"] = str(tmp_dir)

    try:
        cmd = [
            "kaggle",
            "datasets",
            "download",
            "-d",
            dataset_slug,
            "-p",
            str(output_dir),
        ]
        if unzip:
            cmd.append("--unzip")
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(  # noqa: S603 — we control args
            cmd, env=env, capture_output=True, text=True, check=False, timeout=900
        )
        if result.returncode != 0:
            raise RuntimeError(f"kaggle CLI failed: {result.stderr}")
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    return output_dir


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", required=True, help="Kaggle slug, e.g. `user/name`.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/raw/external"),
        help="Target directory (will be created).",
    )
    parser.add_argument("--no-unzip", action="store_true")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")

    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    if (not username or not key) and not (Path.home() / ".kaggle" / "kaggle.json").is_file():
        logger.error(
            "No Kaggle credentials. Either set KAGGLE_USERNAME + KAGGLE_KEY in your "
            "environment (or .env), or place a `kaggle.json` at ~/.kaggle/. "
            "Token: https://www.kaggle.com/settings → 'Create New Token'."
        )
        return 1

    try:
        out = fetch(
            dataset_slug=args.dataset,
            output_dir=args.output,
            unzip=not args.no_unzip,
            username=username,
            key=key,
        )
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2
    logger.info("Done. Files under %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
