# Demo proofs — "it works" evidence for the soutenance

Two visual artifacts that prove the trained models work, independent of the
live dashboard (which is limited by stock-footage domain shift).

## `detection_montage.png` — YOLO detector
Six **LOCO held-out test images** with the trained YOLOv8n's detections drawn.
Shows correct `pallet` / `forklift` / `small_load_carrier` / `pallet_truck`
boxes on real warehouse racks. Pair it with the measured metric:
**mAP@0.5 = 0.22 overall, 0.55 on the dominant pallet class** (see
`ml/artifacts/loco_detector/EVAL.md` — honest, imbalance-characterized).

## `anomaly_proof.png` — GRU-AE trajectory anomaly detector
A **perturbation test** on TOMIE held-out trajectories: the autoencoder
reconstructs *normal* industrial motion cleanly (error ≈ 0.3), but fails on
trajectories with injected irregular motion (teleport + speed spikes). Result:
**100% anomaly recall at ~1% false-positive** on normal motion, with the
threshold (p99) cleanly separating the two distributions. This is the rigorous
"the AE distinguishes normal vs anomalous" evidence — the live over-firing was
a footage-domain issue, fixed by retraining on TOMIE (`metrics.json`).

## Regenerate
```bash
# detector montage: render LOCO test images through the model
# anomaly proof:    scripts/train_trajectory_ae.py trains; the figure is a
#                   perturbation sweep over the held-out windows
```
