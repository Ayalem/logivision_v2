# Third-Party Notices

LOGIVISION is licensed under the MIT License (see `LICENSE`). It depends on third-party components with their own licenses. Significant ones are listed below.

## Ultralytics (YOLO) — AGPL-3.0

The training and inference services use [Ultralytics](https://github.com/ultralytics/ultralytics) (YOLOv8 / YOLOv11), which is distributed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

Implications:
- Modules that **import** `ultralytics` (e.g. `services/inference/`, `services/model-server/`, `ml/scripts/train.py`) form a combined work with an AGPL-3.0 component. If you distribute this software — including making it available as a network service — the AGPL-3.0 terms apply to the combined work and its source code must be made available to users of that service.
- This project is published publicly on GitHub, which satisfies the source-availability requirement for the current development phase.
- For a closed-source or commercial deployment, replace Ultralytics with a permissively licensed detector (e.g. detectors available via `torchvision`, RTMDet, DAMO-YOLO) **or** obtain an Ultralytics Enterprise License.

## Other Notable Dependencies

| Component | License | Notes |
|---|---|---|
| ByteTrack | MIT | OK |
| OpenVINO | Apache-2.0 | OK |
| MLflow | Apache-2.0 | OK |
| DVC | Apache-2.0 | OK |
| Apache Kafka / Flink | Apache-2.0 | OK |
| Feast | Apache-2.0 | OK |
| BentoML | Apache-2.0 | OK |
| Evidently | Apache-2.0 | OK |
| FastAPI | MIT | OK |
| React | MIT | OK |

A full SBOM will be generated as part of CI (see Phase 5, security scanning).
