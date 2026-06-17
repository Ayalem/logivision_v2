"""Client-facing endpoints: zones, cameras, anomalies, KPIs, entries/exits.

These power the warehouse-supervisor dashboard (Amazon/Alibaba style).
They read static YAML (zones, cameras) and peek the Kafka `events` topic;
when Kafka is unreachable they return `{... , degraded: true}` instead of
503 so the frontend can render gracefully with the static parts.

All response shapes match the inspo's `lib/mock-data.ts` types so the
ported frontend can swap mocks → real data without refactor.
"""

from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import time
from collections import defaultdict
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["client"])

REPO_ROOT = Path(__file__).resolve().parents[3]
ZONES_FILE = Path(os.environ.get("LOGIVISION_ZONES", REPO_ROOT / "infra" / "zones.example.yaml"))
CAMERAS_FILE = Path(
    os.environ.get("LOGIVISION_CAMERAS", REPO_ROOT / "infra" / "cameras.example.yaml")
)

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_EVENTS_TOPIC = os.environ.get("KAFKA_EVENTS_TOPIC", "events")
KAFKA_RAW_FRAMES_TOPIC = os.environ.get("KAFKA_RAW_FRAMES_TOPIC", "raw-frames")
KAFKA_DETECTIONS_TOPIC = os.environ.get("KAFKA_DETECTIONS_TOPIC", "detections")
KAFKA_OCCUPANCY_TOPIC = os.environ.get("KAFKA_OCCUPANCY_TOPIC", "zone-occupancy")
LOGIVISION_ROLE = os.environ.get("LOGIVISION_ROLE", "operator")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _occupancy_status(pct: int) -> str:
    if pct >= 90:
        return "critical"
    if pct >= 70:
        return "warning"
    return "normal"


def _polygon_bbox(polygon: list[dict]) -> tuple[float, float, float, float]:
    """Return (x, y, width, height) in % for a normalized polygon."""
    xs = [p["x"] for p in polygon]
    ys = [p["y"] for p in polygon]
    x, y = min(xs), min(ys)
    return (x * 100, y * 100, (max(xs) - x) * 100, (max(ys) - y) * 100)


@lru_cache(maxsize=1)
def _load_yaml_cached(path_str: str, mtime: float) -> dict:
    """Cache YAML parse keyed on (path, mtime) so edits propagate."""
    del mtime  # only used for cache key
    return yaml.safe_load(Path(path_str).read_text(encoding="utf-8")) or {}


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    return _load_yaml_cached(str(path), path.stat().st_mtime)


def _peek_topic(topic: str, n: int, timeout_s: float = 1.0) -> tuple[list[dict], bool]:
    """Peek the last N messages on a Kafka topic.

    Returns (messages, degraded). `degraded=True` when Kafka is unreachable
    or the topic is missing — callers should still return 200 with empty data.
    """
    try:
        from confluent_kafka import Consumer, TopicPartition
    except ImportError:
        return [], True

    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "group.id": f"api-peek-{topic}-{os.getpid()}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "socket.timeout.ms": 1500,
        }
    )
    messages: list[dict] = []
    try:
        try:
            meta = consumer.list_topics(topic, timeout=1.5)
        except Exception:  # noqa: BLE001
            return [], True
        if topic not in meta.topics or meta.topics[topic].error is not None:
            return [], True

        partitions = list(meta.topics[topic].partitions.keys())
        if not partitions:
            return [], False
        per = max(1, n // len(partitions) + 1)
        seek_tps = []
        for p in partitions:
            _, end = consumer.get_watermark_offsets(TopicPartition(topic, p), timeout=1.5)
            seek_tps.append(TopicPartition(topic, p, max(0, end - per)))
        consumer.assign(seek_tps)
        deadline = time.monotonic() + timeout_s
        while len(messages) < n and time.monotonic() < deadline:
            msg = consumer.poll(timeout=0.2)
            if msg is None or msg.error():
                continue
            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except Exception:  # noqa: BLE001
                continue
            payload.setdefault("_offset", msg.offset())
            payload.setdefault("_partition", msg.partition())
            messages.append(payload)
    finally:
        consumer.close()
    messages.sort(key=lambda m: m.get("timestamp_ms", 0), reverse=True)
    return messages[:n], False


def _today_ms_range() -> tuple[int, int]:
    """Start of today (local) and now, in ms."""
    now = datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp() * 1000), int(now.timestamp() * 1000)


