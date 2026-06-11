# LOGIVISION

Production-grade intelligent warehouse surveillance built on Computer Vision (YOLO + ByteTrack) and a fully open-source MLOps stack (MLflow, DVC, Kafka, Flink, Feast, BentoML, K3s).

The full execution plan — phases, sprints, acceptance criteria, technology choices — lives in [`PROJECT_PLAN.md`](PROJECT_PLAN.md). Read it before contributing.

## Current status

Phase 1 complete — YOLO+ByteTrack detector (retrain on clean split: run notebook 00), LSTM congestion forecaster on Parking Birmingham occupancy data, real-time Kafka CEP pipeline, and live React dashboard.
Read [`ONBOARDING.md`](ONBOARDING.md) for the full technical reference and setup guide.

## Constraints

- **Budget: 0 €.** Self-hosted, OSS only. No paid SaaS.
- **GPU: free tiers only** (Colab / Kaggle) for training; CPU + OpenVINO for serving.
- **Reproducible**: every training run is replayable from a single Git commit (data + code + config).

## Quickstart

Requires Python 3.11, Docker, and [uv](https://docs.astral.sh/uv/).

```bash
make bootstrap   # boot the MLOps stack (Kafka + MinIO + MLflow + Postgres)
make demo        # start API + frame grabber + inference worker + CEP in one shot
# Dashboard → http://localhost:8000  (admin view)
# MLflow    → http://localhost:5050
# Kafka UI  → http://localhost:8086
make demo-stop   # tear everything down
```

Run `make help` for the full list of targets.

## Layout

See the monorepo structure and architecture in [`ONBOARDING.md`](ONBOARDING.md).

## License

MIT — see [`LICENSE`](LICENSE). Third-party components and license implications (notably Ultralytics AGPL-3.0) are documented in [`NOTICE.md`](NOTICE.md).
