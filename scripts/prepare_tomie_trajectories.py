"""Convert TOMIE ground-truth annotations to trajectory JSONL for the GRU-AE.

TOMIE ships per-camera CSVs with tracked entities (ObjectName), per-frame 2D
bounding boxes and a Visible flag. We turn the *visible* boxes into the exact
trajectory JSONL that `scripts/export_trajectories.py` emits, so the anomaly
autoencoder (ml/notebooks/08) trains on **real, in-domain industrial motion**
(moving forklifts + pallets) instead of out-of-domain stock-footage tracks.

Using TOMIE's ground truth (not the detector) is the right call here: the
LOCO detector is out of domain on TOMIE's renders, but TOMIE's *annotations*
are exactly the clean, labelled, moving-entity trajectories the AE needs.

Output: data/processed/trajectories/tomie_<camera>.jsonl (+ manifest), the
same schema export_trajectories produces — so nothing downstream changes.

Run:  uv run python scripts/prepare_tomie_trajectories.py
"""

from __future__ import annotations

import ast
import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
TOMIE_ROOT = REPO / "datasets" / "raw" / "tomie"
OUT_DIR = REPO / "data" / "processed" / "trajectories"

FRAME_W, FRAME_H = 1296, 1024  # TOMIE render resolution
NOMINAL_FPS = 10               # consistent dt for the trajectory features
CLASS = {"PALLET": (0, "pallet"), "FORKLIFT": (1, "forklift")}


def _frame_index(file_name: str) -> int | None:
    stem = Path(file_name).stem
    return int(stem) if stem.isdigit() else None


def convert_csv(csv_path: Path, camera: str, scenario: str) -> tuple[Path, int, int]:
    """One camera CSV -> one JSONL. Returns (path, n_records, n_tracks)."""
    track_ids: dict[str, int] = {}
    rows_out = []
    with csv_path.open() as fh:
        for row in csv.DictReader(fh):
            if row.get("Visible") != "1":
                continue
            try:
                bbox = ast.literal_eval(row["BoundingBox"])  # [x, y, w, h]
            except (ValueError, SyntaxError):
                continue
            if len(bbox) != 4 or bbox[2] <= 0 or bbox[3] <= 0:
                continue
            fi = _frame_index(row["fileName"])
            if fi is None:
                continue
            name = row["ObjectName"]
            kind = name.rsplit("_", 2)[0]  # PALLET_NEW_01 -> PALLET
            if kind not in CLASS:
                continue
            cls_id, cls_name = CLASS[kind]
            tid = track_ids.setdefault(name, len(track_ids) + 1)
            x, y, w, h = (float(v) for v in bbox)
            rows_out.append(
                {
                    "video": f"tomie_{scenario}_{camera}",
                    "model_version": "tomie-ground-truth",
                    "frame_idx": fi,
                    "timestamp_ms": int(fi * 1000 / NOMINAL_FPS),
                    "track_id": tid,
                    "class_id": cls_id,
                    "class_name": cls_name,
                    "conf": 1.0,
                    "cx": round(x + w / 2, 2),
                    "cy": round(y + h / 2, 2),
                    "w": round(w, 2),
                    "h": round(h, 2),
                    "frame_w": FRAME_W,
                    "frame_h": FRAME_H,
                }
            )
    rows_out.sort(key=lambda r: (r["track_id"], r["frame_idx"]))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"tomie_{scenario}_{camera}.jsonl"
    with out.open("w") as fh:
        for r in rows_out:
            fh.write(json.dumps(r) + "\n")
    return out, len(rows_out), len(track_ids)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    csvs = sorted(str(p) for p in TOMIE_ROOT.rglob("*.csv"))
    if not csvs:
        raise SystemExit(f"No TOMIE CSVs under {TOMIE_ROOT} — run scripts/fetch_tomie.py first.")
    manifest: dict = {"source": "TOMIE (Zenodo 7849183)", "files": {}}
    tot_rec = tot_trk = 0
    seen: set[str] = set()
    for c in csvs:
        p = Path(c)
        parts = p.parts
        # .../tomie/<scenario>/<scenario>/<camera>/.../data.csv
        cam = next((x for x in parts if x.startswith("camera_")), p.stem)
        scen = next((x for x in parts if x.startswith("scenario_")), "scenario")
        key = f"{scen}_{cam}"
        if key in seen:  # 2 csvs per camera — first wins (data.csv)
            continue
        seen.add(key)
        out, nrec, ntrk = convert_csv(p, cam, scen)
        if nrec == 0:
            out.unlink(missing_ok=True)
            continue
        manifest["files"][out.name] = {"records": nrec, "tracks": ntrk, "src": str(p.relative_to(REPO))}
        tot_rec += nrec
        tot_trk += ntrk
        logger.info("%s -> %d records, %d tracks", out.name, nrec, ntrk)
    (OUT_DIR / "tomie_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    logger.info("Done: %d trajectories, %d tracks across %d cameras.", tot_rec, tot_trk, len(manifest["files"]))
    logger.info("Train the GRU-AE on these via ml/notebooks/08 (point it at data/processed/trajectories/tomie_*.jsonl).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
