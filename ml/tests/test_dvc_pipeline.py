"""Static tests for the DVC pipeline (`dvc.yaml`).

These tests do NOT run the pipeline (that would require real videos /
annotations / a MinIO remote). They verify the YAML is well-formed,
references existing scripts and params, and that `dvc dag` succeeds —
which is enough to catch typos and stage-graph regressions in CI.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DVC_YAML = REPO_ROOT / "dvc.yaml"
PARAMS_YAML = REPO_ROOT / "ml" / "configs" / "data.yaml"


@pytest.fixture(scope="module")
def pipeline() -> dict:
    return yaml.safe_load(DVC_YAML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def params() -> dict:
    return yaml.safe_load(PARAMS_YAML.read_text(encoding="utf-8"))


def test_pipeline_has_expected_stages(pipeline: dict) -> None:
    assert set(pipeline["stages"]) == {"extract_frames", "prepare_dataset"}


def test_every_dep_path_exists_or_is_data(pipeline: dict) -> None:
    """Code deps must exist on disk; data deps may not exist yet (provided by user)."""
    code_dirs = {"ml/"}
    for stage_name, stage in pipeline["stages"].items():
        for dep in stage.get("deps", []):
            if any(dep.startswith(d) for d in code_dirs):
                assert (REPO_ROOT / dep).exists(), f"{stage_name}: missing code dep {dep}"


def test_every_param_path_exists(pipeline: dict, params: dict) -> None:
    """Every params: entry must point to a key that exists in ml/configs/data.yaml."""
    for stage_name, stage in pipeline["stages"].items():
        for entry in stage.get("params", []):
            for _file, keys in entry.items():
                for key in keys:
                    cursor: object = params
                    for part in key.split("."):
                        assert isinstance(
                            cursor, dict
                        ), f"{stage_name}: param {key} traverses non-dict at {part!r}"
                        assert part in cursor, f"{stage_name}: missing param {key}"
                        cursor = cursor[part]


def test_prepare_dataset_depends_on_extract_frames_output(pipeline: dict) -> None:
    """The graph must be connected: prepare_dataset reads what extract_frames wrote."""
    extract_outs = set(pipeline["stages"]["extract_frames"]["outs"])
    prepare_deps = set(pipeline["stages"]["prepare_dataset"]["deps"])
    assert extract_outs & prepare_deps, "prepare_dataset must depend on an extract_frames output"


def test_split_ratios_sum_to_one(params: dict) -> None:
    split = params["prepare_dataset"]["split"]
    total = split["train"] + split["val"] + split["test"]
    assert abs(total - 1.0) < 1e-6, f"split ratios must sum to 1.0, got {total}"


def test_dvc_dag_renders() -> None:
    """`dvc dag` parses the file and prints the graph — final smoke test."""
    result = subprocess.run(
        ["dvc", "dag", "--full"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert (
        result.returncode == 0
    ), f"dvc dag failed:\nSTDOUT:{result.stdout}\nSTDERR:{result.stderr}"
    # Both stage names must appear in the rendered graph.
    assert "extract_frames" in result.stdout
    assert "prepare_dataset" in result.stdout