# ---------------------------------------------------------------------------
# Demo-data fallback
#
# The dashboard must look populated during a soutenance even when Kafka /
# the streaming pipeline isn't running. When `_peek_topic` returns
# `degraded=True` we inject a deterministic set of recent-looking events
# covering every CEP type, so KPIs / anomalies / predictions all render.
# Event IDs are prefixed `demo-` so they're identifiable in logs.
# ---------------------------------------------------------------------------


# Removed: _demo_events() + _events_or_demo() used to synthesize 14 fake
# events whenever the Kafka `events` topic was empty, so the dashboard
# always had numbers to render. They produced the "12.2K cartons / 4
# entries / 6 anomalies" the operator saw with no pipeline running.
# Deleted to honour the no-fake-data principle: every visible KPI /
# forecast / anomaly must trace to a real Kafka event. When the pipeline
# is off, the UI renders a "waiting for pipeline" empty state instead.


def _payload_confidence(payload: dict) -> int | None:
    """Calibrated model confidence (0..1 in the event payload) as a
    percentage, or None when the event carries none (rule events)."""
    try:
        value = float(payload["confidence"])
    except (KeyError, TypeError, ValueError):
        return None
    return int(round(min(1.0, max(0.0, value)) * 100))


def _humanise_event(evt: dict) -> str:
    t = evt.get("event_type", "event")
    p = evt.get("payload") or {}
    klass = p.get("class_name") or "objet"
    zone = p.get("zone") or "—"
    if t == "stationary_object":
        return f"{klass.capitalize()} stationnaire détecté dans {zone}"
    if t == "zone_violation":
        return f"Intrusion en zone restreinte: {klass} dans {zone}"
    if t == "entry":
        return f"Entrée: {klass} → {zone}"
    if t == "exit":
        return f"Sortie: {klass} ← {zone}"
    if t == "trajectory_anomaly":
        feature_fr = {
            "speed": "vitesse anormale",
            "accel": "accélération anormale",
            "dir_change": "changement de direction brutal",
            "log_aspect": "forme anormale",
            "d_aspect": "basculement détecté",
            "sqrt_area": "taille anormale",
            "dwell_ratio": "immobilité prolongée",
            "dt_s": "trajectoire irrégulière",
        }.get(p.get("dominant_feature", ""), "comportement anormal")
        return f"Anomalie de trajectoire ({feature_fr}): {klass}"
    if t == "box_falling":
        return f"Chute détectée: {klass}"
    return f"Événement {t}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/me")
def get_me() -> dict:
    """Current session role. Stub for the demo — replace with OIDC later."""
    role = LOGIVISION_ROLE if LOGIVISION_ROLE in {"operator", "admin"} else "operator"
    return {"role": role, "name": "demo"}


@router.get("/zones")
def list_zones() -> dict:
    """Zones from the YAML registry + REAL occupancy from the
    `zone-occupancy` topic (latest CEP snapshot per zone). When no
    snapshot exists yet, `occupancy` is null and `live` is false —
    the UI renders an em-dash, never an invented percentage."""
    raw = _load_yaml(ZONES_FILE)
    snapshots, _degraded = _peek_topic(KAFKA_OCCUPANCY_TOPIC, n=100, timeout_s=0.5)
    latest: dict[str, dict] = {}
    for snap in snapshots:  # already newest-first
        zone = snap.get("zone")
        if zone and zone not in latest:
            latest[zone] = snap

    out: list[dict] = []
    for entry in raw.get("zones", []) or []:
        name = entry["name"]
        polygon = entry.get("polygon", [])
        x, y, w, h = _polygon_bbox(polygon)
        snap = latest.get(name)
        capacity = int(entry.get("capacity", 10))
        if snap is not None:
            occupancy = int(round(float(snap.get("ratio", 0.0)) * 100))
            current = int(snap.get("occupied_tracks", 0))
            status = _occupancy_status(occupancy)
            updated = datetime.fromtimestamp(
                int(snap.get("timestamp_ms", 0)) / 1000, tz=UTC
            ).isoformat()
        else:
            occupancy, current, status, updated = None, None, "unknown", None
        out.append(
            {
                "id": name,
                "name": entry.get("display_name") or name.replace("_", " ").title(),
                "kind": entry.get("kind") or ("forbidden" if entry.get("forbidden") else "shelf"),
                "category": entry.get("category", "Stockage"),
                "occupancy": occupancy,
                "capacity": capacity,
                "currentItems": current,
                "status": status,
                "live": snap is not None,
                "x": round(x, 2),
                "y": round(y, 2),
                "width": round(w, 2),
                "height": round(h, 2),
                "polygon": [{"x": p["x"], "y": p["y"]} for p in polygon],
                "lastUpdated": updated,
            }
        )
    return {"zones": out}


