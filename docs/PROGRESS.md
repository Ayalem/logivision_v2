# PROGRESS

Lightweight, append-only status log. The authoritative plan is `CLAUDE.md`.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

---

## Phase 1 — MLOps Computer Vision

### Sprint 1.1 — Bootstrap MLOps Stack

- [x] **T1.1.1** Init repo + outillage — merged to `develop` (and `main`).
- [x] **T1.1.2** Stack MLOps locale (Postgres + MinIO + MLflow) — merged to `develop`.
  - Acceptance: `./scripts/bootstrap.sh` = **13 s** (target < 90 s); 4/4 smoke tests green; containers prefixed `logivision-mlops-*` to coexist with the prior v4 stack (stopped, volumes preserved); MLflow port configurable via `MLFLOW_PORT` (default 5050 to avoid macOS ControlCenter on :5000).
- [x] **T1.1.3** DVC + MinIO remote — merged to `develop`. `make dvc-{push,pull,status}` + `docs/mlops/dvc-guide.md`.

**Sprint 1.1 — closed ✅**

### Sprint 1.2 — Pipeline Données

- [x] **T1.2.1** Frame extraction (`ml/scripts/extract_frames.py`) — merged to `develop`.
- [x] **T1.2.2** CVAT stack + YOLO export importer — merged to `develop`. Manual annotation step deferred until real videos exist.
- [x] **T1.2.3** DVC pipeline — merged to `develop`.

**Sprint 1.2 — closed ✅** (manual CVAT annotation deferred until raw videos exist; structure ready).

### Sprint 1.3 — Training + MLflow

- [x] **T1.3.1** Training script + MLflow tracking — merged to `main`. 7/7 mocked tests.
- [x] **T1.3.2** Integration training test — merged to `main`. 15s end-to-end real run.
- [x] **T1.3.3** Colab/Kaggle training doc + notebook template — merged to `main`.

**Sprint 1.3 — closed ✅**

### Sprint 1.4 — Registry + Promotion + OpenVINO

- [x] **T1.4.1** Promotion script + ADR 0003 — `ml/scripts/promote_model.py` (9/9 mocked tests).
- [x] **T1.4.2** OpenVINO FP32 + INT8 (NNCF) export — `ml/scripts/export_openvino.py` (9/9 mocked tests). Adds `openvino` + `nncf` to `ml` deps.
- [x] **T1.4.3** Inference benchmark + Markdown report — `ml/scripts/benchmark_inference.py` (7/7 mocked tests). Reports under `docs/mlops/benchmarks/`.

