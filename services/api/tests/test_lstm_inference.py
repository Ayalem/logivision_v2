"""Occupancy binning + cold-start gates in services/api/_lstm_inference.py."""

from __future__ import annotations

from services.api._lstm_inference import (
    MIN_BIN_COVERAGE,
    MIN_SPAN_HOURS,
    SOURCE_INSUFFICIENT,
    SOURCE_LSTM,
    _bin_zone_occupancy,
    forecast_zone_occupancy,
)

NOW = 1_700_000_000_000
BIN_MS = 30 * 60_000


def _snap(zone: str, bins_ago: int, ratio: float) -> dict:
    return {"zone": zone, "timestamp_ms": NOW - bins_ago * BIN_MS - 1, "ratio": ratio}


def test_bins_are_oldest_first_and_zone_filtered() -> None:
    snaps = [
        _snap("A", 0, 0.8),
        _snap("A", 47, 0.2),
        _snap("B", 0, 0.99),  # other zone — ignored
    ]
    bins = _bin_zone_occupancy(snaps, "A", NOW, n_bins=48, bin_minutes=30)
    assert len(bins) == 48
    assert bins[0] == 0.2  # oldest
    assert bins[-1] == 0.8  # newest
    assert all(v is None for v in bins[1:-1])


def test_multiple_snapshots_in_one_bin_are_averaged() -> None:
    snaps = [_snap("A", 0, 0.4), _snap("A", 0, 0.8)]
    bins = _bin_zone_occupancy(snaps, "A", NOW, n_bins=48, bin_minutes=30)
    assert abs(bins[-1] - 0.6) < 1e-9


def test_out_of_window_and_malformed_snapshots_skipped() -> None:
    snaps = [
        _snap("A", 60, 0.5),  # older than the window
        {"zone": "A", "timestamp_ms": NOW + 10_000, "ratio": 0.5},  # future
        {"zone": "A", "timestamp_ms": NOW - 1, "ratio": "n/a"},  # malformed
    ]
    bins = _bin_zone_occupancy(snaps, "A", NOW, n_bins=48, bin_minutes=30)
    assert all(v is None for v in bins)


def test_cold_start_constants_are_sane() -> None:
    # The forecast path refuses to run below these gates; the values are
    # part of the documented methodology (>=50% coverage over >=12h).
    assert MIN_BIN_COVERAGE == 0.5
    assert MIN_SPAN_HOURS == 12.0


def test_forecast_insufficient_history_with_sparse_snapshots() -> None:
    # Only 3 recent bins of real data → honest insufficient-history result
    # (requires the committed Birmingham artifact; skips if absent).
    snaps = [_snap("A", i, 0.5) for i in range(3)]
    out = forecast_zone_occupancy(snaps, "A", NOW)
    if out is None:  # torch/artifact unavailable in this environment
        return
    assert out["source"] == SOURCE_INSUFFICIENT
    assert out["bins_available"] == 3


def test_forecast_returns_bounded_ratios_with_dense_history() -> None:
    # Full 24 h of snapshots → real LSTM forecast in ratio space (0..1).
    snaps = [_snap("A", i, 0.3 + 0.4 * (i % 2)) for i in range(48)]
    out = forecast_zone_occupancy(snaps, "A", NOW)
    if out is None:
        return
    assert out["source"] == SOURCE_LSTM
    assert len(out["forecast"]) == 3
    assert all(0.0 <= v <= 1.0 for v in out["forecast"])
