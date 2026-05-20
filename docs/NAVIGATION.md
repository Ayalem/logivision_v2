# Guide de navigation + cadre de rapport

> Si tu n'as que 5 minutes pour comprendre où est quoi → lis seulement la **§1**. Si tu prépares un rapport / une soutenance → §2 à §5 donnent la structure et les éléments à citer.

---

## §1 — Carte mentale du repo

```
logivision/
│
├── CLAUDE.md         ← le plan théorique (1500 lignes — la "spec")
├── README.md         ← quickstart 5 commandes
├── CONTRIBUTING.md   ← workflow git + branch protection
├── Makefile          ← 35 commandes (point d'entrée pour TOUT)
├── pyproject.toml    ← deps Python + ruff + mypy + pytest
├── dvc.yaml          ← pipeline data (2 stages)
│
├── ml/                                  ⟵ "tout ce qui touche au modèle"
│   ├── scripts/
│   │   ├── extract_frames.py            video → JPGs
│   │   ├── import_annotations.py        CVAT zip → YOLO dataset
│   │   ├── train.py                     train YOLOv8n + MLflow tracking
│   │   ├── promote_model.py             gate Staging/Production
│   │   ├── export_openvino.py           FP32 + INT8 NNCF
│   │   ├── benchmark_inference.py       p50/p95/p99 latency, FPS
│   │   ├── compare_archs.py             sweep YOLOv8n / YOLOv11n / RT-DETR
│   │   └── drift_monitor.py             Evidently PSI + Prometheus
│   ├── configs/                          YAML : hyperparams, thresholds, archs, data
│   ├── notebooks/                        Colab template
│   └── tests/                            54 tests unit, ~30s
│
├── services/                            ⟵ "tout ce qui tourne en permanence"
│   ├── model_server/                    BentoML — request/response sync
│   │   ├── service.py                    POST /detect
│   │   ├── bentofile.yaml + Dockerfile
│   │   └── tests/
│   ├── frame_grabber/                   video → MinIO + Kafka raw-frames
│   ├── inference_worker/                Kafka raw-frames → detections
│   └── stream_processor/                Kafka detections → events (CEP)
│
├── scripts/                             ⟵ scripts "outils" (pas un service)
│   ├── bootstrap.sh                     démarre stack + .env + .dvc/config.local
│   ├── gen_synthetic_demo.py            génère un mini-dataset annoté
│   ├── fetch_pexels_videos.py           API Pexels CC0
│   └── fetch_kaggle.py                  CLI Kaggle wrapper
│
├── infra/                               ⟵ infrastructure as code
│   ├── docker-compose/
│   │   ├── docker-compose.mlops.yml     Postgres + MinIO + MLflow
│   │   ├── docker-compose.cvat.yml      Annotation UI
│   │   └── docker-compose.kafka.yml     Kafka KRaft + Schema Registry + UI
│   ├── docker/
│   │   ├── mlflow/Dockerfile             MLflow custom (psycopg2 + boto3)
│   │   └── postgres/init.sql             crée la DB `mlflow`
│   ├── kafka/schemas/                    Avro : RawFrame, Detection, Event
│   └── zones.example.yaml                CEP zone polygons
│
├── tests/
│   ├── integration/                     4 smoke tests stack (port up, health)
│   └── load/load_test.py                load test stdlib pour BentoML
│
├── docs/
│   ├── PROGRESS.md                      checklist par tâche
│   ├── JOURNEY.md                       récit narratif (incidents, décisions)
│   ├── ETAT-AVANCEMENT.md               snapshot pour co-équipiers
│   ├── NAVIGATION.md                    ← CE DOCUMENT
│   ├── mlops/
│   │   ├── dvc-guide.md
│   │   ├── annotation-guide.md          CVAT step by step
│   │   ├── training-on-colab.md         tunnel + GPU gratuit
│   │   ├── benchmarks/                  rapports auto-générés par make benchmark/load-test
│   │   └── comparisons/                 rapports auto-générés par make compare-archs
│   └── architecture/adr/
│       └── 0003-model-promotion-process.md
│
└── datasets/                            ⚠️ gitignored, versionné par DVC sur MinIO
    ├── raw/videos/                      Pexels + TalTech Camera3
    ├── raw/frames/                      extrait par extract_frames.py
    ├── raw/annotations.zip              CVAT export zip
    └── processed/<name>/                YOLO format (images/, labels/, data.yaml)
```

