# DVC Guide

DVC (Data Version Control) versions large files — datasets, model weights, intermediate artifacts — *outside* Git, while the small `.dvc` pointers go in Git. Storage is a MinIO bucket (`s3://datasets/dvc-cache`) provisioned by `scripts/bootstrap.sh`.

## Setup (per developer, once)

1. `make install` — installs `dvc[s3]` as a dev dep.
2. `./scripts/bootstrap.sh` — boots PostgreSQL + MinIO + MLflow and (since T1.1.3) writes `.dvc/config.local` with the MinIO credentials from `.env`. `.dvc/config.local` is gitignored.
3. `uv run dvc remote list` — should show:
   ```
   minio   s3://datasets/dvc-cache
   ```
4. `uv run dvc status` — should print `No changes`.

If `bootstrap.sh` did not write the local config (e.g. you started the stack manually), run:

```bash
uv run dvc remote modify --local minio access_key_id "$AWS_ACCESS_KEY_ID"
uv run dvc remote modify --local minio secret_access_key "$AWS_SECRET_ACCESS_KEY"
```

## Adding a dataset

```bash
# Drop the file(s) anywhere under datasets/ (gitignored by default).
cp -r /path/to/videos datasets/raw/videos

# Track it with DVC. This computes hashes, moves the data to the DVC
# cache, and creates a small datasets/raw/videos.dvc pointer file.
uv run dvc add datasets/raw/videos

# `autostage = true` in .dvc/config already added the pointer to git.
git commit -m "data: add raw warehouse videos batch 01"

# Push the actual bytes to MinIO. `git push` does NOT push DVC data.
uv run dvc push
```

## Pulling on a fresh clone

```bash
git clone git@github.com:Ayalem/logivision_v2.git
cd logivision_v2
./scripts/bootstrap.sh       # ensures MinIO is reachable + writes config.local
uv run dvc pull              # downloads tracked data from MinIO
```

## Reproducing a pipeline (later sprints)

Once `ml/dvc.yaml` defines stages (Sprint 1.2):

```bash
uv run dvc repro             # runs only stages whose inputs changed
uv run dvc dag               # show the stage DAG
uv run dvc metrics show      # show tracked metrics
```

## Day-to-day workflow

- After modifying a dataset on disk: `dvc add` → `git commit` the updated `.dvc` pointer → `dvc push`.
- Switching branches that have different data versions: `git checkout <branch>` → `dvc checkout` to sync local files to the branch's pointers.
- Inspecting what's tracked: `dvc list . --recursive`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `dvc push` hangs / `endpoint not reachable` | MinIO is down | `./scripts/bootstrap.sh` |
| `dvc push` returns `403 Forbidden` | `.dvc/config.local` missing credentials | Re-run bootstrap or set them manually (see Setup §3) |
| `dvc status` shows unexpected diff | local cache out of sync | `dvc checkout` |
| Adding huge file is slow | files are copied to cache | OK on first add; subsequent ops use hard-links |

## Why DVC vs Git LFS

| | DVC | Git LFS |
|---|---|---|
| Data storage | Any S3-compatible (MinIO ✓) | LFS-specific server |
| Cost on GitHub | 0 € | quotas + add-on bandwidth |
| Pipelines (`dvc.yaml`) | Yes | No |
| Lock-in | Free, open source | Requires GitHub LFS support |

DVC fits LOGIVISION's "0 € budget, self-hosted MinIO" constraint exactly.

## References

- DVC docs: <https://dvc.org/doc>
- MinIO S3 compatibility: <https://min.io/docs/minio/linux/developers/aws-cli.html>
