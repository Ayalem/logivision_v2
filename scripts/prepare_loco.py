"""Convert LOCO (COCO format) to a YOLO detection dataset.

Input  : datasets/raw/loco/  (images under dataset/subset-{1..5}/, COCO
         annotations under annotations/loco-sub{N}-v1-{train,val}.json),
         produced by scripts/fetch_loco.py.
Output : datasets/processed/loco/  (YOLO layout: images/{split}/ +
         labels/{split}/ + data.yaml).

Split — **scene-separated**, the leak-free choice (each LOCO subset is a
distinct warehouse environment, so no frame from one scene leaks across
splits):

    train = subsets 2, 3, 5      val = subset 1      test = subset 4

Classes (COCO ids are non-contiguous → remapped to 0..4):

    0 small_load_carrier   1 forklift   2 pallet   3 stillage   4 pallet_truck

Run:  uv run python scripts/prepare_loco.py
      make prepare-loco
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "datasets" / "raw" / "loco"
OUT = REPO / "datasets" / "processed" / "loco"

# COCO category id → (YOLO class index, name). LOCO ids are 3,5,7,10,11.
CAT_MAP = {3: 0, 5: 1, 7: 2, 10: 3, 11: 4}
CLASS_NAMES = ["small_load_carrier", "forklift", "pallet", "stillage", "pallet_truck"]

# subset number → (split, annotation-file stem). Scene-separated.
SUBSETS = {
    2: ("train", "loco-sub2-v1-train"),
    3: ("train", "loco-sub3-v1-train"),
    5: ("train", "loco-sub5-v1-train"),
    1: ("val", "loco-sub1-v1-val"),
    4: ("test", "loco-sub4-v1-val"),
}


def _yolo_line(cat_id: int, bbox: list[float], img_w: int, img_h: int) -> str | None:
    """COCO [x,y,w,h] (pixels) → YOLO `cls cx cy w h` (normalised). Drops
    degenerate or out-of-frame boxes that would poison training."""
    cls = CAT_MAP.get(cat_id)
    if cls is None:
        return None
    x, y, w, h = bbox
    if w <= 0 or h <= 0:
        return None
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    nw, nh = w / img_w, h / img_h
    if not (0 <= cx <= 1 and 0 <= cy <= 1) or nw <= 0 or nh <= 0 or nw > 1 or nh > 1:
        return None
    return f"{cls} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"


def _convert_subset(subset_n: int, split: str, stem: str, copy: bool) -> tuple[int, int]:
    """Returns (images_written, boxes_written) for one subset."""
    ann_path = RAW / "annotations" / f"{stem}.json"
    img_dir = RAW / "dataset" / f"subset-{subset_n}"
    if not ann_path.is_file():
        raise SystemExit(f"Missing annotations {ann_path} — run scripts/fetch_loco.py first.")
    if not img_dir.is_dir():
        raise SystemExit(f"Missing images {img_dir} — run scripts/fetch_loco.py first.")

    coco = json.loads(ann_path.read_text())
    images = {im["id"]: im for im in coco["images"]}
    boxes_by_img: dict[int, list[str]] = {}
    for an in coco["annotations"]:
        im = images.get(an["image_id"])
        if im is None:
            continue
        line = _yolo_line(an["category_id"], an["bbox"], im["width"], im["height"])
        if line is not None:
            boxes_by_img.setdefault(an["image_id"], []).append(line)

    img_out = OUT / "images" / split
    lbl_out = OUT / "labels" / split
    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    n_img = n_box = 0
    for idx, (img_id, im) in enumerate(images.items()):
        # Subsets 2-5 nest images under <session>/Kinect/color/; the COCO
        # `path` field is the authoritative location (subset-1 is flat but
        # its path resolves the same way). Strip the leading slash and join
        # to the extracted-zip root.
        src = RAW / im["path"].lstrip("/")
        if not src.is_file():
            continue
        # Enumerated name, namespaced by subset → collision-proof across the
        # nested session folders.
        stem_name = f"s{subset_n}_{idx:05d}"
        dst_img = img_out / f"{stem_name}.jpg"
        if copy:
            shutil.copy2(src, dst_img)
        else:
            dst_img.unlink(missing_ok=True)
            dst_img.symlink_to(src.resolve())
        lines = boxes_by_img.get(img_id, [])
        (lbl_out / f"{stem_name}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
        n_img += 1
        n_box += len(lines)
    return n_img, n_box


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Symlink images instead of copying (saves ~700 MB; local use only).",
    )
    parser.add_argument("--clean", action="store_true", help="Remove existing output first.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.clean and OUT.is_dir():
        shutil.rmtree(OUT)
        logger.info("Removed existing %s", OUT.relative_to(REPO))

    totals = {"train": [0, 0], "val": [0, 0], "test": [0, 0]}
    for subset_n, (split, stem) in SUBSETS.items():
        n_img, n_box = _convert_subset(subset_n, split, stem, copy=not args.symlink)
        totals[split][0] += n_img
        totals[split][1] += n_box
        logger.info("subset-%d → %-5s : %d images, %d boxes", subset_n, split, n_img, n_box)

    data_yaml = OUT / "data.yaml"
    data_yaml.write_text(
        f"path: {OUT}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(CLASS_NAMES))
    )
    logger.info("Wrote %s", data_yaml.relative_to(REPO))
    for split, (ni, nb) in totals.items():
        logger.info("  %-5s: %d images, %d boxes", split, ni, nb)
    logger.info(
        "Done. Train YOLO with data=%s (use Colab/Kaggle GPU).", data_yaml.relative_to(REPO)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
