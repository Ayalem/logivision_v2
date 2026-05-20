"""Unit tests for ml.scripts.drift_monitor — Evidently calls are mocked."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from ml.scripts.drift_monitor import (
    REQUIRED_FEATURES,
    DriftResult,
    _fallback_psi,
    _psi_single,
    _validate,
    render_prometheus,
    run_drift,
)


def _make_df(n: int, seed: int, mean_shift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "brightness": rng.normal(100 + mean_shift, 15, size=n),
            "contrast": rng.normal(50, 10, size=n),
            "n_detections": rng.integers(0, 5, size=n),
            "avg_confidence": rng.uniform(0.3, 0.9, size=n),
        }
    )


def _write(df: pd.DataFrame, tmp_path: Path, name: str) -> Path:
    out = tmp_path / name
    df.to_csv(out, index=False)
    return out


def test_validate_passes_on_complete_schema() -> None:
    df = _make_df(10, seed=1)
    _validate(df, "x")  # no exception


def test_validate_raises_on_missing_columns() -> None:
    df = pd.DataFrame({"brightness": [1, 2]})
    with pytest.raises(ValueError, match="missing required columns"):
        _validate(df, "x")


def test_psi_single_returns_zero_on_identical_distributions() -> None:
    rng = np.random.default_rng(0)
    a = pd.Series(rng.normal(0, 1, 200))
    b = pd.Series(rng.normal(0, 1, 200))
    # Same generator family + similar size → low PSI.
    assert _psi_single(a, b) < 0.2


def test_psi_single_detects_shift() -> None:
    rng = np.random.default_rng(0)
    a = pd.Series(rng.normal(0, 1, 200))
    b = pd.Series(rng.normal(3, 1, 200))  # large mean shift
    assert _psi_single(a, b) > 0.5


def test_fallback_psi_flags_drift_when_threshold_crossed() -> None:
    ref = _make_df(200, seed=1)
    cur = _make_df(200, seed=2, mean_shift=80)  # huge brightness shift
    overall, n_drifted, scores = _fallback_psi(ref, cur, threshold=0.3)
    assert overall is True
    assert n_drifted >= 1
    assert "brightness" in scores
    assert scores["brightness"] > 0.3


def test_fallback_psi_does_not_flag_when_distributions_match() -> None:
    ref = _make_df(200, seed=1)
    cur = _make_df(200, seed=2, mean_shift=0)  # same generative process
    overall, n_drifted, _ = _fallback_psi(ref, cur, threshold=0.3)
    assert overall is False
    assert n_drifted == 0


def test_run_drift_writes_html_and_json(tmp_path: Path) -> None:
    ref_csv = _write(_make_df(100, seed=1), tmp_path, "ref.csv")
    cur_csv = _write(_make_df(100, seed=2, mean_shift=50), tmp_path, "cur.csv")
    out_dir = tmp_path / "out"

    # Force the fallback path by simulating Evidently absent.
    with patch.dict("sys.modules", {"evidently.metric_preset": None, "evidently.report": None}):
        result = run_drift(ref_csv, cur_csv, output_dir=out_dir, threshold=0.3)

    assert Path(result.report_html).is_file()
    assert Path(result.report_json).is_file()
    payload = json.loads(Path(result.report_json).read_text())
    assert "feature_scores" in payload
    assert payload["threshold"] == 0.3
    assert isinstance(payload["dataset_drift"], bool)


def test_render_prometheus_produces_one_line_per_feature() -> None:
    r = DriftResult(
        dataset_drift=True,
        n_drifted_features=2,
        feature_scores={"brightness": 0.55, "n_detections": 0.31, "avg_confidence": 0.1},
        threshold=0.3,
        report_html="x.html",
        report_json="x.json",
    )
    text = render_prometheus(r)
    for feature in r.feature_scores:
        assert f'logivision_drift_score{{feature="{feature}"}}' in text
    assert "logivision_drift_detected 1" in text


def test_required_features_are_stable() -> None:
    # Guard against accidental schema drift in tests.
    assert REQUIRED_FEATURES == [
        "brightness",
        "contrast",
        "n_detections",
        "avg_confidence",
    ]
