# LOGIVISION notebooks — every one is wired into Production

No pedagogical-only notebooks. Each notebook here produces an
**artifact that the running system actually consumes**. The
production chain:

```
v0 (COCO yolov8n.pt)                 # cold start
  ↓                                   notebook 00
v1 (Kaggle-fine-tuned)               # initial Production YOLO
  ↓                                   notebook 06 (2-Phase ULMFiT)
v2 (frozen→unfreeze fine-tune)       # better Production YOLO
  ↓                                   notebook 07 (Noisy Student)
v3 (teacher→pseudo-labels→student)   # continual improvement loop
  ↓                                   re-run weekly as new footage arrives
v4, v5, … (each iteration)
```

Plus:
- **notebook 04** — accuracy evaluation on hand-labelled ground truth.
  The **gating criterion** before promoting any new version.
- **notebook 05** — congestion LSTM. Produces the `model.pt` the
  dashboard's Congestion panel loads at startup.

```
00 ─→ initial YOLO training         (Colab T4 ~25 min)     produces v1
03 ─→ inference + SAM demo          (verification visual)   for soutenance
04 ─→ evaluation on hand-labels     (TODO Day 2)            gating criterion
04 ─→ model evaluation (quant+qual)  (~5 min, no GPU)        ml/artifacts/eval/
05 ─→ congestion LSTM (Birmingham)  (~5 min CPU)            ml/artifacts/congestion_lstm/
06 ─→ 2-Phase ULMFiT fine-tune      (Colab T4 ~30 min)     produces v2
07 ─→ Noisy Student teacher→student (Colab T4 ~45 min)     produces v3, v4, …
```

---

## What each one is for

### 00 — Initial YOLO training (Colab T4)

**Production artifact**: `runs/detect/colab_kaggle_50ep/weights/best.pt`
→ registered as `logivision-detector/v1/Production`.

**Used by**: `services/inference_worker/worker.py` loads this via
`services/model_server/service.py::resolve_model_weights()`.

**How**:
1. Colab → File → Open notebook → GitHub → `Ayalem/logivision_v2`
   → `ml/notebooks/00_colab_training.ipynb`.
2. Runtime → T4 GPU. Add `KAGGLE_USERNAME` + `KAGGLE_KEY` as Colab
   Secrets.
3. Runtime → Run all (~25 min).
4. Locally:
   ```
   unzip ~/Downloads/logivision_colab_run_*.zip -d ml/runs/00_colab/
   make register-from-colab RUN=00_colab
   make worker-restart
   ```

**Current model (v3)**: mAP@0.5=0.995 — **this is inflated** by temporal leakage
in the original Kaggle split (Roboflow shuffled adjacent video frames across
train/test). The scene-aware split fix is already in the notebook code
(`scripts/reshuffle_splits_by_scene.py`). **Retrain to get honest numbers** —
expected real mAP is 0.70–0.85 on genuinely unseen test scenes. See notebook 04
for the evaluation on the clean split.

### 03 — Inference demo + SAM (verification)

**Production artifact**: none — this is the visual proof for the
soutenance defense. Runs the current Production YOLO on a single
Camera3.mp4 clip and overlays bboxes + SAM masks frame by frame.

**Used by**: nobody at runtime. Used by **you** to show that the
model works in real time, with screenshots for the defense slides.

**How**: `make jupyter` → open
`ml/notebooks/03_inference_and_sam.ipynb` → Run all (~3 min).

### 04 — Model evaluation (quantitative + qualitative)

**Status**: Implemented. Run locally or on Colab (no GPU needed for eval).

**Part A** — quantitative: runs `model.val()` on the scene-aware clean
Kaggle test split. Reports mAP@0.5, mAP@0.5:0.95, precision, recall per
class. Saves `ml/artifacts/eval/quantitative.json`.

**Part B** — qualitative: samples 100 frames from Camera3.mp4, runs
inference, shows detection visualisations and a detection-rate summary.
No ground-truth labels needed. Saves `ml/artifacts/eval/qualitative.json`.

**MOTA / IDF1** (full tracking evaluation) requires a hand-annotated
sequence and is scoped as Future Work.

**How**: `make jupyter` → open `04_model_evaluation.ipynb` → Run all.
Or on Colab: open from GitHub.

### 05 — Congestion LSTM (Parking Birmingham)

**Production artifact**: `ml/artifacts/congestion_lstm/model.pt`
trained on the **Parking Birmingham** dataset (Stolfi 2017 / UCI) — 32
parking lots across Birmingham UK, half-hourly occupancy ratio,
Oct–Dec 2016. Direct domain transfer: multi-location bounded-count
time series with diurnal/weekly patterns, same as warehouse zones.

**Used by**: `services/api/_lstm_inference.py::forecast_zone_occupancy()`
loads it at API startup. The dashboard's **Congestion** panel header
flips the badge to `LSTM · Birmingham-transferred · v1`.

**How**: `make jupyter` → open `05_congestion_lstm.ipynb` → Run all
(~5 min CPU, no GPU needed).

### 06 — 2-Phase ULMFiT fine-tune (Colab T4)

**Production artifact**: `runs/two_phase/phase2/weights/best.pt`
→ becomes `logivision-detector/v2/Production` (replacing v1 from
notebook 00).

**Methodology**: Howard & Ruder 2018 ULMFiT gradual unfreezing.
- **Phase 1** (`freeze=10`, 10 epochs, lr=1e-3): backbone frozen,
  train detection head only. Prevents catastrophic forgetting.