**Règle pour naviguer** : la commande `make <cible>` te dit *quel fichier* fait *quoi*. `make help` liste tout. Quand tu veux comprendre un sprint, regarde le bloc Makefile correspondant, puis le script appelé.

---

## §2 — Cadre de rapport — 5 sections que tu peux copier-coller

### 2.1 Contexte et choix techniques

Trois contraintes ont structuré tous les choix :

1. **Budget 0 €** → tout self-hosted, jamais de SaaS payant
2. **GPU gratuit uniquement** → Colab T4 / Kaggle P100 + CPU OpenVINO en prod
3. **Reproductibilité bout-en-bout** → un commit Git rejoue tout (DVC + MLflow tags `git_commit` + `dataset_fingerprint`)

Pour la stack technique, un tableau condensé :

| Besoin | Outil retenu | Pourquoi (vs alternatives) |
|---|---|---|
| Package manager Python | **uv** | ~10× plus rapide que pip/poetry, lockfile natif |
| Detection model | **YOLOv8n** (Ultralytics) | License AGPL OK pour académique, 3M params, 6 MB, ByteTrack intégré |
| Tracking d'expériences | **MLflow** 2.17 self-hosted | OSS, Registry intégré, vs W&B payant |
| Versioning data | **DVC** + remote MinIO | Pointeurs en Git, données sur S3, pas de quota Git LFS |
| Stockage objets | **MinIO** | S3-compatible self-hosted, vs AWS S3 payant |
| Serving sync | **BentoML** 1.3 | Containerisable, vs FastAPI custom |
| Optimisation inference CPU | **OpenVINO** + **NNCF** (INT8) | 3-5× speedup sur CPU Intel, gratuit |
| Annotation | **CVAT** 2.14.4 self-hosted | Standard OSS, vs Roboflow / Labelbox payants |
| Drift detection | **Evidently** + fallback PSI numpy | Rapports HTML, métriques Prometheus |
| Stream processing | **Kafka** (KRaft) + **Apicurio** Schema Registry | KRaft = pas de Zookeeper ; Apicurio = alt OSS Confluent SR |
| CEP | **Python custom** (interface PyFlink-compatible) | Cluster Flink trop lourd pour académique, même contrat d'interface |

### 2.2 Architecture

Deux flux principaux. **Batch** pour l'entraînement, **streaming** pour la production.

**Batch (Phase 1)** — entraîne et version un modèle :
```
caméras / vidéos
  ↓  extract_frames.py
JPG frames
  ↓  CVAT annotation
annotations.zip
  ↓  import_annotations.py
YOLO dataset (images/, labels/, data.yaml)
  ↓  train.py
MLflow run + Registry (logivision-detector v1, v2, …)
  ↓  promote_model.py (gate val_map50 ≥ 0.65, etc.)
Stage = Staging → Production
  ↓  export_openvino.py
FP32 + INT8 artifacts dans MinIO
  ↓  benchmark_inference.py
docs/mlops/benchmarks/run_*.md  ← preuve perf
```

**Streaming (Phase 2)** — sert le modèle en temps réel :
```
caméra IP / fichier vidéo
  ↓  frame_grabber.py
MinIO `frames` bucket  +  Kafka `raw-frames` topic
  ↓  inference_worker.py (consume + YOLO + publish)
Kafka `detections` topic
  ↓  stream_processor/cep.py
Kafka `events` topic  (stationary_object, zone_violation)
  ↓  (à venir : FastAPI WebSocket → frontend React)
```

Le modèle servi est choisi dynamiquement : MLflow Registry Production → fallback Staging → fallback `yolov8n.pt` local. Quand `promote_model.py` passe une nouvelle version en Production, redémarrer les workers suffit pour basculer.

