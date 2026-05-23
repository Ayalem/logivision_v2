# LOGIVISION notebooks — how to run each, what each produces

Six notebooks form the full ML story for the project. They are
**pre-executable on Colab T4 (free)** for the YOLO ones and **local
CPU (3-5 min)** for the LSTM one. The flow goes from raw data →
labelling → training → fine-tuning → inference → time-series
forecasting → wired into the dashboard.

```
00 ─→ Colab YOLO training        (sets the baseline)
01 ─→ Local CPU YOLO training    (without GPU, slower)
02 ─→ Transfer-learning walk-through (pedagogical; understanding)
03 ─→ Inference demo + SAM       (visual proof on Camera3.mp4)
05 ─→ Congestion LSTM (UCI PRSA) (the trained predictive model)
06 ─→ 2-Phase ULMFiT fine-tune   (the production fine-tune recipe)
```

(There is no notebook 04 — it was reserved for the accuracy-evaluation
notebook which is still in the Day-2 plan.)

---

## How to run each

### 00 — Train YOLOv8 on Colab (T4 GPU)

**What it does**: fine-tunes COCO-pretrained YOLOv8n on the Kaggle
`warehouse-delivery-box` dataset (361 train / 99 val / 61 test), 50
epochs, batch 32, imgsz 640. Reports mAP@0.5 / mAP@0.5:0.95 / per-class
P/R on the held-out test split.

**How**:
1. Open https://colab.research.google.com → **File → Open notebook → GitHub
   tab** → paste `Ayalem/logivision_v2` → pick
   `ml/notebooks/00_colab_training.ipynb`.
2. **Runtime → Change runtime type → T4 GPU**.
3. **Secrets** (left rail key icon): add `KAGGLE_USERNAME` + `KAGGLE_KEY`
   from your Kaggle account API token.
4. **Runtime → Run all** (~25 min).
5. Last cell triggers a download of
   `logivision_colab_run_<timestamp>.zip` with `best.pt`,
   `results.csv`, confusion matrices.
6. Locally:
   ```
   unzip ~/Downloads/logivision_colab_run_*.zip -d ml/runs/00_colab/
   make register-from-colab RUN=00_colab
   make worker-restart
   ```

**Output**: `runs/detect/colab_kaggle_50ep/weights/best.pt`.
**Current best**: mAP@0.5 = **0.995** on the local 50-epoch run.

### 01 — YOLOv8 Detection Training (local CPU)

**What it does**: same training task as `00`, but **without GPU**. Use
when you don't want to depend on Colab. ~4 hours on an M-series Mac.

**How**:
```bash
make bootstrap                 # MLflow + MinIO + Postgres (once)
make train                     # local CPU training, logs to MLflow
```

**Output**: a UUID-named run dir under `ml/runs/`, same `weights/best.pt`
+ `results.csv`. Already present locally: 3 runs, best is
`ml/runs/8a4db577ff1e4abf9c8276cdd6967bb7/` at mAP@0.5 = **0.995**.

### 02 — Transfer-Learning Walk-Through

**What it does**: pedagogical notebook explaining transfer learning
step by step (frozen layers, learning-rate scheduling, why we use
COCO weights). No new model — meant to be read with the soutenance
defense in mind.

**How**:
```bash
make jupyter                   # opens at http://localhost:8888
# then click ml/notebooks/02_transfer_learning_yolo.ipynb
```

**Output**: discussion + diagrams. No artifacts.

### 03 — Inference Demo + Segment-Anything (SAM)

**What it does**: loads the Production YOLO model (or fallback), runs
inference on Camera3.mp4, overlays bboxes, optionally calls SAM for
fine-grained masks on detected boxes. Useful for showing the
detector working frame-by-frame in the soutenance.

**How**:
```bash
# Make sure the production model is registered (see step 00 above)
make jupyter
# Open ml/notebooks/03_inference_and_sam.ipynb and Run All
```

**Output**: annotated frames saved to `ml/notebooks/.outputs/03/`.

### 05 — Congestion-Forecast LSTM (UCI PRSA)

**What it does**: trains a **real** 2-layer LSTM on the UCI Beijing
Multi-Site Air-Quality dataset (12 stations, hourly PM2.5, 16 weeks
subset). Reports RMSE/MAE on the held-out test split at +1 h / +3 h /
+6 h horizons against a persistence baseline. The trained `model.pt`
ships with the repo; the dashboard's Congestion panel loads it at
startup.

**How**:
```bash
make jupyter
# Open ml/notebooks/05_congestion_lstm.ipynb and Run All  (~5 min CPU)
```

