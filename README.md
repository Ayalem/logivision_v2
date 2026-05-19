# LOGIVISION

Production-grade intelligent warehouse surveillance built on Computer Vision (YOLO + ByteTrack) and a fully open-source MLOps stack (MLflow, DVC, Kafka, Flink, Feast, BentoML, K3s).

The full execution plan — phases, sprints, acceptance criteria, technology choices — lives in [`CLAUDE.md`](CLAUDE.md). Read it before contributing.

## Current status

Phase 1 (MLOps Computer Vision) — **Sprint 1.1 in progress**. See [`docs/PROGRESS.md`](docs/PROGRESS.md).

## Constraints

- **Budget: 0 €.** Self-hosted, OSS only. No paid SaaS.
- **GPU: free tiers only** (Colab / Kaggle) for training; CPU + OpenVINO for serving.
- **Reproducible**: every training run is replayable from a single Git commit (data + code + config).

## Quickstart

Requires Python 3.11, Docker, and [uv](https://docs.astral.sh/uv/).

```bash
make install              # install Python dev deps
make pre-commit-install   # install Git hooks
make lint                 # ruff + mypy
make test                 # pytest
make up                   # start MLOps stack (after Sprint 1.1.2)
```

Run `make help` for the full list of targets.

## Layout

See the monorepo structure in [`CLAUDE.md` §4](CLAUDE.md). Directories appear as their corresponding sprint lands; the repo is intentionally minimal until then.

## License

MIT — see [`LICENSE`](LICENSE). Third-party components and license implications (notably Ultralytics AGPL-3.0) are documented in [`NOTICE.md`](NOTICE.md).
