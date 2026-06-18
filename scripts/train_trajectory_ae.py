"""Train the trajectory-anomaly GRU-AE on TOMIE ground-truth trajectories.

Standalone, CPU-fast (the model is tiny). Mirrors ml/notebooks/08 but reads
the in-domain TOMIE tracks (moving forklifts + pallets) so the autoencoder
learns normal industrial motion and stops flagging every static detection.

Produces a checkpoint compatible with services/stream_processor/anomaly_scorer.py:
    ml/artifacts/trajectory_ae/model.pt  -> {"config": {...}, "model_state": ...}
    ml/artifacts/trajectory_ae/metrics.json

Run:  uv run python scripts/train_trajectory_ae.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from services.stream_processor.cep import TrackPoint  # noqa: E402
from services.stream_processor.trajectory_features import (  # noqa: E402
    FEATURE_NAMES,
    N_FEATURES,
    STRIDE,
    WINDOW,
    compute_features,
    make_windows,
)

TRAJ_DIR = REPO / "data" / "processed" / "trajectories"
ART_DIR = REPO / "ml" / "artifacts" / "trajectory_ae"
HIDDEN, LATENT, EPOCHS, LR = 32, 16, 60, 1e-3
torch.manual_seed(42)
np.random.seed(42)


class TrajectoryGRUAE(nn.Module):
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


def load_windows() -> np.ndarray:
    files = sorted(TRAJ_DIR.glob("tomie_*.jsonl"))
    if not files:
        raise SystemExit(
            f"No tomie_*.jsonl under {TRAJ_DIR}. Run scripts/fetch_tomie.py + "
            "scripts/prepare_tomie_trajectories.py first."
        )
    tracks: dict[tuple, dict] = {}
    for f in files:
        for line in f.read_text().splitlines():
            r = json.loads(line)
            key = (r["video"], r["track_id"])
            t = tracks.setdefault(
                key, {"points": [], "diag": (r["frame_w"] ** 2 + r["frame_h"] ** 2) ** 0.5}
            )
            t["points"].append(
                TrackPoint(
                    timestamp_ms=r["timestamp_ms"],
                    centroid=(r["cx"], r["cy"]),
                    width=r["w"],
                    height=r["h"],
                )
            )
    wins = []
    for (video, _tid), t in tracks.items():
        t["points"].sort(key=lambda p: p.timestamp_ms)
        feats = compute_features(t["points"], t["diag"])
        for k in range(make_windows(feats).shape[0]):
            wins.append((video, t["points"][k * STRIDE].timestamp_ms, make_windows(feats)[k]))
    wins.sort(key=lambda w: (w[0], w[1]))
    print(f"{len(tracks)} tracks -> {len(wins)} windows")
    return np.stack([w[2] for w in wins]).astype(np.float32)


def main() -> int:
    X = load_windows()  # noqa: N806 — X is conventional for a feature matrix
    if len(X) < 200:
        raise SystemExit(f"Only {len(X)} windows — need more TOMIE footage.")
    n = len(X)
    i_tr, i_va = int(0.70 * n), int(0.85 * n)
    X_train, X_val, X_test = X[:i_tr], X[i_tr:i_va], X[i_va:]  # noqa: N806
    mu = X_train.reshape(-1, N_FEATURES).mean(axis=0)
    sigma = X_train.reshape(-1, N_FEATURES).std(axis=0) + 1e-6

    def norm(a: np.ndarray) -> torch.Tensor:
        return torch.from_numpy(((a - mu) / sigma).astype(np.float32))

    xt, xv, xtest = norm(X_train), norm(X_val), norm(X_test)
    model = TrajectoryGRUAE(N_FEATURES, HIDDEN, LATENT)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    lossf = nn.MSELoss()
    for ep in range(EPOCHS):
        model.train()
        perm = torch.randperm(len(xt))
        tot = 0.0
        for i in range(0, len(xt), 64):
            b = xt[perm[i : i + 64]]
            opt.zero_grad()
            loss = lossf(model(b), b)
            loss.backward()
            opt.step()
            tot += loss.item() * len(b)
        if ep % 15 == 0 or ep == EPOCHS - 1:
            model.eval()
            with torch.no_grad():
                vl = lossf(model(xv), xv).item()
            print(f"  epoch {ep:3d}  train_mse={tot / len(xt):.5f}  val_mse={vl:.5f}")

    # Per-window reconstruction error -> percentile thresholds (val = normal)
    model.eval()
    with torch.no_grad():
        verr = ((model(xv) - xv) ** 2).mean(dim=(1, 2)).numpy()
        terr = ((model(xtest) - xtest) ** 2).mean(dim=(1, 2)).numpy()
    warn = float(np.percentile(verr, 99))
    crit = float(np.percentile(verr, 99.5))
    sweep = {f"p{p}": float(np.percentile(verr, p)) for p in (95, 99, 99.5, 99.9)}

    ART_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "config": {
                "n_features": N_FEATURES,
                "hidden": HIDDEN,
                "latent": LATENT,
                "window": WINDOW,
                "threshold_warning": warn,
                "threshold_critical": crit,
                "threshold_provenance": "TOMIE val-set p99 / p99.5 reconstruction error",
                "mu": mu.tolist(),
                "sigma": sigma.tolist(),
                "feature_names": FEATURE_NAMES,
            },
            "model_state": model.state_dict(),
        },
        ART_DIR / "model.pt",
    )
    metrics = {
        "trained_on": "TOMIE ground-truth trajectories (Zenodo 7849183)",
        "n_windows": int(n),
        "split": {"train": int(i_tr), "val": int(i_va - i_tr), "test": int(n - i_va)},
        "val_recon_error_mean": float(verr.mean()),
        "test_recon_error_mean": float(terr.mean()),
        "threshold_warning_p99": warn,
        "threshold_critical_p99_5": crit,
        "threshold_sweep": sweep,
    }
    (ART_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"saved {ART_DIR / 'model.pt'}  (warn={warn:.5f}, crit={crit:.5f})")
    print(f"saved {ART_DIR / 'metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