Or just look at the embedded outputs — the notebook is pre-executed
and committed with plots inline.

**Output**: `ml/artifacts/congestion_lstm/{model.pt, metrics.json,
history.csv}` (committed, used by `services/api/_lstm_inference.py`).
**Current**: LSTM beats persistence by +5.4 % RMSE at the +3 h horizon.

### 06 — Two-Phase ULMFiT Fine-Tune (Colab T4)

**What it does**: the **production fine-tuning recipe**. Phase 1
freezes the backbone (`freeze=10`) and trains the detection head for
10 epochs. Phase 2 unfreezes the last 3 backbone blocks (`freeze=7`)
with a 10× lower LR (1e-4) for 30 epochs. Compares Phase-2 against
Phase-1 on the held-out test split.

**How** (same workflow as notebook 00):
1. Colab → File → Open notebook → GitHub → pick
   `ml/notebooks/06_two_phase_finetune.ipynb`.
2. T4 GPU runtime, Kaggle secrets set.
3. Run all (~30 min).
4. Locally:
   ```
   unzip ~/Downloads/bundle_two_phase_*.zip -d ml/runs/two_phase/
   make register-from-colab RUN=two_phase
   make worker-restart
   ```

**Output**: `runs/two_phase/{phase1, phase2}/weights/best.pt` +
side-by-side comparison table + training curves.

---

## Full pipeline today (zero-to-Production checklist)

1. **Bootstrap infra**: `make bootstrap && make kafka-up`
2. **Bring up the dataset**: dataset already prepared at
   `data/processed/kaggle_warehouse/` (committed). If missing:
   `uv run python scripts/prepare_kaggle_warehouse.py`.
3. **Train YOLO**: pick one
   - Colab path: notebook 00 (T4, ~25 min) — recommended
   - Local CPU: `make train` (~4 h)
4. **Or use the existing 99.5%-mAP model already on disk**:
   `make register-from-colab RUN=8a4db577ff1e4abf9c8276cdd6967bb7`
5. **(Optional) 2-phase fine-tune** for the soutenance ULMFiT story:
   notebook 06 on Colab T4 (~30 min).
6. **Promote to Production**:
   `make register-from-colab RUN=<your_run_dir>`
7. **Restart the worker**: `make worker-restart`
8. **Run the pipeline**:
   ```
   make frame-grabber SOURCE=datasets/raw/videos/Camera3.mp4 CAMERA=CAM03 FPS=2
   make inference-worker
   make cep ZONES=infra/zones.example.yaml
   ```
9. **Open the dashboard**: http://localhost:5173 — bounding boxes
   from the trained YOLO appear in the Camera3 tile; the AI Model
   Status panel shows the new model version.

---

## Labelling more warehouse data (optional, Phase 3 work)

If you want to grow the dataset beyond Kaggle's 361 images:

```bash
make cvat-up                    # http://localhost:8080
```

1. Create a CVAT project named *logivision-warehouse*.
2. Upload frames you've extracted from your warehouse videos
   (`ffmpeg -i Camera3.mp4 -r 1 frames/cam03_%05d.jpg`).
3. Draw bounding boxes for `box_small`, `box_medium`, `box_large`.
4. Export as YOLO v1.1 format.
5. Drop the export into `data/processed/kaggle_warehouse/<split>/`
   (the YOLO data.yaml is already configured).
6. Re-run notebook 06 — now training on Kaggle + your real warehouse
   labels.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'services'` in Colab | Notebook 00 / 06 already insert `sys.path`. If you cloned manually, run `import sys, pathlib; sys.path.insert(0, str(pathlib.Path.cwd()))` before any `from services.*` import. |
| `pip install services` ran and broke things | That's an unrelated PyPI package — `pip uninstall services`. The correct fix is the `sys.path` insert above. |
| Worker logs `fallback:yolov8n.pt` instead of `logivision-detector/v1/Production` | MLflow has no Production version; run `make register-from-colab RUN=<dir>`. |
| Colab session disconnects mid-training | Re-open the notebook, re-run cells 1–5, then **only** cell 6 — the defensive `try: DATA_YAML` guard recovers from disk. |
| `pyzbar` fails to import on macOS | `brew install zbar && export DYLD_LIBRARY_PATH=/opt/homebrew/opt/zbar/lib`. The `make qr-decoder` target does this automatically. |
| Notebook outputs missing in the committed `.ipynb` | They were stripped accidentally. Re-run with outputs: `jupyter nbconvert --to notebook --execute --inplace <file>.ipynb`. |
