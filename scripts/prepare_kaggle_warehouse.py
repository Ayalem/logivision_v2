"""Convert the Kaggle warehouse-delivery-box dataset to standard YOLO bbox format.

The dataset ships labels as YOLO-OBB (oriented bounding boxes): one line per
instance, 9 columns = `class x1 y1 x2 y2 x3 y3 x4 y4` (corners in 0..1).
We compute the axis-aligned bounding box (AABB) of each quadrilateral and
emit the standard `class cx cy w h` format so the off-the-shelf
`yolov8n.pt` detector can train on it.

Run:
    uv run python scripts/prepare_kaggle_warehouse.py

This writes:
    data/processed/kaggle_warehouse/
      ├── data.yaml
      ├── images/{train,val,test}/*.jpg   (symlinks into the kagglehub cache)
      └── labels/{train,val,test}/*.txt   (converted axis-aligned)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

ROOT = (
    Path.home()
    / ".cache/kagglehub/datasets/zoya77/warehouse-delivery-box-detection-dataset/versions/2/Box Dataset"
)
OUT = Path(__file__).resolve().parent.parent / "data" / "processed" / "kaggle_warehouse"

# Roboflow-exported OBB datasets rarely ship `data.yaml`; the user's
# slice has 3 class IDs (0, 1, 2). Without dataset-card access we use
# defensible generic names — easy to rename via a yaml edit later.
CLASS_NAMES = ["box_small", "box_medium", "box_large"]
SPLITS = {"train": "train", "valid": "val", "test": "test"}  # source → target name


def obb_to_aabb_line(line: str) -> str | None:
    """Convert one OBB row (`cls x1 y1 ... x4 y4`) to AABB (`cls cx cy w h`).

    Drops degenerate rows (zero-area or out-of-range) so they don't poison
    training — they're the single largest reason YOLO reports
    `precision ≈ 0` on Roboflow exports.
    """
    parts = line.strip().split()
    if len(parts) != 9:
        return None  # not an OBB row — keep as-is or drop
    cls = int(parts[0])
    xs = [float(parts[i]) for i in (1, 3, 5, 7)]
    ys = [float(parts[i]) for i in (2, 4, 6, 8)]
    x_min, x_max = max(0.0, min(xs)), min(1.0, max(xs))
    y_min, y_max = max(0.0, min(ys)), min(1.0, max(ys))
    w = x_max - x_min
    h = y_max - y_min
    if w <= 1e-3 or h <= 1e-3:
        return None
    cx = x_min + w / 2
    cy = y_min + h / 2
    return f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def convert_split(src: Path, dst_images: Path, dst_labels: Path) -> tuple[int, int, int]:
    """Convert one split.

    Returns (images_linked, labels_written, instances_kept).
    """
    n_img, n_lbl, n_inst = 0, 0, 0
    dst_images.mkdir(parents=True, exist_ok=True)
    dst_labels.mkdir(parents=True, exist_ok=True)
    for img_path in (src / "images").iterdir():
        if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        target = dst_images / img_path.name
        if not target.exists():
            try:
                target.symlink_to(img_path)
            except OSError:
                shutil.copy2(img_path, target)
        n_img += 1
        lbl_src = src / "labels" / (img_path.stem + ".txt")
        if not lbl_src.is_file():
            (dst_labels / (img_path.stem + ".txt")).write_text("")
            continue
        kept_rows: list[str] = []
        for raw_line in lbl_src.read_text().splitlines():
            line = raw_line.strip()
            if not line:
                continue
            converted = obb_to_aabb_line(line)
            if converted is None:
                # Some Roboflow exports already ship AABB rows (5 cols) — pass through.
                if len(line.split()) == 5:
                    kept_rows.append(line)
                continue
            kept_rows.append(converted)
        (dst_labels / (img_path.stem + ".txt")).write_text("\n".join(kept_rows) + "\n")
        n_lbl += 1
        n_inst += len(kept_rows)
    return n_img, n_lbl, n_inst


def main() -> None:
    assert (
        ROOT.is_dir()
    ), f"Dataset not found at {ROOT}. Run `kagglehub.dataset_download(...)` first."
    OUT.mkdir(parents=True, exist_ok=True)

    totals = {}
    for src_name, tgt_name in SPLITS.items():
        src = ROOT / src_name
        if not src.is_dir():
            print(f"⚠  skipping {src_name} — not in source")
            continue
        dst_img = OUT / "images" / tgt_name
        dst_lbl = OUT / "labels" / tgt_name
        n_img, n_lbl, n_inst = convert_split(src, dst_img, dst_lbl)
        totals[tgt_name] = (n_img, n_lbl, n_inst)
        print(
            f"  {tgt_name:<5}: {n_img:>5} images · {n_lbl:>5} labels · {n_inst:>6} AABB instances"
        )

    # YOLO data.yaml — use ABSOLUTE paths so Ultralytics doesn't get confused
    # by cwd at training time.
    data_yaml = {
        "path": str(OUT.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": dict(enumerate(CLASS_NAMES)),
    }
    (OUT / "data.yaml").write_text(yaml.safe_dump(data_yaml, sort_keys=False))
    print(f"\n✓ wrote {OUT / 'data.yaml'}")
    print("  classes:", CLASS_NAMES)
    print("  splits :", {k: v[0] for k, v in totals.items()})


if __name__ == "__main__":
    main()
