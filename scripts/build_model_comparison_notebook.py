"""Generate ml/notebooks/02_model_comparison.ipynb.

A LOCAL cross-model comparison notebook. Auto-discovers every YOLO
checkpoint under ml/runs/**/weights/best.pt, evaluates each on the
same held-out Kaggle test split, times inference latency, and picks
the winner. Used to decide which model to register as Production.

Replaces the deleted pedagogical 02_transfer_learning_yolo.ipynb
(which was read-only walkthrough material).

Run: uv run python scripts/build_model_comparison_notebook.py
"""

from __future__ import annotations

import json
import pathlib

NB: list[dict] = []


def md(text: str) -> None:
    NB.append({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)})


def code(text: str) -> None:
    NB.append(
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": text.splitlines(keepends=True),
        }
    )


md(
    """# 02 — Cross-model comparison & winner picker

**Goal.** Evaluate every YOLO checkpoint on disk against the same
held-out Kaggle test split, time inference latency, and recommend
which one to register as Production.

## Why this notebook is in production

Notebooks 00, 06, 07 each produce a candidate `best.pt`. There are
also pre-existing local training runs under `ml/runs/<uuid>/`. With
multiple candidates floating around, you need a single
fair-comparison sheet to choose. This notebook is that sheet.

## What it does

1. Auto-discovers every `best.pt` under `ml/runs/**/weights/`.
2. Runs `model.val()` on the same Kaggle test split for each (single
   point of comparison — no cherry-picked val splits).
3. Times per-image inference latency.
4. Builds a side-by-side metrics table + bar charts.
5. Writes `ml/artifacts/model_comparison.json` for the Système panel.
6. Prints the winner with reasoning.

## Output

| Artefact | Path |
|---|---|
| Comparison metrics | `ml/artifacts/model_comparison.json` |
| Per-model val plots | `ml/artifacts/comparison_plots/` |
| Inline winner + reasoning | this notebook's last cell |

## How to use the result

Look at the winner. If you agree:
```
make register-from-colab RUN=<winner_dir>
make worker-restart
```
"""
)

# Cell 1 — env + setup
code(
    """# 1. Env + paths.
import json, time, os, sys, pathlib
from pathlib import Path
import pandas as pd

# Walk up to repo root (where pyproject.toml lives).
REPO = Path.cwd().resolve()
while not (REPO / 'pyproject.toml').is_file() and REPO != REPO.parent:
    REPO = REPO.parent
os.chdir(REPO)
print('repo root:', REPO)

# Compare on the CLEAN scene-aware split — the leaky original split makes
# every candidate look near-perfect and the ranking meaningless.
DATA_YAML = REPO / 'data' / 'processed' / 'kaggle_warehouse_clean' / 'data.yaml'
assert DATA_YAML.is_file(), (
    f'Missing dataset YAML at {DATA_YAML}. '
    'Run `uv run python scripts/prepare_kaggle_warehouse.py` then '
    '`uv run python scripts/reshuffle_splits_by_scene.py` first.'
)

ARTIFACTS = REPO / 'ml' / 'artifacts'
ARTIFACTS.mkdir(parents=True, exist_ok=True)
PLOTS_DIR = ARTIFACTS / 'comparison_plots'
PLOTS_DIR.mkdir(exist_ok=True)
print('dataset:', DATA_YAML)
"""
)

# Cell 2 — discover candidates
code(
    """# 2. Discover every candidate model on disk.
#    Looks for `best.pt` under ml/runs/**/weights/.
#    For each, the "name" is the run directory.
candidates = []
for pt in sorted((REPO / 'ml' / 'runs').glob('**/weights/best.pt')):
    run_dir = pt.parents[1]            # ml/runs/<name>/
    candidates.append({
        'name': run_dir.name,
        'weights': pt,
        'run_dir': run_dir,
        'size_mb': round(pt.stat().st_size / 1e6, 2),
    })

print(f'Found {len(candidates)} candidate models:')
for c in candidates:
    print(f'  - {c["name"]:<35s}  {c["size_mb"]:>6.2f} MB')

if not candidates:
    raise RuntimeError(
        'No candidate models found under ml/runs/**/weights/best.pt. '
        'Run notebook 00 or place Colab bundles under ml/runs/<name>/weights/.'
    )
"""
)

# Cell 3 — evaluate
code(
    """# 3. Evaluate each candidate on the SAME held-out test split.
#    Same DATA_YAML, same split='test', same imgsz=640.
from ultralytics import YOLO

results = []
for c in candidates:
    print(f'\\n=== {c["name"]} ===')
    model = YOLO(str(c['weights']))
    try:
        val = model.val(
            data=str(DATA_YAML),
            split='test',
            imgsz=640,
            verbose=False,
            plots=False,
            project=str(PLOTS_DIR),
            name=c['name'],
            exist_ok=True,
        )
        row = {
            'name':       c['name'],
            'mAP50':      float(val.box.map50),
            'mAP50_95':   float(val.box.map),
            'precision':  float(val.box.mp),
            'recall':     float(val.box.mr),
            'fitness':    float(val.fitness),     # weighted combo Ultralytics uses
            'size_mb':    c['size_mb'],
        }
        for k, v in row.items():
            if isinstance(v, float):
                print(f'  {k:<12s} = {v:.4f}')
            else:
                print(f'  {k:<12s} = {v}')
        results.append(row)
    except Exception as e:
        print(f'  FAILED: {e}')
        results.append({'name': c['name'], 'error': str(e), 'size_mb': c['size_mb']})

df = pd.DataFrame([r for r in results if 'error' not in r])
df = df.sort_values('mAP50', ascending=False).reset_index(drop=True)
print('\\n=== ranked by mAP@0.5 ===')
print(df.to_string(index=False))
"""
)

