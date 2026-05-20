# Manual Dockerfile alternative to `bentoml containerize` (useful when
# you want to bypass the bentoml CLI build step and control every layer).

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install only what the service needs at runtime.
RUN pip install --no-cache-dir \
        "bentoml>=1.3,<2" \
        "ultralytics>=8.3,<9" \
        "openvino>=2024.4,<2025" \
        "opencv-python-headless>=4.10,<5" \
        "numpy>=1.26,<3" \
        "mlflow>=2.17,<3" \
        "boto3>=1.35,<2" \
        "pillow>=10" \
        "pydantic>=2.9,<3"

COPY service.py __init__.py /app/

ENV MODEL_NAME=logivision-detector \
    MODEL_STAGE=Production \
    MLFLOW_TRACKING_URI=http://host.docker.internal:5050 \
    DETECTION_CONF=0.25

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:3000/health || exit 1

CMD ["bentoml", "serve", "service:WarehouseDetector", "--host", "0.0.0.0", "--port", "3000"]
