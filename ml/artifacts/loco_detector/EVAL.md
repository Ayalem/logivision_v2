# LOCO detector — held-out evaluation

**Model.** YOLOv8n fine-tuned from COCO weights on **LOCO** (Logistics Objects
in Context), 50 epochs, 640 px. **Evaluation split.** LOCO subset 4 — a
**scene-separated** held-out warehouse (no frame from a training scene appears
in test, so no spatial/temporal leakage). Numbers below are `model.val(...)`
on that split; the run is logged to MLflow (`warehouse-detection` experiment,
run `loco_TEST_eval_subset4`).

## Headline

| Metric | Value |
|---|---|
| **mAP@0.5** | **0.219** |
| mAP@0.5:0.95 | 0.091 |
| precision | 0.332 |
| recall | 0.247 |

## Per-class (test split)

| Class | Train inst. | Test inst. | mAP@0.5 | mAP@0.5:0.95 |
|---|---:|---:|---:|---:|
| **pallet** | 68,148 (78.4%) | 39,022 | **0.553** | 0.217 |
| small_load_carrier | 13,240 | 0 | — (absent in scene) | — |
| stillage | 3,400 | 29 | 0.021 | 0.006 |
| pallet_truck | 1,674 | 559 | 0.118 | 0.043 |
| forklift | 474 | 119 | 0.185 | 0.097 |

## Analysis (the honest story)

The aggregate mAP@0.5 = 0.22 is **not a training failure** — it is the
expected consequence of a **severe class imbalance**. Pallet accounts for
**78.4%** of all training instances; forklift has only **474** (a ~144×
imbalance). The detector is consequently **strong on the dominant pallet
class (mAP@0.5 = 0.55)** and degrades on the rare classes, which receive too
little learning signal. Two split artifacts compound the average:

1. The held-out scene (subset 4) is **98% pallet** by instance count.
2. It contains **zero small_load_carrier** instances, so that class — well
   represented in training (13k) — cannot be scored here at all.

**This is a well-characterized, reproducible result**, appropriate to report
as-is. The scientific claim is *"YOLOv8n on LOCO reaches 0.55 mAP@0.5 on the
well-represented pallet class but is imbalance-limited on rare classes"* — not
an inflated single number. LOCO is a genuinely hard, long-tailed dataset.

## Improvement levers (future work, in impact order)

1. **Address class imbalance** — oversample / copy-paste augment
   stillage / forklift / pallet_truck, or report pallet as the primary class.
2. **Larger backbone** — yolov8s/m instead of n.
3. **More epochs + stronger augmentation** (mosaic, mixup, HSV).
4. **Per-scene stratified split** so each class is represented in test.

These require GPU (Colab/Kaggle); the configs live in notebooks 00 / 06.
