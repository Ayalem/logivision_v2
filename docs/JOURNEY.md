# Journal de bord — LOGIVISION v5

Ce document raconte **l'avancement concret** du projet : quels sprints ont été faits, dans quel ordre, quels problèmes ont été rencontrés, et comment ils ont été résolus. À lire en complément de `CLAUDE.md` (le plan théorique) et de `PROGRESS.md` (le suivi par tâche).

Date de dernière mise à jour : 2026-05-20.

---

## 1. Vue d'ensemble — où on en est

| Sprint | Statut | Livrables clés |
|---|---|---|
| **1.1 — Bootstrap MLOps** | ✅ Fermé | uv + ruff + mypy + pre-commit, stack Docker (Postgres + MinIO + MLflow), DVC remote MinIO |
| **1.2 — Pipeline données** | ✅ Fermé (annot. manuelle reportée) | `extract_frames.py`, CVAT stack, `import_annotations.py`, pipeline `dvc.yaml` |
| **1.3 — Training + MLflow** | ✅ Fermé | `train.py` (Ultralytics + MLflow), test d'intégration 15 s, guide Colab + notebook |
| **1.4 — Registry + OpenVINO** | ✅ Fermé | `promote_model.py` (2 gates), `export_openvino.py` (FP32 + INT8), `benchmark_inference.py` |
| **1.5 — Multi-arch comparison** | 🟡 Code prêt, exécution gated par data réelle | `compare_archs.py`, `fetch_pexels_videos.py` (API Pexels) |
| **1.6 — BentoML serving** | ⏳ Prochain |  |
| **1.7 — Drift + retraining** | ⏳ |  |

Branche unique : `main` (le gitflow `develop` + `feature/*` a été collapsé pour rester lisible).

---

## 2. Décisions techniques notables

1. **`uv` plutôt que pip/poetry** — install ~10× plus rapide, lock-file natif. `make install` = 8 s.
2. **MLflow port `5050` par défaut** (au lieu de `5000` que dit CLAUDE.md). Raison : macOS Control Center / AirPlay Receiver bind `:5000` par défaut, conflit impossible à résoudre sans désactiver AirPlay côté système. La variable d'env `MLFLOW_PORT` reste configurable.
3. **Containers préfixés `logivision-mlops-*`** au lieu de `logivision-*`. Raison : une stack v4 (du même projet, version précédente) tournait depuis 5 jours sur la machine au moment du bootstrap initial. Préfixer évite le conflit de noms ; les containers v4 peuvent toujours être redémarrés via `docker start`.
4. **`dvc.yaml` à la racine du repo**, pas dans `ml/`. CLAUDE.md disait `ml/dvc.yaml` mais ses propres exemples de paths (`datasets/raw/videos`) sont relatifs à la racine. Mettre le fichier à la racine évite tout `..` ou path hack.
5. **Branche unique `main`** au lieu du gitflow complet. Décision après que la prolifération de branches `feature/*` rendait l'historique illisible pour un projet académique solo. Les collaborateurs ouvriront des PRs courtes ; le owner commit direct sur `main`.
6. **CVAT pinné en v2.14.4** au lieu de la dernière 2.20+. Versions ≥ 2.20 ajoutent kvrocks (queue persistante) et OPA (policy engine) — 7 services vs 4. La 2.14.4 est minimale et fonctionnelle.
7. **Pexels API plutôt que web scraping** pour récupérer des vidéos warehouse. CC0 + REST API officielle + gratuit = pas de risque ToS.
8. **Sources de données réelles identifiées** (à download sur wifi tranquille) :
   - TalTech Records `c6182-bgd05` (Models), `nmw7y-41a87` (Camera 1, 9.97 GB, annotated), `3ytc7-2z453` (Camera 2), `e9wxe-qpv69` (Videos). MIT License.
   - DataDryad `10.5061/dryad.jq2bvq8dv` — 6D-ViCuT, cuboid tracking en packing manuel. CC0.
   - Kaggle `zoya77/warehouse-delivery-box-detection-dataset`. Nécessite `kaggle` CLI.

