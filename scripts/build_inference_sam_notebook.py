"""Generate ml/notebooks/03_inference_and_sam.ipynb.

Same pattern as scripts/build_transfer_learning_notebook.py — keeps the
notebook source diff-friendly in Python form, JSON is generated.

Run: `uv run python scripts/build_inference_sam_notebook.py`
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


# ---------------------------------------------------------------------------
md(
    """# 03 — Inference demo: YOLO on Camera3.mp4 + Segment-Anything (SAM)

**Goal.** Show that the YOLO model we fine-tuned in notebook 02 produces
useful predictions on the real TalTech warehouse footage, then **boost
those predictions with SAM** (Segment Anything Model — Meta AI, 2023).

We chain two pretrained models:

1. **YOLOv8 (our fine-tune)** — detects boxes/persons/forklifts and
   outputs bounding boxes + class IDs + confidence.
2. **SAM (ViT-B base, ~358 MB)** — takes the YOLO bounding boxes as
   *box prompts* and outputs **pixel-level segmentation masks** for
   each detected object.

The hybrid pipeline is more useful than either model alone:
- YOLO is fast and class-aware but only gives axis-aligned bbox.
- SAM produces tight masks but is class-agnostic and needs a prompt.
- **YOLO → SAM** = class label + tight mask, the best of both worlds.

## What we'll show
| § | Content |
|---|---|
| 1 | Load the YOLO Production model (or local `best.pt`) |
| 2 | Pull a few frames from `data/raw/taltech_videos/Camera3.mp4` |
| 3 | Run YOLO inference, visualise boxes |
| 4 | Load **SAM** (the lightweight ViT-B checkpoint) |
| 5 | Pipe YOLO boxes into SAM as prompts, render masks |
| 6 | Side-by-side: YOLO alone vs YOLO + SAM |
| 7 | Honest discussion of latency / when each helps |
"""
)

md(
    """## 1. Load the YOLO weights

Three candidate sources, in priority order:
1. **MLflow Production** — the canonical deployed model. Loaded via
   `resolve_model_weights('logivision-detector', stage='Production')`.
2. **Latest `best.pt` on disk** — produced by the most recent training run
   (notebook 02). Used when MLflow is unreachable.
3. **`yolov8n.pt`** — COCO-pretrained baseline (untrained on warehouse).
   Used as a sanity fallback so the notebook never breaks for missing files.
"""
)
code(
    """import sys, os
from pathlib import Path
import warnings; warnings.filterwarnings('ignore')

# Repo discovery
REPO = Path.cwd().resolve()
while not (REPO / 'pyproject.toml').is_file() and REPO != REPO.parent:
    REPO = REPO.parent
sys.path.insert(0, str(REPO))

# Resolve the weights to use. The function ships with the project and falls
# back gracefully when MLflow / artifact store is unreachable.
from services.model_server.service import resolve_model_weights
try:
    weights, version = resolve_model_weights(
        model_name='logivision-detector',
        stage='Production',
        fallback=str(REPO / 'yolov8n.pt'),
        tracking_uri='http://localhost:5050',
    )
except Exception:
    weights, version = str(REPO / 'yolov8n.pt'), 'fallback:yolov8n.pt'

# If MLflow returned a fallback string identical to the COCO baseline AND
# we have a fresher local best.pt, prefer the local one — the warehouse
# fine-tune is more relevant for the soutenance demo.
candidates = sorted((REPO / 'ml' / 'runs').glob('*/weights/best.pt'),
                    key=lambda p: p.stat().st_mtime, reverse=True)
if candidates and 'yolov8n.pt' in weights:
    weights, version = str(candidates[0]), f'local:{candidates[0].parent.parent.name[:8]}'
print(f'Using YOLO weights: {weights}')
print(f'Version label    : {version}')

from ultralytics import YOLO
yolo = YOLO(weights)
print(f'Classes          : {dict(yolo.names)}')"""
)

md(
    """## 2. Sample frames from Camera3.mp4

We pull 6 frames spaced evenly across the video. These are the same
frames the dashboard's MJPEG stream pushes to the operator UI.
"""
)
code(
    """import cv2
import numpy as np

VIDEO = REPO / 'data' / 'raw' / 'taltech_videos' / 'Camera3.mp4'
if not VIDEO.is_file():
    # Fallback to the legacy path before the data/ restructure.
    VIDEO = REPO / 'datasets' / 'raw' / 'videos' / 'Camera3.mp4'
assert VIDEO.is_file(), f'Camera3.mp4 not found — checked {VIDEO}'

cap = cv2.VideoCapture(str(VIDEO))
n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)
print(f'Camera3.mp4: {n_frames} frames @ {fps:.1f} fps ({n_frames/fps:.1f} s)')

