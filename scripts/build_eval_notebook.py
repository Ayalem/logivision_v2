"""Generate ml/notebooks/04_model_evaluation.ipynb.

Evaluates the Production YOLO+ByteTrack pipeline on two test beds:

  1. Quantitative: held-out Kaggle test split (scene-aware clean split).
     Reports mAP@0.5, mAP@0.5:0.95, precision, recall per class.
     This is the number to cite in the paper.

  2. Qualitative: real Camera3.mp4 footage from our actual pipeline.
     Samples 100 frames at regular intervals, runs inference, shows
     detection visualisations and a detection-rate summary.
     No hand-labels needed — pure qualitative sanity check.

Run: uv run python scripts/build_eval_notebook.py
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
    """# 04 — Model Evaluation

Two-part evaluation of the Production YOLO detector:

| Part | What | Data | Metric |
|------|------|------|--------|
| **A** | Quantitative | Kaggle held-out test split (scene-aware clean) | mAP@0.5, P, R per class |
| **B** | Qualitative | Real Camera3.mp4 warehouse footage | Detection rate, confidence distribution, sample visuals |

## Why two parts?

Part A gives the paper number — mAP on a hand-labelled benchmark
(the clean Kaggle split). Part B shows the model works on the *actual*
warehouse footage, not just benchmark images. The two together answer
the key reviewer question: "does your mAP translate to real deployment?".

> **Note on Part A numbers**: the contaminated v3 model (mAP=0.995)
> used temporal-leaky splits where adjacent frames of the same video
> appear in both train and test. The scene-aware clean split used here
> removes that leakage. Honest numbers will be lower — that is correct.
"""
)

md(
    """## 0. Setup — clone repo + install deps (run me FIRST)

This cell must run **before** the Environment cell. On Colab the working
directory starts at `/content` (no repo), so we clone the repo and `cd`
into it first; otherwise the repo-root search below climbs to `/` and the
notebook fails trying to write artifacts to the filesystem root. Off Colab
it is a safe no-op.
"""
)
code(
    """import sys, os, pathlib

IN_COLAB = 'google.colab' in sys.modules
if IN_COLAB:
    REPO_DIR = pathlib.Path('/content/logivision_v2')
    if not REPO_DIR.is_dir():
        !git clone --depth 1 https://github.com/Ayalem/logivision_v2.git {REPO_DIR}
    os.chdir(REPO_DIR)
    %pip install -q ultralytics==8.3.0 kagglehub==0.3.0 pyyaml==6.0.1 opencv-python-headless==4.10.0.84
print('cwd:', os.getcwd(), '| colab:', IN_COLAB)
"""
)

md(
    """## 1. Environment
"""
)
code(
    """import os, sys, pathlib, json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Locate repo root by walking up to the pyproject.toml. After the Section 0
# bootstrap has chdir'd into the clone this resolves correctly; off Colab it
# works from anywhere inside the repo.
REPO = pathlib.Path.cwd().resolve()
while not (REPO / 'pyproject.toml').is_file() and REPO != REPO.parent:
    REPO = REPO.parent
if not (REPO / 'pyproject.toml').is_file():
    raise RuntimeError(
        f'Repo root not found from {pathlib.Path.cwd()}. '
        'Run the Section 0 bootstrap cell first (it clones the repo + cd into it).'
    )
print('Repo root:', REPO)

