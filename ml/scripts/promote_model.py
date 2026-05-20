"""Promote an MLflow model version through Registry stages.

Reads thresholds from `ml/configs/promotion_thresholds.yaml`, queries MLflow
for the run's metrics, finds the model version that points at that run, and
conditionally transitions its stage.

Promotion rules:
- None -> Staging          : automatic if every staging threshold is met.
- Staging -> Production    : requires `--approve` on the CLI AND every
                             production threshold is met.
- None -> Production       : refused (must go through Staging).
- Already in target stage  : idempotent, exit 0 with a "no-op" message.
- Promoting to Production  : the previous Production version is archived.

Usage:
    python -m ml.scripts.promote_model --run-id <RUN_ID>
    python -m ml.scripts.promote_model --run-id <RUN_ID> --approve
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)

STAGE_NONE = "None"
STAGE_STAGING = "Staging"
STAGE_PRODUCTION = "Production"
STAGE_ARCHIVED = "Archived"


class PromotionError(Exception):
    """Raised when the requested promotion cannot proceed."""


@dataclass
class PromotionResult:
    run_id: str
    model_name: str
    version: str
    previous_stage: str
    new_stage: str
    promoted: bool  # False when no-op (already at the target stage)


def _load_thresholds(path: Path) -> dict[str, dict[str, float]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        "staging": dict(raw["staging_thresholds"]),
        "production": dict(raw["production_thresholds"]),
    }


def _check_metrics(metrics: dict[str, float], gates: dict[str, float]) -> list[str]:
    """Return the list of metric names that did NOT meet their gate."""
    failures = []
    for name, threshold in gates.items():
        value = metrics.get(name)
        if value is None:
            failures.append(f"{name} (missing)")
        elif value < threshold:
            failures.append(f"{name} ({value:.4f} < {threshold:.4f})")
    return failures


def _find_version_for_run(client: MlflowClient, model_name: str, run_id: str) -> object:
    """Return the ModelVersion whose `run_id` matches, or raise PromotionError."""
    versions = client.search_model_versions(f"name='{model_name}'")
    for mv in versions:
        if mv.run_id == run_id:
            return mv
    raise PromotionError(
        f"No version of '{model_name}' is bound to run {run_id}. "
        "Train the model with `dry_register: false` first."
    )


def promote(
    run_id: str,
    model_name: str,
    thresholds_path: Path,
    approve: bool = False,
    tracking_uri: str | None = None,
) -> PromotionResult:
    """Drive one promotion step. Returns what happened, raises on policy refusal."""
    # Import locally so `--help` doesn't pull in MLflow / boto3.
    import mlflow
    from mlflow.tracking import MlflowClient

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    run = client.get_run(run_id)
    metrics = dict(run.data.metrics)
    thresholds = _load_thresholds(thresholds_path)

    version = _find_version_for_run(client, model_name, run_id)
    current_stage: str = version.current_stage

    # Decide the target stage from the current one + the --approve flag.
    if current_stage == STAGE_NONE:
        target_stage = STAGE_STAGING
        gates = thresholds["staging"]
    elif current_stage == STAGE_STAGING:
        if not approve:
            return PromotionResult(
                run_id=run_id,
                model_name=model_name,
                version=str(version.version),
                previous_stage=current_stage,
                new_stage=current_stage,
                promoted=False,
            )
        target_stage = STAGE_PRODUCTION
        gates = thresholds["production"]
    elif current_stage == STAGE_PRODUCTION:
        # Idempotent: already in Production.
        return PromotionResult(
            run_id=run_id,
            model_name=model_name,
            version=str(version.version),
            previous_stage=current_stage,
            new_stage=current_stage,
            promoted=False,
        )
    else:
        raise PromotionError(
            f"Unsupported source stage {current_stage!r} for version {version.version}."
        )

    failures = _check_metrics(metrics, gates)
    if failures:
        raise PromotionError(
            f"Cannot transition {model_name} v{version.version} "
            f"{current_stage} -> {target_stage}: " + "; ".join(failures)
        )

    archive_existing = target_stage == STAGE_PRODUCTION
    client.transition_model_version_stage(
        name=model_name,
        version=version.version,
        stage=target_stage,
        archive_existing_versions=archive_existing,
    )
    return PromotionResult(
        run_id=run_id,
        model_name=model_name,
        version=str(version.version),
        previous_stage=current_stage,
        new_stage=target_stage,
        promoted=True,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-id", required=True, help="The MLflow run to promote.")
    parser.add_argument(
        "--model-name",
        default="logivision-detector",
        help="Registered model name (default: logivision-detector).",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path("ml/configs/promotion_thresholds.yaml"),
        help="Path to the thresholds YAML.",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Required to transition Staging -> Production.",
    )
    parser.add_argument(
        "--tracking-uri",
        default=None,
        help="Override MLFLOW_TRACKING_URI (else read from env / default).",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    try:
        result = promote(
            run_id=args.run_id,
            model_name=args.model_name,
            thresholds_path=args.thresholds,
            approve=args.approve,
            tracking_uri=args.tracking_uri,
        )
    except PromotionError as exc:
        logger.error("%s", exc)
        return 1
    if result.promoted:
        logger.info(
            "%s v%s : %s -> %s",
            result.model_name,
            result.version,
            result.previous_stage,
            result.new_stage,
        )
    else:
        logger.info(
            "%s v%s : already %s (no-op).  Pass --approve to advance further.",
            result.model_name,
            result.version,
            result.previous_stage,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
