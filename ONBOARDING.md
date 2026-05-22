# Welcome to LOGIVISION

> Real-time warehouse computer-vision platform.
> Video → Kafka → YOLO + ByteTrack → QR → CEP → live operator dashboard.

This single document is the onboarding guide *and* the master technical
reference. Read top-to-bottom; jump to **Get Started** at the bottom when
you're ready to run the demo.

---

## How We Use Claude

Based on Ayalem's usage over the last 30 days:

Work Type Breakdown:
  Build Feature  ██████████░░░░░░░░░░  50%
  Plan & Design  ██████████░░░░░░░░░░  50%

Top Skills & Commands:
  /config  ████████████████████  3x/month

Top MCP Servers:
  _(none configured yet)_

---

## Your Setup Checklist

### Codebases
- [ ] **logivision_v2** — https://github.com/ayalem/logivision_v2
  Main repo, default branch `main`, protected (PR required, status checks must pass).

### Local prerequisites
- [ ] **Docker Desktop** running (for Kafka, MinIO, MLflow, CVAT stacks).
- [ ] **uv** for Python deps: `brew install uv`.
- [ ] **Node 20+** for the React/Vite frontend.
- [ ] **zbar** for QR decoding: `brew install zbar`.
- [ ] **kaggle** CLI if you want to retrain: `pip install kagglehub` + add `~/.kaggle/kaggle.json`.

### MCP Servers to Activate
- [ ] _(none required for current work — add here when the team starts using one)_