@router.get("/cameras")
def list_cameras() -> dict:
    """List all configured cameras with status.

    A camera in the YAML registry is `online` by default — the MJPEG stream
    serves its source video regardless of whether the inference pipeline is
    busy.  A separate `kafkaLive` sub-indicator marks cameras that have had
    a `raw-frames` message in the last 30 s, so the operator can see which
    feeds are actually flowing through Kafka. Flagging the tile 'offline'
    just because the worker is idle was misleading — the input video is
    always there.
    """
    raw = _load_yaml(CAMERAS_FILE)
    cameras_raw = raw.get("cameras", []) or []
    frames, degraded = _peek_topic(KAFKA_RAW_FRAMES_TOPIC, n=50, timeout_s=0.5)
    live_camera_ids: set[str] = set()
    now_ms = int(time.time() * 1000)
    for f in frames:
        if now_ms - int(f.get("timestamp_ms") or 0) < 30_000:
            cid = f.get("camera_id")
            if cid:
                live_camera_ids.add(cid)

    # Real per-camera detection counts from the latest worker output —
    # zero when the pipeline is idle, never an invented number.
    det_msgs, _ = _peek_topic(KAFKA_DETECTIONS_TOPIC, n=50, timeout_s=0.5)
    det_counts: dict[str, int] = defaultdict(int)
    for m in det_msgs:
        cid = m.get("camera_id")
        if cid:
            det_counts[cid] += len(m.get("detections", []) or [])

    out: list[dict] = []
    for entry in cameras_raw:
        cid = entry["id"]
        is_live = cid in live_camera_ids
        # Allow zones.yaml to mark a camera as offline / under maintenance
        # explicitly; otherwise we render it online.
        explicit = entry.get("status")
        if explicit in {"offline", "maintenance"}:
            status, fps_value, last_seen = explicit, 0, None
        else:
            status = "online"
            fps_value = entry.get("fps_target", 5)
            last_seen = datetime.now(UTC).isoformat() if is_live else None
        out.append(
            {
                "id": cid,
                "name": entry.get("name", cid),
                "location": entry.get("location", ""),
                "zone": entry.get("zone", ""),
                "status": status,
                "kafkaLive": is_live,
                "resolution": entry.get("resolution", "1280x720"),
                "fps": fps_value,
                "detectionCount": det_counts.get(cid, 0),
                "lastDetection": last_seen,
            }
        )
    return {"cameras": out, "degraded": degraded}


@router.get("/anomalies")
def list_anomalies(n: int = 50) -> dict:
    events, degraded = _peek_topic(KAFKA_EVENTS_TOPIC, n=max(n * 2, 100))
    # real events only - no demo fallback (no-fake-data principle)
    out: list[dict] = []
    for evt in events:
        sev = evt.get("severity", "info")
        if sev == "info":
            continue
        etype_raw = evt.get("event_type", "event")
        payload = evt.get("payload") or {}
        zone_id = payload.get("zone", "")
        out.append(
            {
                "id": evt.get("event_id", ""),
                "type": (
                    "behavior"
                    if etype_raw in {"trajectory_anomaly", "box_falling"}
                    else "overflow"
                    if etype_raw == "stationary_object"
                    else "unauthorized"
                ),
                "severity": "critical" if sev == "critical" else "warning",
                "zone": zone_id.replace("_", " ").title() if zone_id else "—",
                "zoneId": zone_id,
                "description": _humanise_event(evt),
                "timestamp": datetime.fromtimestamp(
                    int(evt.get("timestamp_ms", 0)) / 1000, tz=UTC
                ).isoformat(),
                "resolved": False,
                "cameraId": evt.get("camera_id") or "—",
                # Real model score when the event carries one (the trajectory
                # AE writes payload.score); null for rule events — the UI
                # hides the field rather than inventing a percentage.
                "confidence": _payload_confidence(payload),
                "eventType": etype_raw,
            }
        )
        if len(out) >= n:
            break
    return {"anomalies": out, "degraded": degraded}


@router.get("/entries-exits")
def list_entries_exits(n: int = 50) -> dict:
    events, degraded = _peek_topic(KAFKA_EVENTS_TOPIC, n=max(n * 2, 100))
    # real events only - no demo fallback (no-fake-data principle)
    out: list[dict] = []
    for evt in events:
        etype = evt.get("event_type")
        if etype not in {"entry", "exit"}:
            continue
        payload = evt.get("payload") or {}
        zone_id = payload.get("zone", "")
        out.append(
            {
                "id": evt.get("event_id", ""),
                "type": etype,
                "message": _humanise_event(evt),
                "timestamp": datetime.fromtimestamp(
                    int(evt.get("timestamp_ms", 0)) / 1000, tz=UTC
                ).isoformat(),
                "zone": zone_id,
                "cameraId": evt.get("camera_id") or "—",
                "className": payload.get("class_name", "objet"),
            }
        )
        if len(out) >= n:
            break
    return {"items": out, "degraded": degraded}


