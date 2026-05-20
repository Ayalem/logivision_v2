"""Unit tests for ml.scripts.benchmark_inference (no real inference)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ml.scripts.benchmark_inference import (
    BenchmarkReport,
    VariantResult,
    _percentile,
    render_markdown,
    summarise,
)


def test_percentile_basics() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert _percentile(values, 0) == 10.0
    assert _percentile(values, 50) == 30.0
    assert _percentile(values, 100) == 50.0


def test_percentile_unsorted_input() -> None:
    values = [40, 10, 50, 20, 30]
    assert _percentile(values, 50) == 30


def test_percentile_empty_raises() -> None:
    with pytest.raises(ValueError):
        _percentile([], 50)


def test_summarise_computes_fps_and_quantiles() -> None:
    latencies = [10.0] * 10  # 10 ms x 10 inferences = 100 ms = 0.1 s -> 100 fps
    result = summarise(latencies, peak_rss_mb=512.0, avg_cpu=80.0, name="PyTorch")
    assert result.name == "PyTorch"
    assert result.n_inferences == 10
    assert result.p50_ms == 10.0
    assert result.p95_ms == 10.0
    assert result.p99_ms == 10.0
    assert result.fps == pytest.approx(100.0, rel=1e-3)
    assert result.peak_rss_mb == 512.0
    assert result.avg_cpu_percent == 80.0


def test_render_markdown_includes_table_and_speedup() -> None:
    report = BenchmarkReport(
        run_id="abc123",
        imgsz=320,
        n=50,
        cpu_model="Apple M3",
        variants=[
            VariantResult("PyTorch", 50, 30.0, 35.0, 40.0, 33.3, 500.0, 70.0),
            VariantResult("OpenVINO FP32", 50, 10.0, 12.0, 15.0, 100.0, 350.0, 60.0),
            VariantResult("OpenVINO INT8", 50, 6.0, 8.0, 10.0, 166.7, 300.0, 55.0),
        ],
    )
    md = render_markdown(report)
    assert "Run id: `abc123`" in md
    assert "imgsz: 320" in md
    assert "Apple M3" in md
    assert "PyTorch" in md and "OpenVINO FP32" in md and "OpenVINO INT8" in md
    # Speedup lines must be present and numerically right (FPS 100/33.3 ≈ 3.0; 166.7/33.3 ≈ 5.0).
    assert "Speedup OpenVINO FP32 vs PyTorch: **×3.00**" in md
    assert "Speedup OpenVINO INT8 vs PyTorch: **×5.01**" in md


def test_render_markdown_skips_speedup_without_baseline() -> None:
    """If PyTorch is absent, no speedup line."""
    report = BenchmarkReport(
        run_id="x",
        imgsz=320,
        n=10,
        cpu_model="cpu",
        variants=[VariantResult("OpenVINO FP32", 10, 10.0, 11.0, 12.0, 100.0, 400.0, 50.0)],
    )
    md = render_markdown(report)
    assert "Speedup" not in md


def test_pick_val_images_recycles_when_n_exceeds_pool(tmp_path: Path) -> None:
    from ml.scripts.benchmark_inference import _pick_val_images

    root = tmp_path / "ds"
    val_dir = root / "images" / "val"
    val_dir.mkdir(parents=True)
    for i in range(3):
        (val_dir / f"img_{i}.jpg").write_bytes(b"\xff\xd8FAKE")
    data_yaml = root / "data.yaml"
    import yaml

    data_yaml.write_text(
        yaml.safe_dump(
            {"path": str(root), "train": "images/val", "val": "images/val", "nc": 1, "names": ["x"]}
        )
    )
    picked = _pick_val_images(data_yaml, n=10)
    assert len(picked) == 10  # 3 source × 4 recycle, capped to 10
