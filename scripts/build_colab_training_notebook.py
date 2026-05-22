"""Generate ml/notebooks/00_colab_training.ipynb — a standalone notebook
that fine-tunes YOLOv8 on the Kaggle warehouse-delivery-box dataset
inside Google Colab with a T4 GPU. Detects Colab, sets up env, pulls
dataset via kagglehub, trains 50 epochs at 640 px, packages best.pt
+ results.csv for download.

Run: uv run python scripts/build_colab_training_notebook.py
"""

from __future__ import annotations

import json
import pathlib

NB: list[dict] = []


def md(text: str) -> None:
    NB.append({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)})


def code(text: str) -> None:
    NB.append(
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": text.splitlines(keepends=True),
        }
    )


md(
    """# LOGIVISION — Train YOLOv8 on Google Colab (T4)

**Purpose.** Fine-tune YOLOv8n on the Kaggle warehouse-delivery-box
dataset using a free Colab T4 GPU. 50 epochs at 640 px takes **~25
minutes on T4**, vs ~4 hours on an M3 CPU.

## Before you run

1. *Runtime → Change runtime type → T4 GPU* (confirm top-right).
2. Have your Kaggle API key handy
   (https://www.kaggle.com/settings/account → "Create New Token").
3. Add the key to Colab Secrets:
   *Colab left sidebar → key icon → add secret*
   - `KAGGLE_USERNAME` = your Kaggle username
   - `KAGGLE_KEY` = the long hex string in the downloaded `kaggle.json`
   - Toggle **Notebook access** ON for both.

## What this notebook does

| Cell | Step | Time on T4 |
|---|---|---|
| 1 | Detect Colab; clone repo (depth=1) | 5 s |
| 2 | Install ultralytics, kagglehub, pyyaml | 30 s |
| 3 | Set Kaggle creds from Colab Secrets | <1 s |
| 4 | Download Kaggle dataset (~860 MB) | 1-3 min |
| 5 | Convert OBB labels → AABB (uses `scripts/prepare_kaggle_warehouse.py`) | 10 s |
| 6 | Train YOLOv8n: 50 epochs, imgsz=640, batch=32, AdamW, cos_lr | **~25 min** |
| 7 | Validate on the held-out test split | 30 s |
| 8 | Plot training curves | 5 s |
| 9 | Download `best.pt` + `results.csv` to your machine | 5 s |

At the end you drop the downloaded files into your local repo and
register the model in MLflow with `make register-from-colab`."""
)

# Cell 1 - environment detection + clone
code(
    """# 1. Detect Colab and clone the repo (shallow).
import os, sys, subprocess, pathlib

IN_COLAB = 'google.colab' in sys.modules
print(f'Running on Colab: {IN_COLAB}')
if IN_COLAB:
    if not pathlib.Path('logivision_v2').is_dir():
        subprocess.run(['git', 'clone', '--depth=1',
                        'https://github.com/Ayalem/logivision_v2.git'], check=True)
    os.chdir('logivision_v2')
    print('cwd:', pathlib.Path.cwd())

# Sanity: confirm we can see the dataset prep script we'll reuse.
assert pathlib.Path('scripts/prepare_kaggle_warehouse.py').is_file(), \\
    'prepare_kaggle_warehouse.py missing - did the repo clone correctly?'

# GPU check
import torch
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'CUDA: {torch.version.cuda}')
"""
)

# Cell 2 - deps
code(
    """# 2. Install the deps we actually need. Skip the rest of the repo's
#    dev dependencies — keeps install under 30 s.
%pip install -q ultralytics==8.3.0 kagglehub==0.3.0 pyyaml==6.0.1 mlflow==2.17.0
print('deps installed')
"""
)

# Cell 3 - kaggle creds
code(
    """# 3. Pull Kaggle credentials from Colab Secrets and write ~/.kaggle/kaggle.json.
import json, os, pathlib
try:
    from google.colab import userdata
    KAGGLE_USERNAME = userdata.get('KAGGLE_USERNAME')
    KAGGLE_KEY      = userdata.get('KAGGLE_KEY')
    assert KAGGLE_USERNAME and KAGGLE_KEY, 'Missing Colab secret'
except (ImportError, Exception) as e:
    # Local fallback: read from env (works outside Colab too).
    KAGGLE_USERNAME = os.environ.get('KAGGLE_USERNAME')
    KAGGLE_KEY      = os.environ.get('KAGGLE_KEY')
    assert KAGGLE_USERNAME and KAGGLE_KEY, (
        f'No Kaggle credentials found ({e}). '
        'Add KAGGLE_USERNAME and KAGGLE_KEY as Colab secrets (toggle Notebook access).'
    )

# Hand the creds to kagglehub via the canonical kaggle.json location.
kj = pathlib.Path.home() / '.kaggle' / 'kaggle.json'
kj.parent.mkdir(exist_ok=True)
kj.write_text(json.dumps({'username': KAGGLE_USERNAME, 'key': KAGGLE_KEY}))
os.chmod(kj, 0o600)
print('kaggle.json written; username =', KAGGLE_USERNAME)
"""
)

