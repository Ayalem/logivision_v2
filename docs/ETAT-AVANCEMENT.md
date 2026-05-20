# LOGIVISION — État d'avancement

> Statut au 2026-05-20. À destination des co-équipiers. Le récit complet est dans [`JOURNEY.md`](JOURNEY.md), le plan théorique dans [`../CLAUDE.md`](../CLAUDE.md), le suivi tâche par tâche dans [`../docs/PROGRESS.md`](PROGRESS.md).

## TL;DR

Phase 1 (MLOps Computer Vision) : **6 sprints sur 7 en code complet**. Tout tourne en local, tout est testé (60+ unit tests). Reste : Sprint 1.7 (drift monitoring) + bouclage avec de vraies annotations.

---

## Checklist sprints

| Sprint | Statut | Ce qui marche |
|---|---|---|
| **1.1 — Bootstrap MLOps** | ✅ | `make bootstrap` lance Postgres + MinIO + MLflow en 13 s, 4/4 smoke tests, DVC remote MinIO |
| **1.2 — Pipeline données** | ✅ | `extract_frames.py`, CVAT stack (`make cvat-up`), `import_annotations.py`, `dvc.yaml` (2 stages) |
| **1.3 — Training + MLflow** | ✅ | `make train` → run MLflow + Registry, intégration testée bout-en-bout en 15 s, guide Colab + notebook |
| **1.4 — Registry + OpenVINO** | ✅ | `make promote / promote-prod / export-openvino / benchmark`, ADR 0003 |
| **1.5 — Multi-arch comparison** | 🟡 Code prêt | `make compare-archs` (YOLOv8n + YOLOv11n + RT-DETR-l), `make fetch-videos` (API Pexels CC0) |
| **1.6 — Serving (BentoML)** | ✅ | `make serve` → :3000, `make load-test`, rapport sous `docs/mlops/benchmarks/` |
| **1.7 — Drift + retraining** | ⏳ Next |  |

**Note 1.5** : le code multi-arch tourne ; il manque juste un dataset annoté significatif pour produire un rapport intéressant. Cf. "Données" plus bas.

---

## Ce qui tourne réellement aujourd'hui

```
http://localhost:5050   MLflow UI  (tracking + Model Registry)
http://localhost:9001   MinIO Console
http://localhost:9000   MinIO S3 API
localhost:5432          PostgreSQL  (DBs: logivision + mlflow)
http://localhost:3000   BentoML detector  (quand `make serve` est lancé)
http://localhost:8090   CVAT  (quand `make cvat-up` est lancé)
```

Identifiants par défaut dans `.env.example`. Pour la stack docker : `make bootstrap` crée `.env` à partir du template si absent.

### MLflow contient déjà

- 1 expérience `warehouse-detection-integration` avec **run `4f9eb43c` FINISHED**
- 1 modèle enregistré `logivision-detector-integration` (stage None — entraîné sur 20 frames synthétiques, mAP50 = 0, juste pour valider le pipeline)

---

## Quickstart pour un nouveau co-équipier

```bash
git clone git@github.com:Ayalem/logivision_v2.git && cd logivision_v2
# 1. Python deps (uv installé via curl -LsSf https://astral.sh/uv/install.sh | sh)
make install
make pre-commit-install

# 2. Stack locale (PostgreSQL + MinIO + MLflow)
./scripts/bootstrap.sh           # ~15 s warm

# 3. Vérifie : tous les services healthy
make test-integration            # 4 smoke tests passent

# 4. Mini dataset synthétique + training end-to-end
make demo-data                   # zip d'annotations factices (60 frames)
uv run python -m ml.scripts.import_annotations \
    --input datasets/raw/annotations.zip \
    --output datasets/processed/demo
make train                       # ~2-3 min CPU, log dans MLflow

# 5. Serving
make serve                       # → http://localhost:3000
# autre terminal :
curl -F image=@datasets/processed/demo/images/val/<n'importe>.jpg http://localhost:3000/detect
```

Tout ce qui ressemble à une commande dans ce projet est dans le `Makefile` — `make help` liste les 30+ cibles.

---

## Branches et code