---

## 3. Problèmes rencontrés et résolutions

### 3.1 Incidents pendant le bootstrap

- **Stack v4 préexistante occupait les ports 5432 / 9000 / 9001.** Diagnostic : `docker ps --filter name=logivision`. Solution : `docker stop` la stack v4 (les volumes restent), préfixer les containers v5 `logivision-mlops-*`.
- **macOS `:5000` bloqué par AirPlay Receiver** (`lsof -nP -iTCP:5000` → ControlCenter). Solution : `MLFLOW_PORT=5050`.
- **Détection d'une stack v4 en cours d'exécution** avec containers `logivision-nginx`, `logivision-frontend`, `logivision-video-engine`, `logivision-api`, `logivision-grafana`, `logivision-postgres`, `logivision-redis`, `logivision-prometheus`, `logivision-minio`, `logivision-mediamtx`. v4 = MVP académique précédent. Décision : stopper, garder les volumes, repartir propre.

### 3.2 Incident Git majeur

- **Force-push destructeur sur `main`.** Pendant la phase de nettoyage des trailers `Co-Authored-By: Claude`, un `git push --force-with-lease` sur `main` a écrasé un merge commit que l'utilisateur venait de créer côté GitHub (PR T1.1.1 fraîchement mergée). Récupération : le commit perdu (`02a9e18`) existait encore dans la DB git locale (fetché juste avant le push), restauré via `git push --force origin 02a9e18:main`. Aucun perte de données finale. **Leçon retenue** : `git fetch` systématique avant tout force-push, même sur un repo qu'on croit immobile.
- **Solution durable** pour les trailers Claude : `git filter-branch --msg-filter "grep -v '^Co-Authored-By: Claude'"` réécrit tous les commits historiques en préservant la structure de merge. Push de nouveaux SHAs sur les 3 branches concernées.

### 3.3 Sécurité — secrets partagés en chat

- **GitHub PAT partagé en chat** (fine-grained, repo unique). Conséquence : le token transite par les serveurs Anthropic. Recommandation : révocation immédiate + nouveau token. L'utilisateur a refait + utilisé `claude mcp add` côté terminal.
- **Token Pexels partagé en chat**. Faible enjeu (lecture seule sur médias CC0) mais même principe. Stocké dans `.env` (gitignored) pour cette session ; à régénérer.

### 3.4 Issues techniques chopées par les tests d'intégration

- **MLflow refuse les noms de metric avec parenthèses.** Ultralytics émet `metrics/precision(B)` (B = box). MLflow allow-list = `[A-Za-z0-9_\-./ ]`. Fix : `_sanitize_metric_name()` dans `train.py` qui retire `()` et map `/` → `.`.
- **MLflow `log_artifacts(s3://…)` échoue sans `boto3`.** boto3 n'était pas dans le groupe `ml` — ajouté.
- **Mypy strict refuse `np.ndarray` sans generics** dans `scripts/`. Le path `scripts/` (racine) n'était pas dans l'exclusion mypy, contrairement à `ml/scripts/`. Fix : ajout de `scripts/` à `[tool.mypy] exclude`.
- **Compose v4 + v5 simultanés impossibles** sans renommer les containers (cf. 3.1).
- **DVC `${VAR}` substitution** ne marche pas sans `vars:` au top de `dvc.yaml`. CLAUDE.md ne le précise pas ; ajout du bloc `vars: [ml/configs/data.yaml]`.

### 3.5 Workflow & itération

- **L'utilisateur a explicitement demandé `--dangerously-skip-permissions`** (mode `dontAsk` côté harness). Conséquence : Claude ne demande plus pour les actions routinières (commit / push / merge). Conservé l'obligation de demander pour : force-push sur main, rm -rf, deletions de branches non mergées. Documenté en mémoire (`no_friction_for_routine_pushes.md`).
- **CLAUDE.md modifié hors-bande** par l'utilisateur pendant une session : ajout de sections "Workflow Opérationnel" et "Politique d'Autorisation". Plus un typo `1` puis `11` près d'un schéma ASCII. Règle §14 (modifier CLAUDE.md → PR dédiée) respectée via une PR `docs(claude): add operational workflow and authorization policy`. Le typo a été retiré dans la même PR.
- **Pas de mention "Claude" dans les commits** — règle absolue pour la submission académique. Le trailer `Co-Authored-By: Claude` a été nettoyé rétroactivement de tous les commits, y compris du commit initial. Plus aucun trailer ajouté depuis.

