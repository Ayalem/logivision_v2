# LOGIVISION — Plan d'Exécution Production-Grade pour Claude Code

> **Pour Claude Code** : ce document est ton plan de travail intégral. Lis-le en entier avant toute action. Chaque phase a un objectif, des fichiers à produire, des commandes à exécuter, et des critères d'acceptation. Tu travailles de manière autonome, tu commit/PR à chaque tâche terminée, tu écris des tests, tu mets à jour la doc. Si une instruction est ambiguë, tu privilégies la solution la plus simple qui satisfait les critères d'acceptation — pas de surengineering.

---

## 0. Méta — Comment utiliser ce document

| Section | Pour quoi |
|---|---|
| §1 | Contexte projet et contraintes dures (lire en premier) |
| §2 | Vue d'ensemble architecture cible |
| §3 | Stack technique exhaustive (versions épinglées) |
| §4 | Structure du monorepo |
| §5 | **PHASE 1 — MLOps Computer Vision (PRIORITÉ ABSOLUE)** |
| §6 | PHASE 2 — Streaming Kafka + Flink |
| §7 | PHASE 3 — Feature Store (Feast) |
| §8 | PHASE 4 — Serving, monitoring, drift |
| §9 | PHASE 5 — Infra, observabilité, CI/CD |
| §10 | Standards de code, tests, commits |
| §11 | Définitions de "Done" |
| §12 | Stratégie d'entraînement sans GPU payant |
| §13 | Glossaire et liens |

**Règle d'or** : la Phase 1 doit être 100% fonctionnelle, testée et déployée *avant* de toucher à la Phase 2. On ne fait pas du parallèle sur des phases qui dépendent l'une de l'autre.

---

## 1. Contexte et Contraintes

### 1.1 Projet

LOGIVISION est un système de surveillance intelligent d'entrepôt basé sur la **Computer Vision** (détection et tracking de boîtes/colis via YOLO + ByteTrack) combiné à la lecture de codes-barres/QR codes. Le système ingère des flux vidéo, détecte les objets, traque les mouvements, détecte des anomalies (boîte stationnaire trop longtemps, intrusion en zone interdite, perte de tracking), et expose le tout via un dashboard temps réel.

### 1.2 Différence avec les versions précédentes

| Aspect | v4 (MVP académique) | **v5 (cette version)** |
|---|---|---|
| Objectif | Démo 6 semaines | **Production-grade, niveau industriel** |
| Stack ML | YOLOv8 + script bash | **MLflow + Registry + CI/CD modèles + drift monitoring** |
| Ingestion | OpenCV direct → FastAPI | **Kafka topics partitionnés + schémas Avro** |
| Traitement | Boucle Python | **Apache Flink (CEP, fenêtrage, état)** |
| Features | Calculées à la volée | **Feast Feature Store (online Redis + offline Parquet)** |
| Déploiement | Docker Compose | **K3s + Helm + ArgoCD (GitOps)** |
| Observabilité | Logs print | **Stack LGTM (Loki, Grafana, Tempo, Mimir/Prometheus)** |
| Budget | "On-premise, CPU" | **0€ de licence, GPU gratuit uniquement (Colab/Kaggle)** |

### 1.3 Contraintes dures (non négociables)

- **Budget = 0€** : aucun service payant. Pas de Roboflow payant, pas de Weights & Biases Pro, pas de SageMaker, pas d'AWS, pas d'Azure ML. Uniquement open-source self-hosted.
- **GPU = gratuit uniquement** : Google Colab (free tier, T4 ~12h/jour), Kaggle (30h/sem P100), entraînement local CPU pour fine-tuning incrémental.
- **Stack 100% open-source** : tout doit pouvoir tourner sur un laptop dev + un mini-serveur on-prem (16-32 GB RAM, CPU only en prod).
- **Reproductibilité** : tout run d'entraînement doit être réexécutable à l'identique depuis un commit Git (data + code + config versionnés).
- **Pas de secret hardcodé** : tout via `.env`, Vault dev mode ou Sealed Secrets en prod.

### 1.4 Modèle CV utilisé

**YOLOv8n** (nano, ~3M params, ~6MB) en baseline. Pourquoi :
- Suffisant pour 2-4 caméras à 640×480 sur CPU avec OpenVINO (15-25 FPS sur i5/i7).
- License AGPL-3.0 — OK pour projet open-source.
- Bonus : on évalue **YOLOv11n** et **RT-DETR-S** dans la Phase 1.5 (benchmarks).

Tracking : **ByteTrack** (license MIT) intégré via le module officiel d'Ultralytics.

---

## 2. Architecture Cible

### 2.1 Vue logique (flux de données)

```
┌────────────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Caméras      │────▶│  MediaMTX   │────▶│ Frame Grabber│────▶│   Kafka     │
│ (smartphones,  │RTSP │ (relay RTSP)│RTSP │ (Python svc) │     │  Topics:    │
│  IP cams)      │     └─────────────┘     └──────────────┘     │ raw-frames  │
└────────────────┘                                              │ detections  │
                                                                │ tracks      │
                                                                │ events      │
                                                                └──────┬──────┘
                                                                       │
                          ┌────────────────────────────────────────────┤
                          ▼                                            ▼
                   ┌─────────────┐                              ┌─────────────┐
                   │   Flink     │                              │  Inference  │
                   │  Jobs:      │                              │  Service    │
                   │ - detect    │◀─── lit raw-frames           │ (YOLO+      │
                   │ - track     │     publie detections        │  ByteTrack  │
                   │ - CEP       │     publie tracks/events     │  OpenVINO)  │
                   └──────┬──────┘                              └──────┬──────┘
                          │                                            │
                          │ features online                            │ écrit
                          ▼                                            ▼
                   ┌─────────────┐                              ┌─────────────┐
                   │   Feast     │                              │  PostgreSQL │
                   │ Online:Redis│                              │ + ClickHouse│
                   │ Offline:S3  │                              │ (analytics) │
                   └─────────────┘                              └─────────────┘
                          │
                          ▼
                   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                   │  FastAPI    │────▶│  Frontend   │     │   MLflow    │
                   │  Backend    │ WS  │  React +    │     │  Tracking + │
                   │  + WebSocket│     │  Vite       │     │  Registry   │
                   └─────────────┘     └─────────────┘     └─────────────┘
```

### 2.2 Pattern Kappa (vs Lambda)

Choix : **Kappa**. Un seul pipeline streaming (Kafka + Flink). Le rejeu historique se fait en relisant les topics Kafka avec une retention de 7 jours (configurable). Pas de couche batch séparée — les "vues batch" sont matérialisées par des jobs Flink batch-mode sur les mêmes topics.

**Justification** : moins de duplication de code (un seul codebase de transformations), moins d'incohérences batch/stream, plus simple à opérer à 5 personnes. Le surcoût en complexité de streaming est absorbé par Flink qui gère natif.

### 2.3 Couche MLOps (zoom)

