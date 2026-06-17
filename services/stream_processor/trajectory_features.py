"""Trajectory feature extraction shared by training and online scoring.

This module is imported by BOTH `ml/notebooks/08_trajectory_autoencoder.ipynb`
(via the builder script) and `services/stream_processor/anomaly_scorer.py`.
A single implementation on both sides eliminates training/serving skew —
the methodological claim the article makes explicitly.

Feature vector (8 per timestep, camera/position-invariant — raw centroids
are deliberately excluded so the model generalises across cameras instead
of memorising one scene layout):

    0  speed       ‖Δcentroid‖ / Δt, in frame-diagonals per second
    1  accel       Δspeed / Δt
    2  dir_change  cos(angle between successive velocity vectors);
                   1.0 when either speed ≈ 0 (no direction defined)
    3  log_aspect  log(height/width) — symmetric around square; a box
                   tipping over flips its sign
    4  d_aspect    Δlog_aspect / Δt (captures the tip-over dynamics)
    5  sqrt_area   sqrt(w·h) / frame_diagonal (scale ∝ camera depth)
    6  dwell_ratio fraction of the trailing 30 s of track history within
                   25 px of its rolling centroid (long-dwell signal folded
                   into a short window; thresholds match the CEP
                   stationary rule for a like-for-like baseline)
    7  dt_s        gap to the previous point in seconds (irregular fps is
                   a feature, not an assumption)

Windows: `WINDOW` consecutive timesteps (~5 s at 5 fps) with stride
`STRIDE`. Tracks shorter than `WINDOW`+1 points yield no windows — short
tracks are never scored (documented limitation).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # avoid a runtime import cycle with cep.py
    from services.stream_processor.cep import TrackPoint

N_FEATURES = 8
WINDOW = 25  # timesteps per scoring window (~5 s @ 5 fps)
STRIDE = 5  # window stride (~1 s @ 5 fps)

DWELL_WINDOW_S = 30.0  # matches CEPConfig.stationary_window_s
DWELL_RADIUS_PX = 25.0  # matches CEPConfig.stationary_radius_px

_EPS = 1e-6

FEATURE_NAMES = [
    "speed",
    "accel",
    "dir_change",
    "log_aspect",
    "d_aspect",
    "sqrt_area",
    "dwell_ratio",
    "dt_s",
]


def _dwell_ratio(points: list[TrackPoint], idx: int) -> float:
    """Fraction of the trailing 30 s of history within 25 px of its mean."""
    t_now = points[idx].timestamp_ms
    window = [p for p in points[: idx + 1] if t_now - p.timestamp_ms <= DWELL_WINDOW_S * 1000]
    if len(window) < 2:
        return 0.0
    cx = sum(p.centroid[0] for p in window) / len(window)
    cy = sum(p.centroid[1] for p in window) / len(window)
    inside = sum(
        1 for p in window if math.hypot(p.centroid[0] - cx, p.centroid[1] - cy) <= DWELL_RADIUS_PX
    )
    return inside / len(window)


def compute_features(points: list[TrackPoint], frame_diag: float) -> np.ndarray:
    """Per-timestep features for one track.

    `points` must be time-ordered. Returns an array of shape
    (len(points) - 1, N_FEATURES) — each row describes the transition into
    point i (i >= 1). Fewer than 2 points → shape (0, N_FEATURES).
    """
    n = len(points)
    out = np.zeros((max(0, n - 1), N_FEATURES), dtype=np.float32)
    if n < 2:
        return out

    diag = max(_EPS, float(frame_diag))
    prev_speed = 0.0
    prev_vel: tuple[float, float] | None = None
    prev_log_aspect: float | None = None

    for i in range(1, n):
        cur, prev = points[i], points[i - 1]
        dt_s = max(_EPS, (cur.timestamp_ms - prev.timestamp_ms) / 1000.0)
        dx = cur.centroid[0] - prev.centroid[0]
        dy = cur.centroid[1] - prev.centroid[1]
        dist = math.hypot(dx, dy)
        speed = (dist / diag) / dt_s
        accel = (speed - prev_speed) / dt_s if i > 1 else 0.0

        vel = (dx / dt_s, dy / dt_s)
        if prev_vel is None or dist / diag < _EPS or math.hypot(*prev_vel) < _EPS:
            dir_change = 1.0
        else:
            dot = vel[0] * prev_vel[0] + vel[1] * prev_vel[1]
            norm = math.hypot(*vel) * math.hypot(*prev_vel)
            dir_change = max(-1.0, min(1.0, dot / max(_EPS, norm)))

        w = max(_EPS, float(cur.width))
        h = max(_EPS, float(cur.height))
        log_aspect = math.log(h / w)
        d_aspect = (log_aspect - prev_log_aspect) / dt_s if prev_log_aspect is not None else 0.0
        sqrt_area = math.sqrt(w * h) / diag

        out[i - 1] = (
            speed,
            accel,
            dir_change,
            log_aspect,
            d_aspect,
            sqrt_area,
            _dwell_ratio(points, i),
            dt_s,
        )
        prev_speed = speed
        prev_vel = vel
        prev_log_aspect = log_aspect

    return out


def make_windows(features: np.ndarray, window: int = WINDOW, stride: int = STRIDE) -> np.ndarray:
    """Slice a (T, N_FEATURES) feature matrix into overlapping windows.

    Returns shape (n_windows, window, N_FEATURES); empty when the track is
    shorter than one window.
    """
    n = features.shape[0]
    if n < window:
        return np.zeros((0, window, features.shape[1]), dtype=np.float32)
    starts = range(0, n - window + 1, stride)
    return np.stack([features[s : s + window] for s in starts]).astype(np.float32)
