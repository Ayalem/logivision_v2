"""Import a CVAT YOLO export and produce an Ultralytics-ready dataset.

CVAT YOLO export structure (zip):
    obj_train_data/
        image_001.jpg
        image_001.txt
        ...
    obj.names         <- one class name per line
    obj.data          <- Darknet-style data file (ignored)
    train.txt         <- list of image paths (ignored; we re-split)

Output (Ultralytics convention):
    <output>/
        data.yaml
        images/{train,val,test}/*.jpg|png
        labels/{train,val,test}/*.txt

Usage:
    python -m ml.scripts.import_annotations \\
        --input datasets/raw/annotations/batch01.zip \\
        --output datasets/processed/dataset_v1 \\
        --split 70 15 15

Validation pass logs:
- per-class counts
- min / median / max bbox area
- number of images without label file (warning)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import shutil
import statistics
import zipfile
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


@dataclass(frozen=True)
class Pair:
    image_path: Path
    label_path: Path | None  # None = image without annotations
    stem: str


@dataclass
class ImportReport:
    n_images: int
    n_labelled: int
    n_unlabelled: int
    splits: dict[str, int]
    class_counts: dict[str, int]
    bbox_stats: dict[str, float]
    output_dir: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "n_images": self.n_images,
            "n_labelled": self.n_labelled,
            "n_unlabelled": self.n_unlabelled,
            "splits": self.splits,
            "class_counts": self.class_counts,
            "bbox_stats": self.bbox_stats,
            "output_dir": str(self.output_dir),
        }


def _extract_zip(archive: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(dest)
    return dest


def _read_classes(extracted_root: Path) -> list[str]:
    candidates = list(extracted_root.rglob("obj.names"))
    if not candidates:
        raise FileNotFoundError("obj.names not found in archive — is this a CVAT YOLO export?")
    names = [
        line.strip()
        for line in candidates[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not names:
        raise ValueError("obj.names is empty.")
    return names


def _find_pairs(extracted_root: Path) -> list[Pair]:
    image_paths = sorted(
        p for p in extracted_root.rglob("*") if p.suffix.lower() in IMAGE_EXTENSIONS
    )
    pairs: list[Pair] = []
    for img in image_paths:
        label = img.with_suffix(".txt")
        pairs.append(
            Pair(
                image_path=img,
                label_path=label if label.is_file() else None,
                stem=img.stem,
            )
        )
    return pairs


def _split_pairs(
    pairs: list[Pair], ratios: tuple[float, float, float], seed: int
) -> dict[str, list[Pair]]:
    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError(f"split ratios must sum to 1.0, got {sum(ratios)}")
    rng = random.Random(seed)
    shuffled = list(pairs)
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])
    return {
        "train": shuffled[:n_train],
        "val": shuffled[n_train : n_train + n_val],
        "test": shuffled[n_train + n_val :],
    }


def _copy_split(pairs: list[Pair], output_dir: Path, split: str) -> None:
    images_dir = output_dir / "images" / split
    labels_dir = output_dir / "labels" / split
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    for pair in pairs:
        shutil.copy2(pair.image_path, images_dir / pair.image_path.name)
        if pair.label_path is not None:
            shutil.copy2(pair.label_path, labels_dir / pair.label_path.name)


def _write_data_yaml(output_dir: Path, classes: list[str]) -> None:
    data = {
        "path": str(output_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": len(classes),
        "names": classes,
    }
    (output_dir / "data.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _summarise(
    pairs: list[Pair],
    splits: dict[str, list[Pair]],
    classes: list[str],
    output_dir: Path,
) -> ImportReport:
    class_counts: Counter[str] = Counter()
    bbox_areas: list[float] = []
    for pair in pairs:
        if pair.label_path is None:
            continue
        for raw_line in pair.label_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            class_id = int(parts[0])
            if 0 <= class_id < len(classes):
                class_counts[classes[class_id]] += 1
            if len(parts) >= 5:
                _, _, _, w, h = parts[:5]
                bbox_areas.append(float(w) * float(h))

    bbox_stats: dict[str, float] = {}
    if bbox_areas:
        bbox_stats = {
            "min": min(bbox_areas),
            "median": statistics.median(bbox_areas),
            "max": max(bbox_areas),
            "count": float(len(bbox_areas)),
        }

    n_labelled = sum(1 for p in pairs if p.label_path is not None)
    return ImportReport(
        n_images=len(pairs),
        n_labelled=n_labelled,
        n_unlabelled=len(pairs) - n_labelled,
        splits={k: len(v) for k, v in splits.items()},
        class_counts=dict(class_counts),
        bbox_stats=bbox_stats,
        output_dir=output_dir,
    )


def import_export(
    archive: Path,
    output_dir: Path,
    split: Iterable[float] = (0.7, 0.15, 0.15),
    seed: int = 42,
) -> ImportReport:
    """Top-level entry. Extract the CVAT zip and write Ultralytics layout."""
    if not archive.is_file():
        raise FileNotFoundError(f"Archive does not exist: {archive}")

    ratios = tuple(split)  # type: ignore[assignment]
    if len(ratios) != 3:
        raise ValueError(f"split must have 3 values (train, val, test), got {len(ratios)}")

    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(
            f"Output dir already exists: {output_dir} — delete it or choose a new path."
        )

    extracted = output_dir.parent / f".{output_dir.name}.extracted"
    if extracted.exists():
        shutil.rmtree(extracted)
    try:
        _extract_zip(archive, extracted)
        classes = _read_classes(extracted)
        pairs = _find_pairs(extracted)
        if not pairs:
            raise ValueError("No images found in the archive.")

        splits = _split_pairs(pairs, ratios, seed)
        output_dir.mkdir(parents=True)
        for split_name, split_pairs in splits.items():
            _copy_split(split_pairs, output_dir, split_name)
        _write_data_yaml(output_dir, classes)

        report = _summarise(pairs, splits, classes, output_dir)
        (output_dir / "import-report.json").write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        if report.n_unlabelled:
            logger.warning(
                "%d image(s) have no label file — they were still copied.",
                report.n_unlabelled,
            )
        logger.info("Class distribution: %s", report.class_counts)
        logger.info("Splits: %s", report.splits)
        return report
    finally:
        if extracted.exists():
            shutil.rmtree(extracted)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--input", type=Path, required=True, help="CVAT YOLO export zip.")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Target dataset dir (must not exist).",
    )
    parser.add_argument(
        "--split",
        type=float,
        nargs=3,
        default=[0.7, 0.15, 0.15],
        metavar=("TRAIN", "VAL", "TEST"),
        help="Train/val/test ratios, must sum to 1.0 (default 0.70 0.15 0.15).",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    report = import_export(
        archive=args.input,
        output_dir=args.output,
        split=tuple(args.split),
        seed=args.seed,
    )
    logger.info("Done. Report: %s", report.output_dir / "import-report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
