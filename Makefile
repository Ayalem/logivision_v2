# LOGIVISION — top-level developer commands.
# Run `make help` to list available targets.

SHELL := /bin/bash
.DEFAULT_GOAL := help

UV ?= uv
COMPOSE_DIR := infra/docker-compose
COMPOSE_FILE := $(COMPOSE_DIR)/docker-compose.mlops.yml
COMPOSE_CVAT := $(COMPOSE_DIR)/docker-compose.cvat.yml

.PHONY: help install lint format test test-integration test-cov up down clean train eval pre-commit-install bootstrap dvc-push dvc-pull dvc-status pipeline pipeline-dag cvat-up cvat-down cvat-clean demo-data promote promote-prod export-openvino benchmark compare-archs fetch-videos serve serve-build load-test fetch-kaggle drift kafka-up kafka-down kafka-clean inference-worker frame-grabber cep api frontend-install frontend-dev frontend-build frontend-clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dev dependencies via uv
	$(UV) sync --all-groups

pre-commit-install: install ## Install Git hooks
	$(UV) run pre-commit install --install-hooks

lint: ## Run ruff lint + mypy
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	@if find . -type d \( -name .venv -o -name node_modules -o -name .git \) -prune -o -type f -name '*.py' -print | grep -q .; then \
		$(UV) run mypy .; \
	else \
		echo "(no .py files yet — mypy skipped)"; \
	fi

format: ## Auto-format with ruff
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

test: ## Run pytest
	$(UV) run pytest

test-cov: ## Run pytest with coverage report
	$(UV) run pytest --cov --cov-report=term-missing --cov-report=html

test-integration: ## Run integration smoke tests (requires `make bootstrap` first)
	$(UV) run pytest tests/integration -m integration

bootstrap: ## Boot the MLOps stack and wait for healthchecks (creates .env if missing)
	./scripts/bootstrap.sh

up: ## Start the local MLOps stack (no wait, no .env auto-create)
	docker compose --env-file .env -f $(COMPOSE_FILE) up -d --build

down: ## Stop the local MLOps stack
	docker compose --env-file .env -f $(COMPOSE_FILE) down

clean: ## Stop the stack AND purge named volumes (asks for confirmation)
	@read -p "This will DELETE all local data volumes. Type 'yes' to continue: " ans && [ "$$ans" = "yes" ]
	docker compose --env-file .env -f $(COMPOSE_FILE) down --volumes --remove-orphans

dvc-push: ## Push DVC-tracked data to the MinIO remote
	$(UV) run dvc push

dvc-pull: ## Pull DVC-tracked data from the MinIO remote
	$(UV) run dvc pull

dvc-status: ## Show local-vs-cache and cache-vs-remote DVC status
	$(UV) run dvc status
	$(UV) run dvc status --cloud

pipeline: ## Reproduce the data pipeline (extract_frames + prepare_dataset)
	$(UV) run dvc repro

pipeline-dag: ## Render the pipeline DAG to stdout
	$(UV) run dvc dag --full

cvat-up: ## Start the CVAT annotation stack (UI on :8090)
	docker compose -f $(COMPOSE_CVAT) up -d
	@echo "CVAT UI starting at http://localhost:8090 (first boot ~60s for migrations)."

cvat-down: ## Stop CVAT (volumes preserved)
	docker compose -f $(COMPOSE_CVAT) down

cvat-clean: ## Stop CVAT AND wipe its volumes (asks for confirmation)
	@read -p "This will DELETE all CVAT annotations / users / jobs. Type 'yes' to continue: " ans && [ "$$ans" = "yes" ]
	docker compose -f $(COMPOSE_CVAT) down --volumes --remove-orphans

demo-data: ## Generate a synthetic CVAT-style YOLO export at datasets/raw/annotations.zip
	$(UV) run python scripts/gen_synthetic_demo.py

train: ## Train YOLOv8n via ml/scripts/train.py (uses ml/configs/yolov8n.yaml)
	$(UV) run python -m ml.scripts.train --config ml/configs/yolov8n.yaml

promote: ## Promote MLflow model None -> Staging based on thresholds.  Usage: make promote RUN=<run-id>
	@test -n "$(RUN)" || { echo "ERROR: pass RUN=<mlflow-run-id>"; exit 1; }
	$(UV) run python -m ml.scripts.promote_model --run-id $(RUN)

promote-prod: ## Promote MLflow model Staging -> Production (requires explicit approval).  Usage: make promote-prod RUN=<run-id>
	@test -n "$(RUN)" || { echo "ERROR: pass RUN=<mlflow-run-id>"; exit 1; }
	$(UV) run python -m ml.scripts.promote_model --run-id $(RUN) --approve

export-openvino: ## Export run's model to OpenVINO FP32 + INT8 (NNCF), log to MLflow.  Usage: make export-openvino RUN=<run-id>
	@test -n "$(RUN)" || { echo "ERROR: pass RUN=<mlflow-run-id>"; exit 1; }
	$(UV) run python -m ml.scripts.export_openvino --run-id $(RUN)

