"""LSTM congestion-forecast inference for the dashboard.

Loads `ml/artifacts/congestion_lstm/model.pt` (the PyTorch state_dict
trained by `ml/notebooks/05_congestion_lstm.ipynb` on Parking Birmingham
occupancy ratios) and exposes a single high-level call:

    forecast = forecast_zone_occupancy(snapshots, zone_id, now_ms)

`snapshots` are messages from the `zone-occupancy` Kafka topic emitted by
the CEP's ZoneOccupancyAggregator — per-zone occupancy *ratios* (0..1).
That is the exact quantity the model was trained on (Birmingham car-park
occupancy ratios on a 30-min grid), which is what makes the domain
transfer defensible: same feature, same resolution, same normalisation —
only the location type changes (car park → warehouse zone).

Design notes:
  * Lazy-loaded model — the cold-path /api/predictions endpoint never
    pays the import / load cost until the first call.
  * Module-level singleton — the model is loaded once per process.
  * Graceful degradation — if the artifact is missing or PyTorch can't
    be imported, every call returns `None`. The caller falls back to
    the rule-based forecast.
  * Honest cold start — with less than half the 24 h input window (or
    under 12 h of span) of real history, we return
    `{"source": "insufficient-history", ...}` instead of fabricating a
    curve. The dashboard says so. Gaps *between* real observations are
    forward-filled (documented imputation, not fabrication).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO_ROOT / "ml" / "artifacts" / "congestion_lstm"
MODEL_PATH = ARTIFACT_DIR / "model.pt"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"

# Source tag used by the dashboard's Congestion panel to decide which
# badge to render. Keep stable — frontend matches the string literally.
SOURCE_LSTM = "lstm-birmingham-v2"
SOURCE_RULE = "rule-v0"
SOURCE_INSUFFICIENT = "insufficient-history"

# Cold-start gates: require at least this fraction of input bins to hold
# real observations, spanning at least this many hours.
MIN_BIN_COVERAGE = 0.5
MIN_SPAN_HOURS = 12.0

_model_cache: dict[str, Any] = {"loaded": False, "model": None, "config": None}


def _load_model_once() -> tuple[Any, dict] | tuple[None, None]:
    """Lazy-init the model + config. Returns (None, None) on any failure."""
    if _model_cache["loaded"]:
        return _model_cache["model"], _model_cache["config"]
    _model_cache["loaded"] = True  # don't retry on later calls

    if not MODEL_PATH.is_file():
        logger.info("LSTM artifact missing at %s; falling back to rule-based forecast.", MODEL_PATH)
        return None, None

    try:
        import torch
        import torch.nn as nn
    except ImportError:
        logger.warning("PyTorch unavailable; LSTM disabled.")
        return None, None

    class CongestionLSTM(nn.Module):
        """Mirror of the architecture in notebook 05.

        Kept inline so the API doesn't depend on the notebook's namespace
        and the worker doesn't need PyTorch at *import* time.
        """

        def __init__(self, n_nodes: int, n_horizons: int, hidden: int = 64, dropout: float = 0.2):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=n_nodes,
                hidden_size=hidden,
                num_layers=2,
                batch_first=True,
                dropout=dropout,
            )
            self.head = nn.Linear(hidden, n_horizons * n_nodes)
            self.n_horizons = n_horizons
            self.n_nodes = n_nodes

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            out, _ = self.lstm(x)
            last = out[:, -1, :]
            y = self.head(last)
            return y.view(-1, self.n_horizons, self.n_nodes)

    try:
        ckpt = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
        config = ckpt["config"]
        if config.get("feature") != "occupancy_ratio":
            # Refuse to serve a checkpoint trained on a different quantity
            # (e.g. the legacy PRSA event-count model) — the inference-side
            # binning below produces occupancy ratios and nothing else.
            logger.warning(
                "LSTM checkpoint feature=%r is not 'occupancy_ratio'; refusing to load. "
                "Re-run notebook 05 to produce a compatible artifact.",
                config.get("feature"),
            )
            return None, None
        model = CongestionLSTM(
            n_nodes=config["n_nodes"],
            n_horizons=config["n_horizons"],
        )
        model.load_state_dict(ckpt["model_state"])
        model.eval()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load LSTM checkpoint (%s); falling back to rule.", exc)
        return None, None

    _model_cache["model"] = model
    _model_cache["config"] = config
    logger.info(
        "Congestion LSTM loaded — %d nodes, horizons %s, %d×%dmin input bins",
        config["n_nodes"],
        config["horizons_hours"],
        config["input_len"],
        config.get("bin_minutes", 30),
    )
    return model, config


def _bin_zone_occupancy(
    snapshots: list[dict],
    zone_id: str,
    now_ms: int,
    n_bins: int,
    bin_minutes: int,
) -> list[float | None]:
    """Mean occupancy ratio per `bin_minutes` bin for `zone_id`.

    Returns a list of length `n_bins`, oldest first; bins with no
    snapshot are `None` (the caller decides whether coverage suffices).
    """
    bin_ms = bin_minutes * 60_000
    cutoff = now_ms - n_bins * bin_ms
    sums: dict[int, float] = {}
    counts: dict[int, int] = {}
    for snap in snapshots:
        if snap.get("zone") != zone_id:
            continue
        ts = int(snap.get("timestamp_ms", 0))
        if ts < cutoff or ts > now_ms:
            continue
        bins_ago = int((now_ms - ts) / bin_ms)
        if 0 <= bins_ago < n_bins:
            try:
                ratio = float(snap["ratio"])
            except (KeyError, TypeError, ValueError):
                continue
            sums[bins_ago] = sums.get(bins_ago, 0.0) + ratio
            counts[bins_ago] = counts.get(bins_ago, 0) + 1
    # Oldest-first: index 0 = (n_bins-1) bins ago.
    out: list[float | None] = []
    for i in range(n_bins):
        key = n_bins - 1 - i
        out.append(sums[key] / counts[key] if counts.get(key) else None)
    return out


def forecast_zone_occupancy(snapshots: list[dict], zone_id: str, now_ms: int) -> dict | None:
    """Run the LSTM on `zone_id`'s recent occupancy-ratio history.

    Returns a dict like:
        {
            "source": "lstm-birmingham-v2",
            "horizons_hours": [1, 3, 6],
            "forecast": [0.42, 0.71, 0.95],   # predicted occupancy ratio 0..1
            "input_window_hours": 24,
        }
    or `{"source": "insufficient-history", ...}` when there isn't enough
    real history yet, or `None` if the model couldn't be loaded.
    """
    model, config = _load_model_once()
    if model is None or config is None:
        return None

    try:
        import torch
    except ImportError:
        return None

    import numpy as np

    n_nodes: int = config["n_nodes"]
    horizons: list[int] = config["horizons_hours"]
    input_len: int = config["input_len"]
    bin_minutes: int = int(config.get("bin_minutes", 30))
    window_hours = input_len * bin_minutes / 60

    bins = _bin_zone_occupancy(snapshots, zone_id, now_ms, input_len, bin_minutes)

    observed = [i for i, v in enumerate(bins) if v is not None]
    coverage = len(observed) / input_len
    span_hours = ((observed[-1] - observed[0]) * bin_minutes / 60) if observed else 0.0
    if coverage < MIN_BIN_COVERAGE or span_hours < MIN_SPAN_HOURS:
        return {
            "source": SOURCE_INSUFFICIENT,
            "horizons_hours": horizons,
            "bins_available": len(observed),
            "bins_required": input_len,
            "span_hours": round(span_hours, 1),
            "span_required_hours": MIN_SPAN_HOURS,
            "input_window_hours": window_hours,
        }

    # Impute gaps BETWEEN real observations (ffill, then bfill for any
    # leading gap). This is documented imputation over a >=50%-covered
    # window — not fabrication of history we never saw.
    series: list[float] = []
    last: float | None = None
    for v in bins:
        if v is not None:
            last = v
        series.append(last if last is not None else -1.0)
    first_real = next(v for v in series if v >= 0)
    series = [v if v >= 0 else first_real for v in series]

    # Normalise exactly like training: z-score of occupancy ratios. The
    # checkpoint stores per-lot mu/sigma; the warehouse zone is mapped to
    # the average lot statistics.
    mu = float(np.mean(config["mu"]))
    sigma = float(np.mean(config["sigma"])) or 1.0
    z = [(v - mu) / sigma for v in series]

    # Pad to n_nodes channels by repeating the zone's series. The LSTM
    # input projection is dataset-agnostic: copying the channel preserves
    # the temporal signal at every output channel.
    arr = np.tile(np.array(z, dtype=np.float32)[:, None], (1, n_nodes))
    x = torch.from_numpy(arr).unsqueeze(0)  # shape (1, input_len, n_nodes)

    with torch.no_grad():
        pred = model(x)  # (1, n_horizons, n_nodes)
    # Average per-channel predictions, then de-normalise back to ratio
    # space and clip to the feature's natural bounds.
    z_forecast = pred.squeeze(0).mean(dim=1).numpy()
    forecast = np.clip(z_forecast * sigma + mu, 0.0, 1.0)

    return {
        "source": SOURCE_LSTM,
        "horizons_hours": horizons,
        "forecast": [round(float(v), 3) for v in forecast],
        "input_window_hours": window_hours,
    }


def model_info() -> dict:
    """Return registry-level info for the Système / Admin panel.

    Always returns a dict (even when the model isn't loaded) so the UI
    can render a "model not loaded" state without an error path.
    """
    model, config = _load_model_once()
    info: dict[str, Any] = {
        "name": "logivision-congestion",
        "version": SOURCE_LSTM if model is not None else None,
        "architecture": "CongestionLSTM (2-layer, hidden=64)",
        "training_dataset": "Parking Birmingham (Stolfi 2017) — 30-min occupancy ratios",
        "loaded": model is not None,
    }
    if METRICS_PATH.is_file():
        try:
            metrics = json.loads(METRICS_PATH.read_text())
            info["metrics"] = metrics
        except Exception:  # noqa: BLE001
            pass
    if model is not None:
        info["config"] = {
            "n_nodes": config["n_nodes"],
            "n_horizons": config["n_horizons"],
            "horizons_hours": config["horizons_hours"],
            "input_len": config["input_len"],
            "bin_minutes": config.get("bin_minutes", 30),
            "feature": config.get("feature", "occupancy_ratio"),
        }
    return info
