# ADR 0003 — Model promotion process

- **Status**: Accepted
- **Date**: 2026-05-20
- **Deciders**: Ayalem (project owner)
- **Tags**: mlops, mlflow, registry, ml-deployment

## Context

`ml/scripts/train.py` already registers every successful training run in MLflow under the model name `logivision-detector` (stage `None`). We need a controlled way to advance a version through `Staging` and `Production` without manual clicks in the MLflow UI, while remaining safe enough for an academic project where a single developer plays every role (engineer, reviewer, ops).

Two failure modes to avoid:

1. **Silent regressions** — auto-promote everything, push a worse model than the current Production.
2. **Bottleneck on a human** — require N approvals for each step, never ship.

## Decision

A **two-gate threshold-based promotion**, implemented in `ml/scripts/promote_model.py`:

| Transition | Trigger | Gate |
|---|---|---|
| `None → Staging` | `make promote RUN=<id>` | all `staging_thresholds` met |
| `Staging → Production` | `make promote-prod RUN=<id>` (i.e. `--approve`) | all `production_thresholds` met **and** explicit `--approve` flag |
| `None → Production` | (refused) | a model must be observed in Staging at least once |
| `<target> → <target>` | re-run | no-op, exit 0 |

The promotion to `Production` archives the previously-Production version automatically (via MLflow's `archive_existing_versions=True`).

Thresholds live in `ml/configs/promotion_thresholds.yaml` and are versioned alongside the code:

```yaml
policy_version: 1
staging_thresholds:
  val_map50: 0.65
  val_map50_95: 0.40
  val_precision: 0.60
  val_recall: 0.60
production_thresholds:
  val_map50: 0.75
  val_map50_95: 0.50
  val_precision: 0.70
  val_recall: 0.70
```

Tightening or loosening these values is a policy change: bump `policy_version` and record it in a follow-up ADR.

## Consequences

**Positive**
- One source of truth for what "good enough to ship" means.
- Reproducible: any run can be re-evaluated against the same thresholds at any time.
- Safe by default: `--approve` is a human acknowledgement.

**Negative**
- The thresholds are validation-only — they don't catch drift, fairness, or latency regressions. Those need separate gates (Sprint 1.7 drift; Sprint 1.4 T1.4.3 benchmark).
- For the first model ever (no Production exists), `Staging → Production` still requires the production thresholds. Bootstrapping requires the first model to clear them, or temporarily lower them via a `policy_version` bump.

## Alternatives considered

1. **Always-auto promote** — rejected: removes any human checkpoint, dangerous when thresholds are wrong.
2. **Manual UI clicks only** — rejected: doesn't survive a multi-machine workflow (Colab trains, laptop promotes).
3. **PR-based promotion** (open a PR that calls the API on merge) — overkill for a solo project, deferred to Phase 5 CI/CD.

## References

- [`ml/scripts/promote_model.py`](../../../ml/scripts/promote_model.py)
- [`ml/configs/promotion_thresholds.yaml`](../../../ml/configs/promotion_thresholds.yaml)
- [MLflow Model Registry stages](https://mlflow.org/docs/latest/model-registry.html#transitioning-an-mlflow-models-stage)