benchmark: ## Benchmark PyTorch/OpenVINO FP32/INT8 variants of a run, write a Markdown report.  Usage: make benchmark RUN=<run-id>
	@test -n "$(RUN)" || { echo "ERROR: pass RUN=<mlflow-run-id>"; exit 1; }
	$(UV) run python -m ml.scripts.benchmark_inference --run-id $(RUN)

compare-archs: ## Train every architecture in ml/configs/comparison.yaml and write a Markdown report
	$(UV) run python -m ml.scripts.compare_archs --config ml/configs/comparison.yaml

fetch-videos: ## Fetch warehouse videos from Pexels (requires PEXELS_API_KEY env var)
	$(UV) run python scripts/fetch_pexels_videos.py --query warehouse --n 10 --output datasets/raw/videos

fetch-kaggle: ## Fetch a Kaggle dataset (needs KAGGLE_USERNAME + KAGGLE_KEY).  Usage: make fetch-kaggle DATASET=user/name
	@test -n "$(DATASET)" || { echo "ERROR: pass DATASET=user/name"; exit 1; }
	$(UV) run python scripts/fetch_kaggle.py --dataset $(DATASET) --output datasets/raw/external

serve: ## Serve the detector locally via BentoML on :3000
	cd services/model_server && $(UV) run bentoml serve service:WarehouseDetector --host 0.0.0.0 --port 3000

serve-build: ## Build a Bento (containerizable artifact) for the detector
	cd services/model_server && $(UV) run bentoml build

load-test: ## Run a quick load test against a running detector.  Usage: make load-test IMAGE=path/to/frame.jpg
	@test -n "$(IMAGE)" || { echo "ERROR: pass IMAGE=path/to/frame.jpg"; exit 1; }
	$(UV) run python tests/load/load_test.py --image $(IMAGE) --concurrency 1,5,10 --requests 30

drift: ## Compute drift between two feature snapshots.  Usage: make drift REF=ref.csv CUR=cur.csv
	@test -n "$(REF)" || { echo "ERROR: pass REF=ref.csv"; exit 1; }
	@test -n "$(CUR)" || { echo "ERROR: pass CUR=cur.csv"; exit 1; }
	$(UV) run python -m ml.scripts.drift_monitor --reference $(REF) --current $(CUR)

kafka-up: ## Start Kafka (KRaft) + Schema Registry + Kafka UI.  Topics created automatically.
	docker compose -f infra/docker-compose/docker-compose.kafka.yml up -d
	@echo "Kafka :9092 (host) / :9094 (intra-compose)"
	@echo "Apicurio Schema Registry: http://localhost:8085"
	@echo "Kafka UI:                 http://localhost:8086"

kafka-down: ## Stop the Kafka stack (volumes preserved).
	docker compose -f infra/docker-compose/docker-compose.kafka.yml down

kafka-clean: ## Stop AND wipe Kafka volumes (asks confirmation).
	@read -p "This DELETES all Kafka data. Type 'yes' to continue: " ans && [ "$$ans" = "yes" ]
	docker compose -f infra/docker-compose/docker-compose.kafka.yml down --volumes --remove-orphans

inference-worker: ## Run the inference worker that consumes raw-frames -> detections.
	$(UV) run python -m services.inference_worker.worker

frame-grabber: ## Push frames from a video file/dir/RTSP into raw-frames.  Usage: make frame-grabber SOURCE=path/to/video.mp4 [CAMERA=CAM01] [FPS=2] [MAX=50]
	@test -n "$(SOURCE)" || { echo "ERROR: pass SOURCE=path/to/video.mp4"; exit 1; }
	$(UV) run python -m services.frame_grabber.grabber \
		--source $(SOURCE) \
		--camera-id $${CAMERA:-CAM01} \
		--fps $${FPS:-2} \
		$${MAX:+--max $$MAX}

cep: ## Run the CEP processor (consumes `detections`, emits `events`).  Optional: ZONES=infra/zones.example.yaml
	$(UV) run python -m services.stream_processor.cep \
		$${ZONES:+--zones $$ZONES} \
		$${STATIONARY_SECONDS:+--stationary-seconds $$STATIONARY_SECONDS}

api: ## Start the FastAPI dashboard backend on :8000 (also serves the frontend).
	$(UV) run uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --reload

eval: ## Evaluate the registered model (Sprint 1.3)
	@test -f ml/scripts/eval.py || { echo "ERROR: ml/scripts/eval.py not yet created (Sprint 1.3)."; exit 1; }
	$(UV) run python ml/scripts/eval.py --config ml/configs/yolov8n.yaml

# ---------------------------------------------------------------------------
# Frontend (Vite + React + R3F warehouse dashboard)
# ---------------------------------------------------------------------------

frontend-install: ## Install npm dependencies for frontend/
	cd frontend && npm install --no-audit --no-fund

frontend-dev: ## Run the Vite dev server (http://localhost:5173, proxies /api + /ws to :8000)
	cd frontend && npm run dev

frontend-build: ## Produce a production build at frontend/dist/ (served by FastAPI at /)
	cd frontend && npm run build

frontend-clean: ## Wipe frontend/dist and frontend/node_modules (irreversible)
	rm -rf frontend/dist frontend/node_modules