for p in (str(REPO), str(REPO / 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)

EVAL_DIR = REPO / 'ml' / 'artifacts' / 'eval'
EVAL_DIR.mkdir(parents=True, exist_ok=True)
print('Eval artifacts:', EVAL_DIR)
"""
)

md(
    """## 2. Load the Production model

Tries (in order): MLflow Production version → committed teacher checkpoint
→ COCO baseline yolov8n.
"""
)
code(
    """from ultralytics import YOLO
import pathlib

TEACHER_CANDIDATES = [
    REPO / 'ml' / 'artifacts' / 'yolo_teacher' / 'best.pt',
    REPO / 'ml' / 'runs' / 'two_phase' / 'phase2' / 'weights' / 'best.pt',
    REPO / 'runs' / 'two_phase' / 'phase2' / 'weights' / 'best.pt',
]
MODEL_PT = next((p for p in TEACHER_CANDIDATES if p.is_file()), None)

if MODEL_PT is None:
    # Try to pull from MLflow if running locally with the stack up
    try:
        import mlflow
        mlflow.set_tracking_uri('http://localhost:5050')
        client = mlflow.tracking.MlflowClient()
        versions = client.get_latest_versions('logivision-detector', stages=['Production'])
        if versions:
            run_id = versions[0].run_id
            art = mlflow.artifacts.download_artifacts(f'runs:/{run_id}/weights/best.pt')
            MODEL_PT = pathlib.Path(art)
            print('Loaded Production model from MLflow:', MODEL_PT)
    except Exception as e:
        print(f'MLflow not reachable ({e}), using COCO baseline')

USING_FALLBACK = False
if MODEL_PT is None:
    MODEL_PT = 'yolov8n.pt'
    USING_FALLBACK = True
    print('WARNING: no warehouse-trained model found (no local checkpoint, MLflow unreachable).')
    print('Falling back to COCO yolov8n. Part A (mAP) will be SKIPPED — COCO classes do')
    print('not match the warehouse classes, so the number would be meaningless.')
    print('To get a real mAP: have the MLflow stack up, or upload best.pt to')
    print('ml/artifacts/yolo_teacher/best.pt before running.')

model = YOLO(str(MODEL_PT))
print('Model loaded:', MODEL_PT, '(COCO fallback)' if USING_FALLBACK else '(warehouse-trained)')
"""
)

md(
    """## Part A — Quantitative evaluation on the LOCO test split

Runs `model.val()` on the **scene-separated** held-out test split (LOCO
subset 4 — a warehouse never seen in training). If the YOLO dataset is
not present locally it is rebuilt with `fetch_loco.py` + `prepare_loco.py`
(no credentials — LOCO is CC0 public domain).
"""
)
code(
    """CLEAN_YAML = REPO / 'datasets' / 'processed' / 'loco' / 'data.yaml'

if USING_FALLBACK:
    print('Skipping Part A — no warehouse-trained model is loaded (see Section 2).')
    print('A COCO model evaluated on warehouse classes would report a meaningless mAP.')
    CLEAN_YAML = None
elif not CLEAN_YAML.is_file():
    print('LOCO YOLO dataset not found — building it (fetch + convert, ~769 MB) ...')
    import subprocess
    subprocess.run([sys.executable, 'scripts/fetch_loco.py'], check=True)
    subprocess.run([sys.executable, 'scripts/prepare_loco.py'], check=True)
    print('LOCO dataset built.')
else:
    print('Using cached LOCO dataset:', CLEAN_YAML)

if CLEAN_YAML and CLEAN_YAML.is_file():
    print('\\n--- Running val on clean test split ---')
    val_results = model.val(data=str(CLEAN_YAML), split='test', verbose=True)
    quant = {
        'mAP50':     float(val_results.box.map50),
        'mAP50_95':  float(val_results.box.map),
        'precision': float(val_results.box.mp),
        'recall':    float(val_results.box.mr),
    }
    print('\\n=== PART A RESULTS ===')
    for k, v in quant.items():
        print(f'  {k:<15} {v:.4f}')

    with open(EVAL_DIR / 'quantitative.json', 'w') as f:
        json.dump({
            'model': str(MODEL_PT),
            'split': 'loco/test (subset 4 — scene-separated, no cross-scene leakage)',
            'metrics': quant,
        }, f, indent=2)
    print('Saved:', EVAL_DIR / 'quantitative.json')
"""
)

md(
    """## Part B — Qualitative evaluation on real Camera3.mp4

Samples 100 frames from the actual warehouse video used in the demo
pipeline. Runs inference, visualises detections, reports detection
statistics. No ground-truth labels needed.
"""
)
code(
    """import cv2, random

# Find Camera3.mp4 — could be a symlink or the actual file
CAMERA_CANDIDATES = [
    REPO / 'datasets' / 'raw' / 'videos' / 'Camera3.mp4',
    REPO / 'datasets' / 'raw' / 'taltech_videos' / 'Camera3.mp4',
]
VIDEO_PATH = next((p for p in CAMERA_CANDIDATES if p.is_file() or p.is_symlink()), None)

if VIDEO_PATH is None:
    print('Camera3.mp4 not found — skipping Part B.')
    print('Run `make camera-videos` to create the symlinks.')
else:
    print('Video:', VIDEO_PATH)
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps_video    = cap.get(cv2.CAP_PROP_FPS) or 25
    print(f'  {total_frames} frames  @ {fps_video:.1f} fps  = {total_frames/fps_video:.1f}s')

    # Sample 100 frames at regular intervals
    N_SAMPLE = 100
    sample_indices = np.linspace(0, total_frames - 1, N_SAMPLE, dtype=int)

    frames, confidences, n_detections = [], [], []
    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, bgr = cap.read()
        if not ok:
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        results = model.predict(rgb, conf=0.3, verbose=False)
        boxes = results[0].boxes
        n_det = len(boxes) if boxes is not None else 0
        confs = boxes.conf.cpu().numpy().tolist() if boxes is not None and n_det > 0 else []
        frames.append(rgb)
        n_detections.append(n_det)
        confidences.extend(confs)
    cap.release()

    # Statistics
    det_rate = np.mean([n > 0 for n in n_detections])
    mean_conf = float(np.mean(confidences)) if confidences else 0.0
    mean_per_frame = float(np.mean(n_detections))

    print(f'\\n=== PART B RESULTS ===')
    print(f'  Frames sampled:        {len(frames)}')
    print(f'  Detection rate:        {det_rate:.1%} (frames with ≥1 box)')
    print(f'  Mean boxes/frame:      {mean_per_frame:.2f}')
    print(f'  Mean confidence:       {mean_conf:.3f}')
    print(f'  Total detections:      {sum(n_detections)}')

    # Visualise 6 sample frames with detections
    has_det = [(i, f, n) for i, (f, n) in enumerate(zip(frames, n_detections)) if n > 0]
    sample_vis = random.sample(has_det, min(6, len(has_det))) if has_det else []

    if sample_vis:
        fig, axes = plt.subplots(2, 3, figsize=(15, 8))
        axes = axes.flatten()
        for ax, (fi, frame, n_det) in zip(axes, sample_vis):
            result_idx = fi
            cap2 = cv2.VideoCapture(str(VIDEO_PATH))
            cap2.set(cv2.CAP_PROP_POS_FRAMES, int(sample_indices[fi]))
            _, bgr2 = cap2.read()
            cap2.release()
            rgb2 = cv2.cvtColor(bgr2, cv2.COLOR_BGR2RGB)
            r = model.predict(rgb2, conf=0.3, verbose=False)[0]
            vis = r.plot()[:, :, ::-1]  # BGR→RGB
            ax.imshow(vis)
            ax.set_title(f'frame {sample_indices[fi]}  ({n_det} det)', fontsize=9)
            ax.axis('off')
        for ax in axes[len(sample_vis):]:
            ax.axis('off')
        fig.suptitle('Camera3.mp4 — sample detections (Production YOLO)', fontsize=11)
        plt.tight_layout(); plt.show()
    else:
        print('No frames with detections found — check model checkpoint.')

    qual = {
        'model': str(MODEL_PT),
        'video': 'Camera3.mp4',
        'n_sampled': len(frames),
        'detection_rate': float(det_rate),
        'mean_boxes_per_frame': float(mean_per_frame),
        'mean_confidence': float(mean_conf),
        'total_detections': int(sum(n_detections)),
    }
    with open(EVAL_DIR / 'qualitative.json', 'w') as f:
        json.dump(qual, f, indent=2)
    print('Saved:', EVAL_DIR / 'qualitative.json')
"""
)

md(
    """## Summary

| Metric | Value | Notes |
|--------|-------|-------|
| mAP@0.5 (clean split) | *see quantitative.json* | Scene-aware, no temporal leakage |
| mAP@0.5:0.95 (clean split) | *see quantitative.json* | |
| Detection rate on Camera3.mp4 | *see qualitative.json* | Real warehouse footage |
| Mean confidence on Camera3.mp4 | *see qualitative.json* | |

The clean-split mAP is the number cited in the paper. The detection rate on
Camera3.mp4 shows qualitative real-world performance. Both together justify
the model's readiness for deployment.

**MOTA / IDF1 tracking evaluation** (ByteTrack end-to-end) requires a
hand-annotated multi-object tracking sequence and is scoped as Future Work.
"""
)

# Write notebook
notebook = {
    "cells": NB,
    "metadata": {
        "kernelspec": {"display_name": "Python 3 (uv)", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
out = pathlib.Path("ml/notebooks/04_model_evaluation.ipynb")
out.write_text(json.dumps(notebook, indent=1, ensure_ascii=False))
print(f"wrote {out}  ({out.stat().st_size:,} bytes, {len(NB)} cells)")