# Cell 4 — latency
code(
    """# 4. Inference latency on a single 640x640 image.
#    Two timings:
#     - cold: first inference (includes graph build/JIT)
#     - warm: median over 30 runs
import numpy as np, time

def latency_ms(weights_path, n=30):
    model = YOLO(str(weights_path))
    img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    # warm-up
    model.predict(img, verbose=False)
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        model.predict(img, verbose=False)
        times.append((time.perf_counter() - t0) * 1000)
    return {
        'p50_ms': float(np.percentile(times, 50)),
        'p95_ms': float(np.percentile(times, 95)),
        'mean_ms': float(np.mean(times)),
    }

for r in results:
    if 'error' in r:
        continue
    cand = next(c for c in candidates if c['name'] == r['name'])
    print(f'  measuring {r["name"]} ...')
    lat = latency_ms(cand['weights'])
    r.update({
        'p50_ms':  round(lat['p50_ms'],  2),
        'p95_ms':  round(lat['p95_ms'],  2),
        'mean_ms': round(lat['mean_ms'], 2),
    })

df = pd.DataFrame([r for r in results if 'error' not in r])
df = df.sort_values('mAP50', ascending=False).reset_index(drop=True)
print('\\n=== with latency ===')
print(df.to_string(index=False))
"""
)

# Cell 5 — comparison plots
code(
    """# 5. Side-by-side comparison plots.
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
names = df['name'].tolist()
short_names = [n[:18] + ('…' if len(n) > 18 else '') for n in names]

# Accuracy: mAP@0.5 vs mAP@0.5:0.95
x = np.arange(len(names))
w = 0.35
axes[0].bar(x - w/2, df['mAP50'],    width=w, label='mAP@0.5',     color='#2563EB')
axes[0].bar(x + w/2, df['mAP50_95'], width=w, label='mAP@0.5:0.95', color='#06B6D4')
axes[0].set_xticks(x); axes[0].set_xticklabels(short_names, rotation=20, ha='right')
axes[0].set_ylabel('mAP'); axes[0].set_title('Detection accuracy on held-out test')
axes[0].set_ylim(0, 1.05); axes[0].grid(alpha=0.2, axis='y'); axes[0].legend()

# Latency: lower is better
axes[1].bar(x, df['p50_ms'], color='#10B981')
axes[1].errorbar(x, df['p50_ms'],
                 yerr=[df['p50_ms'] - df['p50_ms'], df['p95_ms'] - df['p50_ms']],
                 fmt='none', color='#374151', capsize=4)
axes[1].set_xticks(x); axes[1].set_xticklabels(short_names, rotation=20, ha='right')
axes[1].set_ylabel('ms (p50 with p95 bar)'); axes[1].set_title('Per-image latency')
axes[1].grid(alpha=0.2, axis='y')

plt.tight_layout(); plt.show()
"""
)

# Cell 6 — pick winner + save artifact
code(
    """# 6. Winner = highest mAP@0.5:0.95 (the harder metric — rewards
#    boxes that are tight around the object, not just barely-overlapping).
#    If two are within 1% mAP@0.5:0.95, the faster one wins.
winner = None
for _, row in df.iterrows():
    if winner is None:
        winner = row
        continue
    map_diff = winner['mAP50_95'] - row['mAP50_95']
    if map_diff < 0.01 and row['p50_ms'] < winner['p50_ms']:
        winner = row

print('=' * 60)
print(f'WINNER: {winner["name"]}')
print('=' * 60)
print(f'  mAP@0.5         = {winner["mAP50"]:.4f}')
print(f'  mAP@0.5:0.95    = {winner["mAP50_95"]:.4f}')
print(f'  precision       = {winner["precision"]:.4f}')
print(f'  recall          = {winner["recall"]:.4f}')
print(f'  latency p50     = {winner["p50_ms"]:.2f} ms')
print()
print('Promote to Production:')
print(f'  make register-from-colab RUN={winner["name"]}')
print(f'  make worker-restart')

# Persist for the Système panel.
out = {
    'ranked':  df.to_dict(orient='records'),
    'winner':  winner['name'],
    'dataset': 'kaggle-warehouse-delivery-box (test split)',
}
(ARTIFACTS / 'model_comparison.json').write_text(json.dumps(out, indent=2, default=float))
print(f'\\nsaved: {ARTIFACTS / "model_comparison.json"}')
"""
)

md(
    """## What to do with the result

If the winner is the model you expected (e.g. the Colab-staged
one), promote it:
```bash
make register-from-colab RUN=<winner_name>
make worker-restart
```

If the winner is *unexpected* (e.g. an old local run beats the
new Colab one), that's the value of this notebook — it caught a
regression before you replaced Production. Investigate why before
promoting.

The Système page consumes `model_comparison.json` to show the
ranked table inline alongside the live `/api/model-info`.
"""
)

notebook = {
    "cells": NB,
    "metadata": {
        "kernelspec": {"display_name": "Python 3 (uv)", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
out = pathlib.Path("ml/notebooks/02_model_comparison.ipynb")
out.write_text(json.dumps(notebook, indent=1, ensure_ascii=False))
print(f"wrote {out}  ({out.stat().st_size:,} bytes, {len(NB)} cells)")
