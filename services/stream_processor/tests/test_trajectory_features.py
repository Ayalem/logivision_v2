"""Unit tests for the shared trajectory feature extractor."""

from __future__ import annotations

import math

import numpy as np

from services.stream_processor.cep import TrackPoint
from services.stream_processor.trajectory_features import (
    N_FEATURES,
    compute_features,
    make_windows,
)

DIAG = 1000.0


def _pt(t_ms: int, x: float, y: float, w: float = 40.0, h: float = 40.0) -> TrackPoint:
    return TrackPoint(timestamp_ms=t_ms, centroid=(x, y), width=w, height=h)


def test_fewer_than_two_points_yields_empty() -> None:
    assert compute_features([], DIAG).shape == (0, N_FEATURES)
    assert compute_features([_pt(0, 0, 0)], DIAG).shape == (0, N_FEATURES)


def test_constant_velocity_track() -> None:
    # 10 px every 200 ms along x → speed = (10/1000) / 0.2 = 0.05 diag/s.
    pts = [_pt(i * 200, 10.0 * i, 100.0) for i in range(5)]
    f = compute_features(pts, DIAG)
    assert f.shape == (4, N_FEATURES)
    np.testing.assert_allclose(f[:, 0], 0.05, rtol=1e-5)  # speed
    np.testing.assert_allclose(f[1:, 1], 0.0, atol=1e-5)  # accel after warm-up
    np.testing.assert_allclose(f[1:, 2], 1.0, atol=1e-5)  # straight line
    np.testing.assert_allclose(f[:, 7], 0.2, rtol=1e-5)  # dt_s


def test_direction_reversal_flips_cosine() -> None:
    # Move right 3 steps, then back left: cos(180°) = −1 at the turn.
    pts = [_pt(0, 0, 0), _pt(200, 50, 0), _pt(400, 100, 0), _pt(600, 50, 0)]
    f = compute_features(pts, DIAG)
    assert f[-1, 2] < -0.99


def test_aspect_flip_shows_in_log_aspect_delta() -> None:
    # Tall box (h/w = 2) tips to flat (h/w = 0.5) in one 200 ms step.
    pts = [
        _pt(0, 100, 100, w=20, h=40),
        _pt(200, 100, 100, w=20, h=40),
        _pt(400, 100, 130, w=40, h=20),
    ]
    f = compute_features(pts, DIAG)
    # log(2) → log(0.5): delta = −2·log(2) over 0.2 s.
    expected = (math.log(0.5) - math.log(2.0)) / 0.2
    assert abs(f[-1, 4] - expected) < 1e-4


def test_stationary_track_has_high_dwell_ratio_and_zero_speed() -> None:
    pts = [_pt(i * 200, 300.0, 300.0) for i in range(10)]
    f = compute_features(pts, DIAG)
    np.testing.assert_allclose(f[:, 0], 0.0, atol=1e-9)  # speed
    np.testing.assert_allclose(f[:, 6], 1.0, atol=1e-9)  # dwell ratio
    np.testing.assert_allclose(f[:, 2], 1.0, atol=1e-9)  # no direction defined


def test_moving_track_has_low_dwell_ratio() -> None:
    # 100 px per step — far outside the 25 px dwell radius.
    pts = [_pt(i * 200, 100.0 * i, 0.0) for i in range(8)]
    f = compute_features(pts, DIAG)
    assert f[-1, 6] < 0.5


def test_windows_shape_and_stride() -> None:
    feats = np.arange(40 * N_FEATURES, dtype=np.float32).reshape(40, N_FEATURES)
    w = make_windows(feats, window=25, stride=5)
    assert w.shape == (4, 25, N_FEATURES)  # starts at 0, 5, 10, 15
    np.testing.assert_array_equal(w[1, 0], feats[5])


def test_short_track_yields_no_windows() -> None:
    feats = np.zeros((10, N_FEATURES), dtype=np.float32)
    assert make_windows(feats, window=25, stride=5).shape == (0, 25, N_FEATURES)
