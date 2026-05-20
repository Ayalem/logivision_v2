# LOGIVISION — top-level developer commands.
# Run `make help` to list available targets.

SHELL := /bin/bash
.DEFAULT_GOAL := help

UV ?= uv
COMPOSE_DIR := infra/docker-compose
COMPOSE_FILE := $(COMPOSE_DIR)/docker-compose.mlops.yml
COMPOSE_CVAT := $(COMPOSE_DIR)/docker-compose.cvat.yml

.PHONY: help install lint format test test-integration test-cov up down clean train eval pre-commit-install bootstrap dvc-push dvc-pull dvc-status pipeline pipeline-dag cvat-up cvat-down cvat-clean demo-data promote promote-prod export-openvino benchmark compare-archs fetch-videos serve serve-build load-test

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

serve: ## Serve the detector locally via BentoML on :3000
	cd services/model_server && $(UV) run bentoml serve service:WarehouseDetector --host 0.0.0.0 --port 3000

serve-build: ## Build a Bento (containerizable artifact) for the detector
	cd services/model_server && $(UV) run bentoml build

load-test: ## Run a quick load test against a running detector.  Usage: make load-test IMAGE=path/to/frame.jpg
	@test -n "$(IMAGE)" || { echo "ERROR: pass IMAGE=path/to/frame.jpg"; exit 1; }
	$(UV) run python tests/load/load_test.py --image $(IMAGE) --concurrency 1,5,10 --requests 30

eval: ## Evaluate the registered model (Sprint 1.3)
	@test -f ml/scripts/eval.py || { echo "ERROR: ml/scripts/eval.py not yet created (Sprint 1.3)."; exit 1; }
	$(UV) run python ml/scripts/eval.py --config ml/configs/yolov8n.yaml
