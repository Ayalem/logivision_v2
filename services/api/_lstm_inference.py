"""LSTM congestion-forecast inference for the dashboard.

Loads `ml/artifacts/congestion_lstm/model.pt` (the PyTorch state_dict
trained by `ml/notebooks/05_congestion_lstm.ipynb` on UCI Beijing PRSA)
and exposes a single high-level call:

    forecast = forecast_zone_occupancy(events, zone_id, now_ms)

`forecast` is a dict with three horizons (1 h / 3 h / 6 h) of predicted
occupancy plus a `source` tag the frontend uses to flip the panel badge
between `lstm-prsa-v1` and `rule-v0`.

Design notes:
  * Lazy-loaded model — the cold-path /api/predictions endpoint never
    pays the import / load cost until the first call.
  * Module-level singleton — the model is loaded once per process.
  * Graceful degradation — if the artifact is missing or PyTorch can't
    be imported, every call returns `None`. The caller falls back to
    the rule-based forecast.
  * Domain-transfer honesty — the model was trained on 12 PRSA stations.
    We pad warehouse-zone inputs to 12 channels by repeating the zone's
    own history, so the input projection layer sees a valid shape.
    This is documented in the paper's Methodology section.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO_ROOT / "ml" / "artifacts" / "congestion_lstm"
MODEL_PATH = ARTIFACT_DIR / "model.pt"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"

# Source tag used by the dashboard's Congestion panel to decide which
# badge to render. Keep stable — frontend matches the string literally.
SOURCE_LSTM = "lstm-prsa-v1"
SOURCE_RULE = "rule-v0"

# How we bin the recent events into the LSTM's hourly input window.
INPUT_WINDOW_HOURS = 24

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
        "Congestion LSTM loaded — %d nodes, horizons %s",
        config["n_nodes"],
        config["horizons_hours"],
    )
    return model, config


def _bin_events_by_hour(events: list[dict], zone_id: str, now_ms: int, n_hours: int) -> list[float]:
    """Count `stationary_object` events for `zone_id` per hour.

    Returns a list of length `n_hours`, oldest first. Empty hours are 0.
    """
    # Bucket index = hours-ago (0 = current hour, n_hours-1 = oldest).
    buckets: dict[int, int] = defaultdict(int)
    cutoff = now_ms - n_hours * 3_600_000
    for e in events:
        ts = int(e.get("timestamp_ms", 0))
        if ts < cutoff or ts > now_ms:
            continue
        if e.get("event_type") != "stationary_object":
            continue
        payload = e.get("payload") or {}
        if payload.get("zone") != zone_id:
            continue
        hours_ago = int((now_ms - ts) / 3_600_000)
        if 0 <= hours_ago < n_hours:
            buckets[hours_ago] += 1
    # Oldest-first: index 0 = (n_hours-1) hours ago.
    return [float(buckets[n_hours - 1 - i]) for i in range(n_hours)]


def forecast_zone_occupancy(events: list[dict], zone_id: str, now_ms: int) -> dict | None:
    """Run the LSTM on `zone_id`'s recent occupancy history.

    Returns a dict like:
        {
            "source": "lstm-prsa-v1",
            "horizons_hours": [1, 3, 6],
            "forecast": [0.42, 0.71, 0.95],   # predicted z-scored occupancy
            "input_window_hours": 24,
        }
    or `None` if the model couldn't be loaded.
    """
    model, config = _load_model_once()
    if model is None or config is None:
        return None

    try:
        import torch
    except ImportError:
        return None

    n_nodes: int = config["n_nodes"]
    horizons: list[int] = config["horizons_hours"]
    input_len: int = config["input_len"]

    # Build the zone's hourly occupancy history.
    series = _bin_events_by_hour(events, zone_id, now_ms, input_len)

    # Normalise: the LSTM was trained on z-scored data. We don't have
    # the warehouse zone's own mu/sigma yet (need months of data), so
    # we use the average PRSA mu/sigma from the checkpoint. Documented
    # in the paper as the transfer-learning trade-off.
    import numpy as np

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
    # Average the per-channel predictions back to a single zone forecast.
    forecast = pred.squeeze(0).mean(dim=1).tolist()

    return {
        "source": SOURCE_LSTM,
        "horizons_hours": horizons,
        "forecast": [round(float(v), 3) for v in forecast],
        "input_window_hours": input_len,
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
        "training_dataset": "UCI Beijing Multi-Site Air-Quality (PRSA)",
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
        }
    return info
