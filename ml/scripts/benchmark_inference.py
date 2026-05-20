"""Benchmark a run's three model flavors (PyTorch / OpenVINO FP32 / INT8).

Loads, for a given MLflow run id:
    - `best.pt`  (PyTorch checkpoint, downloaded from MLflow)
    - `openvino-fp32/best.xml`
    - `openvino-int8/best.xml`

Runs N inferences on the validation set referenced by the run's
`dataset_path` tag, and writes a Markdown report at
`docs/mlops/benchmarks/run_<YYYYMMDD_HHMM>.md` with:
    - p50 / p95 / p99 latency
    - FPS (throughput)
    - peak RSS (resident memory) in MB
    - average CPU% sampled during the run
    - INT8-vs-PyTorch speedup ratio

Usage:
    python -m ml.scripts.benchmark_inference --run-id <RUN>
    python -m ml.scripts.benchmark_inference --run-id <RUN> --n 50 --imgsz 320
"""

from __future__ import annotations

import argparse
import logging
import platform
import statistics
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class VariantResult:
    name: str
    n_inferences: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    fps: float
    peak_rss_mb: float
    avg_cpu_percent: float


@dataclass
class BenchmarkReport:
    run_id: str
    imgsz: int
    n: int
    cpu_model: str
    variants: list[VariantResult]


class BenchmarkError(Exception):
    """Raised when the benchmark cannot be performed."""


def _percentile(values: list[float], pct: float) -> float:
    """Return percentile `pct` (0-100) using the nearest-rank method."""
    if not values:
        raise ValueError("percentile of an empty list")
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(pct / 100 * (len(s) - 1)))))
    return s[k]


def summarise(
    latencies_ms: list[float], peak_rss_mb: float, avg_cpu: float, name: str
) -> VariantResult:
    n = len(latencies_ms)
    total_s = sum(latencies_ms) / 1000.0
    fps = n / total_s if total_s > 0 else 0.0
    return VariantResult(
        name=name,
        n_inferences=n,
        p50_ms=_percentile(latencies_ms, 50),
        p95_ms=_percentile(latencies_ms, 95),
        p99_ms=_percentile(latencies_ms, 99),
        fps=fps,
        peak_rss_mb=peak_rss_mb,
        avg_cpu_percent=avg_cpu,
    )


class _ResourceSampler:
    """Sample process RSS and CPU% in a background thread, every `interval` seconds."""

    def __init__(self, interval: float = 0.1) -> None:
        import psutil

        self._proc = psutil.Process()
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.peak_rss_mb = 0.0
        self.cpu_samples: list[float] = []

    def __enter__(self) -> _ResourceSampler:
        # Prime cpu_percent (first call returns 0.0).
        self._proc.cpu_percent(interval=None)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            rss_mb = self._proc.memory_info().rss / (1024 * 1024)
            if rss_mb > self.peak_rss_mb:
                self.peak_rss_mb = rss_mb
            self.cpu_samples.append(self._proc.cpu_percent(interval=None))
            self._stop.wait(self._interval)

    @property
    def avg_cpu_percent(self) -> float:
        if not self.cpu_samples:
            return 0.0
        return statistics.mean(self.cpu_samples)


def benchmark_variant(model_path: Path, images: list[Path], imgsz: int, name: str) -> VariantResult:
    """Time inferences for a single variant and return the aggregated VariantResult."""
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    # Warm-up — the first call lazily loads weights / compiles graphs.
    if images:
        model(str(images[0]), imgsz=imgsz, verbose=False)

    latencies_ms: list[float] = []
    with _ResourceSampler(interval=0.05) as sampler:
        for img in images:
            start = time.perf_counter()
            model(str(img), imgsz=imgsz, verbose=False)
            latencies_ms.append((time.perf_counter() - start) * 1000.0)

    return summarise(
        latencies_ms=latencies_ms,
        peak_rss_mb=sampler.peak_rss_mb,
        avg_cpu=sampler.avg_cpu_percent,
        name=name,
    )


