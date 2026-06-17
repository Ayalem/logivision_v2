# LOGIVISION

Real-time warehouse computer-vision platform: video → Kafka → YOLO + ByteTrack → QR → CEP → live operator dashboard. Built on an open-source MLOps stack (MLflow, DVC, Kafka; Flink/Feast/BentoML/K3s are documented upgrade paths).

**📖 Everything is in one document: [`ONBOARDING.md`](ONBOARDING.md)** — architecture, data flow, the models, roadmap, contribution workflow, and licenses. Read it before contributing.

## Quickstart

Requires Python 3.11, Docker, and [uv](https://docs.astral.sh/uv/).

```bash
make bootstrap   # MLOps stack (Kafka + MinIO + MLflow + Postgres)
make demo        # API + frame grabber + inference worker + CEP
# Dashboard → http://localhost:8000   MLflow → http://localhost:5050   Kafka UI → http://localhost:8086
make demo-stop   # tear down
```

Run `make help` for all targets.

## Constraints

- **Budget 0 €** — self-hosted OSS only, no paid SaaS.
- **GPU**: free tiers only (Colab / Kaggle) for training; CPU + OpenVINO for serving.
- **Reproducible**: every training run is replayable from a single Git commit (data + code + config).

## License

MIT — see [`LICENSE`](LICENSE). Third-party license implications (notably Ultralytics AGPL-3.0) are documented in [`ONBOARDING.md`](ONBOARDING.md#licenses--third-party-notices).