### 2.3 Pipeline MLOps — boucle complète

Ce qui rend ce projet "production-grade" plutôt qu'un POC :

1. **Reproductibilité** — `git_commit` + `dataset_fingerprint` (sha256 du data.yaml et de chaque label) sont taggés sur chaque run MLflow. Un run de 2026-04 peut être ré-exécuté à l'identique en 2026-09 si data + code sont retrouvables.
2. **Gating** — `promote_model.py` refuse `Staging → Production` sans `--approve` ET sans les seuils. ADR 0003 documente la décision.
3. **Quantization avec garde-fous** — `export_openvino.py` abort si l'INT8 dégrade le mAP50 de plus de 5 %.
4. **Monitoring** — `benchmark_inference.py` produit un rapport Markdown par run, `drift_monitor.py` produit HTML + JSON + Prometheus.
5. **Tests** — 70+ tests, dont un *end-to-end réel* (T1.3.2) qui entraîne 1 epoch sur 20 frames synthétiques et vérifie via le MLflow client que tout est loggué correctement (15 s wall-time).

### 2.4 Données utilisées

| Source | Type | License | Usage |
|---|---|---|---|
| `gen_synthetic_demo.py` | Synthétique (rectangles colorés + labels YOLO) | (code) | Smoke-tests, integration tests, premier training |
| Pexels API | Vidéos warehouse | CC0 | 16 vidéos téléchargées via `make fetch-videos` |
| TalTech Camera3.mp4 | Synthétique 3D (Blender) | MIT | 1 vidéo téléchargée manuellement, 50 frames extraites |
| TalTech Camera1/Camera2/Models | Synthétique 3D + annotations + modèles pré-entraînés | MIT | Identifiés (8-10 GB chacun), pas téléchargés (taille) |
| DataDryad 6D-ViCuT | Tracking de cuboïdes en packing manuel | CC0 | Identifié (92 GB total), pas téléchargé |
| Kaggle warehouse-delivery-box | Annoté warehouse boxes | (variable) | Script `fetch_kaggle.py` prêt, en attente de KAGGLE_KEY rempli |

**Décision honnête à mettre dans le rapport** : l'absence d'annotations réelles a empêché de mesurer une vraie performance détection. Le modèle servi en démo retombe sur `yolov8n.pt` (COCO pré-entraîné) — qui ne connaît pas la classe "forklift" ni "pallet". Ce n'est pas un bug, c'est une *limitation gracefully handled* : `service.py` log le `model_version=fallback:yolov8n.pt` pour tracer.

### 2.5 Limites et travaux futurs

- **Frontend pas démarré** : CLAUDE.md liste la stack React + Vite + Tailwind mais aucun sprint frontend ; un PR `docs(claude): add frontend sprints` est requis.
- **Flink remplacé par Python** : le CEP tourne en un seul process Python avec état en mémoire. Pour scale > 1 caméra à 30 fps, il faut le vrai cluster Flink (interface compatible déjà respectée).
- **Retraining trigger** : `drift_monitor.py` détecte mais ne déclenche pas. Le GitHub Action `.github/workflows/retrain-on-drift.yml` reste à écrire (Phase 5).
- **Tracking ByteTrack** : `cep.py` utilise un track_id heuristique (centroid quantisé). Vrai tracking via Ultralytics `model.track(...)` à intégrer.
- **Pas de signed commits / branch protection active** : le repo est public, branche unique `main`, owner peut push direct ; les règles GitHub sont documentées mais à activer manuellement.

---

## §3 — Comment expliquer le projet à l'oral en 3 minutes

