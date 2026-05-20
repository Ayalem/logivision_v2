"""Tests for ml.scripts.import_annotations."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from ml.scripts.import_annotations import import_export

CLASSES = ["box", "person", "forklift"]


def _make_fake_export(tmp_path: Path, n_images: int = 10, n_unlabelled: int = 0) -> Path:
    """Create a fake CVAT YOLO export zip with `n_images` (image, label) pairs.

    The last `n_unlabelled` images get no .txt file (image with zero objects).
    """
    work = tmp_path / "fake_export"
    obj_dir = work / "obj_train_data"
    obj_dir.mkdir(parents=True)

    rng = np.random.default_rng(0)
    for i in range(n_images):
        img = np.full((240, 320, 3), rng.integers(0, 255, 3), dtype=np.uint8)
        img_path = obj_dir / f"frame_{i:03d}.jpg"
        cv2.imwrite(str(img_path), img)
        if i < n_images - n_unlabelled:
            # one bbox of class 0 ('box') and one of class 1 ('person'), normalised cxcywh.
            label_path = obj_dir / f"frame_{i:03d}.txt"
            label_path.write_text(
                "0 0.50 0.50 0.30 0.40\n" "1 0.20 0.30 0.10 0.20\n",
                encoding="utf-8",
            )

    (work / "obj.names").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    (work / "obj.data").write_text(
        "classes = 3\nnames = obj.names\ntrain = train.txt\n",
        encoding="utf-8",
    )
    (work / "train.txt").write_text(
        "\n".join(f"obj_train_data/frame_{i:03d}.jpg" for i in range(n_images)),
        encoding="utf-8",
    )

    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in work.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(work))
    return archive


def test_import_creates_yolo_structure(tmp_path: Path) -> None:
    archive = _make_fake_export(tmp_path, n_images=10)
    out = tmp_path / "dataset_v1"

    report = import_export(archive=archive, output_dir=out, seed=42)

    # Layout
    for split in ("train", "val", "test"):
        assert (out / "images" / split).is_dir()
        assert (out / "labels" / split).is_dir()
    # 70 / 15 / 15 of 10 = 7 / 1 / 2 (the floor split)
    assert report.splits == {"train": 7, "val": 1, "test": 2}
    assert report.n_images == 10
    assert report.n_labelled == 10
    assert report.n_unlabelled == 0
    # data.yaml
    data = yaml.safe_load((out / "data.yaml").read_text())
    assert data["nc"] == 3
    assert data["names"] == CLASSES
    assert data["train"] == "images/train"
    # import-report
    assert (out / "import-report.json").is_file()
    report_on_disk = json.loads((out / "import-report.json").read_text())
    assert report_on_disk["class_counts"] == {"box": 10, "person": 10}


def test_split_ratios_custom(tmp_path: Path) -> None:
    archive = _make_fake_export(tmp_path, n_images=20)
    out = tmp_path / "dataset_v2"
    report = import_export(archive=archive, output_dir=out, split=(0.5, 0.25, 0.25))
    assert report.splits == {"train": 10, "val": 5, "test": 5}


def test_unlabelled_images_kept_but_warned(tmp_path: Path) -> None:
    archive = _make_fake_export(tmp_path, n_images=10, n_unlabelled=3)
    out = tmp_path / "dataset_v3"
    report = import_export(archive=archive, output_dir=out)
    assert report.n_unlabelled == 3
    assert report.n_labelled == 7
    # The image files for unlabelled frames are still copied.
    total_imgs = sum(1 for _ in (out / "images").rglob("*.jpg"))
    assert total_imgs == 10
    # Only labelled ones produce .txt
    total_lbls = sum(1 for _ in (out / "labels").rglob("*.txt"))
    assert total_lbls == 7


def test_seed_makes_split_deterministic(tmp_path: Path) -> None:
    archive = _make_fake_export(tmp_path, n_images=20)
    out1 = tmp_path / "ds_a"
    out2 = tmp_path / "ds_b"
    import_export(archive=archive, output_dir=out1, seed=123)
    import_export(archive=archive, output_dir=out2, seed=123)
    train1 = sorted(p.name for p in (out1 / "images" / "train").iterdir())
    train2 = sorted(p.name for p in (out2 / "images" / "train").iterdir())
    assert train1 == train2


def test_seed_change_alters_split(tmp_path: Path) -> None:
    archive = _make_fake_export(tmp_path, n_images=20)
    out1 = tmp_path / "ds_a"
    out2 = tmp_path / "ds_b"
    import_export(archive=archive, output_dir=out1, seed=1)
    import_export(archive=archive, output_dir=out2, seed=999)
    train1 = sorted(p.name for p in (out1 / "images" / "train").iterdir())
    train2 = sorted(p.name for p in (out2 / "images" / "train").iterdir())
    assert train1 != train2


def test_missing_archive_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        import_export(archive=tmp_path / "nope.zip", output_dir=tmp_path / "out")


def test_existing_output_dir_refused(tmp_path: Path) -> None:
    archive = _make_fake_export(tmp_path, n_images=5)
    out = tmp_path / "dataset"
    out.mkdir()
    with pytest.raises(FileExistsError):
        import_export(archive=archive, output_dir=out)


def test_bad_split_ratio_rejected(tmp_path: Path) -> None:
    archive = _make_fake_export(tmp_path, n_images=5)
    out = tmp_path / "dataset"
    with pytest.raises(ValueError, match="sum to 1"):
        import_export(archive=archive, output_dir=out, split=(0.5, 0.5, 0.5))


def test_missing_obj_names_rejected(tmp_path: Path) -> None:
    # Build a broken export without obj.names.
    work = tmp_path / "broken"
    (work / "obj_train_data").mkdir(parents=True)
    archive = tmp_path / "broken.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(work / "obj_train_data", "obj_train_data")
    with pytest.raises(FileNotFoundError, match="obj.names"):
        import_export(archive=archive, output_dir=tmp_path / "out")