@router.get("/kpis")
def get_kpis() -> dict:
    """Roll up REAL Kafka events into the dashboard's KPI tiles.

    No fake fallbacks: every visible number comes from the live events
    topic. When the pipeline isn't running, the topic is empty, the
    KPIs are zero, and pipelineActive=false so the UI can render a
    "waiting for pipeline" empty state instead of fabricating traffic.
    """
    events, degraded_events = _peek_topic(KAFKA_EVENTS_TOPIC, n=2000)
    detections, _ = _peek_topic("detections", n=100, timeout_s=0.5)
    cameras_raw = _load_yaml(CAMERAS_FILE).get("cameras", []) or []

    start_ms, _ = _today_ms_range()
    entries_today = sum(
        1
        for e in events
        if e.get("event_type") == "entry" and int(e.get("timestamp_ms", 0)) >= start_ms
    )
    exits_today = sum(
        1
        for e in events
        if e.get("event_type") == "exit" and int(e.get("timestamp_ms", 0)) >= start_ms
    )
    active_anomalies = sum(
        1
        for e in events
        if e.get("severity") in {"warning", "critical"}
        and int(e.get("timestamp_ms", 0)) >= start_ms
    )

    # Per-camera health: a camera is "online" if it has a recent raw-frame.
    frames, _ = _peek_topic(KAFKA_RAW_FRAMES_TOPIC, n=50, timeout_s=0.5)
    now_ms = int(time.time() * 1000)
    live_ids = {
        f.get("camera_id")
        for f in frames
        if f.get("camera_id") and now_ms - int(f.get("timestamp_ms") or 0) < 30_000
    }

    # Total cartons in the warehouse = real entries - real exits seen on
    # the events topic. Topic retention bounds how far back this counts
    # (default 7 days). Pure derived value; no synthetic seeding.
    total_entries = sum(1 for e in events if e.get("event_type") == "entry")
    total_exits = sum(1 for e in events if e.get("event_type") == "exit")
    total_boxes = max(0, total_entries - total_exits)

    avg_proc = 0
    inference_samples = [d.get("inference_ms") for d in detections if d.get("inference_ms")]
    if inference_samples:
        avg_proc = int(sum(inference_samples) / len(inference_samples))

    # pipelineActive: did ANY real signal arrive recently? UI uses this
    # to flip tile rendering between "—" and live numbers.
    pipeline_active = bool(events) or bool(detections) or bool(live_ids)

    # Stock level needs a configured capacity. 1000 is the default
    # target until per-zone capacity gets surfaced.
    capacity = 1000
    stock_pct = round(100 * total_boxes / capacity) if pipeline_active else 0

    return {
        "totalBoxes": total_boxes,
        "todayEntries": entries_today,
        "todayExits": exits_today,
        "activeAnomalies": active_anomalies,
        "systemStatus": (
            "operational"
            if pipeline_active and not degraded_events
            else ("degraded" if degraded_events else "waiting")
        ),
        "camerasOnline": len(live_ids),
        "totalCameras": len(cameras_raw),
        "avgProcessingTime": avg_proc,
        "stockLevel": min(100, stock_pct),
        "pipelineActive": pipeline_active,
        "degraded": degraded_events,
    }


# ---------------------------------------------------------------------------
# Predictions, heatmap, insight chains (Phase A.3)
#
# For the academic demo these are *synthesized* server-side from the recent
# events peek rather than emitted by a separate process. Production target
# is a dedicated `services/stream_processor/predictions.py` (or PyFlink job)
# that publishes them to a `predictions` topic — the frontend would then
# read from a unified WebSocket and not call REST. The response shapes
# below are stable: swapping the source later is a no-op for the UI.
# ---------------------------------------------------------------------------


CONGESTION_THRESHOLD = 2  # ≥ N stationary events in a zone → congestion
CONGESTION_WINDOW_S = 300  # window for grouping (5 min)
COLLISION_PAIR_WINDOW_S = 30  # ≤ 30 s between events in same zone → collision risk
HEATMAP_GRID = 20  # 20x20 cells over the 0..1 floor