- **Phase 2** (`freeze=7`, 30 epochs, lr=1e-4): last 3 backbone
  blocks unfrozen, low LR. Adapts deep features to warehouse
  specifics.

**How**: same Colab workflow as notebook 00, picks
`ml/notebooks/06_two_phase_finetune.ipynb`. Bundle download at the
end. Locally:
```
unzip ~/Downloads/bundle_two_phase_*.zip -d ml/runs/two_phase/
make register-from-colab RUN=two_phase
make worker-restart
```

### 07 — Noisy Student teacher→student (Colab T4)

**Production artifact**: `runs/noisy_student/student/weights/best.pt`
→ becomes `logivision-detector/v3/Production` **only if** the
student beats the teacher on the held-out Kaggle test split (gating
inside the notebook). On rerun: `v4`, `v5`, …

**Methodology**: Xie et al. 2020 Noisy Student.
1. Teacher = current Production model (v2 from notebook 06 or
   later).
2. Teacher pseudo-labels unlabeled warehouse footage at conf ≥ 0.5.
3. Student = yolov8s (one size up from teacher's yolov8n), trained
   on Kaggle + pseudo-labeled frames with strong noise (high
   mosaic, mixup, dropout, HSV jitter).
4. Evaluate student vs teacher on held-out Kaggle test.
5. Promote student to Production ONLY if `student_wins=True`.

**Unlabeled data source**: `machowe/warehouse-object-detection-dataset`
(Kaggle) — a second, different-distribution warehouse dataset. This is
the correct Noisy Student setup: unlabeled frames from a *different*
domain force the student to generalise, not just memorise the teacher's
outputs on its training images.

**Continual production loop** — re-run weekly:
- In production, new RTSP camera dumps replace the Kaggle unlabeled set.
- Each iteration uses the current Production model as the new teacher.
- The dataset effectively grows each run; the student keeps improving
  past what 361 hand-labeled Kaggle images alone could achieve.

**How**: same Colab workflow, picks
`ml/notebooks/07_noisy_student.ipynb`. Read the gating output before
promoting:
```
unzip ~/Downloads/bundle_noisy_student_*.zip -d ml/runs/noisy_student/
cat ml/runs/noisy_student/metrics.json   # check student_wins == true
make register-from-colab RUN=noisy_student
make worker-restart
```

---

## Zero-to-Production from a fresh clone

```bash
# 1. Bring up infra
make bootstrap                # MLflow + MinIO + Postgres
make kafka-up                 # Kafka KRaft

# 2. Initial YOLO training. Pick one:
#    (a) Register after running notebook 00 on Colab (honest mAP on clean split):
make register-from-colab RUN=00_colab
#       (v3 mAP=0.995 is on the contaminated split — do NOT use for paper claims)
#    (b) FRESH: open ml/notebooks/00_colab_training.ipynb on Colab T4,
#        run all, then `make register-from-colab RUN=00_colab`.

# 3. (optional) better v2 via 2-Phase ULMFiT:
#    open ml/notebooks/06 on Colab T4, run all, register as v2.

# 4. (optional) v3+ via Noisy Student (only after collecting some
#    unlabeled warehouse footage):
#    open ml/notebooks/07 on Colab T4, run all, ONLY register if
#    student_wins=true in metrics.json.

# 5. Always restart the worker after promoting:
make worker-restart

# 6. Run the pipeline (each in its own terminal)
make api
make frame-grabber SOURCE=datasets/raw/videos/Camera3.mp4 CAMERA=CAM03 FPS=2
make inference-worker
make cep ZONES=infra/zones.example.yaml

# 7. Open the dashboard
open http://localhost:5173   # or http://localhost:8000
```

---

## Labelling more warehouse data (optional, accelerates Noisy Student)

The more unlabeled warehouse footage you give to notebook 07, the
better the next student. To add labelled data instead (which
notebooks 00 / 06 use directly):

```bash
make cvat-up                  # http://localhost:8080
```

1. Create CVAT project `logivision-warehouse`.
2. Upload extracted frames:
   ```
   ffmpeg -i datasets/raw/taltech_videos/Camera3.mp4 -r 1 frames/cam03_%05d.jpg
   ```
3. Draw bboxes for `box_small`, `box_medium`, `box_large`.
4. Export as YOLO v1.1.
5. Merge into `data/processed/kaggle_warehouse/`.
6. Re-run notebook 06 — now training on Kaggle + your labels.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'services'` in Colab | Notebooks 00 / 06 / 07 insert `sys.path` at startup. If you wrote your own cell, run `import sys, pathlib; sys.path.insert(0, str(pathlib.Path.cwd()))` before any `from services.*` import. |
| `pip install services` ran and broke things | That's an unrelated PyPI package — `pip uninstall services`. The fix is the `sys.path` insert. |
| Worker logs `fallback:yolov8n.pt` | MLflow has no Production version. Run `make register-from-colab RUN=<dir>`. |
| Notebook 07 says `student_wins=false` | Don't promote. Either pseudo-label confidence threshold was too low (try 0.7) or the unlabeled frames were too out-of-distribution. Iterate. |
| Notebook 07 cell 5 fails on `machowe/warehouse-object-detection-dataset` | Add `KAGGLE_USERNAME` + `KAGGLE_KEY` as Colab Secrets (same as notebooks 00/06). The dataset is ~200 MB and downloads automatically via kagglehub. |
| `pyzbar` fails on macOS | `brew install zbar && export DYLD_LIBRARY_PATH=/opt/homebrew/opt/zbar/lib`. `make qr-decoder` handles this automatically. |