# Cell 4 - download dataset
code(
    """# 4. Download the dataset (~860 MB). kagglehub caches under ~/.cache/kagglehub.
import kagglehub
DATASET_PATH = kagglehub.dataset_download('zoya77/warehouse-delivery-box-detection-dataset')
print('downloaded to:', DATASET_PATH)

# kagglehub returns the dataset root; our converter expects the
# 'Box Dataset/' subdirectory underneath.
import pathlib
KAGGLE_BOX = pathlib.Path(DATASET_PATH) / 'Box Dataset'
assert KAGGLE_BOX.is_dir(), f'Unexpected layout: {list(pathlib.Path(DATASET_PATH).iterdir())}'
for split in ('train', 'valid', 'test'):
    n = len(list((KAGGLE_BOX / split / 'images').glob('*')))
    print(f'  {split:<5}: {n:>5} images')
"""
)

# Cell 5 - convert
code(
    """# 5. Convert OBB labels -> axis-aligned bbox using the same script the
#    repo uses locally. We just point its ROOT constant at the Colab cache.
import importlib, sys
sys.path.insert(0, 'scripts')
import prepare_kaggle_warehouse as prep
prep.ROOT = KAGGLE_BOX                      # point at the Colab cache
prep.OUT  = pathlib.Path('data/processed/kaggle_warehouse')
prep.main()

DATA_YAML = (prep.OUT / 'data.yaml').resolve()
print('data.yaml:', DATA_YAML)
print(DATA_YAML.read_text())
"""
)

# Cell 6 - train
code(
    """# 6. Train. ~25 min on T4.
#    Hyperparameters chosen for the soutenance demo:
#      - 50 epochs (good convergence on 361 train images)
#      - imgsz=640 (production size; not the 320 demo size)
#      - batch=32 (T4 has 16 GB - safe headroom; bump to 48 if you want)
#      - cos_lr=True (anneals smoothly; matches ULMFiT recipe)
#      - patience=15 (early stop if val mAP plateaus)
#      - device=0 (GPU 0)

# Defensive: if cells 1-5 weren't run in order, recover DATA_YAML from disk.
# This lets you re-run cell 6 alone after a restart, as long as cell 5 ran
# at least once in the current Colab session.
try:
    DATA_YAML
except NameError:
    import pathlib
    DATA_YAML = pathlib.Path('data/processed/kaggle_warehouse/data.yaml').resolve()
    if not DATA_YAML.is_file():
        raise FileNotFoundError(
            f'{DATA_YAML} not found — please run cells 1-5 (Runtime -> Run all).'
        )
    print(f'(recovered DATA_YAML from disk: {DATA_YAML})')

from ultralytics import YOLO

model = YOLO('yolov8n.pt')                  # COCO weights as starting point
results = model.train(
    data=str(DATA_YAML),
    epochs=50,
    imgsz=640,
    batch=32,
    optimizer='AdamW',
    lr0=0.001,
    cos_lr=True,
    patience=15,
    device=0,
    project='runs',
    name='colab_kaggle_50ep',
    exist_ok=True,
    verbose=False,
    plots=True,
    seed=42,
)
print('training done')
"""
)

# Cell 7 - val
code(
    """# 7. Final validation on the held-out test split (not the val we early-stopped on).
val_results = model.val(data=str(DATA_YAML), split='test', verbose=False)
print('--- Final test-set metrics ---')
print(f'mAP@0.5         : {val_results.box.map50:.4f}')
print(f'mAP@0.5:0.95    : {val_results.box.map:.4f}')
print(f'mean precision  : {val_results.box.mp:.4f}')
print(f'mean recall     : {val_results.box.mr:.4f}')
print('per class:')
for i, name in val_results.names.items():
    print(f'  {name:<14} mAP50={val_results.box.maps[i]:.4f}')
"""
)

