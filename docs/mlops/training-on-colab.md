# Training on Free GPU (Colab / Kaggle)

LOGIVISION trains on free GPU tiers — never paid. Two platforms cover the budget:

| Platform | GPU | Session cap | Quota | Best for |
|---|---|---|---|---|
| **Google Colab Free** | T4 (16 GB VRAM) | 12 h max, random disconnects | fair-use | exploration, debug, short runs |
| **Kaggle Kernels** | P100 16 GB or T4 ×2 | 9 h max | **30 h GPU / week** | "official" full-length training |

Use Kaggle for the runs you want logged in MLflow as Production candidates; Colab for everything else.

## Architecture during a remote training

```
   Colab / Kaggle (GPU)                       Your laptop (local)
   ─────────────────────                      ───────────────────
   git clone logivision_v2                    Docker stack up
   uv pip install ...                         ├── MinIO  :9000
   dvc pull                                   ├── MLflow :5050
   python -m ml.scripts.train ──── HTTPS ──►  └── cloudflared tunnel ──► trycloudflare.com URL
                                              (or fly.io, Oracle Free, ngrok)
   dvc push   (writes new weights)
```

The remote job talks to your **local MLflow** through an HTTPS tunnel. DVC pushes weights to **your local MinIO** (also tunneled if you run from outside the LAN — locally it's just direct).

## One-time prep (local laptop)

### 1. Start the stack and a tunnel

```bash
./scripts/bootstrap.sh                # MLflow + MinIO + Postgres up
brew install cloudflared              # or: curl -L … | sh on Linux
cloudflared tunnel --url http://localhost:5050
```

Cloudflared prints a URL like `https://random-words.trycloudflare.com`. Note it — it expires when you kill the tunnel.

For a stable URL across sessions, use **Oracle Cloud Always Free** (1 ARM VM, 24 GB RAM, free forever) or **fly.io free tier** — host MLflow there instead of on the laptop. Both are documented further down.

### 2. Prepare your dataset

```bash
# Either real data:
python -m ml.scripts.extract_frames --input datasets/raw/videos --output datasets/raw/frames
# … then annotate in CVAT → export → import_annotations.py

# Or synthetic demo (good for first end-to-end smoke):
make demo-data
python -m ml.scripts.import_annotations \
    --input datasets/raw/annotations.zip \
    --output datasets/processed/current

# Push to MinIO so Colab can pull.
dvc add datasets/processed/current
git add datasets/processed/current.dvc
git commit -m "data: training snapshot"
dvc push
git push
```

## Colab — run a training

### Step A — Add secrets in Colab

*Colab UI → 🔑 icon (Secrets) → add each as Notebook-accessible.*

| Name | Value |
|---|---|
| `MLFLOW_TRACKING_URI` | the `https://….trycloudflare.com` URL |
| `MINIO_ACCESS_KEY` | from your local `.env` (`MINIO_ROOT_USER`) |
| `MINIO_SECRET_KEY` | from your local `.env` (`MINIO_ROOT_PASSWORD`) |
| `MINIO_ENDPOINT` | a tunnel for `:9000` (separate `cloudflared` instance) |

### Step B — Open the template notebook

The repo ships with `ml/notebooks/colab_train_template.ipynb`. Open it via *File → Open → GitHub* in Colab and point at `Ayalem/logivision_v2` → `develop` branch.

Cells:

1. **Setup** — installs `uv` and the project deps.
2. **Auth** — reads secrets into env vars.
3. **DVC pull** — fetches the current dataset.
4. **Train** — runs `ml.scripts.train` with `--device cuda`.
5. **Push** — `dvc push` the new weights.

### Step C — Pick GPU runtime

Runtime → Change runtime type → **T4 GPU**. Confirm:

```python
import torch
print(torch.cuda.is_available(), torch.cuda.get_device_name(0))
# → True NVIDIA T4
```

### Step D — Run, then save back

```python
!python -m ml.scripts.train --config ml/configs/yolov8n.yaml --device cuda
!dvc push
```

Once finished, the MLflow UI on your laptop shows the run, with parameters, metrics, confusion matrices, and `best.pt` under artifacts. Run reproducibility is anchored by the `git_commit` and `dataset_fingerprint` tags.

## Kaggle — same loop, different secrets

Kaggle's secrets are at *Add-ons → Secrets*. Same names as Colab.

Kaggle gives ~30 GPU-hours / week with **no random disconnects**, so it's the right place for longer runs. The notebook content is identical; just replace `from google.colab import userdata` with:

```python
from kaggle_secrets import UserSecretsClient
secrets = UserSecretsClient()
import os
os.environ["MLFLOW_TRACKING_URI"]  = secrets.get_secret("MLFLOW_TRACKING_URI")
os.environ["AWS_ACCESS_KEY_ID"]    = secrets.get_secret("MINIO_ACCESS_KEY")
os.environ["AWS_SECRET_ACCESS_KEY"] = secrets.get_secret("MINIO_SECRET_KEY")
os.environ["MLFLOW_S3_ENDPOINT_URL"] = secrets.get_secret("MINIO_ENDPOINT")
```

## Long-running training (12 h+) — checkpoint strategy

Ultralytics writes `last.pt` after **every epoch** under the run directory. To survive a Colab disconnect:

1. Set `epochs: 200` in `ml/configs/yolov8n.yaml`.
2. Save `last.pt` to `/content/drive/...` (mounted Google Drive) at the end of every epoch by adding a small callback. (See the notebook template's *Resume* cell.)
3. If disconnected, restart the runtime, mount Drive, and run:
   ```python
   !python -m ml.scripts.train \
       --config ml/configs/yolov8n.yaml \
       --device cuda \
       --resume /content/drive/MyDrive/logivision/runs/<run-id>/weights/last.pt
   ```

(Note: `--resume` is implemented by Ultralytics, not by our wrapper yet — pass it as a flag and Ultralytics picks it up.)

## Self-hosted, always-on MLflow (no tunnel)

If you don't want to keep `cloudflared` running on your laptop, deploy MLflow on a free always-on host:

- **Oracle Cloud Always Free** — 1 ARM VM (24 GB RAM, 4 vCPU), no time limit. Install Docker, copy `infra/docker-compose/docker-compose.mlops.yml`, point a DNS to it.
- **fly.io free tier** — 3 shared-cpu-1x VMs, 256 MB RAM each, enough for MLflow + small MinIO.

Either way, set `MLFLOW_TRACKING_URI` to your stable URL and skip the tunnel step.

## Cost audit

Every training run respects the 0 € rule. Verify with `docs/cost-audit.md` (to be added in Phase 5):

- No `gcloud auth` running anywhere.
- No `aws configure` keys outside MinIO/local.
- No paid Weights & Biases / SageMaker / Vertex AI client installed.
- GPU hours stay inside Colab + Kaggle free quotas.

## Troubleshooting

| Symptom | Fix |
|---|---|
| MLflow run not visible locally | tunnel URL changed; check `cloudflared` is still running |
| `dvc pull` says `endpoint not reachable` | tunnel the MinIO port too, or run from same LAN |
| `torch.cuda.is_available()` returns False | Runtime → Change runtime type → GPU |
| Training is very slow on T4 | `--imgsz 320 --batch 32` first; bump once correct |
| Out-of-memory on T4 | drop `batch`, then `imgsz`, then `model.weights` from `yolov8n` to `yolov8n-seg.yaml` (smaller backbone is the wrong knob — adjust batch first) |
| Run shows status `KILLED` in MLflow | Colab disconnected; resume from `last.pt` via `--resume` |

## References

- Ultralytics docs: <https://docs.ultralytics.com/modes/train/>
- MLflow tracking: <https://mlflow.org/docs/latest/tracking.html>
- Cloudflare Quick Tunnels: <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/>
- DVC remote on S3: <https://dvc.org/doc/user-guide/data-management/remote-storage/amazon-s3>
