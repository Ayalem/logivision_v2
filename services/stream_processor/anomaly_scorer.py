"""Online trajectory-anomaly scoring for the CEP (GRU autoencoder).

Loads `ml/artifacts/trajectory_ae/model.pt` (trained by
`ml/notebooks/08_trajectory_autoencoder.ipynb`) and scores each tracked
object's trailing motion window. Windows whose reconstruction error
exceeds the thresholds stored in the checkpoint (validation-percentile
provenance) yield a `ScoreResult` the CEP turns into a
`trajectory_anomaly` Kafka event.

Mirrors the design of `services/api/_lstm_inference.py`:
  * Lazy singleton — model loaded once per process, on first use.
  * Inline nn.Module mirror of the notebook architecture.
  * Graceful degradation — missing artifact / missing torch → scorer
    reports itself unavailable and the CEP falls back to rules mode.

Train/serve skew: features come from the same
`trajectory_features.compute_features` the notebook used. The scorer
evaluates a track at most once per second (`SCORE_STRIDE_S`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from services.stream_processor.trajectory_features import (
    FEATURE_NAMES,
    WINDOW,
    compute_features,
)

if TYPE_CHECKING:
    from services.stream_processor.cep import TrackState

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_PATH = REPO_ROOT / "ml" / "artifacts" / "trajectory_ae" / "model.pt"

MODEL_VERSION = "trajectory-ae-v1"
SCORE_STRIDE_S = 1.0  # score each track at most once per second


@dataclass
class ScoreResult:
    score: float
    threshold: float
    severity: str  # "warning" | "critical"
    dominant_feature: str
    model_version: str = MODEL_VERSION


class AnomalyScorer:
    """Per-process scorer; one instance shared across all tracks."""

    def __init__(self, artifact_path: Path = ARTIFACT_PATH):
        self._artifact_path = artifact_path
        self._loaded = False
        self._model: Any = None
        self._config: dict | None = None
        self._last_scored_ms: dict[str, int] = {}

    # ── loading ─────────────────────────────────────────────────────────

    def _load_once(self) -> bool:
        if self._loaded:
            return self._model is not None
        self._loaded = True

        if not self._artifact_path.is_file():
            logger.info("Trajectory-AE artifact missing at %s.", self._artifact_path)
            return False
        try:
            import torch
            import torch.nn as nn
        except ImportError:
            logger.warning("PyTorch unavailable; trajectory-AE scoring disabled.")
            return False

        class TrajectoryGRUAE(nn.Module):
            """Mirror of the architecture in notebook 08."""

            def __init__(self, n_features: int, hidden: int = 32, latent: int = 16):
                super().__init__()
                self.encoder = nn.GRU(n_features, hidden, batch_first=True)
                self.to_latent = nn.Linear(hidden, latent)
                self.from_latent = nn.Linear(latent, hidden)
                self.decoder = nn.GRU(hidden, hidden, batch_first=True)
                self.head = nn.Linear(hidden, n_features)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                _, h = self.encoder(x)
                z = self.to_latent(h[-1])
                rep = self.from_latent(z).unsqueeze(1).repeat(1, x.shape[1], 1)
                out, _ = self.decoder(rep)
                return self.head(out)

        try:
            ckpt = torch.load(self._artifact_path, map_location="cpu", weights_only=False)
            config = ckpt["config"]
            model = TrajectoryGRUAE(
                n_features=config["n_features"],
                hidden=config.get("hidden", 32),
                latent=config.get("latent", 16),
            )
            model.load_state_dict(ckpt["model_state"])
            model.eval()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load trajectory-AE checkpoint (%s).", exc)
            return False

        self._model = model
        self._config = config
        logger.info(
            "Trajectory AE loaded — window=%d, thresholds warn=%.5f crit=%.5f (%s)",
            config["window"],
            config["threshold_warning"],
            config["threshold_critical"],
            config.get("threshold_provenance", "?"),
        )
        return True

    @property
    def available(self) -> bool:
        return self._load_once()

    # ── scoring ─────────────────────────────────────────────────────────

    def score_track(
        self,
        track_id: str,
        state: TrackState,
        now_ms: int,
        frame_diag: float,
    ) -> ScoreResult | None:
        """Score the track's trailing window. None when not scorable.

        Not scorable: model unavailable, track shorter than the window,
        or the per-track scoring stride hasn't elapsed.
        """
        if not self._load_once():
            return None
        config = self._config
        assert config is not None  # guarded by _load_once
        window = int(config["window"])
        if len(state.points) < window + 1:
            return None
        last = self._last_scored_ms.get(track_id, 0)
        if now_ms - last < SCORE_STRIDE_S * 1000:
            return None
        self._last_scored_ms[track_id] = now_ms

        import numpy as np
        import torch

        points = list(state.points)[-(window + 1) :]
        feats = compute_features(points, frame_diag)  # (window, n_features)
        if feats.shape[0] < window:
            return None
        mu = np.asarray(config["mu"], dtype=np.float32)
        sigma = np.asarray(config["sigma"], dtype=np.float32)
        z = (feats[-window:] - mu) / sigma
        x = torch.from_numpy(z.astype(np.float32)).unsqueeze(0)

        with torch.no_grad():
            err = (self._model(x) - x) ** 2  # (1, window, n_features)
        score = float(err.mean())
        warn = float(config["threshold_warning"])
        crit = float(config["threshold_critical"])
        if score < warn:
            return None

        per_feature = err.mean(dim=(0, 1)).numpy()
        names = config.get("feature_names", FEATURE_NAMES)
        dominant = names[int(per_feature.argmax())]
        severity = "critical" if score >= crit else "warning"
        return ScoreResult(
            score=score,
            threshold=crit if severity == "critical" else warn,
            severity=severity,
            dominant_feature=dominant,
        )

    def forget_track(self, track_id: str) -> None:
        self._last_scored_ms.pop(track_id, None)


__all__ = ["AnomalyScorer", "ScoreResult", "MODEL_VERSION", "WINDOW"]
