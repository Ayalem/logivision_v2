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

- [~] **T1.3.1** Training script + config on `feature/T1.3.1-train-script`.
  - Files: `ml/scripts/train.py`, `ml/configs/yolov8n.yaml`, `ml/tests/test_train.py`, `scripts/gen_synthetic_demo.py`, `Makefile` (`demo-data`, `train`).
  - Tech: Ultralytics 8.4.x (`YOLO(...).train(...)`), MLflow 2.17 client (params + tags + metrics + artifacts + Registry), `dataset_fingerprint` = sha256 of `data.yaml` + every label file (cheap reproducibility tag). Heavy unit tests are mocked (no real `torch` load), an integration test on a tiny synthetic dataset is gated by `-m integration`.
  - Acceptance: 7/7 mocked tests pass; `scripts/gen_synthetic_demo.py` → `ml.scripts.import_annotations` round-trip produces a 30-frame YOLO dataset in <2 s; real `make train` deferred to user (full epoch on CPU = ~2-3 min, MLflow logs visible at http://localhost:5050).
- [~] **T1.3.2** Integration training test on `feature/T1.3.2-train-integration`.
  - Files: `ml/tests/test_train_integration.py` (gen → import → train → MLflow client verify), `ml/scripts/train.py` (added `_sanitize_metric_name` for MLflow's `[A-Za-z0-9_\-./ ]` allow-list), `pyproject.toml` (`boto3` added to `ml` group for MLflow → MinIO artifact upload).
  - Acceptance: 1 integration test passes in **~15 s** running a real YOLOv8n from-scratch 1-epoch training (imgsz=128, batch=2, 20 synthetic frames). Verifies `status=FINISHED`, params logged, all 6 required tags present, all 4 val metrics present.
- [ ] T1.3.3 Colab/Kaggle training doc.

### Sprint 1.3 — Training + MLflow

- [ ] T1.3.1 `ml/scripts/train.py` + config.
- [ ] T1.3.2 Tests.
- [ ] T1.3.3 Colab training guide.

### Sprint 1.4 — Registry + Promotion + OpenVINO

- [ ] T1.4.1 Promotion script + thresholds.
- [ ] T1.4.2 OpenVINO export (FP32 + INT8 NNCF).
- [ ] T1.4.3 Benchmark script + report.

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
