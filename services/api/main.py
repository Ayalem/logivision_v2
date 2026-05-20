"""FastAPI backend — read-only facade over MLflow Registry + Kafka events.

Endpoints:
    GET  /health
    GET  /api/registry/models                  list registered models + versions
    GET  /api/registry/runs                    last N MLflow runs
    GET  /api/runs/{run_id}                    detail of one run (metrics, tags)
    GET  /api/topics/{topic}/messages?n=20     last N messages on a Kafka topic
    GET  /api/drift/reports                    list drift reports under docs/mlops/drift/
    GET  /api/benchmarks                       list benchmark reports
    WS   /ws/events                            live stream of `events` Kafka topic

Serves the static dashboard from services/frontend/ at /  (Vite-free single-page UI).

Run with:
    make api
    open http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "services" / "frontend"

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5050")
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_EVENTS_TOPIC = os.environ.get("KAFKA_EVENTS_TOPIC", "events")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup/shutdown hooks (placeholder — connection pools could live here)."""
    logger.info("api startup: MLflow=%s Kafka=%s", MLFLOW_TRACKING_URI, KAFKA_BOOTSTRAP)
    yield
    logger.info("api shutdown")


app = FastAPI(title="LOGIVISION API", version="0.1.0", lifespan=lifespan)


# ---------- helpers ----------


def _mlflow_client():
    from mlflow.tracking import MlflowClient

    return MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)


# ---------- health ----------


@app.get("/health")
def health() -> dict:
    """Lightweight reachability check (does NOT touch MLflow / Kafka)."""
    return {"status": "ok"}


# ---------- registry ----------


@app.get("/api/registry/models")
def list_models() -> dict:
    try:
        client = _mlflow_client()
        models = client.search_registered_models()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"mlflow unreachable: {exc}") from exc
    out = []
    for m in models:
        versions = []
        for v in m.latest_versions or []:
            versions.append(
                {
                    "version": v.version,
                    "stage": v.current_stage,
                    "run_id": v.run_id,
                    "creation_timestamp": v.creation_timestamp,
                }
            )
        out.append({"name": m.name, "versions": versions})
    return {"models": out}


@app.get("/api/registry/runs")
def list_runs(limit: int = 10) -> dict:
    try:
        client = _mlflow_client()
        experiments = client.search_experiments()
        runs: list[dict] = []
        for exp in experiments:
            for r in client.search_runs(experiment_ids=[exp.experiment_id], max_results=limit):
                runs.append(
                    {
                        "run_id": r.info.run_id,
                        "experiment": exp.name,
                        "status": r.info.status,
                        "start_time": r.info.start_time,
                        "metrics": dict(r.data.metrics),
                        "tags": {
                            k: v for k, v in r.data.tags.items() if not k.startswith("mlflow.")
                        },
                    }
                )
        runs.sort(key=lambda r: r["start_time"] or 0, reverse=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"mlflow unreachable: {exc}") from exc
    return {"runs": runs[:limit]}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    try:
        client = _mlflow_client()
        r = client.get_run(run_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=f"run not found: {exc}") from exc
    return {
        "run_id": r.info.run_id,
        "status": r.info.status,
        "start_time": r.info.start_time,
        "end_time": r.info.end_time,
        "params": dict(r.data.params),
        "metrics": dict(r.data.metrics),
        "tags": dict(r.data.tags),
    }


# ---------- kafka topic peek ----------