```
1.  "LOGIVISION détecte et suit des cartons dans un entrepôt à partir de
     flux vidéo, en utilisant uniquement de l'open-source et du GPU gratuit."

2.  "L'architecture suit le pattern Kappa : tout passe par un pipeline
     streaming Kafka. Pas de batch séparé."

3.  "Le modèle est versionné dans MLflow Registry. Chaque entraînement
     produit un artifact dans MinIO et est promu de Staging à Production
     selon des seuils mAP."

4.  "Le serving est en deux modes : BentoML pour les requêtes synchrones
     (REST /detect), et un worker Kafka qui consomme un topic de frames
     pour le mode streaming. Le même MLflow Registry est la source de
     vérité dans les deux cas."

5.  "Le drift est détecté en comparant les distributions de features
     (luminosité, nombre de détections, confidence moyenne) entre une
     fenêtre récente et un snapshot DVC. Les events sont publiés sur
     Kafka et exposés en Prometheus."

6.  "Le CEP émet deux types d'événements : `stationary_object` quand
     une boîte ne bouge pas pendant N secondes, et `zone_violation`
     quand un objet entre dans une zone interdite définie en YAML."
```

---

## §4 — Commandes-démo pour soutenance

À lancer dans l'ordre, dans 4 terminaux séparés. Chaque ligne produit un output visible utilisable comme preuve.

```bash
# Terminal 1 — stack MLOps
./scripts/bootstrap.sh
# UI MLflow:  http://localhost:5050
# UI MinIO:   http://localhost:9001

# Terminal 2 — stack streaming
make kafka-up
# UI Kafka:   http://localhost:8086

# Terminal 3 — pipeline data + training (synthétique)
make demo-data
uv run python -m ml.scripts.import_annotations \
    --input datasets/raw/annotations.zip --output datasets/processed/demo
make train
# observe le run apparaître dans MLflow UI

# Terminal 3 (suite) — promotion + export
RUN_ID=<copier depuis MLflow UI>
make promote RUN=$RUN_ID
# observe le passage None → Staging dans MLflow Registry

# Terminal 4 — serving sync
make serve &
curl -F image=@datasets/processed/demo/images/val/<une-frame>.jpg \
    http://localhost:3000/detect
# voir JSON avec détections + inference_ms + model_version

# Terminal 4 (suite) — streaming end-to-end
make inference-worker &
make cep ZONES=infra/zones.example.yaml &
make frame-grabber SOURCE=datasets/raw/videos/Camera3.mp4 FPS=2 MAX=20
# consomme les topics pour voir les messages :
docker exec logivision-kafka /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9094 --topic detections --from-beginning --max-messages 5
docker exec logivision-kafka /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9094 --topic events --from-beginning --max-messages 5
```

Si tout marche, tu auras montré : data → train → promote → serve sync → serve async → CEP. C'est l'arc complet du projet.

---

## §5 — Glossaire express

| Terme | 1 ligne |
|---|---|
| **YOLO** | Famille de détecteurs d'objets temps réel (You Only Look Once) |
| **mAP50** | Mean Average Precision à IoU=0.5 — métrique standard de détection |
| **MLflow** | Tracking + Registry pour modèles ML (notre Postgres + MinIO l'alimentent) |
| **DVC** | Git pour gros fichiers — pointeurs .dvc en Git, données sur S3 |
| **OpenVINO IR** | Intermediate Representation — format inférence optimisé Intel |
| **NNCF** | Neural Network Compression Framework — quantization INT8 par Intel |
| **Kafka KRaft** | Kafka sans Zookeeper (consensus interne via Raft) |
| **CEP** | Complex Event Processing — détecter des patterns sur un flux |
| **PSI** | Population Stability Index — métrique de drift entre 2 distributions |
| **ADR** | Architecture Decision Record — un markdown par décision archi |
| **Avro** | Format binaire avec schéma versionné, compagnon naturel de Kafka |
| **ByteTrack** | Algo de tracking multi-objets simple et SOTA 2022 (MIT) |

---

## §6 — Le repo en chiffres

- **28 commits** sur `main`, branche unique
- **~3000 lignes** de Python (services + ml/scripts + tests)
- **70+ tests** unitaires + 5 marqués `integration`
- **8 services Docker** distincts (3 MLOps + 4 CVAT + Kafka stack)
- **6 schémas Avro / configs YAML** versionnés
- **5 docs** dans `docs/` (PROGRESS, JOURNEY, ETAT-AVANCEMENT, NAVIGATION, ADRs)
- **35 cibles Makefile** — l'unique surface utilisateur du projet
