# PROGRESS

Lightweight, append-only status log. The authoritative plan is `PROJECT_PLAN.md`.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

---

## Phase 1 — MLOps Computer Vision

### Sprint 1.1 — Bootstrap MLOps Stack

- [~] **T1.1.1** Init repo + outillage (PR opened on `feature/T1.1.1-init-tooling`)
  - Files: `pyproject.toml`, `.pre-commit-config.yaml`, `Makefile`, `.gitignore`, `.dockerignore`, `.env.example`, `README.md`, `CONTRIBUTING.md`, `LICENSE`, `NOTICE.md`, `.github/pull_request_template.md`, `docs/PROGRESS.md`.
  - Acceptance: `make install` < 60 s; `make lint` green on empty tree; `pre-commit run --all-files` green; README < 200 words.
- [ ] **T1.1.2** Stack MLOps locale (Postgres + MinIO + MLflow) via Docker Compose, `scripts/bootstrap.sh`, smoke test.
- [ ] **T1.1.3** Setup DVC + MinIO remote + `docs/mlops/dvc-guide.md`.

### Sprint 1.2 — Pipeline Données

- [ ] T1.2.1 Frame extraction script + tests.
- [ ] T1.2.2 CVAT self-hosted + import pipeline + `data.yaml` generator.
- [ ] T1.2.3 DVC pipeline.

### Sprint 1.3 — Training + MLflow

- [ ] T1.3.1 `ml/scripts/train.py` + config.
- [ ] T1.3.2 Tests.
- [ ] T1.3.3 Colab training guide.

### Sprint 1.4 — Registry + Promotion + OpenVINO

- [ ] T1.4.1 Promotion script + thresholds.
- [ ] T1.4.2 OpenVINO export (FP32 + INT8 NNCF).
- [ ] T1.4.3 Benchmark script + report.

### Sprint 1.5 — Model comparison

- [ ] T1.5.1 Mul1ti-arch training (YOLOv8n, YOLOv11n, RT-DETR, optional YOLOv10n).
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

---

## Blockers / decisions log

_None._