---

## 4. Architecture sur disque — où chaque chose vit

```
logivision/
├── CLAUDE.md             ← plan théorique (1500+ lignes, autorité)
├── PROGRESS.md           ← suivi des tâches (statut [ ] [~] [x] [!])
├── JOURNEY.md            ← CE DOCUMENT (récit)
├── README.md             ← quickstart
├── CONTRIBUTING.md       ← branche unique + branch protection
├── Makefile              ← 25 cibles (install, bootstrap, train, promote, ...)
├── pyproject.toml        ← uv workspace, deps groupes [dev] [ml]
├── dvc.yaml              ← pipeline data (extract_frames → prepare_dataset)
├── .env                  ← secrets locaux (gitignored)
│
├── ml/
│   ├── scripts/
│   │   ├── extract_frames.py        ← T1.2.1 vidéo → JPG
│   │   ├── import_annotations.py    ← T1.2.2 CVAT export → YOLO dataset
│   │   ├── train.py                 ← T1.3.1 YOLO + MLflow
│   │   ├── promote_model.py         ← T1.4.1 Registry gate
│   │   ├── export_openvino.py       ← T1.4.2 FP32 + INT8 NNCF
│   │   ├── benchmark_inference.py   ← T1.4.3 latence/FPS/RAM/CPU
│   │   └── compare_archs.py         ← T1.5.1 sweep multi-arch
│   ├── tests/                       ← 50+ tests unit, 2 integration (opt-in)
│   ├── configs/
│   │   ├── data.yaml                ← params pipeline DVC
│   │   ├── yolov8n.yaml             ← hyperparams training
│   │   ├── comparison.yaml          ← archs + augmentations
│   │   └── promotion_thresholds.yaml← gates Staging / Production
│   └── notebooks/
│       └── colab_train_template.ipynb  ← notebook prêt à ouvrir sur Colab
│
├── scripts/
│   ├── bootstrap.sh                 ← démarre la stack + écrit .env + .dvc/config.local
│   ├── gen_synthetic_demo.py        ← génère un mini dataset CVAT-style synthétique
│   └── fetch_pexels_videos.py       ← API Pexels (CC0)
│
├── infra/
│   ├── docker-compose/
│   │   ├── docker-compose.mlops.yml ← Postgres + MinIO + MLflow
│   │   └── docker-compose.cvat.yml  ← CVAT v2.14.4
│   └── docker/
│       ├── mlflow/Dockerfile        ← MLflow custom (mlflow + psycopg2 + boto3)
│       └── postgres/init.sql        ← crée la DB `mlflow` à côté de `logivision`
│
├── tests/integration/               ← smoke tests stack (4 tests, marker integration)
│
├── docs/
│   ├── architecture/adr/
│   │   └── 0003-model-promotion-process.md ← ADR MADR
│   └── mlops/
│       ├── dvc-guide.md
│       ├── annotation-guide.md
│       ├── training-on-colab.md
│       ├── openvino-guide.md         ← (à venir)
│       ├── benchmarks/.gitkeep       ← rapports auto-générés ici
│       └── comparisons/              ← rapports compare_archs ici
│
├── datasets/                        ← gitignored, DVC-tracked
│   ├── raw/
│   │   ├── videos/                  ← 16 mp4 (15 Pexels + 1 TalTech Camera3)
│   │   └── frames/                  ← 531 JPG extraites (16 sous-dossiers)
│   └── processed/                   ← le dataset YOLO prêt à entraîner (créé par import_annotations.py)
│
└── .dvc/                            ← DVC remote = MinIO s3://datasets/dvc-cache
    ├── config                        ← committed
    └── config.local                  ← creds, gitignored
```

