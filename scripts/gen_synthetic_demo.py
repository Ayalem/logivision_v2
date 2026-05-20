"""Generate a synthetic CVAT-style YOLO export for end-to-end demo runs.

Produces `datasets/raw/annotations.zip` containing:
    obj_train_data/
        frame_000.jpg ... frame_NNN.jpg    (synthetic 320x240 RGB images)
        frame_000.txt ... frame_NNN.txt    (YOLO labels matching the rectangles)
    obj.names
    obj.data
    train.txt

Each frame has 1-3 colored rectangles (classes `box`, `person`, `forklift`).
The script is deterministic (seed=42 by default), so re-running gives the
same dataset — useful for reproducible training experiments.

Usage:
    python scripts/gen_synthetic_demo.py --n 60 --output datasets/raw/annotations.zip
"""

from __future__ import annotations

import argparse
import random
import tempfile
import zipfile
from pathlib import Path

import cv2
import numpy as np

CLASSES = ["box", "person", "forklift"]
CLASS_COLORS = {
    0: (60, 60, 220),  # box       -> red-ish
    1: (60, 200, 60),  # person    -> green-ish
    2: (200, 140, 30),  # forklift  -> blue/cyan-ish
}

IMG_W, IMG_H = 320, 240


def _rand_rect(rng: random.Random, class_id: int) -> tuple[int, int, int, int]:
    """Return a random (x1, y1, x2, y2) box for the given class."""
    if class_id == 0:  # box: small square
        w = rng.randint(30, 60)
        h = rng.randint(30, 60)
    elif class_id == 1:  # person: tall thin
        w = rng.randint(20, 40)
        h = rng.randint(70, 110)
    else:  # forklift: wide
        w = rng.randint(60, 100)
        h = rng.randint(40, 70)
    x1 = rng.randint(0, IMG_W - w - 1)
    y1 = rng.randint(0, IMG_H - h - 1)
    return x1, y1, x1 + w, y1 + h


def _yolo_line(class_id: int, x1: int, y1: int, x2: int, y2: int) -> str:
    cx = (x1 + x2) / 2 / IMG_W
    cy = (y1 + y2) / 2 / IMG_H
    w = (x2 - x1) / IMG_W
    h = (y2 - y1) / IMG_H
    return f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def _make_frame(rng: random.Random) -> tuple[np.ndarray, list[str]]:
    img = np.full((IMG_H, IMG_W, 3), rng.randint(20, 70), dtype=np.uint8)  # dark background
    n_objects = rng.randint(1, 3)
    lines: list[str] = []
    for _ in range(n_objects):
        cls = rng.randint(0, len(CLASSES) - 1)
        x1, y1, x2, y2 = _rand_rect(rng, cls)
        cv2.rectangle(img, (x1, y1), (x2, y2), CLASS_COLORS[cls], thickness=-1)
        lines.append(_yolo_line(cls, x1, y1, x2, y2))
    return img, lines


def build_export(n_frames: int, output_zip: Path, seed: int = 42) -> Path:
    rng = random.Random(seed)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        obj_dir = tmp_root / "obj_train_data"
        obj_dir.mkdir()
        for i in range(n_frames):
            img, lines = _make_frame(rng)
            cv2.imwrite(str(obj_dir / f"frame_{i:04d}.jpg"), img)
            (obj_dir / f"frame_{i:04d}.txt").write_text("\n".join(lines), encoding="utf-8")
        (tmp_root / "obj.names").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
        (tmp_root / "obj.data").write_text(
            f"classes = {len(CLASSES)}\nnames = obj.names\ntrain = train.txt\n",
            encoding="utf-8",
        )
        (tmp_root / "train.txt").write_text(
            "\n".join(f"obj_train_data/frame_{i:04d}.jpg" for i in range(n_frames)),
            encoding="utf-8",
        )

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in tmp_root.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(tmp_root))
    return output_zip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--n", type=int, default=60, help="Number of frames (default 60).")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/raw/annotations.zip"),
        help="Output zip path (default datasets/raw/annotations.zip).",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    out = build_export(args.n, args.output, args.seed)
    print(f"Wrote {args.n} frames + labels to {out}")
    print(
        "Next:  python -m ml.scripts.import_annotations "
        f"--input {out} --output datasets/processed/demo"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