```
┌──────────────────────────────────────────────────────────────────┐
│                       BOUCLE MLOps                                │
│                                                                   │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────┐│
│  │ Données    │───▶│ Annotation │───▶│  Training  │───▶│ Eval   ││
│  │ (vidéos    │    │ (CVAT      │    │ (Colab +   │    │ + Bench││
│  │  + frames) │    │  self-host)│    │  MLflow)   │    │        ││
│  └─────┬──────┘    └────────────┘    └─────┬──────┘    └───┬────┘│
│        │                                    │               │     │
│        │ DVC                                │ MLflow        │     │
│        ▼                                    ▼               ▼     │
│  ┌────────────┐                      ┌─────────────┐  ┌─────────┐│
│  │ MinIO (S3) │                      │   Model     │  │ Drift   ││
│  │ datasets/  │                      │  Registry   │  │ (Evidently)
│  │ models/    │                      │  Stages:    │  │         ││
│  └────────────┘                      │  None→Stage │  └────┬────┘│
│                                      │  →Prod      │       │     │
│                                      └──────┬──────┘       │     │
│                                             │              │     │
│                                             ▼              ▼     │
│                                      ┌─────────────┐  ┌─────────┐│
│                                      │  BentoML    │◀─│ Trigger ││
│                                      │  Serving    │  │ retrain ││
│                                      └─────────────┘  └─────────┘│
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Stack Technique (versions épinglées)

> Claude Code : utilise ces versions exactes dans les `requirements.txt`, `package.json`, `Dockerfile`, etc. Si une version a une faille connue, tu fais une PR séparée pour la bump après avoir vérifié la compatibilité.

### 3.1 Computer Vision & ML

| Composant | Version | Rôle |
|---|---|---|
| `ultralytics` | 8.3.x | YOLOv8/v11 training + inference |
| `torch` | 2.4.x (CPU) / 2.4.x+cu121 (Colab) | Backend deep learning |
| `openvino` | 2024.4.x | Optimisation inference CPU (3-5× speedup) |
| `opencv-python-headless` | 4.10.x | Video IO, preprocessing |
| `supervision` | 0.24.x | Annotations, ByteTrack wrapper |
| `albumentations` | 1.4.x | Data augmentation |

### 3.2 MLOps

| Composant | Version | Rôle |
|---|---|---|
| `mlflow` | 2.17.x | Tracking + Registry (self-hosted) |
| `dvc` | 3.55.x | Versioning data + models |
| `bentoml` | 1.3.x | Packaging et serving modèles |
| `evidently` | 0.4.x | Data/model drift |
| `whylogs` | 1.5.x | Profiling données (alternative drift) |
| `prefect` | 3.0.x | Orchestration workflows (lieu d'Airflow, plus simple) |
| `feast` | 0.40.x | Feature Store |

### 3.3 Streaming & Big Data

| Composant | Version | Rôle |
|---|---|---|
| Apache Kafka | 3.8.x (KRaft, no ZK) | Bus de messages |
| `confluent-kafka` (python) | 2.5.x | Producer/consumer Python |
| Apache Flink | 1.20.x | Stream processing + CEP |
| `pyflink` | 1.20.x | API Python Flink |
| Schema Registry (Apicurio) | 3.0.x | Schémas Avro (alt open à Confluent SR) |
| MediaMTX | 1.9.x | Relais RTSP/RTMP/WebRTC |

### 3.4 Stockage

| Composant | Version | Rôle |
|---|---|---|
| MinIO | RELEASE.2024-10-x | Object storage S3-compatible |
| PostgreSQL | 16.x | Métadonnées (MLflow, Feast, app) |
| Redis | 7.4.x | Cache + Feast online store |
| ClickHouse | 24.8.x | OLAP analytics (événements, KPIs) |

### 3.5 Backend / Frontend

| Composant | Version | Rôle |
|---|---|---|
| Python | 3.11.x | Backend services |
| FastAPI | 0.115.x | API REST + WebSocket |
| Pydantic | 2.9.x | Validation |
| SQLAlchemy | 2.0.x | ORM |
| Alembic | 1.13.x | Migrations DB |
| Node.js | 20 LTS | Build frontend |
| React | 18.3.x | UI |
| Vite | 5.4.x | Bundler |
| TailwindCSS | 3.4.x | Styling |
| TanStack Query | 5.59.x | Data fetching |
| Recharts | 2.13.x | Charts |

### 3.6 Infra & Observabilité

| Composant | Version | Rôle |
|---|---|---|
| Docker | 27.x | Conteneurs |
| Docker Compose | v2.29.x | Orchestration dev |
| K3s | v1.31.x | Kubernetes léger prod |
| Helm | 3.16.x | Packaging K8s |
| ArgoCD | 2.12.x | GitOps |
| Prometheus | 2.55.x | Métriques |
| Grafana | 11.3.x | Dashboards |
| Loki | 3.2.x | Logs |
| Tempo | 2.6.x | Traces |
| OpenTelemetry Collector | 0.111.x | Pipeline observabilité |
| Traefik | 3.1.x | Reverse proxy + TLS |

### 3.7 CI/CD & Qualité

| Composant | Rôle |
|---|---|
| GitHub Actions | CI/CD principal |
| `pre-commit` | Hooks Git locaux |
| `ruff` 0.7.x | Lint + format Python |
| `mypy` 1.13.x | Type checking Python |
| `pytest` 8.3.x | Tests Python |
| `vitest` 2.1.x | Tests frontend |
| `playwright` 1.48.x | Tests E2E |
| `trivy` | Scan vulnérabilités images |
| `dvc` + `cml` | CI pour modèles ML |

---

## 4. Structure du Monorepo

```
logivision/
├── .github/
│   ├── workflows/
│   │   ├── ci-backend.yml
│   │   ├── ci-frontend.yml
│   │   ├── ci-ml.yml              # entraînement déclenché sur PR avec [train]
│   │   ├── cd-staging.yml
│   │   ├── cd-prod.yml
│   │   └── security-scan.yml
│   └── ISSUE_TEMPLATE/
├── .dvc/                          # config DVC
├── docs/
│   ├── architecture/
│   │   ├── adr/                   # Architecture Decision Records
│   │   ├── c4-context.md
│   │   ├── c4-container.md
│   │   └── data-flow.md
│   ├── mlops/
│   │   ├── training-guide.md
│   │   ├── model-registry.md
│   │   └── drift-monitoring.md
│   ├── runbooks/
│   │   ├── incident-no-detections.md
│   │   ├── incident-kafka-lag.md
│   │   └── retraining-procedure.md
│   └── api/                       # OpenAPI specs
│
├── services/
│   ├── frame-grabber/             # RTSP → Kafka
│   │   ├── app/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── inference/                 # YOLO + ByteTrack → Kafka
│   │   ├── app/
│   │   ├── tests/
│   │   ├── models/                # .gitignored, géré par DVC
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── flink-jobs/                # Jobs CEP, agrégations
│   │   ├── jobs/
│   │   │   ├── detection_enrichment.py
│   │   │   ├── stationary_detection.py
│   │   │   └── zone_violation.py
│   │   ├── tests/
│   │   └── Dockerfile
│   ├── api/                       # FastAPI principal
│   │   ├── app/
│   │   │   ├── routers/
│   │   │   ├── models/
│   │   │   ├── services/
│   │   │   └── ws/
│   │   ├── tests/
│   │   ├── alembic/
│   │   └── Dockerfile
│   ├── feature-server/            # Feast feature server
│   │   ├── feature_repo/
│   │   └── Dockerfile
│   ├── model-server/              # BentoML serving
│   │   ├── service.py
│   │   ├── bentofile.yaml
│   │   └── Dockerfile
│   └── drift-monitor/             # Evidently job périodique
│       ├── app/
│       └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── lib/
│   ├── public/
│   ├── tests/
│   ├── package.json
│   └── vite.config.ts
│
├── ml/
│   ├── notebooks/                 # Colab notebooks (.ipynb)
│   │   ├── 01_data_exploration.ipynb
│   │   ├── 02_baseline_yolov8n.ipynb
│   │   ├── 03_hyperparam_search.ipynb
│   │   └── 04_model_comparison.ipynb
│   ├── pipelines/                 # Prefect flows
│   │   ├── training_flow.py
│   │   ├── eval_flow.py
│   │   └── drift_flow.py
│   ├── scripts/
│   │   ├── prepare_dataset.py
│   │   ├── train.py
│   │   ├── eval.py
│   │   ├── export_openvino.py
│   │   └── register_model.py
│   ├── configs/
│   │   ├── data.yaml              # paths datasets
│   │   ├── yolov8n.yaml           # hyperparams
│   │   └── yolov11n.yaml
│   └── dvc.yaml                   # pipeline DVC
│
├── datasets/                      # tracked by DVC, .gitignored content
│   ├── raw/
│   ├── processed/
│   └── annotations/
│
├── infra/
│   ├── docker-compose/
│   │   ├── docker-compose.dev.yml
│   │   ├── docker-compose.kafka.yml
│   │   ├── docker-compose.mlops.yml
│   │   ├── docker-compose.observability.yml
│   │   └── docker-compose.full.yml
│   ├── k8s/
│   │   ├── base/
│   │   ├── overlays/
│   │   │   ├── staging/
│   │   │   └── prod/
│   │   └── helm/
│   │       ├── logivision/
│   │       └── values-*.yaml
│   ├── argocd/
│   │   └── applications/
│   ├── flink/
│   │   ├── conf/
│   │   └── Dockerfile
│   ├── kafka/
│   │   ├── schemas/               # Avro .avsc
│   │   └── topics.yaml
│   ├── mediamtx/
│   │   └── mediamtx.yml
│   ├── nginx/
│   ├── grafana/
│   │   ├── dashboards/
│   │   └── provisioning/
│   ├── prometheus/
│   ├── loki/
│   └── opentelemetry/
│
├── scripts/                       # scripts shell racine
│   ├── bootstrap.sh
│   ├── seed-data.sh
│   ├── run-training-colab.sh
│   └── deploy-staging.sh
│
├── tests/
│   ├── integration/
│   └── e2e/                       # Playwright
│
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .dockerignore
├── Makefile                       # commandes raccourcis
├── README.md
├── CONTRIBUTING.md
├── CLAUDE.md                      # CE FICHIER
├── LICENSE
└── pyproject.toml                 # workspace racine (uv/rye)
```

---

## 5. PHASE 1 — MLOps Computer Vision (PRIORITÉ ABSOLUE)

> **Durée estimée** : 3 à 4 semaines de boulot Claude Code à plein temps.
> **Objectif** : à la fin de cette phase, on peut entraîner YOLO sur Colab, logguer tout dans MLflow, promouvoir un modèle dans le Registry, le servir via BentoML, mesurer la dérive en production. **Sans aucune dépendance à Kafka/Flink/Feast** — ceux-là viennent en Phase 2-3.

### 5.1 Vue d'ensemble Phase 1

```
Sprint 1.1  →  Setup repo, infra MLOps locale (MLflow, MinIO, DVC, Postgres)
Sprint 1.2  →  Pipeline data : collecte, annotation, versioning
Sprint 1.3  →  Pipeline training : YOLOv8n baseline + tracking MLflow
Sprint 1.4  →  Model registry + promotion automatisée + export OpenVINO
Sprint 1.5  →  Benchmarks (YOLOv8n vs YOLOv11n vs RT-DETR-S)
Sprint 1.6  →  Serving BentoML + tests de charge
Sprint 1.7  →  Drift monitoring (Evidently) + retraining trigger
```

### 5.2 Sprint 1.1 — Bootstrap MLOps Stack

#### Tâches

**T1.1.1 — Init repo + outillage**

Fichiers à créer :
- `pyproject.toml` racine avec `uv` comme package manager (plus rapide que pip/poetry).
- `.pre-commit-config.yaml` avec : `ruff`, `mypy`, `trailing-whitespace`, `end-of-file-fixer`, `detect-secrets`, `gitleaks`.
- `Makefile` avec cibles : `make install`, `make lint`, `make test`, `make up`, `make down`, `make train`, `make eval`.
- `.gitignore` complet (Python, Node, IDE, ML artifacts, secrets, datasets bruts).
- `.env.example` documentant toutes les vars d'env nécessaires.
- `README.md` racine : pitch projet + quickstart 5 commandes.
- `CONTRIBUTING.md` : workflow Git (Gitflow simplifié : `main`, `develop`, `feature/*`, `fix/*`, `chore/*`), convention commit (Conventional Commits), template PR.

Commandes :
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv init logivision --package
uv add --dev ruff mypy pytest pytest-cov pytest-asyncio pre-commit
pre-commit install
git init && git checkout -b develop
```

Critères d'acceptation :
- `make install` installe tout en < 60s (uv est ultra-rapide).
- `make lint` passe sans erreur sur un fichier vide.
- `pre-commit run --all-files` passe.
- README explique le projet en < 200 mots et liste les commandes principales.

**T1.1.2 — Stack MLOps locale via Docker Compose**

Fichier : `infra/docker-compose/docker-compose.mlops.yml`.

Services à inclure :
- `postgres` (port 5432) — DB pour MLflow + app.
- `minio` (port 9000 API, 9001 console) — object storage avec bucket `mlflow` et `datasets`.
- `mlflow` (port 5000) — backend Postgres, artifact store MinIO.
- `pgadmin` (port 5050, optionnel) — pour debug DB.

Détails :
- MLflow utilise l'image `ghcr.io/mlflow/mlflow:v2.17.0` étendue avec `psycopg2-binary` et `boto3`.
- Healthchecks sur tous les services.
- Volumes nommés pour persistance.
- Network `logivision-net` dédié.
- Variables d'env via `.env` (jamais hardcodées).

Script `scripts/bootstrap.sh` qui :
1. Crée le `.env` à partir de `.env.example` s'il n'existe pas.
2. Démarre la stack : `docker compose -f infra/docker-compose/docker-compose.mlops.yml up -d`.
3. Attend les healthchecks (boucle avec timeout 120s).
4. Crée les buckets MinIO via `mc` (MinIO client) : `mlflow`, `datasets`, `models`.
5. Affiche les URLs des UIs.

Critères d'acceptation :
- `./scripts/bootstrap.sh` démarre tout en < 90s sur un laptop standard.
- MLflow UI accessible sur `http://localhost:5000`, sans erreur dans les logs.
- MinIO console accessible, buckets visibles.
- `make down` arrête tout proprement, `make clean` purge les volumes (avec confirmation).
- Un test smoke `tests/integration/test_mlops_stack.py` qui ping chaque service.

**T1.1.3 — Setup DVC**

Fichiers :
- `.dvc/config` configuré avec remote MinIO :
  ```ini
  [core]
      remote = minio
  ['remote "minio"']
      url = s3://datasets/dvc-cache
      endpointurl = http://localhost:9000
      access_key_id = ${MINIO_ACCESS_KEY}
      secret_access_key = ${MINIO_SECRET_KEY}
  ```
- `dvc.yaml` initial vide (sera rempli au Sprint 1.3).
- `.dvcignore`.

Commandes :
```bash
uv add --dev dvc[s3]
dvc init
dvc remote add -d minio s3://datasets/dvc-cache
dvc remote modify minio endpointurl http://localhost:9000
dvc remote modify minio --local access_key_id ${MINIO_ACCESS_KEY}
dvc remote modify minio --local secret_access_key ${MINIO_SECRET_KEY}
```

Critères d'acceptation :
- `dvc status` répond sans erreur.
- Documentation `docs/mlops/dvc-guide.md` rédigée : comment ajouter un dataset, comment puller.

### 5.3 Sprint 1.2 — Pipeline Données

#### Tâches

**T1.2.1 — Collecte vidéo et frame extraction**

Script `ml/scripts/extract_frames.py` :
- Input : un dossier de vidéos `datasets/raw/videos/` (mp4, mov).
- Output : frames JPG dans `datasets/raw/frames/{video_id}/frame_{n:06d}.jpg`.
- Args : `--fps` (défaut 2, on extrait pas toutes les frames sinon trop redondant), `--max-frames-per-video`, `--resize` (défaut 640).
- Métadonnées : un `manifest.jsonl` listant chaque frame avec son timestamp, vidéo source, dimensions.
- Reproductible : seed déterministe pour le sampling.

Tests : `tests/test_extract_frames.py` avec une vidéo factice générée par OpenCV (10 frames de couleurs unies).

**T1.2.2 — Annotation avec CVAT self-hosted**

Fichier `infra/docker-compose/docker-compose.cvat.yml` : déploie CVAT en local (port 8080).

Procédure documentée dans `docs/mlops/annotation-guide.md` :
1. Créer une organisation CVAT.
2. Importer les frames.
3. Définir les labels : `box`, `person`, `forklift`, `qr_code`, `barcode`, `pallet` (configurable).
4. Annoter (équipe humaine — pas Claude Code).
5. Exporter au format YOLO (zip).

Script `ml/scripts/import_annotations.py` :
- Décompresse l'export CVAT.
- Valide la structure (split train/val/test 70/15/15 par défaut, configurable).
- Convertit au format YOLO standard : `images/{split}/`, `labels/{split}/`.
- Génère le `data.yaml` Ultralytics correspondant.
- Vérifie : ratio classes, distribution tailles bbox, frames sans label (warning).
- Output dans `datasets/processed/dataset_v{N}/`.

Tests : annotations factices + assertion sur la structure de sortie.

**T1.2.3 — Versioning DVC du dataset**

Pipeline DVC dans `ml/dvc.yaml` :
```yaml
stages:
  extract_frames:
    cmd: python ml/scripts/extract_frames.py --input datasets/raw/videos --output datasets/raw/frames --fps 2
    deps:
      - datasets/raw/videos
      - ml/scripts/extract_frames.py
    outs:
      - datasets/raw/frames
  
  prepare_dataset:
    cmd: python ml/scripts/import_annotations.py --input datasets/raw/annotations.zip --output datasets/processed/current
    deps:
      - datasets/raw/annotations.zip
      - datasets/raw/frames
      - ml/scripts/import_annotations.py
    outs:
      - datasets/processed/current
    params:
      - ml/configs/data.yaml:split
```

Critères d'acceptation Sprint 1.2 :
- `dvc repro` regénère le dataset à partir des vidéos brutes.
- `dvc push` synchronise vers MinIO.
- Sur un autre poste, `git clone && dvc pull` récupère exactement le même dataset.
- Tests passent en CI.
- Doc complète dans `docs/mlops/data-pipeline.md`.

### 5.4 Sprint 1.3 — Pipeline Training avec MLflow

#### Tâches

**T1.3.1 — Script d'entraînement YOLOv8n**

Fichier `ml/scripts/train.py`. Structure attendue :

```python
"""
Train YOLOv8n on warehouse dataset with MLflow tracking.

Usage:
    python ml/scripts/train.py --config ml/configs/yolov8n.yaml
    
On Colab:
    !python ml/scripts/train.py --config ml/configs/yolov8n.yaml --device cuda
"""
import argparse
from pathlib import Path

import mlflow
import mlflow.pytorch
import yaml
from ultralytics import YOLO

from logivision.ml.utils import (
    get_git_commit,
    log_dataset_artifacts,
    log_model_artifacts,
    setup_mlflow,
)


def train(config: dict) -> dict:
    setup_mlflow(
        tracking_uri=config["mlflow"]["tracking_uri"],
        experiment_name=config["mlflow"]["experiment"],
    )
    
    with mlflow.start_run() as run:
        # 1. Log config + git commit + dataset version (DVC hash)
        mlflow.log_params(config["hyperparameters"])
        mlflow.set_tags({
            "git_commit": get_git_commit(),
            "dataset_version": Path("datasets/processed/current.dvc").read_text(),
            "model_arch": config["model"]["arch"],
            "framework": "ultralytics",
        })
        
        # 2. Train
        model = YOLO(config["model"]["weights"])  # 'yolov8n.pt' (pretrained COCO)
        results = model.train(
            data=config["data"]["yaml_path"],
            epochs=config["hyperparameters"]["epochs"],
            imgsz=config["hyperparameters"]["imgsz"],
            batch=config["hyperparameters"]["batch"],
            device=config["runtime"]["device"],
            project=config["runtime"]["output_dir"],
            name=run.info.run_id,
            exist_ok=True,
            patience=config["hyperparameters"]["patience"],
            optimizer=config["hyperparameters"]["optimizer"],
            lr0=config["hyperparameters"]["lr0"],
            seed=config["hyperparameters"]["seed"],
        )
        
        # 3. Log metrics (final + per-epoch)
        for epoch_metrics in results.results_dict.items():
            mlflow.log_metric(epoch_metrics[0], epoch_metrics[1])
        
        # 4. Log artifacts : weights, confusion matrix, sample predictions
        log_model_artifacts(results.save_dir)
        
        # 5. Validation finale + log metrics
        val_results = model.val(data=config["data"]["yaml_path"])
        mlflow.log_metrics({
            "val_map50": val_results.box.map50,
            "val_map50_95": val_results.box.map,
            "val_precision": val_results.box.mp,
            "val_recall": val_results.box.mr,
        })
        
        # 6. Log model via mlflow.pytorch (avec signature inférée)
        mlflow.pytorch.log_model(
            pytorch_model=model.model,
            artifact_path="model",
            registered_model_name="logivision-detector",
        )
        
        return {
            "run_id": run.info.run_id,
            "map50": val_results.box.map50,
            "map50_95": val_results.box.map,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    
    config = yaml.safe_load(args.config.read_text())
    result = train(config)
    print(f"Training done: {result}")


if __name__ == "__main__":
    main()
```

Config `ml/configs/yolov8n.yaml` :
```yaml
mlflow:
  tracking_uri: http://localhost:5000
  experiment: warehouse-detection

model:
  arch: yolov8n
  weights: yolov8n.pt  # pretrained COCO

data:
  yaml_path: datasets/processed/current/data.yaml

hyperparameters:
  epochs: 100
  imgsz: 640
  batch: 16
  patience: 20
  optimizer: AdamW
  lr0: 0.001
  seed: 42

runtime:
  device: cpu  # override en CLI pour Colab : --device cuda
  output_dir: ml/runs
```

**T1.3.2 — Tests du script de training**

`ml/tests/test_train.py` :
- Mock MLflow et Ultralytics.
- Vérifie que tous les params/tags/metrics attendus sont loggés.
- Test d'intégration léger : 1 epoch sur 10 images factices, vérifie qu'un run MLflow est créé.

**T1.3.3 — Doc "Comment entraîner sur Colab gratuit"**

`docs/mlops/training-on-colab.md` doit expliquer :

1. **Setup Colab** : monter Google Drive, cloner le repo, installer uv, installer deps.
2. **Tunnel MLflow** : utiliser `ngrok` (free tier) ou `cloudflared` (free) pour exposer le MLflow local du laptop vers Colab. Procédure step-by-step.
3. **Alternative recommandée** : MLflow tracking serveur déployé temporairement sur un VPS gratuit (Oracle Cloud Free Tier, fly.io free), ou local + tunnel.
4. **Récupérer les artifacts** : `dvc pull` au début, push des poids entraînés à la fin.
5. **Gestion sessions Colab** (12h max free) : checkpoints toutes les 10 epochs, reprise possible.
6. **Kaggle alternative** : 30h/sem P100, intégration similaire.

Critères d'acceptation Sprint 1.3 :
- `python ml/scripts/train.py --config ml/configs/yolov8n.yaml` lance un run, log dans MLflow.
- Le run apparaît dans l'UI MLflow avec : params, metrics, tags, artifacts (poids `best.pt`, `last.pt`, matrices, exemples).
- Le modèle est registered sous `logivision-detector` au stage `None`.
- Tests unitaires + intégration passent.
- Procédure Colab testée et documentée (un screencast/screenshots dans la doc).

### 5.5 Sprint 1.4 — Model Registry + Promotion + Export

#### Tâches

**T1.4.1 — Stages Registry et workflow de promotion**

MLflow Model Registry est utilisé avec les stages :
- `None` → modèle fraîchement entraîné, non validé.
- `Staging` → modèle ayant passé la validation auto (métriques + tests).
- `Production` → modèle actuellement servi.
- `Archived` → ancien modèle de prod, gardé pour rollback.

Script `ml/scripts/promote_model.py` :
- Input : `--run-id` ou `--version`.
- Vérifie que les seuils sont atteints : `val_map50 >= 0.65`, `val_map50_95 >= 0.40` (configurables dans `ml/configs/promotion_thresholds.yaml`).
- Si OK et stage actuel = `None` → passe à `Staging`.
- Pour passer à `Production` : nécessite `--approve` explicite + référence à un test E2E réussi (CI doit avoir vert).

**T1.4.2 — Export OpenVINO**

Script `ml/scripts/export_openvino.py` :
- Récupère un modèle du registry à un stage donné (défaut `Production`).
- Exporte au format OpenVINO IR (FP32 et INT8 quantifié).
- Pour INT8 : utilise un dataset de calibration (200 images aléatoires du train set).
- Logue les modèles exportés comme artifacts du même run MLflow.
- Compare la mAP avant/après quantification, log la différence.
- Si dégradation > 5% sur mAP50, abort et log une alerte.

```python
# pseudo-code clé
from ultralytics import YOLO
import openvino as ov

model = YOLO("best.pt")
model.export(format="openvino", imgsz=640, half=False)  # FP32

# Quantification INT8 avec NNCF
import nncf
core = ov.Core()
fp32_model = core.read_model("best_openvino_model/best.xml")
calibration_dataset = nncf.Dataset(calibration_loader, transform_fn)
int8_model = nncf.quantize(fp32_model, calibration_dataset)
ov.save_model(int8_model, "best_int8.xml")
```

**T1.4.3 — Benchmark inference**

Script `ml/scripts/benchmark_inference.py` :
- Charge 3 versions du modèle : PyTorch `.pt`, OpenVINO FP32, OpenVINO INT8.
- Mesure sur 100 images : latence p50/p95/p99, FPS, RAM, CPU%.
- Tableau Markdown généré dans `docs/mlops/benchmarks/run_{date}.md`.
- Tableau Recharts injecté dans le dashboard.

Critères d'acceptation Sprint 1.4 :
- Workflow de promotion testé sur 2 modèles factices (un qui passe, un qui échoue).
- Modèles OpenVINO exportés et benchmarkés.
- Le speedup INT8 vs PyTorch CPU documenté (attendu : 3-5×).
- ADR `docs/architecture/adr/0003-model-promotion-process.md` rédigé.

### 5.6 Sprint 1.5 — Comparaison de modèles

#### Tâches

**T1.5.1 — Entraînement de plusieurs architectures**

Notebooks Colab dans `ml/notebooks/04_model_comparison.ipynb` :
- YOLOv8n
- YOLOv11n
- RT-DETR-l (si la mémoire Colab le permet, sinon RT-DETR-s)
- (Bonus) YOLOv10n

Tous avec les mêmes hyperparams (epochs, batch, seed) sur le même split DVC.

**T1.5.2 — Étude d'ablation**

Notebook `ml/notebooks/03_hyperparam_search.ipynb` :
- Optuna integration avec MLflow.
- Search space : lr0, batch, optimizer, augmentations (mosaic, mixup).
- 20-30 trials, garder le best.
- Tableau de Pareto front (mAP vs FPS).

**T1.5.3 — Rapport de comparaison**

`docs/mlops/model-comparison.md` :
- Tableau metrics + latence + taille.
- Choix justifié pour la production (probablement YOLOv8n INT8 si CPU only, ou YOLOv11n FP32 si on a un peu de GPU).
- Liens vers les runs MLflow correspondants.

Critères d'acceptation Sprint 1.5 :
- ≥ 3 architectures comparées sur le même dataset.
- Hyperparam search effectué et logué dans MLflow.
- Rapport markdown commit avec graphiques (sauvegardés en png dans `docs/mlops/assets/`).

### 5.7 Sprint 1.6 — Serving avec BentoML

#### Tâches

**T1.6.1 — Service BentoML**

Fichier `services/model-server/service.py` :

```python
import bentoml
from bentoml.io import Image, JSON
from pydantic import BaseModel
from typing import List
import numpy as np
from openvino.runtime import Core


class Detection(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]


class InferenceResponse(BaseModel):
    detections: List[Detection]
    inference_ms: float
    model_version: str


@bentoml.service(
    resources={"cpu": "2"},
    traffic={"timeout": 10},
)
class WarehouseDetector:
    """YOLO + OpenVINO detector served via BentoML."""

    def __init__(self) -> None:
        # Charge le modèle depuis MLflow Registry au stage Production
        import mlflow.pyfunc
        self.model_version = self._load_from_registry()
        self.core = Core()
        # ... load OpenVINO model
        
    def _load_from_registry(self) -> str:
        # Logique : lit MLFLOW_TRACKING_URI, récupère
        # logivision-detector @ Production, download artifacts
        ...

    @bentoml.api
    def detect(self, image: Image) -> InferenceResponse:
        ...
```

`services/model-server/bentofile.yaml` :
```yaml
service: "service:WarehouseDetector"
labels:
  owner: logivision-team
  project: detection
include:
  - "*.py"
python:
  packages:
    - openvino==2024.4.0
    - opencv-python-headless==4.10.0.84
    - numpy==1.26.4
    - mlflow==2.17.0
docker:
  python_version: "3.11"
  distro: debian
```

**T1.6.2 — Tests de charge**

Script `tests/load/k6-inference.js` (k6 est gratuit, OSS) :
- Scénarios : 1, 5, 10, 50 utilisateurs concurrents.
- Métriques : latence p95, RPS, taux d'erreur.
- Seuils d'échec : p95 > 500ms ou error rate > 1% → fail.
- Output : rapport JSON + HTML.

Doc `docs/mlops/load-test-results.md` avec courbes.

**T1.6.3 — Container et déploiement**

```bash
bentoml build
bentoml containerize warehouse_detector:latest
# Image OCI poussée vers registry interne (ghcr.io/logivision/model-server)
```

Helm chart dans `infra/k8s/helm/logivision/templates/model-server.yaml` avec :
- Deployment, Service, HPA (autoscale CPU > 70%).
- ConfigMap pour MLFLOW_TRACKING_URI.
- Secret pour MinIO credentials.
- ServiceMonitor pour Prometheus.

Critères d'acceptation Sprint 1.6 :
- `bentoml serve` lance le service local, `curl -F image=@test.jpg http://localhost:3000/detect` retourne du JSON valide.
- Tests de charge passent les seuils.
- Service déployable sur K3s local (test fait dans la PR).

### 5.8 Sprint 1.7 — Drift Monitoring + Retraining Trigger

#### Tâches

**T1.7.1 — Drift Detection avec Evidently**

Service `services/drift-monitor/` :
- Job Prefect périodique (toutes les 6h).
- Compare la distribution des features des **dernières 24h** vs le **dataset de référence** (snapshot DVC).
- Features monitorées :
  - **Sur les inputs** : luminosité moyenne des frames, contraste, taille moyenne des bbox détectées, nombre de détections par frame.
  - **Sur les outputs** : distribution des classes, score de confiance moyen, ratio de détections rejetées (confiance < seuil).
- Métriques Evidently : Population Stability Index (PSI), Jensen-Shannon, Wasserstein selon le type.
- Rapport HTML stocké dans MinIO, lien dans le dashboard.

**T1.7.2 — Alerting**

- Si drift détecté sur ≥ 2 features critiques → publish event `model.drift.detected` dans un topic Kafka (Phase 2) ou simplement webhook + email pour la Phase 1.
- Métrique Prometheus `logivision_drift_score{feature="..."}` exportée.
- Alerte Grafana qui fire un webhook.

**T1.7.3 — Retraining trigger**

Workflow GitHub Action `.github/workflows/retrain-on-drift.yml` :
- Triggered manuellement ou via repository_dispatch event (envoyé par le drift monitor).
- Pull le dernier dataset DVC (incluant les nouvelles données labelisées).
- Lance le training (sur Colab via GitHub Action qui call un script de soumission Colab, ou local CPU pour fine-tuning).
- Si nouveau modèle > ancien modèle sur le validation set → auto-promote en Staging, ouvre une PR pour approbation Production.

Critères d'acceptation Sprint 1.7 :
- Drift simulé (injection de frames sombres) déclenche bien une alerte.
- Le rapport Evidently est consultable depuis le dashboard.
- Le workflow de retraining est documenté dans `docs/runbooks/retraining-procedure.md`.

### 5.9 Définition de "Done" Phase 1

La Phase 1 est terminée quand **toutes** ces affirmations sont vraies :

- [ ] Un développeur peut cloner le repo, lancer `make bootstrap`, et avoir la stack MLOps complète qui tourne en < 5 minutes.
- [ ] Un dataset peut être ajouté, annoté, versionné DVC, et un training reproductible peut être lancé.
- [ ] Tous les runs sont trackés dans MLflow avec params, metrics, artifacts, tags (git_commit + dvc_hash).
- [ ] Le Model Registry contient au moins 1 modèle en stage `Production`.
- [ ] Le service de serving fonctionne, est testé en charge, et est déployé sur K3s local.
- [ ] Le drift monitoring tourne et a détecté au moins un drift simulé en test.
- [ ] La couverture de tests > 70% sur le code Python.
- [ ] La CI GitHub Actions passe sur `develop` et `main`.
- [ ] La doc est à jour : 1 ADR par décision majeure, runbooks pour les opérations courantes.
- [ ] **Aucun service payant n'est utilisé**. Audit fait dans `docs/cost-audit.md`.

---

## 6. PHASE 2 — Streaming Kafka + Flink

> **Durée estimée** : 2 semaines.
> **Prérequis** : Phase 1 DONE. Modèle en Production dans Registry, service BentoML opérationnel.
> **Objectif** : remplacer l'appel direct HTTP au model-server par un pipeline streaming Kafka → Flink → Kafka → consommateurs.

### 6.1 Topics Kafka

| Topic | Partitions | Retention | Cleanup | Schéma |
|---|---|---|---|---|
| `raw-frames` | 6 | 1h | delete | `RawFrame.avsc` (frame_id, camera_id, timestamp, jpeg_bytes ref, width, height) |
| `detections` | 6 | 24h | delete | `Detection.avsc` (frame_id, detections[]: {class, conf, bbox}, model_version, inference_ms) |
| `tracks` | 6 | 24h | delete | `Track.avsc` (track_id, camera_id, history[], current_bbox, status) |
| `events` | 3 | 7d | compact | `Event.avsc` (event_id, type, severity, payload) |
| `model-drift` | 1 | 30d | delete | `DriftEvent.avsc` |
| `dlq-*` | 1 | 7d | delete | dead-letter queues |

> **Note importante sur `raw-frames`** : on ne met **pas** les bytes JPEG dans Kafka (taille = explosion). On stocke la frame dans MinIO sous `s3://frames/{camera_id}/{date}/{frame_id}.jpg` et le message Kafka contient juste la **référence** (URI). Kafka transporte les métadonnées, MinIO transporte les bytes.

### 6.2 Schemas (Avro)

Schémas dans `infra/kafka/schemas/`. Exemple `Detection.avsc` :

```json
{
  "type": "record",
  "name": "Detection",
  "namespace": "com.logivision.events.v1",
  "fields": [
    {"name": "frame_id", "type": "string"},
    {"name": "camera_id", "type": "string"},
    {"name": "timestamp_ms", "type": "long"},
    {"name": "model_version", "type": "string"},
    {"name": "inference_ms", "type": "float"},
    {"name": "frame_uri", "type": "string"},
    {"name": "detections", "type": {
      "type": "array",
      "items": {
        "type": "record",
        "name": "BoundingBox",
        "fields": [
          {"name": "class_id", "type": "int"},
          {"name": "class_name", "type": "string"},
          {"name": "confidence", "type": "float"},
          {"name": "x1", "type": "float"},
          {"name": "y1", "type": "float"},
          {"name": "x2", "type": "float"},
          {"name": "y2", "type": "float"}
        ]
      }
    }}
  ]
}
```

Registry : **Apicurio Registry** (alt OSS au Confluent Schema Registry, license Apache 2.0).

### 6.3 Services à créer

**T2.1 — Service `frame-grabber`** (`services/frame-grabber/`)
- Connecte à MediaMTX en RTSP (par caméra).
- Décode les frames (target 5 FPS, configurable par caméra).
- Upload chaque frame dans MinIO (`s3://frames/...`).
- Publish event `raw-frames` Kafka avec l'URI.
- Headers Kafka : `camera_id`, `producer_id`, `schema_version`.
- Métriques Prometheus : frames/sec, upload latency, kafka publish errors.

**T2.2 — Service `inference` refactor**
- Le BentoML server reste en place pour les besoins synchrones (debug, API REST publique).
- **Nouveau** : un worker `inference-worker` qui consomme `raw-frames`, fait l'inférence, publish `detections`.
- Consumer group `inference-workers` (scalable horizontalement : N workers, N ≤ partitions du topic).
- Idempotence : produce avec key = `frame_id`, le consommateur en aval (Flink) gère les doublons.

**T2.3 — Jobs Flink**

Job 1 : `detection_enrichment.py`
- Source : topic `detections`.
- Enrichit avec : zone géographique (lookup statique via state), tracking ID (passage par ByteTrack stateful).
- Sink : topic `tracks`.

Job 2 : `stationary_detection.py` (CEP)
- Source : topic `tracks`.
- Détecte un objet qui ne bouge pas pendant > 5 minutes (fenêtre sliding, position quasi-stable).
- Sink : topic `events` avec type `stationary_object`.

Job 3 : `zone_violation.py`
- Source : topic `tracks`.
- Zones interdites définies dans une config (BroadcastState pour rechargement à chaud).
- Sink : `events` avec type `zone_violation`.

Job 4 : `kpi_aggregator.py`
- Source : `detections`, `events`.
- Fenêtres tumbling 1min, 5min, 1h.
- Sink : ClickHouse via JDBC sink.

### 6.4 Déploiement Flink

- Session cluster Flink 1.20.x en mode K8s natif.
- 1 JobManager (HA via ZooKeeper-less = K8s HA), 3 TaskManagers de 2 slots chacun.
- Checkpoints : MinIO (S3 backend), interval 60s.
- Savepoints : trigger manuel via Flink CLI ou Helm hook.
- UI Flink exposée derrière Traefik avec auth basique.

### 6.5 Critères d'acceptation Phase 2

- [ ] Bout en bout : caméra → MediaMTX → frame-grabber → Kafka → inference-worker → Kafka → Flink → events Kafka → consommé par l'API → poussé via WebSocket au frontend.
- [ ] Latence E2E p95 < 3 secondes (à mesurer via traces OpenTelemetry).
- [ ] Capacité : 4 caméras à 5 FPS sans backpressure.
- [ ] Tests de chaos : kill un broker Kafka → pas de perte de données. Kill un TaskManager Flink → reprise depuis le dernier checkpoint en < 30s.
- [ ] Schemas versionnés et evolution testée (ajout d'un champ optionnel sans casser les consommateurs).

---

## 7. PHASE 3 — Feature Store (Feast)

> **Durée estimée** : 1 semaine.

### 7.1 Pourquoi un Feature Store ici

Pour LOGIVISION les features dérivées du tracking (vitesse moyenne d'une boîte, durée passée dans une zone, etc.) sont :
- Calculées en streaming par Flink.
- Utilisées en online (dashboard temps réel, déclenchement d'alertes).
- Utilisées en offline (entraînement de modèles d'anomaly detection, analytics historiques).

Feast évite le **training-serving skew** : la même définition de feature est utilisée des deux côtés.

### 7.2 Setup Feast

`services/feature-server/feature_repo/`
- `feature_store.yaml` : registry Postgres, online Redis, offline file/S3.
- `entities.py` : `Box`, `Camera`, `Zone`.
- `features.py` : feature views.
- `data_sources.py` : source Kafka (push source) pour online ingestion + source Parquet (MinIO) pour offline.

Exemple :
```python
from feast import Entity, FeatureView, Field, PushSource, KafkaSource
from feast.types import Float32, Int64, String
from datetime import timedelta

box = Entity(name="box", join_keys=["box_id"])

tracking_push_source = PushSource(
    name="tracking_push",
    batch_source=...,
)

box_movement_fv = FeatureView(
    name="box_movement_stats",
    entities=[box],
    ttl=timedelta(hours=24),
    schema=[
        Field(name="avg_speed_px_per_sec", dtype=Float32),
        Field(name="time_stationary_sec", dtype=Float32),
        Field(name="zone_changes_count", dtype=Int64),
        Field(name="current_zone", dtype=String),
    ],
    source=tracking_push_source,
)
```

### 7.3 Ingestion online

Job Flink dédié `feature_ingestion_job.py` qui :
- Calcule les features en streaming.
- Push vers Feast online store via l'API push : `store.push("tracking_push", df)`.
- (Alternative plus simple : écrit directement dans Redis avec la convention de clé Feast.)

### 7.4 Ingestion offline

Snapshot quotidien (job Prefect) :
- Lit les topics Kafka (ou ClickHouse) pour les 24h passées.
- Aggrège au format feature view.
- Écrit en Parquet partitionné sur MinIO (`s3://features/box_movement_stats/year=.../month=.../day=...`).
- Materialize Feast pour rendre disponible pour le training.

### 7.5 Utilisation

**Online (dashboard, alerting)** :
```python
features = store.get_online_features(
    features=["box_movement_stats:avg_speed_px_per_sec",
              "box_movement_stats:time_stationary_sec"],
    entity_rows=[{"box_id": "box_42"}],
).to_dict()
```

**Offline (training d'un anomaly detector)** :
```python
entity_df = pd.read_sql("SELECT box_id, event_timestamp FROM events", db)
training_df = store.get_historical_features(
    entity_df=entity_df,
    features=["box_movement_stats:avg_speed_px_per_sec", ...],
).to_df()
```

### 7.6 Critères d'acceptation Phase 3

- [ ] Feature server déployé, healthchecks OK.
- [ ] Push streaming testé : un track Kafka → feature à jour dans Redis < 2s.
- [ ] Materialization batch testée : training d'un classifieur d'anomalies sur features historiques.
- [ ] Doc `docs/mlops/feature-store-guide.md` complète.

---

## 8. PHASE 4 — Serving Avancé, Monitoring, A/B testing

> **Durée estimée** : 1 semaine.

### 8.1 Multi-modèles et A/B testing

BentoML supporte le **runner ensemble**. On déploie 2 modèles en parallèle :
- Modèle `Production` (stable).
- Modèle `Staging` (candidat).

Splitter dans le service : 95% prod, 5% staging. Les prédictions des deux sont loggées dans Kafka topic `predictions-shadow`. Comparaison offline :
- Latence
- Accord (% de prédictions identiques)
- Métriques sur les frames où on a une vérité terrain (annotée a posteriori).

Promotion : si le candidat est meilleur sur N jours consécutifs, alerte pour promotion manuelle.

### 8.2 Monitoring modèle en prod

Dashboard Grafana dédié `model-performance` avec :
- Throughput inférence (req/s)
- Latence p50/p95/p99
- Distribution confiance prédictions
- Taux de détections vides (0 box détectée)
- Drift scores en live (alimenté par drift-monitor)
- Coût compute (CPU% × heures)

### 8.3 Alerting (Alertmanager)

Règles Prometheus :
- `LogivisionModelLatencyHigh` : p95 > 500ms pendant 5min → warning.
- `LogivisionModelLatencyCritical` : p95 > 1s pendant 5min → critical, page on-call.
- `LogivisionDriftHigh` : drift_score > 0.3 → warning, ouverture auto d'une issue GitHub.
- `LogivisionInferenceErrorRate` : taux erreur > 2% sur 5min → critical.

### 8.4 Critères d'acceptation Phase 4

- [ ] 2 modèles servis en shadow, comparaison loggée et consultable.
- [ ] Dashboard model-performance fonctionnel avec données réelles.
- [ ] Alertes testées via injection de scénarios de panne.

---

## 9. PHASE 5 — Infra, Observabilité, CI/CD

> **Durée estimée** : 2 semaines (peut être démarrée en parallèle de la Phase 1 dès le Sprint 1.4).

### 9.1 Kubernetes (K3s)

- K3s mono-node pour dev/staging, multi-node (3 noeuds) pour prod.
- Storage : Longhorn (CSI distribué) ou local-path-provisioner pour dev.
- Ingress : Traefik (intégré K3s).
- Cert-manager pour TLS automatique.

### 9.2 GitOps avec ArgoCD

- ArgoCD installé via Helm.
- App-of-apps pattern : `infra/argocd/applications/` contient les définitions de toutes les applis.
- Sync auto sur la branche `main` pour prod, `develop` pour staging.
- Notifications Slack/Discord sur sync success/failure.

### 9.3 Stack observabilité LGTM

Tous installés via le chart `grafana/lgtm-distributed` ou versions individuelles :
- **Loki** : agrégation logs (label-based, pas full-text).
- **Grafana** : visualisation.
- **Tempo** : traces distribuées.
- **Mimir** (ou Prometheus standalone) : métriques long-terme.

Instrumentation :
- Tous les services Python : `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-kafka-python`, exporters OTLP vers le collector.
- Logs structurés JSON (avec `structlog`), parsé par Promtail/Alloy.
- Trace propagation : header `traceparent` traverse Kafka via headers, manuellement injecté.

### 9.4 CI/CD GitHub Actions

| Workflow | Trigger | Actions |
|---|---|---|
| `ci-backend.yml` | PR touchant `services/` | lint, type-check, test, build image, scan Trivy, push GHCR si merge |
| `ci-frontend.yml` | PR touchant `frontend/` | lint, test, build, lighthouse CI |
| `ci-ml.yml` | PR touchant `ml/` avec label `[train]` | lance training via runner self-hosted ou Colab, log MLflow, post résultats en commentaire PR via CML |
| `cd-staging.yml` | push sur `develop` | update image tag dans `infra/k8s/overlays/staging/`, ArgoCD pick up |
| `cd-prod.yml` | release tag `v*` | update prod overlay |
| `security-scan.yml` | nightly | Trivy on all images, dependency audit, Snyk free |

Self-hosted runner sur le laptop dev (gratuit, illimité pour repos privés) pour les jobs lourds (training).

### 9.5 Secrets

- En dev : `.env` non commit + `direnv`.
- En staging/prod : **Sealed Secrets** (Bitnami) — secrets chiffrés commit dans git, déchiffrés en cluster.
- Alternative : Vault dev mode dans le cluster, intégré via External Secrets Operator.

### 9.6 Critères d'acceptation Phase 5

- [ ] Cluster K3s déployé en staging (peut être local ou VPS).
- [ ] ArgoCD sync automatique fonctionne.
- [ ] Stack LGTM opérationnelle, dashboards Grafana provisionnés via code.
- [ ] Tous les services émettent traces + métriques + logs structurés.
- [ ] CI/CD passe le green sur une PR test bidon.

---

## 10. Standards de Code et de Collaboration

### 10.1 Python

- `ruff` configuré (line-length 100, target-version py311, sélection : E, F, I, N, UP, B, A, C4, RET, SIM, ARG, PTH, PLE, PLW).
- `mypy --strict` sur le code applicatif (sauf scripts ML qui peuvent être plus laxistes).
- Docstrings Google style.
- Type hints obligatoires sur signatures publiques.
- Imports triés par ruff/isort.

### 10.2 Tests

- `pytest` avec `pytest-asyncio`, `pytest-cov`, `pytest-mock`.
- Convention : `tests/test_<module>.py`, fonctions `test_<feature>_<scenario>`.
- Coverage cible : 70%+ sur les services, 50%+ sur les scripts ML.
- Fixtures dans `conftest.py` au niveau approprié.
- Tests de mutation occasionnels avec `mutmut` (pas en CI, manuel).

### 10.3 Frontend

- ESLint + Prettier + Tailwind plugin.
- TypeScript `strict: true`.
- Tests : Vitest + React Testing Library + Playwright pour E2E.
- Composants UI : shadcn/ui (libre, code copié dans le repo).

### 10.4 Git

Workflow : **Gitflow simplifié**.

Branches :
- `main` : production. Protégée. Merges via PR uniquement, 1 reviewer + CI verte.
- `develop` : staging. Protégée. Merges via PR + CI verte.
- `feature/<short-name>` : nouvelles features.
- `fix/<short-name>` : bug fixes.
- `chore/<short-name>` : tooling, docs, refactor.
- `release/v*` : préparation release.
- `hotfix/<short-name>` : urgences sur prod.

Commits : **Conventional Commits**.
- `feat(api): add detection history endpoint`
- `fix(inference): handle empty frames`
- `chore(deps): bump ultralytics to 8.3.40`
- `docs(mlops): add training guide`
- `test(api): cover detection router`

PR template dans `.github/pull_request_template.md` avec checklist : tests passent, doc à jour, ADR si décision archi, screenshots si UI.

### 10.5 Documentation

- README à jour à chaque PR significative.
- ADRs dans `docs/architecture/adr/`, numérotés `0001-titre.md`, format MADR.
- Runbooks dans `docs/runbooks/` : un par scénario incident probable.
- OpenAPI auto-généré par FastAPI, exposé sur `/docs`.

---

## 11. Définitions de "Done" globales

Une tâche/sprint/phase est "Done" quand :

1. **Code** : merged dans `develop` via PR, tous les checks CI verts.
2. **Tests** : tests unitaires + intégration ajoutés, couverture maintenue.
3. **Doc** : README, docstrings, ADR si pertinent, runbook si nouveau scénario opérationnel.
4. **Observabilité** : nouveau service expose `/health`, `/metrics`, logs structurés.
5. **Sécurité** : pas de secret en clair, scan Trivy passe (CRITICAL=0, HIGH<5).
6. **Revue** : 1 reviewer humain a approuvé (ou auto-approbation documentée si solo).
7. **Démo** : capture d'écran ou GIF dans la PR montrant que ça marche.

---

## 12. Stratégie d'Entraînement sans GPU Payant

### 12.1 Plateformes gratuites éligibles

| Plateforme | GPU | Durée session | Quota | Pour quoi |
|---|---|---|---|---|
| Google Colab Free | T4 ~16GB | 12h max, déconnexions aléatoires | "fair use" (varie) | Training initial, expérimentations |
| Kaggle Kernels | P100 16GB ou T4×2 | 9h max | 30h GPU/semaine | Training long, hyperparam search |
| Lightning AI Studios | T4 partiel | 22h gratos/mois | 22h | Backup |
| Paperspace Gradient | M4000 | Variable | Limité | Backup |
| Saturn Cloud | T4 | 30h/mois | 30h | Backup |

**Stratégie principale** : Kaggle pour le training "officiel" (limites stables, environnement reproductible), Colab pour l'exploration et le debug.

### 12.2 Workflow d'entraînement gratuit

```
1. [Local]  Préparer dataset via DVC : dvc repro, dvc push
2. [Local]  Commit + push code
3. [Kaggle/Colab] Notebook qui : git clone du repo, dvc pull, lance ml/scripts/train.py
4. [Colab]  Log vers MLflow distant (via tunnel cloudflared depuis laptop, voir 12.4)
5. [Colab]  À la fin : dvc push des poids, end run MLflow
6. [Local]  Récupérer le modèle, l'évaluer, le promouvoir via MLflow CLI
```

### 12.3 Notebooks template

`ml/notebooks/colab_train_template.ipynb` doit contenir :

```python
# Cellule 1 — Setup
!pip install -q uv
!git clone https://github.com/Ayalem/logivision_v2.git
%cd logivision
!uv pip install -e ".[ml]" --system

# Cellule 2 — Auth & secrets (via Colab Secrets / Kaggle Secrets)
import os
from google.colab import userdata  # ou kaggle_secrets
os.environ["MLFLOW_TRACKING_URI"] = userdata.get("MLFLOW_TRACKING_URI")
os.environ["AWS_ACCESS_KEY_ID"] = userdata.get("MINIO_ACCESS_KEY")
os.environ["AWS_SECRET_ACCESS_KEY"] = userdata.get("MINIO_SECRET_KEY")
os.environ["MLFLOW_S3_ENDPOINT_URL"] = userdata.get("MINIO_ENDPOINT")

# Cellule 3 — DVC pull
!dvc remote modify --local minio access_key_id $AWS_ACCESS_KEY_ID
!dvc remote modify --local minio secret_access_key $AWS_SECRET_ACCESS_KEY
!dvc pull

# Cellule 4 — Train
!python ml/scripts/train.py --config ml/configs/yolov8n.yaml --device cuda

# Cellule 5 — Cleanup
!dvc push  # push des poids vers MinIO
```

### 12.4 Tunnel MLflow

Sur le laptop dev :
```bash
# Installer cloudflared (gratuit, pas de compte requis pour quick tunnels)
brew install cloudflared  # ou apt

# Lancer le tunnel
cloudflared tunnel --url http://localhost:5000
# Output : https://random-words.trycloudflare.com → utiliser cette URL dans Colab
```

Alternative : **ngrok free** (1 tunnel actif gratos, URL change à chaque restart).

Pour une URL stable et gratuite : déployer MLflow sur **Oracle Cloud Always Free** (1 VM ARM 4 cores 24GB RAM gratos à vie) ou **fly.io free tier** (3 micro VMs gratuites).

### 12.5 Fine-tuning incrémental CPU local

Pour les drobes de réentraînement quand on a juste quelques nouvelles images :
- `model.train(epochs=5, freeze=10, ...)` : freeze des 10 premières couches, fine-tune les dernières.
- Sur CPU i7 récent : ~30 min pour 5 epochs sur 500 images.
- Suffisant pour adaptation domaine léger sans toucher au backbone.

### 12.6 Budget temps GPU à respecter

- Training baseline YOLOv8n 100 epochs sur 2000 images : ~2h sur T4 → 1 session Colab.
- Hyperparam search Optuna 20 trials : ~8h sur T4 → 1 session ou 2 morceaux.
- Comparaison 4 architectures × 100 epochs : ~10h cumulés → étaler sur 2-3 sessions Kaggle.

**Total budget** estimé pour finir la Phase 1 : ~50h GPU sur 4 semaines = ~12h/semaine = OK avec Kaggle seul.

---

## 13. Glossaire et Liens

### 13.1 Glossaire

| Terme | Définition |
|---|---|
| ADR | Architecture Decision Record. Un markdown par décision archi importante, format MADR. |
| Avro | Format de sérialisation binaire avec schéma, utilisé avec Kafka. |
| ByteTrack | Algo de tracking multi-objets simple et efficace, SOTA 2022. |
| CEP | Complex Event Processing. Détection de patterns sur des flux d'événements (Flink CEP API). |
| DVC | Data Version Control. Git-like pour datasets et modèles. |
| Drift | Dérive : changement de distribution des données entre train et prod, dégradant le modèle. |
| Feast | Feature Store open-source (online + offline). |
| GitOps | Pratique où l'état désiré du système est dans Git, ArgoCD reconcilie. |
| Kappa | Pattern d'archi streaming-only (vs Lambda qui combine batch + stream). |
| KRaft | Kafka sans Zookeeper. |
| LGTM | Loki + Grafana + Tempo + Mimir, stack obs Grafana Labs. |
| MLflow | Plateforme MLOps : tracking + projects + models + registry. |
| OpenVINO | Toolkit Intel pour optimiser inference deep learning sur CPU. |
| PSI | Population Stability Index. Métrique de drift entre 2 distributions. |
| RTSP | Real-Time Streaming Protocol. Standard caméras IP. |
| Sealed Secrets | Bitnami project pour chiffrer des K8s secrets et les commit dans Git. |
| YOLO | You Only Look Once. Famille de détecteurs d'objets temps réel. |

### 13.2 Liens essentiels

- Ultralytics YOLOv8 : https://docs.ultralytics.com/
- MLflow : https://mlflow.org/docs/latest/
- DVC : https://dvc.org/doc
- Apache Kafka : https://kafka.apache.org/documentation/
- Apache Flink : https://nightlies.apache.org/flink/flink-docs-stable/
- Feast : https://docs.feast.dev/
- BentoML : https://docs.bentoml.com/
- Evidently AI : https://docs.evidentlyai.com/
- ArgoCD : https://argo-cd.readthedocs.io/
- OpenTelemetry Python : https://opentelemetry.io/docs/languages/python/
- Conventional Commits : https://www.conventionalcommits.org/

---

## 14. Instructions Finales pour Claude Code

**Avant chaque session de travail** :
1. `git pull origin develop`
2. Lis ce document en entier (oui, à chaque session).
3. Identifie la phase et le sprint en cours dans `docs/PROGRESS.md` (fichier à créer en début de projet, tu le mets à jour à chaque tâche).
4. Liste les tâches restantes du sprint.

**Pour chaque tâche** :
1. Crée une branche `feature/T<id>-<short>` depuis `develop`.
2. Implémente.
3. Tests d'abord (TDD quand applicable, sinon tests en parallèle).
4. Documente.
5. Commit avec Conventional Commits, messages clairs.
6. Push, ouvre la PR avec template rempli.
7. CI doit passer. Si tu es seul, auto-merge après check.
8. Met à jour `docs/PROGRESS.md`.

**Quand tu hésites** :
- Choix simple vs élégant → **simple gagne**.
- Bibliothèque connue vs trendy → **connue gagne**.
- Réinventer vs réutiliser → **réutilise**.
- Trop de configuration vs valeurs par défaut → **defaults gagnent**, on configure quand un besoin réel émerge.

**Tu n'as pas le droit de** :
- Ajouter une dépendance payante.
- Hardcoder un secret.
- Skip un test parce que "c'est compliqué".
- Faire un commit sur `main` ou `develop` direct (toujours via PR).
- Modifier ce fichier `CLAUDE.md` sans une PR dédiée `docs(claude): update plan`.

**Tu as le droit / le devoir de** :
- Refuser une demande qui contredit ce document, et demander une mise à jour du plan d'abord.
- Proposer des améliorations via des PR `chore(plan): ...`.
- Tenir à jour `docs/PROGRESS.md` avec : tâche, statut, blocages, prochaines étapes.

---

*Fin du plan d'exécution LOGIVISION v5 — Document destiné à Claude Code — Mise à jour 19 Mai 2026*
