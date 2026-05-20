"""Unit tests for ml.scripts.compare_archs — training is fully mocked."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ml.scripts.compare_archs import (
    ArchResult,
    _build_train_config,
    _train_one,
    render_markdown,
    run_comparison,
)

COMPARISON_CFG = {
    "mlflow": {"tracking_uri": "http://localhost:5050", "experiment": "warehouse-arch-comparison"},
    "data": {"yaml_path": "datasets/processed/demo/data.yaml"},
    "shared_hyperparameters": {
        "epochs": 5,
        "imgsz": 320,
        "batch": 4,
        "patience": 2,
        "optimizer": "AdamW",
        "lr0": 0.001,
        "seed": 42,
    },
    "architectures": {
        "yolov8n": {"weights": "yolov8n.yaml"},
        "yolov11n": {"weights": "yolo11n.yaml"},
    },
    "runtime": {"device": "cpu", "output_dir": "/tmp/runs", "dry_register": True},
}


def test_build_train_config_picks_per_arch_weights_and_model_name() -> None:
    cfg = _build_train_config(COMPARISON_CFG, "yolov11n", "yolo11n.yaml")
    assert cfg["model"]["arch"] == "yolov11n"
    assert cfg["model"]["weights"] == "yolo11n.yaml"
    assert cfg["mlflow"]["registered_model_name"] == "logivision-detector-yolov11n"
    # hyperparameters are a copy (mutations shouldn't leak back into COMPARISON_CFG)
    cfg["hyperparameters"]["epochs"] = 999
    assert COMPARISON_CFG["shared_hyperparameters"]["epochs"] == 5


def test_train_one_records_metrics_on_success() -> None:
    fake_train_result = MagicMock(run_id="RUN-42", map50=0.81, map50_95=0.55)
    with (
        patch("ml.scripts.train.train", return_value=fake_train_result),
        patch("mlflow.set_tracking_uri"),
        patch("mlflow.tracking.MlflowClient"),
    ):
        result = _train_one("yolov8n", "yolov8n.yaml", COMPARISON_CFG, tag="t1")
    assert isinstance(result, ArchResult)
    assert result.name == "yolov8n"
    assert result.run_id == "RUN-42"
    assert result.map50 == 0.81
    assert result.failed_reason is None


def test_train_one_captures_failures_without_raising() -> None:
    with (
        patch("ml.scripts.train.train", side_effect=RuntimeError("CUDA OOM")),
        patch("mlflow.set_tracking_uri"),
    ):
        result = _train_one("rtdetr_l", "rtdetr-l.yaml", COMPARISON_CFG, tag="t1")
    assert result.failed_reason == "CUDA OOM"
    assert result.map50 == 0.0
    assert result.run_id == ""


def test_render_markdown_sorts_by_map50_descending() -> None:
    results = [
        ArchResult("a", "a.yaml", "r-a", map50=0.50, map50_95=0.30, train_seconds=10.0),
        ArchResult("b", "b.yaml", "r-b", map50=0.80, map50_95=0.55, train_seconds=12.0),
        ArchResult(
            "c", "c.yaml", "", map50=0.0, map50_95=0.0, train_seconds=1.0, failed_reason="boom"
        ),
    ]
    md = render_markdown(results, COMPARISON_CFG, tag="t1")
    # Data rows start with `| <arch>` where <arch> doesn't begin with a hyphen.
    rows = [
        line
        for line in md.splitlines()
        if line.startswith("| ") and not line.startswith("| Architecture")
    ]
    assert rows[0].startswith("| b ")
    assert rows[1].startswith("| a ")
    assert rows[2].startswith("| c ")
    assert "Winner" in md
    assert "make promote RUN=r-b" in md
    assert "boom" in md


def test_run_comparison_writes_md_and_json(tmp_path: Path) -> None:
    fake_results = {
        "yolov8n": ArchResult("yolov8n", "yolov8n.yaml", "RUN-A", 0.70, 0.45, 12.0),
        "yolov11n": ArchResult("yolov11n", "yolo11n.yaml", "RUN-B", 0.80, 0.55, 15.0),
    }

    def _fake_train_one(name: str, _weights: str, _cfg: dict, _tag: str) -> ArchResult:
        return fake_results[name]

    with patch("ml.scripts.compare_archs._train_one", side_effect=_fake_train_one):
        out = run_comparison(COMPARISON_CFG, report_dir=tmp_path)
    assert out.is_file()
    assert out.suffix == ".md"
    assert out.with_suffix(".json").is_file()
    md = out.read_text()
    assert "yolov8n" in md and "yolov11n" in md
    assert "Winner" in md