def _pick_val_images(data_yaml: Path, n: int) -> list[Path]:
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    root = Path(data.get("path", data_yaml.parent)).resolve()
    val_dir = root / data["val"]
    images = sorted(p for p in val_dir.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not images:
        raise BenchmarkError(f"No images under val split: {val_dir}")
    if len(images) < n:
        # Recycle to reach n (cheap, deterministic).
        repeats = (n // len(images)) + 1
        images = (images * repeats)[:n]
    return images[:n]


def render_markdown(report: BenchmarkReport) -> str:
    """Format the report as Markdown."""
    lines: list[str] = []
    lines.append(f"# Benchmark — run_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}")
    lines.append("")
    lines.append(f"Run id: `{report.run_id}`  ·  imgsz: {report.imgsz}  ·  N: {report.n}")
    lines.append(f"CPU: {report.cpu_model}")
    lines.append("")
    lines.append("|             | p50 ms | p95 ms | p99 ms |   FPS | RSS MB |  CPU% |")
    lines.append("|-------------|-------:|-------:|-------:|------:|-------:|------:|")
    for v in report.variants:
        lines.append(
            f"| {v.name:<11} | {v.p50_ms:6.2f} | {v.p95_ms:6.2f} | {v.p99_ms:6.2f} "
            f"| {v.fps:5.2f} | {v.peak_rss_mb:6.1f} | {v.avg_cpu_percent:5.1f} |"
        )

    # Speedup vs PyTorch baseline.
    by_name = {v.name: v for v in report.variants}
    if "PyTorch" in by_name:
        baseline_fps = by_name["PyTorch"].fps
        if baseline_fps > 0:
            lines.append("")
            for name in ("OpenVINO FP32", "OpenVINO INT8"):
                if name in by_name:
                    speedup = by_name[name].fps / baseline_fps
                    lines.append(f"- Speedup {name} vs PyTorch: **×{speedup:.2f}**")
    lines.append("")
    return "\n".join(lines)


def run_benchmark(
    run_id: str,
    n: int = 100,
    imgsz: int = 640,
    tracking_uri: str | None = None,
    report_dir: Path = Path("docs/mlops/benchmarks"),
) -> Path:
    import mlflow
    from mlflow.tracking import MlflowClient

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    run = client.get_run(run_id)
    data_yaml_str = run.data.tags.get("dataset_path")
    if not data_yaml_str or not Path(data_yaml_str).is_file():
        raise BenchmarkError(
            f"Run {run_id} has no valid `dataset_path` tag (got {data_yaml_str!r})."
        )
    data_yaml = Path(data_yaml_str)
    images = _pick_val_images(data_yaml, n)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        variants: list[tuple[str, str, Path]] = []
        # PyTorch
        pt_root = client.download_artifacts(run_id=run_id, path="model", dst_path=str(work / "pt"))
        pt_weights = next(Path(pt_root).rglob("best.pt"), None)
        if pt_weights:
            variants.append(("PyTorch", "model/best.pt", pt_weights))
        # OpenVINO FP32
        try:
            ov_fp32_root = client.download_artifacts(
                run_id=run_id, path="openvino-fp32", dst_path=str(work / "ov_fp32")
            )
            xml = next(Path(ov_fp32_root).rglob("*.xml"), None)
            if xml:
                variants.append(("OpenVINO FP32", "openvino-fp32/*.xml", xml))
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenVINO FP32 artifacts not found in this run: %s", exc)
        # OpenVINO INT8
        try:
            ov_int8_root = client.download_artifacts(
                run_id=run_id, path="openvino-int8", dst_path=str(work / "ov_int8")
            )
            xml = next(Path(ov_int8_root).rglob("*.xml"), None)
            if xml:
                variants.append(("OpenVINO INT8", "openvino-int8/*.xml", xml))
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenVINO INT8 artifacts not found in this run: %s", exc)

        if not variants:
            raise BenchmarkError(f"Run {run_id} has no usable model artifacts.")

        results: list[VariantResult] = []
        for label, _src, weights in variants:
            logger.info("Benchmarking %s ...", label)
            results.append(benchmark_variant(weights, images, imgsz=imgsz, name=label))

    report = BenchmarkReport(
        run_id=run_id,
        imgsz=imgsz,
        n=n,
        cpu_model=platform.processor() or platform.machine(),
        variants=results,
    )

    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    out = report_dir / f"run_{stamp}.md"
    out.write_text(render_markdown(report), encoding="utf-8")
    logger.info("Wrote %s", out)
    return out


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("docs/mlops/benchmarks"),
    )
    parser.add_argument("--tracking-uri", default=None)
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    try:
        out = run_benchmark(
            run_id=args.run_id,
            n=args.n,
            imgsz=args.imgsz,
            tracking_uri=args.tracking_uri,
            report_dir=args.report_dir,
        )
    except BenchmarkError as exc:
        logger.error("%s", exc)
        return 1
    logger.info("Report: %s", out)
    return 0


# Silence the unused-import warning while keeping the type registered.
_ = asdict


if __name__ == "__main__":
    sys.exit(main())