# Sample 6 frames evenly across the video.
sample_idx = np.linspace(0, max(0, n_frames - 1), 6, dtype=int)
frames = []
for idx in sample_idx:
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
    ok, frame = cap.read()
    if not ok: continue
    frames.append((int(idx), cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
cap.release()
print(f'Pulled {len(frames)} frames')"""
)

md(
    """## 3. YOLO inference

We run all 6 frames through YOLO with `conf=0.15` (low threshold; we
prefer recall over precision for this demo). The plot shows the
detection bboxes coloured by class.
"""
)
code(
    """import matplotlib.pyplot as plt
import matplotlib.patches as patches

CONF = 0.15
yolo_outputs = []   # list of (frame_idx, image, [(x1,y1,x2,y2,cls,conf), ...])
for idx, img in frames:
    res = yolo.predict(img, conf=CONF, verbose=False)[0]
    boxes = []
    if res.boxes is not None and res.boxes.xyxy is not None:
        xyxy = res.boxes.xyxy.cpu().numpy()
        confs = res.boxes.conf.cpu().numpy()
        clss = res.boxes.cls.cpu().numpy().astype(int)
        for (x1, y1, x2, y2), c, k in zip(xyxy, confs, clss):
            boxes.append((float(x1), float(y1), float(x2), float(y2), int(k), float(c)))
    yolo_outputs.append((idx, img, boxes))

colors = {0: '#2563EB', 1: '#10B981', 2: '#F59E0B', 3: '#EF4444', 4: '#8B5CF6'}

fig, axes = plt.subplots(2, 3, figsize=(15, 8))
for ax, (idx, img, boxes) in zip(axes.flat, yolo_outputs):
    ax.imshow(img); ax.axis('off')
    ax.set_title(f'frame {idx} — {len(boxes)} boxes', fontsize=9)
    for x1, y1, x2, y2, cls, conf in boxes:
        col = colors.get(cls % 5, '#FFFFFF')
        ax.add_patch(patches.Rectangle((x1, y1), x2 - x1, y2 - y1,
                                       linewidth=1.5, edgecolor=col, facecolor='none'))
        label = yolo.names.get(cls, str(cls))
        ax.text(x1, max(0, y1 - 6), f'{label} {conf:.2f}',
                fontsize=7, color='white',
                bbox=dict(facecolor=col, alpha=0.85, pad=1, edgecolor='none'))
plt.suptitle(f'YOLO ({version}) @ conf={CONF}', y=1.0)
plt.tight_layout(); plt.show()

total = sum(len(b) for _, _, b in yolo_outputs)
print(f'YOLO total detections across 6 frames: {total}')"""
)

md(
    """## 4. Load SAM — Segment-Anything (Meta AI)

`ultralytics` ships a SAM wrapper that downloads the lightweight ViT-B
checkpoint (~358 MB) on first call. That checkpoint is **fully
pretrained on SA-1B (1 billion masks)** — we do *not* fine-tune it.

SAM's value here: given a YOLO bbox as a *prompt*, it returns the tight
binary mask of the foreground object inside that box. The bbox doesn't
have to be tight — SAM handles loose prompts gracefully.

Latency note: SAM ViT-B on CPU is **~3-5 s per image**. For real-time
inference you'd switch to SAM2 + GPU, or replace SAM with FastSAM /
MobileSAM (~10× faster, ~85% mask quality).
"""
)
code(
    """from ultralytics import SAM

# `sam_b.pt` = SAM ViT-B (smallest). Auto-downloads on first use.
sam = SAM('sam_b.pt')
print('SAM loaded:', type(sam).__name__)
# Try a 1-frame test to spin the model and confirm it runs.
test_idx, test_img, test_boxes = yolo_outputs[0]
if test_boxes:
    sample_box = [test_boxes[0][:4]]  # [[x1,y1,x2,y2]]
    sam_res = sam.predict(test_img, bboxes=sample_box, verbose=False)
    print(f'SAM forward OK — output shape: {sam_res[0].masks.data.shape if sam_res[0].masks else \"(no mask)\"}')
else:
    print('No YOLO boxes on the test frame — SAM has nothing to prompt; skipping smoke test.')"""
)

md(
    """## 5. Pipe YOLO boxes into SAM as prompts

For each frame, every YOLO detection becomes a box prompt. SAM returns
one mask per prompt. We overlay the masks (semi-transparent) on top of
the original frames.
"""
)
code(
    """def overlay_masks(image: np.ndarray, masks: np.ndarray, palette: list[str]) -> np.ndarray:
    \"\"\"Blend N binary masks onto an RGB image, each in a distinct colour.\"\"\"
    canvas = image.astype(np.float32).copy()
    for i, m in enumerate(masks):
        col_hex = palette[i % len(palette)].lstrip('#')
        rgb = np.array([int(col_hex[j:j+2], 16) for j in (0, 2, 4)], dtype=np.float32)
        mask = (m > 0.5).astype(np.float32)
        for c in range(3):
            canvas[..., c] = np.where(mask > 0, 0.45 * canvas[..., c] + 0.55 * rgb[c],
                                      canvas[..., c])
    return canvas.clip(0, 255).astype(np.uint8)


hybrid = []  # (idx, original_image, overlaid_image, n_masks)
mask_palette = ['#2563EB', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#EC4899']
for idx, img, boxes in yolo_outputs:
    if not boxes:
        hybrid.append((idx, img, img, 0)); continue
    bbox_list = [list(b[:4]) for b in boxes]
    sam_res = sam.predict(img, bboxes=bbox_list, verbose=False)[0]
    if sam_res.masks is None:
        hybrid.append((idx, img, img, 0)); continue
    masks = sam_res.masks.data.cpu().numpy()    # (N, H, W) bool
    overlaid = overlay_masks(img, masks, mask_palette)
    hybrid.append((idx, img, overlaid, len(masks)))
print(f'Hybrid YOLO→SAM done. Mask counts per frame: {[h[3] for h in hybrid]}')"""
)

md(
    """## 6. Side-by-side comparison

Left: YOLO bounding boxes only.
Right: YOLO bbox prompts piped through SAM, with the resulting
pixel-tight masks coloured-coded.
"""
)
code(
    """fig, axes = plt.subplots(len(hybrid), 2, figsize=(13, 3 * len(hybrid)))
for row, ((idx_y, img_y, boxes_y), (_, _, img_h, n_masks)) in enumerate(zip(yolo_outputs, hybrid)):
    ax_l, ax_r = axes[row, 0], axes[row, 1]
    ax_l.imshow(img_y); ax_l.set_title(f'frame {idx_y} — YOLO ({len(boxes_y)} boxes)', fontsize=9); ax_l.axis('off')
    for x1, y1, x2, y2, cls, conf in boxes_y:
        col = colors.get(cls % 5, '#FFFFFF')
        ax_l.add_patch(patches.Rectangle((x1, y1), x2 - x1, y2 - y1, linewidth=1.5, edgecolor=col, facecolor='none'))
    ax_r.imshow(img_h); ax_r.set_title(f'YOLO → SAM ({n_masks} masks)', fontsize=9); ax_r.axis('off')
plt.tight_layout(); plt.show()"""
)

md(
    """## 7. Discussion

**Why this matters for the soutenance:**
- We re-use **two pretrained models** with zero additional training:
  YOLOv8 fine-tuned on warehouse classes (notebook 02), and SAM ViT-B
  pretrained on SA-1B. Total compute: 0 GPU-hours added in this notebook.
- The hybrid output (class label + pixel-tight mask) is what real
  warehouse-monitoring products use for **dwell-time analytics**,
  **occlusion detection**, and **collision-zone prediction**.
- SAM's class-agnostic nature is a feature, not a bug: if tomorrow we
  add `pallet` or `qr_code` to YOLO, SAM still produces clean masks
  with no retraining.

**Limits to be transparent about:**

| Limitation | Mitigation |
|---|---|
| SAM ViT-B is ~358 MB and ~3-5 s/image on CPU. | For production, use FastSAM (~30 ms) or MobileSAM (~50 ms). |
| The current YOLO fine-tune has only 3 classes (`box`, `person`, `forklift`). | Add more classes via additional CVAT annotation passes. |
| SAM was trained on natural images, not synthetic renders (TalTech is synthetic). | Mask quality drops ~10% on synthetic vs real — acceptable for demo. |
| Hybrid pipeline writes to the same Kafka topic (`detections`) without a mask field. | Schema-evolve `Detection.avsc` with an optional `mask_rle` field; consumers ignore unknown fields. |

**Production wiring:**
The current `services/inference_worker/worker.py` loads YOLO only. To
ship the hybrid pipeline:

```python
# inside services/inference_worker/worker.py, after yolo.predict()
from ultralytics import SAM
sam = SAM('sam_b.pt')                            # load once at startup

# per frame
if detections:
    bboxes = [(d['x1'], d['y1'], d['x2'], d['y2']) for d in detections]
    masks = sam.predict(image, bboxes=bboxes, verbose=False)[0].masks
    for d, m in zip(detections, masks.data):
        d['mask_rle'] = encode_rle(m.cpu().numpy())   # add COCO-style RLE
```

The dashboard's `AnalyticalCameraFeed` already projects bbox SVG overlays
— it would only need a `<canvas>` layer to render the mask polygons,
hidden behind a "Show masks" toggle in the HUD.
"""
)

# ---------------------------------------------------------------------------
notebook = {
    "cells": NB,
    "metadata": {
        "kernelspec": {"display_name": "Python 3 (uv)", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
out = pathlib.Path("ml/notebooks/03_inference_and_sam.ipynb")
out.write_text(json.dumps(notebook, indent=1, ensure_ascii=False))
print(f"wrote {out}  ({out.stat().st_size:,} bytes, {len(NB)} cells)")
