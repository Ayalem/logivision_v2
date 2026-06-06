"""Re-split data/processed/kaggle_warehouse/ by SCENE not by frame.

The Kaggle warehouse-delivery-box dataset (via Roboflow) is delivered
with frames randomly shuffled across train/val/test splits. Adjacent
frames of the same flight thus end up in different splits, giving
the model trivial "next-frame" recall that inflates mAP — by audit,
11 of 256 scenes appear in 2 or 3 splits, the biggest having 60 train
+ 10 val + 7 test frames of the SAME flight.

This script:
  1. Reads every image basename under data/processed/kaggle_warehouse/
  2. Groups by scene_id (filename minus the frame index + .rf hash)
  3. Re-assigns each entire scene to ONE split (train/val/test)
  4. Writes a CLEAN copy under data/processed/kaggle_warehouse_clean/
  5. Emits data.yaml ready for Ultralytics

The original kaggle_warehouse/ dir is untouched so v3 remains
reproducible for honest comparison in the paper.
"""

from __future__ import annotations

import json
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "processed" / "kaggle_warehouse"
OUT = REPO / "data" / "processed" / "kaggle_warehouse_clean"
SEED = 42
# Target split ratios by FRAME count (we approximate by scene count).
RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}


def scene_of(stem: str) -> str:
    """`158_flight_1625_4284_png.rf.<hash>` → `158_flight_1625`."""
    return re.sub(r"_\d+_png\.rf\..*$", "", stem)


def main() -> int:
    assert SRC.is_dir(), f"missing source dataset {SRC}"

    # Collect every frame in the existing dataset, regardless of split.
    frames: dict[str, list[Path]] = defaultdict(list)
    for split in ("train", "val", "test"):
        img_dir = SRC / "images" / split
        if not img_dir.is_dir():
            continue
        for p in img_dir.iterdir():
            frames[scene_of(p.stem)].append(p)

    scenes = sorted(frames.keys())
    print(f"discovered {len(scenes)} scenes, {sum(len(v) for v in frames.values())} frames")

    # Deterministically assign whole scenes to splits.
    random.seed(SEED)
    random.shuffle(scenes)

    n = len(scenes)
    cuts = {
        "train": int(n * RATIOS["train"]),
        "val": int(n * (RATIOS["train"] + RATIOS["val"])),
    }
    split_of_scene = {}
    for i, sc in enumerate(scenes):
        if i < cuts["train"]:
            split_of_scene[sc] = "train"
        elif i < cuts["val"]:
            split_of_scene[sc] = "val"
        else:
            split_of_scene[sc] = "test"

    # Realize the split: copy images + labels into the new layout.
    if OUT.is_dir():
        shutil.rmtree(OUT)
    for s in ("train", "val", "test"):
        (OUT / "images" / s).mkdir(parents=True, exist_ok=True)
        (OUT / "labels" / s).mkdir(parents=True, exist_ok=True)

    counts: dict[str, dict[str, int]] = {
        s: {"scenes": 0, "frames": 0} for s in ("train", "val", "test")
    }
    for sc, paths in frames.items():
        s = split_of_scene[sc]
        counts[s]["scenes"] += 1
        for img_path in paths:
            # Find label in the original layout (may be in any split's labels/).
            for src_split in ("train", "val", "test"):
                lbl = SRC / "labels" / src_split / (img_path.stem + ".txt")
                if lbl.is_file():
                    break
            else:
                continue
            shutil.copy(img_path, OUT / "images" / s / img_path.name)
            shutil.copy(lbl, OUT / "labels" / s / lbl.name)
            counts[s]["frames"] += 1

    # Verify: 0 scene crosses two splits.
    seen: dict[str, str] = {}
    for s in ("train", "val", "test"):
        for p in (OUT / "images" / s).iterdir():
            sc = scene_of(p.stem)
            if sc in seen and seen[sc] != s:
                raise AssertionError(f"leakage: scene {sc} in {seen[sc]} and {s}")
            seen[sc] = s
    print("✓ 0 scene leakage across splits")

    # Re-emit data.yaml. Reuse original class list (Ultralytics-style YAML
    # uses an inline dict for `names:`; load with PyYAML for safety).
    import yaml as _yaml

    src_yaml_doc = _yaml.safe_load((SRC / "data.yaml").read_text())
    out_doc = {
        "path": str(OUT.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": src_yaml_doc["names"],
    }
    if "nc" in src_yaml_doc:
        out_doc["nc"] = src_yaml_doc["nc"]
    (OUT / "data.yaml").write_text(_yaml.safe_dump(out_doc, sort_keys=False))

    # Summary
    print()
    print(f'{"split":<8s} {"scenes":>8s} {"frames":>8s}')
    for s in ("train", "val", "test"):
        print(f'{s:<8s} {counts[s]["scenes"]:>8d} {counts[s]["frames"]:>8d}')
    (OUT / "split_summary.json").write_text(
        json.dumps(
            {
                "seed": SEED,
                "ratios": RATIOS,
                "counts": counts,
                "scene_assignment": split_of_scene,
            },
            indent=2,
        )
    )
    print(f"\nclean data.yaml: {OUT / 'data.yaml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