---

## 5. Stack en cours d'exécution (`./scripts/bootstrap.sh`)

| Service | URL | Auth | Volumes (persistants) |
|---|---|---|---|
| MLflow | http://localhost:5050 | aucune (local) | `logivision-postgres-data` (via Postgres) + `logivision-minio-data` (via MinIO) |
| MinIO Console | http://localhost:9001 | `logivision` / `change-me-in-local-minimum-8-chars` | `logivision-minio-data` |
| MinIO S3 API | http://localhost:9000 | idem | idem |
| PostgreSQL | `localhost:5432` | `logivision` / `change-me-in-local` | `logivision-postgres-data` |
| (Optionnel) CVAT | http://localhost:8090 après `make cvat-up` | superuser via `manage.py createsuperuser` | 4 volumes `logivision-cvat-*` |

`make down` arrête, `make clean` détruit les volumes.

---

## 6. Commandes de référence

```bash
# Bootstrap (cold start)
make install                 # uv sync, ~10 s
make pre-commit-install      # hooks Git
./scripts/bootstrap.sh       # stack up, < 20 s warm

# Tests
make lint                    # ruff + mypy
make test                    # pytest unit
make test-integration        # pytest -m integration (stack required)

# Data pipeline
make demo-data               # zip synthétique 60 frames
make fetch-videos            # API Pexels (PEXELS_API_KEY required)
uv run python -m ml.scripts.extract_frames --input datasets/raw/videos --output datasets/raw/frames
uv run python -m ml.scripts.import_annotations --input datasets/raw/annotations.zip --output datasets/processed/demo
make pipeline-dag            # affiche le DAG DVC
make pipeline                # `dvc repro`

# Training
make train                   # train YOLOv8n sur `datasets/processed/demo`
make compare-archs           # sweep multi-architecture

# Lifecycle modèle
make promote RUN=<id>        # None -> Staging si seuils OK
make promote-prod RUN=<id>   # Staging -> Production avec --approve
make export-openvino RUN=<id># FP32 + INT8 NNCF -> MLflow
make benchmark RUN=<id>      # rapport Markdown sous docs/mlops/benchmarks/

# DVC
make dvc-push / dvc-pull / dvc-status
```

---

## 7. Métriques actuelles

- **Lignes Python** : ~2 500 (scripts ML + tests + glue)
- **Tests** : 54 collectés, 5 marqués integration. Couverture validée sur les chemins critiques.
- **Commits sur `main`** : ~15 (après nettoyage du gitflow).
- **Services Docker** : 3 (MLOps) + 4 (CVAT optionnel) + 0 (frontend, pas encore commencé).
- **Dépendances Python `ml` group** : ultralytics, torch CPU, opencv-headless, numpy, mlflow, boto3, openvino, nncf, bentoml (en ajout), pyyaml, pillow.

---

## 8. À venir

- **Sprint 1.6** : BentoML serving (next).
- **Sprint 1.7** : Drift monitoring (Evidently) + retraining trigger.
- **Frontend track** (non planifié dans CLAUDE.md, à patcher) : dashboard React/Vite/Tailwind.
- **Phase 2** : streaming Kafka + Flink (après Phase 1 close à 100 %).

---

## 9. Choses qui ne sont PAS encore faites mais devraient

- `make benchmark` n'a jamais produit de vrai rapport — le seul run MLflow réussi n'a pas encore d'export OpenVINO. Solution : `make export-openvino RUN=4f9eb43c…` puis `make benchmark RUN=4f9eb43c…`.
- Aucune annotation réelle sur les 531 frames téléchargées. Tant qu'on n'a pas de labels, `make train` doit pointer sur le dataset synthétique (`datasets/processed/demo/`).
- Branch protection sur `main` côté GitHub — à activer manuellement par l'utilisateur sur https://github.com/Ayalem/logivision_v2/settings/branches.
- Token Pexels et token GitHub partagés en chat — à régénérer.
