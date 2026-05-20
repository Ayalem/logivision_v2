"""Lightweight load test for the BentoML detector.

No external dep (k6 etc.): uses `urllib` + `concurrent.futures` to send
concurrent requests and measures end-to-end latency on the client side.
Output is a Markdown table under docs/mlops/benchmarks/load_<timestamp>.md.

Usage:
    # Assumes `bentoml serve services.model_server.service:WarehouseDetector` is up.
    uv run python tests/load/load_test.py \\
        --url http://localhost:3000/detect \\
        --image datasets/raw/frames/Camera3/frame_000000.jpg \\
        --concurrency 1,5,10 --requests 30
"""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    concurrency: int
    n_requests: int
    n_ok: int
    n_err: int
    total_s: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    rps: float


def _multipart_body(image_path: Path) -> tuple[bytes, str]:
    boundary = "----LogiVisionBoundary" + uuid4().hex
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    payload = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode()
    payload += image_path.read_bytes()
    payload += f"\r\n--{boundary}--\r\n".encode()
    return payload, f"multipart/form-data; boundary={boundary}"


def _one_request(url: str, body: bytes, content_type: str, timeout: float) -> tuple[bool, float]:
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", content_type)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (client-side test)
            resp.read()
        return True, (time.perf_counter() - start) * 1000.0
    except Exception as exc:  # noqa: BLE001
        logger.debug("request failed: %s", exc)
        return False, (time.perf_counter() - start) * 1000.0


def _percentile(latencies: list[float], pct: float) -> float:
    if not latencies:
        return 0.0
    s = sorted(latencies)
    k = max(0, min(len(s) - 1, int(round(pct / 100 * (len(s) - 1)))))
    return s[k]


def run_stage(
    url: str, image: Path, concurrency: int, requests: int, timeout: float = 10.0
) -> StageResult:
    body, ct = _multipart_body(image)
    latencies: list[float] = []
    errors = 0
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_one_request, url, body, ct, timeout) for _ in range(requests)]
        for f in as_completed(futures):
            ok, ms = f.result()
            if ok:
                latencies.append(ms)
            else:
                errors += 1
    total = time.perf_counter() - started
    return StageResult(
        concurrency=concurrency,
        n_requests=requests,
        n_ok=len(latencies),
        n_err=errors,
        total_s=total,
        p50_ms=_percentile(latencies, 50),
        p95_ms=_percentile(latencies, 95),
        p99_ms=_percentile(latencies, 99),
        rps=requests / total if total > 0 else 0.0,
    )


def render(results: list[StageResult]) -> str:
    lines = [f"# Load test — {datetime.now(UTC).strftime('%Y%m%d_%H%M')}", ""]
    lines.append("| concur | requests | OK | err | total s | p50 ms | p95 ms | p99 ms | rps |")
    lines.append("|-------:|---------:|---:|----:|--------:|-------:|-------:|-------:|----:|")
    for r in results:
        lines.append(
            f"| {r.concurrency:>6} | {r.n_requests:>8} | {r.n_ok:>2} | {r.n_err:>3} "
            f"| {r.total_s:7.2f} | {r.p50_ms:6.2f} | {r.p95_ms:6.2f} | {r.p99_ms:6.2f} | {r.rps:4.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", default="http://localhost:3000/detect")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument(
        "--concurrency",
        default="1,5,10",
        help="Comma-separated list of concurrency levels to test.",
    )
    parser.add_argument("--requests", type=int, default=30, help="Requests per stage.")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/mlops/benchmarks"),
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")

    if not args.image.is_file():
        logger.error("Image not found: %s", args.image)
        return 1
    levels = [int(c.strip()) for c in args.concurrency.split(",") if c.strip()]
    results: list[StageResult] = []
    for c in levels:
        logger.info("Running stage concurrency=%d requests=%d ...", c, args.requests)
        results.append(run_stage(args.url, args.image, c, args.requests, args.timeout))

    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"load_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.md"
    out.write_text(render(results), encoding="utf-8")
    (out.with_suffix(".json")).write_text(
        json.dumps([r.__dict__ for r in results], indent=2),
        encoding="utf-8",
    )
    logger.info("Report: %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