# Cell 8 - plot curves
code(
    """# 8. Plot the training curves so they're embedded in the notebook output.
import pandas as pd
import matplotlib.pyplot as plt

run_dir = pathlib.Path('runs/colab_kaggle_50ep')
df = pd.read_csv(run_dir / 'results.csv')
df.columns = [c.strip() for c in df.columns]

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
axes[0].plot(df['epoch'], df['metrics/mAP50(B)'],     label='mAP@0.5',     color='#2563EB', linewidth=2)
axes[0].plot(df['epoch'], df['metrics/mAP50-95(B)'], label='mAP@0.5:0.95', color='#06B6D4', linewidth=2)
axes[0].set_xlabel('epoch'); axes[0].set_ylabel('mAP'); axes[0].set_title('Validation mAP')
axes[0].grid(alpha=0.3); axes[0].legend()

axes[1].plot(df['epoch'], df['train/box_loss'], label='box loss', color='#EF4444')
axes[1].plot(df['epoch'], df['train/cls_loss'], label='cls loss', color='#F59E0B')
axes[1].plot(df['epoch'], df['train/dfl_loss'], label='dfl loss', color='#8B5CF6')
axes[1].set_xlabel('epoch'); axes[1].set_ylabel('loss'); axes[1].set_title('Training losses')
axes[1].grid(alpha=0.3); axes[1].legend()
plt.tight_layout(); plt.show()

best = df.loc[df['metrics/mAP50(B)'].idxmax()]
print(f'Best epoch: {int(best.epoch)} -> mAP50={best[\"metrics/mAP50(B)\"]:.3f}, '
      f'precision={best[\"metrics/precision(B)\"]:.3f}, recall={best[\"metrics/recall(B)\"]:.3f}')
"""
)

# Cell 9 - package + download
code(
    """# 9. Package best.pt + last.pt + results.csv + confusion matrix into a
#    single zip and trigger a Colab download to your machine.
import shutil
from datetime import datetime

run_dir = pathlib.Path('runs/colab_kaggle_50ep')
stamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
bundle = pathlib.Path(f'/content/logivision_colab_run_{stamp}')
bundle.mkdir(exist_ok=True)
for f in ('weights/best.pt', 'weights/last.pt', 'results.csv',
          'confusion_matrix.png', 'confusion_matrix_normalized.png',
          'args.yaml', 'labels.jpg'):
    src = run_dir / f
    if src.is_file():
        shutil.copy(src, bundle / pathlib.Path(f).name)
zip_path = shutil.make_archive(str(bundle), 'zip', bundle)
print(f'bundle: {zip_path} ({pathlib.Path(zip_path).stat().st_size/1e6:.1f} MB)')

# Trigger Colab download (or use right-click in the file panel if this fails)
if IN_COLAB:
    from google.colab import files
    files.download(zip_path)
"""
)

# Final markdown - what to do with the downloaded zip
md(
    """## Next steps on your laptop

After the download completes:

```bash
# 1. Unzip into the repo's ml/runs directory under a colab-named subdir.
RUN_NAME=$(basename ~/Downloads/logivision_colab_run_*.zip .zip)
mkdir -p ml/runs/$RUN_NAME/weights
unzip -o ~/Downloads/${RUN_NAME}.zip -d ml/runs/$RUN_NAME/
mv ml/runs/$RUN_NAME/best.pt ml/runs/$RUN_NAME/weights/best.pt
mv ml/runs/$RUN_NAME/last.pt ml/runs/$RUN_NAME/weights/last.pt

# 2. Register in your local MLflow + promote to Production.
make register-from-colab RUN=$RUN_NAME

# 3. Restart the inference worker so it picks up the new model.
make worker-restart
```

The dashboard's `System` tab will show the new model version + metrics on
next refresh. Detections start using the Colab-trained weights in ~10 s.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `KAGGLE_USERNAME` secret missing | Add it in the Colab sidebar (key icon), toggle Notebook access ON, re-run cell 3 |
| `CUDA out of memory` | Drop `batch=32` to `batch=16` in cell 6 |
| Training stalls at 0 mAP after 5+ epochs | Re-check `data.yaml` — classes/paths must match what cell 5 wrote |
| `files.download()` does nothing | Click the file panel on the left, right-click the zip, "Download" |
"""
)

# Serialize
notebook = {
    "cells": NB,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
        "accelerator": "GPU",
        "colab": {"provenance": [], "gpuType": "T4"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
out = pathlib.Path("ml/notebooks/00_colab_training.ipynb")
out.write_text(json.dumps(notebook, indent=1, ensure_ascii=False))
print(f"wrote {out}  ({out.stat().st_size:,} bytes, {len(NB)} cells)")