**Sprint 1.4 — closed ✅** (a real bench requires a fully-exported run; the user's existing T1.3.2 run only has PyTorch weights — re-run `make export-openvino RUN=<id>` first, then `make benchmark RUN=<id>`).

### Sprint 1.5 — Multi-architecture comparison

- [~] **T1.5.1 (partial)** Multi-arch sweep — `ml/scripts/compare_archs.py` + `ml/configs/comparison.yaml`. Trains YOLOv8n / YOLOv11n / RT-DETR-l on the same dataset with shared hyperparams + augmentation (mosaic, mixup, HSV, flips, rotation), logs each to MLflow with a `comparison_group` tag, writes Markdown + JSON report under `docs/mlops/comparisons/`. 5/5 mocked tests. Run with `make compare-archs`.
- [ ] **T1.5.2** Optuna hyperparam search (deferred — Ray of diminishing returns on synthetic data).
- [ ] **T1.5.3** Final comparison report once `make compare-archs` has actually run on the demo dataset (`make demo-data` first).
- _Bonus_ — **Real-data sourcing** : `scripts/fetch_pexels_videos.py` uses the Pexels free API (CC0 license) to fetch warehouse videos legally; no scraping. `make fetch-videos` (needs `PEXELS_API_KEY` from <https://www.pexels.com/api/>). Also identified TalTech synthetic warehouse dataset (MIT, 4 records on data.taltech.ee, ~10 GB) and DataDryad 6D-ViCuT (CC0, cuboid tracking) — gated by user's wifi.

### Sprint 1.6 — Serving (BentoML)

- [x] **T1.6** Done. BentoML service serves at :3000 (yolov8n.pt fallback à défaut de Production), load test stdlib, premier rapport sous `docs/mlops/benchmarks/load_*.md`.

### Sprint 1.7 — Drift monitoring

- [x] **T1.7.1** Drift detection — `ml/scripts/drift_monitor.py`. Compare deux snapshots de features (CSV/Parquet, schéma `brightness/contrast/n_detections/avg_confidence`) via Evidently DataDriftPreset (PSI). Fallback `_fallback_psi` en numpy pur si Evidently absent. Produit HTML + JSON sous `docs/mlops/drift/`.
- [x] **T1.7.2** Metrics — `render_prometheus()` sort un format scrapeable (`logivision_drift_score{feature="..."}` + `logivision_drift_detected`). Exit code 1 si drift détecté → utilisable dans un cron / CI step.
- [ ] **T1.7.3** Retraining trigger via GitHub Actions (reporté en Phase 5).
- _Bonus_ — `scripts/fetch_kaggle.py` + `make fetch-kaggle DATASET=...` pour télécharger tout dataset Kaggle annoté (besoin de `KAGGLE_USERNAME` + `KAGGLE_KEY` dans `.env`).

**Original delivery (placeholder)**:

- [~] **T1.6.1 + T1.6.2 + T1.6.3** Bundled in a single delivery on `main`.
  - Files: `services/model_server/{service.py,bentofile.yaml,Dockerfile,tests/test_service.py}`, `tests/load/load_test.py`, `Makefile` (`serve`, `serve-build`, `load-test`).
  - Tech: BentoML 1.3 service that resolves the model at boot via `MlflowClient.search_model_versions` (Production → Staging → local fallback `yolov8n.pt`). Pydantic v2 response schema (`Detection`, `InferenceResponse`). Pure-stdlib load tester (no `k6` install) measuring p50/p95/p99 latency + RPS at concurrency levels 1/5/10.
  - Acceptance: 9/9 mocked unit tests on the resolver. The Bento builds (`make serve-build`) and serves locally (`make serve`).

### Sprint 1.5 — Model comparison

- [ ] T1.5.1 Multi-arch training (YOLOv8n, YOLOv11n, RT-DETR, optional YOLOv10n).
- [ ] T1.5.2 Optuna hyperparam search.
- [ ] T1.5.3 Comparison report.

### Sprint 1.6 — Serving (BentoML)

- [ ] T1.6.1 BentoML service.
- [ ] T1.6.2 k6 load tests.
- [ ] T1.6.3 Containerize + Helm chart.

### Sprint 1.7 — Drift + Retraining

- [ ] T1.7.1 Evidently drift job.
- [ ] T1.7.2 Alerting.
- [ ] T1.7.3 Retraining workflow.

---

## Phase 2 — Streaming (Kafka + Flink)
_Not started — blocked on Phase 1 DoD._

## Phase 3 — Feature Store (Feast)
_Not started._

## Phase 4 — Advanced serving / monitoring / A/B
_Not started._

## Phase 5 — Infra / observability / CI/CD
_Not started (may start in parallel from Sprint 1.4)._

## Frontend track (web dashboard) — _planning pending_

CLAUDE.md defines the stack (`§3.5`: React + Vite + Tailwind + TanStack Query + Recharts) and shows the dashboard in the architecture (`§2.1`), but does **not** plan it as numbered sprints. The dashboard is implicitly required from Sprint 1.4 (`benchmark charts`) and explicitly from Sprint 1.7 (`Evidently report viewer`).

A follow-up PR `docs(claude): add frontend sprints` will add an F-series of sprints to CLAUDE.md (proposed: F.1 scaffold, F.2 detection viewer, F.3 model perf dashboard, F.4 drift / alerts).

---

## Blockers / decisions log

- `2026-05-19` — Frontend not planned as explicit sprints in CLAUDE.md. To be addressed in a dedicated `docs(claude)` PR after T1.1.1 merges.