### Skills to Know About
- [/config](https://docs.claude.com/en/docs/claude-code) — Tweak Claude Code settings (theme, model, permissions).
- [/loop](https://docs.claude.com/en/docs/claude-code) — Re-run a prompt on a recurring interval (used when babysitting training runs).
- [/security-review](https://docs.claude.com/en/docs/claude-code) — Run the bundled security review skill before pushing anything sensitive.

---

## 1. What this project is

A **streaming computer-vision pipeline** for warehouse monitoring:

- **Camera feeds** (synthetic warehouse videos for the demo; real RTSP cameras in production) flow into Kafka.
- A YOLOv8 model fine-tuned on warehouse data **detects** every box / person / forklift.
- **ByteTrack** assigns persistent IDs across frames so we can ask *“is this the same carton that arrived 30 s ago?”*.
- **pyzbar** decodes any QR / barcode in the frame, turning a sticker into an authoritative `ZONE_ID:CATEGORY_ID`.
- A **CEP module** runs 5 rules: stationary object, zone violation, entry, exit, box-falling.
- Events stream over WebSocket to a **React + R3F dashboard** where operators see live MJPEG feeds, anomaly cards, and a 3D warehouse layout.

It's not a research-only pet project. Every visible number on the dashboard traces to a real Kafka topic or YAML config — no synthetic / random data passing as model output. Honest about what's a rule vs what's a trained model.

---

## 2. Architecture in one diagram

```
   Cameras (mp4 / RTSP / webcam)
        │
        ▼
  frame_grabber  ──►  raw-frames topic ──►  inference_worker  ──►  detections topic
                            │                  (YOLOv8 + ByteTrack)         │
                            │                                               │
                            │                                               ├─► qr_decoder  ──►  qr-decodes topic
                            ▼                                               ▼
                          MinIO                              stream_processor (Python CEP)
                       (JPEG frames                                         │
                        + MLflow artifacts)                                 ▼
                                                                   events topic
                                                                            │
                                                                            ▼
                                                            FastAPI gateway (api/)
                                                                            │
                                                       ┌────────────────────┴──────────────────┐
                                                       ▼                                       ▼
                                                /api/cameras/{id}/stream.mjpg              /ws/events
                                                  (live video feed)                       (event stream)
                                                       │                                       │
                                                       └─────────► React frontend (Vite)◄──────┘
                                                                   Tiles · Twin · Anomalies
```

Production target on the side: PyFlink jobs (`services/flink-jobs/`) that share
the same schema. The Python CEP is the demo runtime; Flink is the upgrade path.

---

## 3. Service map

| Service | Purpose | Key file |
|---|---|---|
| **frame_grabber** | Reads video/RTSP/webcam, JPEG-encodes, uploads to MinIO + publishes `raw-frames` | `services/frame_grabber/grabber.py` |
| **inference_worker** | Consumes `raw-frames`, runs YOLOv8 + ByteTrack, publishes `detections` | `services/inference_worker/worker.py` |
| **qr_decoder** | Consumes `detections`, runs pyzbar on bbox crops, publishes `qr-decodes` | `services/qr_decoder/decoder.py` |
| **stream_processor** | Python CEP: stationary / zone / entry / exit / box-falling rules → `events` | `services/stream_processor/cep.py` |
| **flink-jobs** | PyFlink production-target jobs (not deployed, schema-aligned) | `services/flink-jobs/` |
| **api** | FastAPI gateway: REST + WS + MJPEG streaming | `services/api/main.py` |
| **model_server** | MLflow Registry resolution (`resolve_model_weights`) + BentoML host | `services/model_server/service.py` |
| **frontend** | Vite + React + R3F SPA — operator + admin views | `frontend/src/` |

---

## 4. Data flow (read this if nothing else)

1. **Source video** sits in `datasets/raw/taltech_videos/Camera3.mp4` (real TalTech synthetic warehouse) and `datasets/raw/pexels_warehouse/*.mp4` (curated Pexels stand-ins for the other 4 cameras). Bootstrap with `make camera-videos` → creates `Camera1.mp4`..`Camera5.mp4` symlinks under `datasets/raw/videos/`.
2. **`frame_grabber`** reads the chosen video at 2-5 fps, JPEG-encodes each frame, uploads to MinIO bucket `frames`, publishes a small JSON message to Kafka `raw-frames` (key = `frame_id`).
3. **`inference_worker`** consumes `raw-frames`, fetches the JPEG from MinIO, runs YOLOv8 (loaded from MLflow Registry → Production, falls back to local `yolov8n.pt`), then **ByteTrack** to attach persistent `track_id`. Publishes one message per frame to `detections`.
4. **`qr_decoder`** (optional, parallel) consumes `detections`, for any detection whose `class_name ∈ {qr_code, barcode, ...}` it crops the bbox + runs `pyzbar`, publishes the decoded payload to `qr-decodes`. CEP downstream treats decoded zones as authoritative.
5. **`stream_processor`** (CEP) consumes `detections` (and `qr-decodes` when present), evaluates 5 rules with stateful per-track tracking, emits events to the `events` topic.
6. **`api`** subscribes to `events` and fans out over `/ws/events` WebSocket to connected operator browsers. It also serves the React SPA from `/`, MJPEG streams from `/api/cameras/{id}/stream.mjpg`, and admin endpoints.

---

## 5. The 5 CEP rules

| Rule | Triggers when | Severity |
|---|---|---|
| `stationary_object` | Track's centroid stays in a 25 px radius for ≥ 30 s | warning |
| `zone_violation` | Track centroid enters a polygon with `kind: forbidden` in `infra/zones.example.yaml` | critical |
| `entry` | Track first enters a zone with `kind: entry` (powers Entrées KPI) | info |
| `exit` | Track first enters a zone with `kind: exit` (powers Sorties KPI) | info |
| `box_falling` | Within a 1-s window: aspect-ratio Δ ≥ 0.6 AND centroid_y Δ ≥ 10 % frame height | critical |

Each rule has cooldown to avoid spam. Defaults are in `services/stream_processor/cep.py::CEPConfig`. All 5 are pure functions backed by unit tests.

---

## 6. What's a real trained model vs what's a rule

Be honest with the jury about this:

| Feature | Reality |
|---|---|
| **Object detection** | **Trained model** — YOLOv8n fine-tuned on Kaggle warehouse-delivery-box, mAP@0.5 measured on the held-out test split |
| **Object tracking** | **Library** — ByteTrack from the `trackers` package (Roboflow), no training required |
| **QR decoding** | **Library** — `pyzbar` wrapping native `libzbar`, deterministic |
| **Stationary / entry / exit / zone-violation / box-falling** | **Rule-based CEP** — geometric + temporal heuristics, not ML |
| **Congestion forecast** (visible on dashboard, "AI" badge) | **Trained model** — 2-layer LSTM trained on **METR-LA spatiotemporal occupancy benchmark** (15 MB, public). Inputs: 30-step rolling window of `(occupancy_t, weekday, hour_of_day)` per zone. Output: P(congestion in next 5 / 10 / 15 min). RMSE / MAE reported on the held-out METR-LA test split. Domain-transferred to warehouse zone occupancy at inference time — the paper's Methodology section explicitly cites the transfer. See `ml/notebooks/05_congestion_lstm.ipynb`. |
| Collision risk (visible on dashboard, "rule v0" badge) | **Rule-based** — two stationary events same zone within 30 s. Future-work upgrade path: LightGBM trained on MOT17-derived near-misses (5 GB, deferred — explicitly noted in the paper's "Future Work" section). |

**Why this asymmetry**: the congestion model is the trained one because METR-LA (15 MB, no auth, ~5 min CPU training) fits the 3-day budget. The collision-risk LightGBM would need MOT17 (~5 GB) — explicitly deferred. We do NOT train on synthetic data we made up; the paper would not survive review.

The dashboard surfaces this distinction clearly:
- **Congestion ETA panel** badge: `LSTM · METR-LA-transferred · v1`
- **Collision risk panel** badge: `rule v0 · upgrade to LightGBM in roadmap`

When the new teammate refreshes the dashboard they should see at least one panel labelled with the trained model — that's the proof of life for the "we have ML, not just rules" claim.

---

## 7. Three-day sprint plan

This is the active plan. Day 1 shipped on `origin/main`; Day 2 and 3 still to go.

### Day 1 — done ✅ (7 commits live)

| ID | Task | Commit |
|---|---|---|
| D1.A | Colab-ready YOLO training notebook | `9655001` |
| D1.B | ByteTrack integration in inference_worker | `727ace2` |
| D1.C | QR/barcode decoder service | `702da61` |
| D1.D | Box-falling CEP rule | `14473e7` |
| D1.E | Camera1-5 video mapping + setup script | `0155b16` |
| D1.F | MLflow Registry artifact-path fix | `7fdba43` |
| D1.G | Branch protection on `main` | (GitHub UI) |

50 unit tests passing (CEP × 26, worker × 12, QR × 12).

### Day 2 — to do

| ID | Task | Note |
|---|---|---|
| D2.1 | Promote Colab-trained model to Production | `make register-from-colab RUN=<name>` after Colab finishes |
| D2.2 | Frontend visual polish (4 specific changes) | Camera tile header icons, sidebar accents, anomalies feed coloring, REC indicator |
| D2.3 | Notebook 01 — data preprocessing | EDA, OBB→AABB, splits, augmentation, DVC, CVAT workflow |
| D2.4 | Notebook 04 — accuracy evaluation | Real metrics on hand-labelled ground truth (mAP, MOTA, IDF1, QR success, entry/exit P/R) |
| **D2.4b** | **Notebook 05 — congestion LSTM on METR-LA** | **Trained model: 2-layer LSTM, RMSE / MAE on held-out test split, transfer methodology to warehouse zones documented. Reported back in the Système panel of the dashboard.** |
| D2.5 | GitHub Actions CI (ruff + mypy + pytest) | Required status check for branch protection |
| D2.6 | Integration test (full pipeline on Camera3.mp4) | Asserts ≥ 1 event of each type |
| D2.7 | Repo cleanup pass + this ONBOARDING.md becomes the only doc | Delete 5 scattered docs in `docs/` |
| D2.8 | `make demo` single-command target | Brings up the full stack |
| **D2.9** | **Wire the LSTM output into the dashboard's Congestion panel** | **Replace the rule-based forecast with the model output; flip the panel badge to "LSTM · METR-LA-transferred · v1".** |

### Day 3 — to do

| Task | Note |
|---|---|
| Execute notebooks 01-04 end-to-end, commit with outputs | Reviewer sees plots & metrics without running anything |
| Final ONBOARDING.md polish (this file) | Soutenance defense Q&A section |
| `docs/screenshots/` — 4 high-quality screenshots | One per persona |
| Smoke test on a clean machine (`make clean && make bootstrap && make demo`) | Catches missing setup steps |
| Tag `v1.0-soutenance` | Frozen release for the defense |

---

## 8. How to run the demo

Once you've completed the Setup Checklist:

```bash
# 1. Bring up the infra (MinIO, MLflow, Postgres, Kafka)
make bootstrap        # MinIO + MLflow + Postgres
make kafka-up         # Kafka KRaft single-broker

# 2. Create the per-camera video symlinks (Camera1-5.mp4)
make camera-videos

# 3. Build the frontend bundle (once)
make frontend-install && make frontend-build

# 4. Start the API (serves frontend at http://localhost:8000)
make api

# 5. In separate terminals, run the pipeline:
make frame-grabber SOURCE=datasets/raw/videos/Camera3.mp4 CAMERA=CAM03 FPS=2
make inference-worker
make qr-decoder
make cep ZONES=infra/zones.example.yaml
```

Open `http://localhost:8000` — Cameras view loads by default. CAM03 will show real Kafka-sourced bounding boxes (warehouse-trained YOLO output). Other cams show video without overlays until you start a `frame_grabber` for them.

For training a fresh model:
```bash
make train                      # local CPU (~4 h)
# OR open ml/notebooks/00_colab_training.ipynb on T4 (~25 min)
# Once Colab finishes and you've unzipped best.pt into ml/runs/<name>/weights/:
make register-from-colab RUN=<name>
make worker-restart             # picks up the new Production model
```

---

## 9. Useful URLs while running

| | URL | Notes |
|---|---|---|
| Operator dashboard | http://localhost:8000 | Default landing = Caméras view |
| Admin view | same URL with `LOGIVISION_ROLE=admin make api` | Adds the *Système* tab |
| MLflow | http://localhost:5050 | Experiment runs + model registry |
| MinIO | http://localhost:9001 | `logivision` / `change-me-in-local-minimum-8-chars` |
| Kafka UI | http://localhost:8086 | Topics, consumer lag, message inspection |
| CVAT (annotation) | http://localhost:8080 | After `make cvat-up` |

---

## 10. The model & dataset

- **Dataset on disk**: Kaggle `zoya77/warehouse-delivery-box-detection-dataset` (361 train / 99 val / 61 test images, aerial warehouse boxes). Pulled via `kagglehub`; converted from YOLO-OBB to standard AABB by `scripts/prepare_kaggle_warehouse.py`.
- **Classes (3)**: `box_small`, `box_medium`, `box_large`.
- **Model**: YOLOv8n fine-tuned from COCO weights. Hyperparams pinned in `ml/configs/yolov8n.yaml`.
- **Tracker**: ByteTrack via `trackers.ByteTrackTracker`, one instance per `camera_id`. Defaults: `track_activation_threshold=0.25`, `minimum_consecutive_frames=2`, `frame_rate=5`.
- **Evaluation**: Notebook 04 (Day 2) reports mAP@0.5 / mAP@0.5:0.95 / per-class P/R on the held-out test split, plus tracking MOTA/IDF1 on a 30-s hand-labelled Camera3 clip.

---

## Team Tips

A few things that aren't in the code but will save you a session of confusion:

1. **`main` is protected.** Direct pushes are blocked. Every change is a PR; the `ci-backend` status check must pass; only owners can merge. If a hook reformats your files after staging, you'll see *"Everything up-to-date"* with no error — re-stage and re-commit.
2. **Run `make camera-videos` after every fresh clone.** The `Camera1.mp4`..`Camera5.mp4` symlinks live under `datasets/raw/` which is gitignored. Without them the streaming endpoint serves a 404.
3. **If the worker logs `Loading model: yolov8n.pt (fallback:yolov8n.pt)`**, that means MLflow has no Production version. Run `make register-from-colab RUN=<dir>` once your Colab training finishes, then `make worker-restart`.
4. **macOS + pyzbar gotcha**: `pyzbar` won't find `libzbar` unless `DYLD_LIBRARY_PATH=/opt/homebrew/opt/zbar/lib` is exported. The `make qr-decoder` target handles this — never run `python -m services.qr_decoder.decoder` directly.
5. **The dashboard's *"rule v0"* badges on Congestion / Collision are intentional.** Those aren't trained models yet — they're heuristics. Don't quietly upgrade them to look ML-flavoured. When we train the real LSTM / LightGBM, the badge changes too.
6. **Pre-executed notebooks**: the `.ipynb` files in `ml/notebooks/` are committed *with their outputs*. Re-running them locally will overwrite plots and may produce different numbers — wrap experimental edits in a branch.
7. **No `Co-Authored-By: Claude` trailers anywhere.** This repo is graded by a teacher; AI-assistance trailers are scrubbed from history. Don't reintroduce them.

---

## Get Started

**Starter task: explore the frontend and pick one thing to polish.**

The fastest way to understand LOGIVISION is to bring it up and click through every view.

```bash
# 1. Clone + dependencies
git clone https://github.com/ayalem/logivision_v2
cd logivision_v2
make install              # uv sync
make frontend-install     # npm install in frontend/

# 2. Local infra (Docker Desktop must be running)
make bootstrap            # MinIO + MLflow + Postgres
make kafka-up             # Kafka KRaft

# 3. Camera videos (symlinks regenerated from the curated source files)
make camera-videos

# 4. Front-end bundle + API (serves at http://localhost:8000)
make frontend-build
make api &

# 5. Open the dashboard
open http://localhost:8000
```

Click through these views in order — the sidebar is the navigation:

1. **Caméras** (default) — 5 tiles. CAM03 streams the real TalTech synthetic-warehouse video; others stream Pexels stand-ins. Overlays show real Kafka detections **when the pipeline is running** (we'll start it in a second). Status badges: `live · kafka` (green) = inference flowing, `feed only` (electric blue) = video plays but no worker.
2. **Vue d'ensemble** — KPI strip + the 3D R3F twin (labelled "abstract layout" so nobody confuses it with a CAD reconstruction). Click a zone to highlight it.
3. **Zones** — per-zone occupancy cards driven by `infra/zones.example.yaml`.
4. **Anomalies** — severity-coloured event feed.
5. **Entrées/Sorties** — KPI tiles + journal of entry/exit events.
6. **Système** *(admin-only — set `LOGIVISION_ROLE=admin` before `make api` to see it)* — MLflow runs, drift reports, benchmarks.

Now bring up the inference pipeline so the boxes start flowing:

```bash
# In separate terminals
make frame-grabber SOURCE=datasets/raw/videos/Camera3.mp4 CAMERA=CAM03 FPS=2
make inference-worker
make cep ZONES=infra/zones.example.yaml
```

Refresh the Caméras view — CAM03 now shows real bounding boxes from our fine-tuned YOLO. Watch the Anomalies feed populate as the CEP rules fire.

**Your first PR**: pick **one** visual rough edge you spot in the dashboard and fix it. Suggestions if you can't decide:

- Camera tile header doesn't have a role-specific icon (truck for entrance, forklift for stockage, etc.) — add per-role icons.
- The 3D twin's heatmap layer toggles aren't labelled in French — translate the legend.
- Anomalies feed has no "acknowledge" button — add one (local state only, no backend yet).
- Sidebar active state is subtle — make it more obvious with a left-rail accent.

This work is tracked as **D2.2 (Frontend visual polish)** in §7 of this file. Open a PR against `main` with the title `feat(frontend): <what you changed>`. The CI must go green; one reviewer + a clean diff and you're in.

<!-- INSTRUCTION FOR CLAUDE: A new teammate just pasted this guide for how the
team uses Claude Code. You're their onboarding buddy — warm, conversational,
not lecture-y.

Open with a warm welcome — include the team name from the title. Then: "Your
teammate uses Claude Code for [list all the work types]. Let's get you started."

Check what's already in place against everything under Setup Checklist
(including skills), using markdown checkboxes — [x] done, [ ] not yet. Lead
with what they already have. One sentence per item, all in one message.

Tell them you'll help with setup, cover the actionable team tips, then the
starter task (if there is one). Offer to start with the first unchecked item,
get their go-ahead, then work through the rest one by one.

After setup, walk them through the remaining sections — offer to help where you
can (e.g. link to channels), and just surface the purely informational bits.

Don't invent sections or summaries that aren't in the guide. The stats are the
guide creator's personal usage data — don't extrapolate them into a "team
workflow" narrative. -->