def _predict_from_events(
    events: list[dict],
    now_ms: int,
    occupancy_snapshots: list[dict] | None = None,
) -> dict[str, list[dict]]:
    """Pure: derive prediction events from a slice of recent CEP events.

    `occupancy_snapshots` are `zone-occupancy` topic messages — the LSTM's
    input. Returns a dict with keys: congestion, collision, trajectories.
    """
    cutoff = now_ms - CONGESTION_WINDOW_S * 1000

    # Per-zone stationary timestamps for congestion forecast.
    by_zone: dict[str, list[dict]] = defaultdict(list)
    # Per-track point history for trajectory hints.
    by_track: dict[str, list[dict]] = defaultdict(list)

    for e in events:
        ts = int(e.get("timestamp_ms", 0))
        if ts < cutoff:
            continue
        if e.get("event_type") == "stationary_object":
            zone = (e.get("payload") or {}).get("zone")
            if zone:
                by_zone[zone].append(e)
        tid = e.get("track_id")
        payload = e.get("payload") or {}
        cx, cy = payload.get("centroid_x"), payload.get("centroid_y")
        if tid and cx is not None and cy is not None:
            with contextlib.suppress(TypeError, ValueError):
                by_track[tid].append({"t": ts, "x": float(cx), "y": float(cy)})

    # Try the trained LSTM first; fall back to rule when the model isn't
    # loaded (artifact missing, PyTorch unavailable) or there isn't enough
    # real occupancy history yet (honest `insufficient-history` tag).
    from services.api._lstm_inference import (
        SOURCE_INSUFFICIENT,
        SOURCE_LSTM,
        SOURCE_RULE,
        forecast_zone_occupancy,
    )

    congestion: list[dict] = []
    for zone, evts in by_zone.items():
        if len(evts) < CONGESTION_THRESHOLD:
            continue
        latest_ts = max(int(e.get("timestamp_ms", 0)) for e in evts)

        lstm_out = forecast_zone_occupancy(occupancy_snapshots or [], zone, now_ms)
        extra: dict = {}
        if lstm_out is not None and lstm_out["source"] == SOURCE_LSTM:
            # Forecast values are occupancy ratios (0..1) de-normalised by
            # the inference module — render directly as density.
            density = float(lstm_out["forecast"][0])
            # ETA shrinks with predicted occupancy. Floor at 30 s.
            eta = max(30, int(240 * (1 - density)))
            # Conservative fixed confidence for v2; the panel also shows
            # the held-out RMSE from /api/model-info.
            confidence = 0.75
            source = SOURCE_LSTM
            extra["horizons_hours"] = lstm_out["horizons_hours"]
            extra["forecast_ratios"] = lstm_out["forecast"]
        else:
            # Rule fallback.
            eta = max(30, 240 - len(evts) * 30)
            confidence = min(0.95, 0.55 + 0.1 * len(evts))
            density = min(1.0, len(evts) / 10.0)
            source = SOURCE_RULE
            if lstm_out is not None and lstm_out["source"] == SOURCE_INSUFFICIENT:
                # Tell the UI the LSTM exists but needs more real history.
                extra["lstm_status"] = SOURCE_INSUFFICIENT
                extra["lstm_bins_available"] = lstm_out["bins_available"]
                extra["lstm_bins_required"] = lstm_out["bins_required"]

        congestion.append(
            {
                "event_id": f"cgf-{zone}-{latest_ts}",
                "event_type": "congestion_forecast",
                "severity": "warning",
                "zone": zone,
                "eta_seconds": eta,
                "confidence": round(confidence, 2),
                "density": round(density, 2),
                "timestamp_ms": latest_ts,
                "forecast_source": source,
                **extra,
            }
        )

    collision: list[dict] = []
    # Sort stationary events by time; if 2 land in same zone close together
    # and on different tracks, treat as collision risk.
    seen_pairs: set[tuple[str, str]] = set()
    for zone, evts in by_zone.items():
        evts_sorted = sorted(evts, key=lambda e: int(e.get("timestamp_ms", 0)))
        for i in range(len(evts_sorted)):
            for j in range(i + 1, len(evts_sorted)):
                a, b = evts_sorted[i], evts_sorted[j]
                dt_s = (int(b.get("timestamp_ms", 0)) - int(a.get("timestamp_ms", 0))) / 1000.0
                if dt_s > COLLISION_PAIR_WINDOW_S:
                    break
                ta, tb = a.get("track_id"), b.get("track_id")
                if not ta or not tb or ta == tb:
                    continue
                pair = tuple(sorted([ta, tb]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                pa = a.get("payload") or {}
                # Approximate the intersection point as the midpoint of the
                # two latest centroids (good enough for the visual demo).
                try:
                    pax, pay = float(pa.get("centroid_x", 0)), float(pa.get("centroid_y", 0))
                    pb_ = b.get("payload") or {}
                    pbx, pby = float(pb_.get("centroid_x", 0)), float(pb_.get("centroid_y", 0))
                    point = ((pax + pbx) / 2.0, (pay + pby) / 2.0)
                except (TypeError, ValueError):
                    point = (0.5, 0.5)
                collision.append(
                    {
                        "event_id": f"col-{ta}-{tb}",
                        "event_type": "collision_risk",
                        "severity": "critical",
                        "track_a": ta,
                        "track_b": tb,
                        "zone": zone,
                        "eta_seconds": max(5, int(60 - dt_s)),
                        "point_x": round(point[0], 3),
                        "point_y": round(point[1], 3),
                        "timestamp_ms": int(b.get("timestamp_ms", 0)),
                    }
                )

    trajectories: list[dict] = []
    # Keep the 8 most recently active tracks with ≥ 2 points.
    ranked_tracks = sorted(
        by_track.items(),
        key=lambda kv: max(p["t"] for p in kv[1]),
        reverse=True,
    )
    for tid, points in ranked_tracks[:8]:
        if len(points) < 2:
            continue
        history = points[-5:]
        # Linear extrapolation: project 5 s ahead using the last two points.
        p_last = history[-1]
        p_prev = history[-2]
        dt = max(1, (p_last["t"] - p_prev["t"]) / 1000.0)
        vx = (p_last["x"] - p_prev["x"]) / dt
        vy = (p_last["y"] - p_prev["y"]) / dt
        horizon_s = 5.0
        predicted = {"x": p_last["x"] + vx * horizon_s, "y": p_last["y"] + vy * horizon_s}
        trajectories.append(
            {
                "event_id": f"trj-{tid}-{p_last['t']}",
                "event_type": "trajectory_hint",
                "severity": "info",
                "track_id": tid,
                "points": history,
                "predicted_point": predicted,
                "horizon_seconds": horizon_s,
                "speed_units_per_s": round(math.hypot(vx, vy), 3),
                "timestamp_ms": p_last["t"],
            }
        )

    return {"congestion": congestion, "collision": collision, "trajectories": trajectories}


@router.get("/model-info")
def get_model_info() -> dict:
    """Exposed metadata for the trained congestion-forecast model.

    Drives the dashboard's "trained model" badge in the Système panel:
    name, version, held-out test metrics (RMSE / MAE), dataset.
    """
    from services.api._lstm_inference import model_info

    return model_info()


@router.get("/predictions")
def list_predictions(n: int = 50) -> dict:
    events, degraded = _peek_topic(KAFKA_EVENTS_TOPIC, n=max(n * 4, 200))
    # real events only - no demo fallback (no-fake-data principle)
    now_ms = int(time.time() * 1000)
    # 24 h of 5-min snapshots across ~7 zones ≈ 2000 messages.
    snapshots, _ = _peek_topic(KAFKA_OCCUPANCY_TOPIC, n=2500, timeout_s=1.5)
    derived = _predict_from_events(events, now_ms, snapshots)
    # Flatten and cap.
    flat = derived["congestion"] + derived["collision"] + derived["trajectories"]
    flat.sort(key=lambda e: e.get("timestamp_ms", 0), reverse=True)
    return {
        "predictions": flat[:n],
        "buckets": {
            "congestion": derived["congestion"][:20],
            "collision": derived["collision"][:10],
            "trajectories": derived["trajectories"][:8],
        },
        "degraded": degraded,
    }


def _heatmap_grid(layer: str, events: list[dict], zones: list[dict], size: int) -> list[dict]:
    """Build an `size`x`size` density grid in [0..1] for the requested layer."""
    cell = 1.0 / size
    grid = [[0.0 for _ in range(size)] for _ in range(size)]

    def add_blob(cx: float, cy: float, weight: float, sigma: float = 0.08) -> None:
        # Gaussian splat onto the grid — cheap and visually smooth.
        for iy in range(size):
            for ix in range(size):
                x = (ix + 0.5) * cell
                y = (iy + 0.5) * cell
                d2 = (x - cx) ** 2 + (y - cy) ** 2
                grid[iy][ix] += weight * math.exp(-d2 / (2 * sigma * sigma))

    def _event_centroids(filtered: list[dict]) -> list[tuple[float, float]]:
        pts: list[tuple[float, float]] = []
        for e in filtered:
            p = e.get("payload") or {}
            try:
                pts.append((float(p.get("centroid_x")), float(p.get("centroid_y"))))
            except (TypeError, ValueError):
                continue
        return pts

    # Every layer traces to real data: event centroids or static zone
    # geometry. No baseline/demo blobs — an idle pipeline yields an
    # empty grid and the UI renders it as such.
    if layer == "traffic":
        for cx, cy in _event_centroids(events):
            add_blob(cx, cy, 1.0)
    elif layer == "shelf":
        # Static config visualisation: shelf zone centres from zones.yaml.
        for z in zones:
            if (z.get("kind") or "") == "shelf":
                xs = [p["x"] for p in z.get("polygon", [])]
                ys = [p["y"] for p in z.get("polygon", [])]
                if xs and ys:
                    add_blob((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0.9, sigma=0.07)
    elif layer == "idle":
        # Complement of observed traffic — only meaningful once there IS
        # observed traffic; otherwise stays empty.
        pts = _event_centroids(events)
        if pts:
            for cx, cy in pts:
                add_blob(cx, cy, 1.0)
            for iy in range(size):
                for ix in range(size):
                    grid[iy][ix] = max(0.0, 1.0 - grid[iy][ix])
    elif layer == "bottleneck":
        # Where things actually pile up: stationary / falling / anomaly events.
        slow_types = {"stationary_object", "box_falling", "trajectory_anomaly"}
        for cx, cy in _event_centroids([e for e in events if e.get("event_type") in slow_types]):
            add_blob(cx, cy, 1.0, sigma=0.06)
    elif layer == "worker":
        # Person-class events only.
        for cx, cy in _event_centroids(
            [e for e in events if (e.get("payload") or {}).get("class_name") == "person"]
        ):
            add_blob(cx, cy, 1.0)

    # Normalize 0..1.
    vmax = max((max(row) for row in grid), default=0.0)
    if vmax > 0:
        for iy in range(size):
            for ix in range(size):
                grid[iy][ix] = round(grid[iy][ix] / vmax, 3)

    out: list[dict] = []
    for iy in range(size):
        for ix in range(size):
            v = grid[iy][ix]
            if v > 0.02:  # skip near-zero to shrink the payload
                out.append(
                    {"x": round((ix + 0.5) * cell, 3), "y": round((iy + 0.5) * cell, 3), "value": v}
                )
    return out


@router.get("/heatmap")
def get_heatmap(
    layer: str = Query("traffic", pattern="^(traffic|shelf|idle|bottleneck|worker)$"),
    grid: int = Query(HEATMAP_GRID, ge=8, le=64),
) -> dict:
    events, degraded = _peek_topic(KAFKA_EVENTS_TOPIC, n=200, timeout_s=0.5)
    # real events only - no demo fallback (no-fake-data principle)
    zones_raw = _load_yaml(ZONES_FILE).get("zones", []) or []
    cells = _heatmap_grid(layer, events, zones_raw, grid)
    return {
        "layer": layer,
        "grid": grid,
        "cell_size": round(1.0 / grid, 4),
        "cells": cells,
        "degraded": degraded,
    }


def _insight_chains(
    events: list[dict], now_ms: int, snapshots: list[dict] | None = None
) -> list[dict]:
    """Derive narrative insight chains from recent events.

    Every chain traces to a real congestion/collision signal — when there
    are none, the rail renders its empty state (no demo fallback).
    """
    derived = _predict_from_events(events, now_ms, snapshots)
    chains: list[dict] = []

    for c in derived["congestion"][:3]:
        zone = c["zone"]
        eta = c["eta_seconds"]
        chain_id = f"ic-{c['event_id']}"
        chains.append(
            {
                "id": chain_id,
                "title": f"Congestion prévue dans {zone.replace('_', ' ').title()}",
                "outcome": f"Densité prédite {int(c['density'] * 100)} % — reroutage conseillé",
                "severity": "warning",
                "timestamp_ms": c["timestamp_ms"],
                "steps": [
                    {
                        "label": "Ralentissement chariot détecté",
                        "status": "done",
                        "ts_ms": c["timestamp_ms"],
                    },
                    {
                        "label": f"IA prédit congestion dans {eta}s",
                        "status": "done",
                        "ts_ms": c["timestamp_ms"],
                    },
                    {
                        "label": "Reroutage suggéré via allée parallèle",
                        "status": "done",
                        "ts_ms": c["timestamp_ms"],
                    },
                    {
                        "label": "En attente de validation opérateur",
                        "status": "pending",
                        "ts_ms": None,
                    },
                ],
            }
        )

    for col in derived["collision"][:2]:
        chain_id = f"ic-{col['event_id']}"
        chains.append(
            {
                "id": chain_id,
                "title": "Risque de collision détecté",
                "outcome": f"ETA {col['eta_seconds']} s — alerte poussée aux conducteurs",
                "severity": "critical",
                "timestamp_ms": col["timestamp_ms"],
                "steps": [
                    {
                        "label": "2 trajectoires convergentes",
                        "status": "done",
                        "ts_ms": col["timestamp_ms"],
                    },
                    {
                        "label": f"Point d'impact estimé ({col['point_x']:.2f}, {col['point_y']:.2f})",
                        "status": "done",
                        "ts_ms": col["timestamp_ms"],
                    },
                    {
                        "label": "Alerte sonore + visuelle envoyée",
                        "status": "done",
                        "ts_ms": col["timestamp_ms"],
                    },
                    {
                        "label": "Décélération automatique recommandée",
                        "status": "pending",
                        "ts_ms": None,
                    },
                ],
            }
        )

    # No fabricated fallback chain: an empty list means the rail renders
    # its "no insights yet" state (no-fake-data principle).
    chains.sort(key=lambda c: c["timestamp_ms"], reverse=True)
    return chains


@router.get("/insights")
def list_insights(n: int = 10) -> dict:
    events, degraded = _peek_topic(KAFKA_EVENTS_TOPIC, n=300, timeout_s=0.5)
    now_ms = int(time.time() * 1000)
    snapshots, _ = _peek_topic(KAFKA_OCCUPANCY_TOPIC, n=2500, timeout_s=1.0)
    chains = _insight_chains(events, now_ms, snapshots)
    return {"insights": chains[:n], "degraded": degraded}


# ---------------------------------------------------------------------------
# Workforce & tasks — operational CRUD for the Workforce/Tasks dashboard pages.
# This is an in-memory prototype store, NOT model output, so seeding sample
# rows is fine (the no-fake-data rule covers KPIs/forecasts/anomalies, which
# stay tied to real Kafka events). The full DB-backed version lives on the
# frontend-updates branch (services/api/database.py); swap this for it when
# persistence is needed.
# ---------------------------------------------------------------------------
_WORKERS: list[dict] = [
    {
        "id": "W-001",
        "name": "Yassine B.",
        "email": "yassine@logivision.com",
        "role": "operator",
        "zone": "DOCK-A",
        "status": "active",
        "last_seen": "just now",
        "efficiency": 94,
    },
    {
        "id": "W-002",
        "name": "Farah E.",
        "email": "farah@logivision.com",
        "role": "admin",
        "zone": "Control Room",
        "status": "active",
        "last_seen": "2 min ago",
        "efficiency": 98,
    },
    {
        "id": "W-003",
        "name": "Karim T.",
        "email": "karim@logivision.com",
        "role": "operator",
        "zone": "AISLE-A1",
        "status": "break",
        "last_seen": "15 min ago",
        "efficiency": 88,
    },
]
_TASKS: list[dict] = [
    {
        "id": "T-001",
        "title": "Inspecter palette zone A1",
        "zone": "AISLE-A1",
        "priority": "high",
        "due_time": "Today",
        "column": "To Do",
        "assigned_to": "W-001",
    },
    {
        "id": "T-002",
        "title": "Vérifier chariot quai B",
        "zone": "DOCK-B",
        "priority": "medium",
        "due_time": "Today",
        "column": "In Progress",
        "assigned_to": "W-003",
    },
]


@router.get("/workers")
def list_workers() -> dict:
    return {"workers": _WORKERS}


@router.post("/workers")
def create_worker(worker: dict) -> dict:
    worker.setdefault("id", f"W-{len(_WORKERS) + 1:03d}")
    worker.setdefault("status", "active")
    worker.setdefault("last_seen", "just now")
    worker.setdefault("efficiency", 100)
    _WORKERS.append(worker)
    return worker


@router.get("/tasks")
def list_tasks() -> dict:
    return {"tasks": _TASKS}


@router.post("/tasks")
def create_task(task: dict) -> dict:
    task.setdefault("id", f"T-{len(_TASKS) + 1:03d}")
    task.setdefault("column", "To Do")
    _TASKS.append(task)
    return task


# Demo auth for the redesign's login flow. NOT real security — a prototype
# gate matching the credentials shown on the login page. Swap for the
# DB-backed auth (frontend-updates branch) before any real deployment.
_DEMO_CREDENTIALS = {
    "admin@logivision.com": {"password": "admin123", "role": "admin"},
    "worker@logivision.com": {"password": "worker123", "role": "worker"},
}


@router.post("/login")
def login(creds: dict) -> dict:
    email = (creds.get("email") or "").strip().lower()
    user = _DEMO_CREDENTIALS.get(email)
    if not user or user["password"] != (creds.get("password") or ""):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    return {"token": f"demo-{email}-{int(time.time())}", "role": user["role"]}
