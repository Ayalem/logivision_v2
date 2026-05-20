"""Detect data + prediction drift between two snapshots.

Two inputs, both as a CSV/Parquet of per-frame features. The schema is:

    timestamp_ms,brightness,contrast,width,height,n_detections,avg_confidence,top_class

Pipeline:
    1. Load reference + current dataframes.
    2. Run Evidently's DataDriftPreset (defaults to PSI for numeric features).
    3. Persist:
         - HTML report  (docs/mlops/drift/run_<ts>.html)
         - JSON summary (docs/mlops/drift/run_<ts>.json) — drift_score per feature
                                                            + overall `dataset_drift` bool
    4. Optionally publish a Prometheus-style line per feature on stdout (`--prom`)
       so an external scraper can grab it.
    5. Exit code:
         0 = no drift
         1 = drift detected on at least one watched feature
         2 = input error

Generate the per-frame features by replaying frames through `extract_frames.py`
and the detector — see `compute_features_from_frames()` for the helper used by
the upcoming retraining trigger (Sprint 1.7 T1.7.3).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


REQUIRED_FEATURES = [
    "brightness",
    "contrast",
    "n_detections",
    "avg_confidence",
]


@dataclass
class DriftResult:
    dataset_drift: bool
    n_drifted_features: int
    feature_scores: dict[str, float]  # feature -> drift score (0..1, higher = more drift)
    threshold: float
    report_html: str
    report_json: str


def _load_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() in {".csv", ".tsv"}:
        sep = "," if path.suffix.lower() == ".csv" else "\t"
        return pd.read_csv(path, sep=sep)
    raise ValueError(f"Unsupported extension: {path.suffix} (use .csv or .parquet)")


def _validate(df: pd.DataFrame, name: str) -> None:
    missing = [f for f in REQUIRED_FEATURES if f not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def compute_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    threshold: float = 0.3,
) -> tuple[bool, int, dict[str, float]]:
    """Return (overall_drift, n_drifted, per_feature_scores).

    Uses PSI for numeric features. Falls back to a hand-rolled PSI if Evidently
    is not importable — keeps the test suite light.
    """
    try:
        from evidently.metric_preset import DataDriftPreset
        from evidently.report import Report
    except ImportError:
        logger.warning("Evidently not installed — falling back to PSI in numpy.")
        return _fallback_psi(reference, current, threshold)

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference[REQUIRED_FEATURES], current_data=current[REQUIRED_FEATURES])
    payload = report.as_dict()

    drift_metric = next(
        (m for m in payload.get("metrics", []) if m.get("metric") == "DatasetDriftMetric"),
        None,
    )
    overall = bool(drift_metric and drift_metric.get("result", {}).get("dataset_drift", False))

    per_feature: dict[str, float] = {}
    feature_metric = next(
        (m for m in payload.get("metrics", []) if m.get("metric") == "DataDriftTable"),
        None,
    )
    if feature_metric:
        for fname, fdata in feature_metric.get("result", {}).get("drift_by_columns", {}).items():
            per_feature[fname] = float(fdata.get("drift_score", 0.0))
    n_drifted = sum(1 for s in per_feature.values() if s >= threshold)
    return overall, n_drifted, per_feature


def _psi_single(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    """Population Stability Index between two 1-D distributions."""
    import numpy as np

    if len(reference) == 0 or len(current) == 0:
        return 0.0
    edges = np.quantile(reference, np.linspace(0, 1, bins + 1))
    edges = np.unique(edges)
    if len(edges) < 2:
        return 0.0
    ref_hist, _ = np.histogram(reference, bins=edges)
    cur_hist, _ = np.histogram(current, bins=edges)
    ref_p = ref_hist / max(ref_hist.sum(), 1)
    cur_p = cur_hist / max(cur_hist.sum(), 1)
    eps = 1e-6
    psi = float(((cur_p - ref_p) * np.log((cur_p + eps) / (ref_p + eps))).sum())
    return abs(psi)


def _fallback_psi(
    reference: pd.DataFrame, current: pd.DataFrame, threshold: float
) -> tuple[bool, int, dict[str, float]]:
    scores = {f: _psi_single(reference[f], current[f]) for f in REQUIRED_FEATURES if f in reference}
    n_drifted = sum(1 for s in scores.values() if s >= threshold)
    return n_drifted > 0, n_drifted, scores


def run_drift(
    reference_path: Path,
    current_path: Path,
    output_dir: Path,
    threshold: float = 0.3,
) -> DriftResult:
    ref = _load_table(reference_path)
    cur = _load_table(current_path)
    _validate(ref, "reference")
    _validate(cur, "current")

    overall, n_drifted, scores = compute_drift(ref, cur, threshold)

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    html_path = output_dir / f"run_{stamp}.html"
    json_path = output_dir / f"run_{stamp}.json"

    # Compact HTML — embed the JSON inside a <pre> for now.  Evidently's full
    # Report().save_html(...) is optional; the JSON is the authoritative output.
    try:
        from evidently.metric_preset import DataDriftPreset
        from evidently.report import Report

        report = Report(metrics=[DataDriftPreset()])
        report.run(reference_data=ref[REQUIRED_FEATURES], current_data=cur[REQUIRED_FEATURES])
        report.save_html(str(html_path))
    except Exception as exc:  # noqa: BLE001 — Evidently optional
        logger.warning("Evidently HTML render failed (%s); writing JSON only.", exc)
        html_path.write_text(
            f"<html><body><pre>{json.dumps(scores, indent=2)}</pre></body></html>",
            encoding="utf-8",
        )

    json_path.write_text(
        json.dumps(
            {
                "dataset_drift": overall,
                "n_drifted_features": n_drifted,
                "threshold": threshold,
                "feature_scores": scores,
                "ref_n_rows": int(len(ref)),
                "cur_n_rows": int(len(cur)),
                "ref_path": str(reference_path),
                "cur_path": str(current_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return DriftResult(
        dataset_drift=overall,
        n_drifted_features=n_drifted,
        feature_scores=scores,
        threshold=threshold,
        report_html=str(html_path),
        report_json=str(json_path),
    )


def render_prometheus(result: DriftResult) -> str:
    """Plain-text Prometheus exposition format. One line per feature plus overall."""
    lines = [
        "# HELP logivision_drift_score Per-feature drift score (0=stable, higher=more drift).",
        "# TYPE logivision_drift_score gauge",
    ]
    for feature, score in result.feature_scores.items():
        lines.append(f'logivision_drift_score{{feature="{feature}"}} {score:.6f}')
    lines.append("# HELP logivision_drift_detected 1 if dataset drift, else 0.")
    lines.append("# TYPE logivision_drift_detected gauge")
    lines.append(f"logivision_drift_detected {1 if result.dataset_drift else 0}")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--reference", type=Path, required=True, help="Reference features CSV/Parquet."
    )
    parser.add_argument("--current", type=Path, required=True, help="Current features CSV/Parquet.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/mlops/drift"),
        help="Output directory for HTML + JSON reports.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="PSI (or drift_score) threshold; per-feature drift triggered above this.",
    )
    parser.add_argument(
        "--prom",
        action="store_true",
        help="Also print Prometheus-format metrics to stdout (for scraping).",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    try:
        result = run_drift(
            reference_path=args.reference,
            current_path=args.current,
            output_dir=args.output,
            threshold=args.threshold,
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 2
    if args.prom:
        print(render_prometheus(result))
    logger.info(
        "dataset_drift=%s n_drifted=%d/%d  HTML=%s  JSON=%s",
        result.dataset_drift,
        result.n_drifted_features,
        len(result.feature_scores),
        result.report_html,
        result.report_json,
    )
    # Optional Markdown one-liner for chat/CI.
    print(
        json.dumps(
            {
                "dataset_drift": result.dataset_drift,
                "n_drifted_features": result.n_drifted_features,
                "feature_scores": result.feature_scores,
                "html": result.report_html,
            }
        )
    )
    return 1 if result.dataset_drift else 0


# Silence the unused-import warning while keeping the type registered.
_ = asdict


if __name__ == "__main__":
    sys.exit(main())
