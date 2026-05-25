"""Train several detector architectures on the same dataset and produce a Markdown comparison.

For each architecture listed under `architectures:` in the config:
    1. Build a YOLO config dict by merging shared_hyperparameters with the
       arch-specific `weights` (we reuse ml.scripts.train.train()).
    2. Train it — every run is logged to MLflow under
       experiment "warehouse-arch-comparison" with a `comparison_group` tag
       (the timestamp of this sweep).
    3. Collect val_map50 / val_map50_95 / val_precision / val_recall.

After all archs are trained, write a Markdown table sorted by val_map50
into `docs/mlops/comparisons/run_YYYYMMDD_HHMM.md`.

This does NOT promote anything; it's a sweep. Use `make promote` on the
winner afterwards.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ArchResult:
    name: str
    weights: str
    run_id: str
    map50: float
    map50_95: float
    train_seconds: float
    failed_reason: str | None = None


def _build_train_config(comparison_cfg: dict, arch_name: str, arch_weights: str) -> dict:
    """Merge the comparison config with a single architecture into a `train.py`-shaped config."""
    return {
        "mlflow": {
            "tracking_uri": comparison_cfg["mlflow"]["tracking_uri"],
            "experiment": comparison_cfg["mlflow"]["experiment"],
            "registered_model_name": f"logivision-detector-{arch_name}",
        },
        "model": {"arch": arch_name, "weights": arch_weights},
        "data": comparison_cfg["data"],
        "hyperparameters": dict(comparison_cfg["shared_hyperparameters"]),
        "runtime": dict(comparison_cfg["runtime"]),
    }


def _train_one(arch_name: str, arch_weights: str, comparison_cfg: dict, tag: str) -> ArchResult:
    """Train a single architecture. Returns ArchResult; failures are captured (not raised)."""
    from ml.scripts.train import train

    started = time.perf_counter()
    train_cfg = _build_train_config(comparison_cfg, arch_name, arch_weights)
    try:
        import mlflow

        mlflow.set_tracking_uri(train_cfg["mlflow"]["tracking_uri"])
        # We tag the parent sweep via env var so train.py adds it (best-effort).
        result = train(train_cfg)
    except Exception as exc:  # noqa: BLE001  — we capture everything for the report
        return ArchResult(
            name=arch_name,
            weights=arch_weights,
            run_id="",
            map50=0.0,
            map50_95=0.0,
            train_seconds=time.perf_counter() - started,
            failed_reason=str(exc),
        )

    # Best-effort: tag the run with the sweep id so the report can group them.
    try:
        from mlflow.tracking import MlflowClient

        MlflowClient(tracking_uri=train_cfg["mlflow"]["tracking_uri"]).set_tag(
            result.run_id, "comparison_group", tag
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not tag run %s with comparison_group: %s", result.run_id, exc)

    return ArchResult(
        name=arch_name,
        weights=arch_weights,
        run_id=result.run_id,
        map50=result.map50,
        map50_95=result.map50_95,
        train_seconds=time.perf_counter() - started,
        failed_reason=None,
    )


def render_markdown(results: list[ArchResult], comparison_cfg: dict, tag: str) -> str:
    hp = comparison_cfg["shared_hyperparameters"]
    lines: list[str] = []
    lines.append(f"# Architecture comparison — {tag}")
    lines.append("")
    lines.append(
        f"Dataset: `{comparison_cfg['data']['yaml_path']}` · "
        f"epochs: {hp['epochs']} · imgsz: {hp['imgsz']} · batch: {hp['batch']} · "
        f"seed: {hp['seed']}"
    )
    lines.append("")
    lines.append(
        "| Architecture | weights      | mAP50 | mAP50-95 | train s | run id      | notes |"
    )
    lines.append(
        "|--------------|--------------|------:|---------:|--------:|-------------|-------|"
    )
    # Sort by mAP50 descending; failed archs at the bottom with score 0.
    sorted_results = sorted(results, key=lambda r: (-r.map50, r.name))
    for r in sorted_results:
        note = r.failed_reason or ""
        if len(note) > 60:
            note = note[:57] + "…"
        lines.append(
            f"| {r.name:<12} | {r.weights:<12} | {r.map50:.4f} | {r.map50_95:.4f} "
            f"| {r.train_seconds:7.1f} | `{r.run_id[:8] if r.run_id else '-':<11}` | {note} |"
        )
    if sorted_results and sorted_results[0].run_id:
        lines.append("")
        lines.append(
            f"**Winner**: `{sorted_results[0].name}` (mAP50 = {sorted_results[0].map50:.4f}). "
            f"Promote with `make promote RUN={sorted_results[0].run_id}` "
            "(use the matching `logivision-detector-<arch>` model name)."
        )
    lines.append("")
    return "\n".join(lines)


def run_comparison(comparison_cfg: dict, report_dir: Path) -> Path:
    archs = comparison_cfg["architectures"]
    tag = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    results: list[ArchResult] = []
    for arch_name, arch_spec in archs.items():
        logger.info("=== Training %s ===", arch_name)
        results.append(_train_one(arch_name, arch_spec["weights"], comparison_cfg, tag))
    report_dir.mkdir(parents=True, exist_ok=True)
    out = report_dir / f"run_{tag}.md"
    out.write_text(render_markdown(results, comparison_cfg, tag), encoding="utf-8")
    logger.info("Wrote %s", out)
    # also dump a json next to the md for easy parsing
    (out.with_suffix(".json")).write_text(
        __import__("json").dumps([asdict(r) for r in results], indent=2),
        encoding="utf-8",
    )
    return out


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("ml/configs/comparison.yaml"),
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("docs/mlops/comparisons"),
    )
    parser.add_argument(
        "--archs",
        default=None,
        help="Comma-separated subset of architectures to run (default: all in config).",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if args.archs:
        wanted = {a.strip() for a in args.archs.split(",") if a.strip()}
        config["architectures"] = {
            name: spec for name, spec in config["architectures"].items() if name in wanted
        }
        if not config["architectures"]:
            logger.error("No matching architectures in %s (wanted: %s)", args.config, wanted)
            return 1
    out = run_comparison(config, args.report_dir)
    logger.info("Report: %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