@app.get("/api/topics/{topic}/messages")
def topic_messages(topic: str, n: int = 20) -> dict:
    """Read the last N messages off a topic in a one-shot consumer.

    Note: cheap (O(N)) for small N. Don't call with n > a few hundred.
    """
    try:
        from confluent_kafka import Consumer, TopicPartition
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="confluent-kafka not installed") from exc

    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "group.id": f"api-peek-{topic}-{os.getpid()}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    try:
        meta = consumer.list_topics(topic, timeout=5)
        if topic not in meta.topics or meta.topics[topic].error is not None:
            raise HTTPException(status_code=404, detail=f"topic not found: {topic}")
        partitions = list(meta.topics[topic].partitions.keys())
        tps = [TopicPartition(topic, p) for p in partitions]
        end_offsets = {tp.partition: consumer.get_watermark_offsets(tp)[1] for tp in tps}
        # Seek to (end - n_per_partition) on each partition.
        per_partition = max(1, n // max(1, len(partitions)) + 1)
        seek_tps = []
        for p in partitions:
            start = max(0, end_offsets[p] - per_partition)
            seek_tps.append(TopicPartition(topic, p, start))
        consumer.assign(seek_tps)
        messages: list[dict] = []
        deadline = time.monotonic() + 3.0
        while len(messages) < n and time.monotonic() < deadline:
            msg = consumer.poll(timeout=0.2)
            if msg is None or msg.error():
                continue
            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except Exception:  # noqa: BLE001
                payload = {"raw": msg.value().decode("utf-8", errors="replace")}
            messages.append(
                {
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "key": msg.key().decode("utf-8", errors="replace") if msg.key() else None,
                    "value": payload,
                }
            )
    finally:
        consumer.close()
    return {"topic": topic, "messages": messages[:n]}


# ---------- drift + benchmark reports ----------


@app.get("/api/drift/reports")
def drift_reports() -> dict:
    root = REPO_ROOT / "docs" / "mlops" / "drift"
    if not root.is_dir():
        return {"reports": []}
    return {
        "reports": sorted(
            [
                {"name": p.name, "size_bytes": p.stat().st_size, "modified": p.stat().st_mtime}
                for p in root.iterdir()
                if p.suffix in {".html", ".json"}
            ],
            key=lambda r: r["modified"],
            reverse=True,
        )
    }


@app.get("/api/benchmarks")
def benchmarks() -> dict:
    root = REPO_ROOT / "docs" / "mlops" / "benchmarks"
    if not root.is_dir():
        return {"reports": []}
    return {
        "reports": sorted(
            [
                {"name": p.name, "size_bytes": p.stat().st_size, "modified": p.stat().st_mtime}
                for p in root.iterdir()
                if p.suffix in {".md", ".json"}
            ],
            key=lambda r: r["modified"],
            reverse=True,
        )
    }


# ---------- WebSocket events ----------


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """Stream Kafka `events` to the client. Reconnect-friendly."""
    await websocket.accept()
    try:
        from confluent_kafka import Consumer
    except ImportError:
        await websocket.send_json({"error": "confluent-kafka not installed"})
        await websocket.close(code=1011)
        return

    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "group.id": f"api-ws-{os.getpid()}",
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([KAFKA_EVENTS_TOPIC])
    try:
        while True:
            msg = await asyncio.get_event_loop().run_in_executor(None, consumer.poll, 0.5)
            if msg is None:
                # heartbeat to keep the WS alive through proxies
                try:
                    await asyncio.wait_for(websocket.send_json({"heartbeat": True}), timeout=1.0)
                except (TimeoutError, WebSocketDisconnect):
                    break
                continue
            if msg.error():
                continue
            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except Exception:  # noqa: BLE001
                payload = {"raw": msg.value().decode("utf-8", errors="replace")}
            try:
                await websocket.send_json({"event": payload})
            except WebSocketDisconnect:
                break
    finally:
        consumer.close()


# ---------- static frontend ----------


@app.get("/", response_model=None)
def index() -> JSONResponse | FileResponse:
    """Serve the dashboard if the frontend dir exists, otherwise return a hint."""
    index_html = FRONTEND_DIR / "index.html"
    if index_html.is_file():
        return FileResponse(str(index_html))
    return JSONResponse(
        {
            "service": "LOGIVISION API",
            "frontend": f"missing — expected at {FRONTEND_DIR}",
            "endpoints": [
                "/health",
                "/api/registry/models",
                "/api/registry/runs",
                "/api/runs/{run_id}",
                "/api/topics/{topic}/messages",
                "/api/drift/reports",
                "/api/benchmarks",
                "/ws/events",
            ],
        }
    )


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