- **Une seule branche : `main`** (le gitflow `develop` + `feature/*` a été collapsé pour la lisibilité, cf. `CONTRIBUTING.md`).
- Co-équipiers ouvrent une **PR depuis une branche courte**, owner peut commit direct.
- **Aucun trailer `Co-Authored-By: Claude`** dans l'historique (projet académique). Toute génération automatique doit être anonymisée avant commit.

Branch protection à activer sur `main` côté GitHub (cf. CONTRIBUTING.md §"Branch protection settings").

---

## Structure du repo

```
ml/                        scripts ML, configs YAML, tests, notebooks
services/model_server/     BentoML service prêt à containeriser
scripts/                   gen synthetic, fetch Pexels, bootstrap
infra/docker-compose/      stacks MLOps + CVAT
infra/docker/              Dockerfiles MLflow custom + init.sql Postgres
tests/integration/         smoke tests stack
tests/load/                load test stdlib
docs/                      JOURNEY (récit), PROGRESS (tâches), ETAT-AVANCEMENT (ce doc), mlops/{guides, benchmarks, comparisons}, architecture/adr/
datasets/                  ⚠️ gitignored — versionné via DVC sur MinIO
```

Carte détaillée des emplacements : `docs/JOURNEY.md` section 4.

---

## Données — état des datasets

| Source | Statut | Annotations ? | Taille |
|---|---|---|---|
| Synthétique local (`make demo-data`) | ✅ Génère 60 frames + labels CVAT-style | ✅ auto | ~150 KB |
| Pexels warehouse (`make fetch-videos`) | ✅ 16 vidéos téléchargées | ❌ | ~67 MB |
| TalTech Camera3 video | ✅ Téléchargée manuellement par le user | ❌ (Models record contient les annotations) | 87 MB |
| TalTech Models record (`c6182-bgd05`) | ⏳ Pas encore téléchargé | ✅ probable | À vérifier |
| TalTech Camera1 (`nmw7y-41a87`) | ⏸️ Trop gros (9.97 GB) | ✅ | 9.97 GB |
| DataDryad 6D-ViCuT | ⏳ Pas encore téléchargé | ✅ cuboid tracking | À vérifier |
| Kaggle warehouse-delivery-box | ⏳ Besoin Kaggle CLI + token | ✅ probablement | Variable |

`datasets/processed/` est ce que YOLO consomme — `data.yaml` pointe vers `images/{train,val,test}` et `labels/...`.

---

## Problèmes connus

1. **Aucun modèle en Production** dans le MLflow Registry → `make serve` retombe sur `yolov8n.pt` (COCO pretrained). C'est attendu tant qu'un vrai dataset n'a pas été entraîné.
2. **Pas de protection branche sur `main`** côté GitHub — à activer manuellement.
3. **Tokens partagés en chat** dans des sessions précédentes (GitHub PAT, Pexels API key) — à rotater quand possible.
4. **Stack v4 (version précédente du projet) coexiste** côté Docker : ses containers sont arrêtés mais existent. Les noms `logivision-mlops-*` (v5) évitent tout conflit.
5. **macOS** : MLflow tourne sur **`:5050`** (pas `:5000` — AirPlay Receiver bloque). `MLFLOW_PORT` est configurable.

---

## Tests

- `make test` : 50+ unit tests, ~30 s
- `make test-integration` : 4 smoke tests (stack required), ~2 s
- `pytest -m integration ml/tests/test_train_integration.py` : training réel YOLOv8n 1 epoch sur 20 frames, ~15 s
- Couverture : non mesurée systématiquement, mais chaque script ML a 5-9 tests unitaires couvrant les chemins critiques.

---

## Prochaines étapes

1. **Sprint 1.7** (drift monitoring) — Evidently job périodique qui compare la distribution des inputs sur 24 h vs un snapshot de référence DVC. Alerte si PSI / Jensen-Shannon > seuil.
2. **Vraies annotations** — quand wifi tranquille : télécharger TalTech Models + DataDryad → adapter `ml/configs/yolov8n.yaml` → `make train` real → `make promote --approve` → BentoML cesse de fallback.
3. **Frontend** — pas planifié dans CLAUDE.md, à patcher en PR `docs(claude): add frontend sprints` (cf. PROGRESS.md "Frontend track").
4. **Phase 2** (streaming Kafka + Flink) — bloqué tant que Phase 1 n'est pas 100% close.
