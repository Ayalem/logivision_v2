# Annotation Workflow (CVAT → DVC)

This guide covers the manual annotation loop for LOGIVISION: from raw videos to a DVC-tracked Ultralytics dataset that `ml/scripts/train.py` can consume (T1.3).

## 1. Prerequisites

- The MLOps stack is up (`./scripts/bootstrap.sh`). Annotation does not require it, but DVC push at the end does.
- You have raw videos at `datasets/raw/videos/`.
- Frames extracted via `python -m ml.scripts.extract_frames --input datasets/raw/videos --output datasets/raw/frames --fps 2 --resize 640`.

## 2. Boot CVAT

```bash
make cvat-up                 # pulls cvat/server + cvat/ui v2.14.4, ~600 MB on first run
```

CVAT is on `http://localhost:8090`. First boot takes 30–60 s while migrations run; check progress with `docker logs -f logivision-cvat-server`.

Create the superuser (once):

```bash
docker exec -it logivision-cvat-server \
    python manage.py createsuperuser
```

Log in at `http://localhost:8090`, create an Organization, then create a Project with the labels you need:

```
box · person · forklift · qr_code · barcode · pallet
```

(Adjust to your taxonomy. Keep names lowercase, no spaces — these become class names in YOLO `data.yaml`.)

## 3. Create a Task and Upload Frames

In CVAT UI:
1. *Projects* → your project → *+ Task*.
2. Name it `batch-01-frames`.
3. Upload the JPG frames produced by `extract_frames.py` (drag-and-drop the folder).
4. Submit.

## 4. Annotate

Open the task → *Job #N* → annotate boxes using:

- `B` or *Draw rectangle* tool — draw bounding boxes.
- `T` — track an object across frames (avoids re-drawing identical boxes on consecutive frames).
- *Filters* in the right panel — quickly find frames with no annotations.

Tip: focus first on labelled object classes that are easy to confuse (e.g. `box` vs `pallet`) and define crisp annotation rules in your team.

## 5. Export

When done:
1. *Menu (≡)* → *Export task dataset*.
2. Format: **YOLO 1.1**.
3. Click *OK* — CVAT prepares a `<task-name>.zip` and offers it for download.

Place the export at `datasets/raw/annotations/batch-01.zip`.

## 6. Convert to Ultralytics Layout

```bash
python -m ml.scripts.import_annotations \
    --input datasets/raw/annotations/batch-01.zip \
    --output datasets/processed/dataset_v1 \
    --split 0.7 0.15 0.15 \
    --seed 42
```

This produces:

```
datasets/processed/dataset_v1/
    data.yaml
    images/{train,val,test}/...
    labels/{train,val,test}/...
    import-report.json
```

The `import-report.json` contains per-class counts and bbox area stats — a quick sanity check on class imbalance.

## 7. Version with DVC

```bash
dvc add datasets/processed/dataset_v1
git add datasets/processed/dataset_v1.dvc
git commit -m "data: import warehouse annotations batch 01"
dvc push
```

## 8. Tear Down CVAT

```bash
make cvat-down                # keeps volumes (work-in-progress preserved)
# or
docker compose -f infra/docker-compose/docker-compose.cvat.yml down --volumes  # destructive
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `cvat_server` keeps restarting | initial migrations crashed | `docker logs logivision-cvat-server`; usually missing volume permission |
| UI shows `502` | `cvat_server` not ready yet | wait 60 s or `docker restart logivision-cvat-server` |
| YOLO export missing `obj.names` | task has no labels defined | go back to the Project's *Labels* tab |
| Import script errors `obj.names not found` | export was *Job dataset* (no labels) instead of *Task dataset* | re-export at task level |
