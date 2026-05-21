"""Complex Event Processing on the `detections` stream → emits `events`.

CLAUDE.md §6.3 describes 3 Flink jobs (stationary_detection, zone_violation,
kpi_aggregator). Running a full Flink cluster locally is heavy; this module
ships the same logic as a single Python process backed by an in-process
state store. It is *good enough* for the academic demo and for local
development; the production deployment would replace this with the PyFlink
jobs whose interface contract this code already matches.

Rules implemented:
    - stationary_object — a tracked object whose centroid stays within
      `stationary_radius_px` for `stationary_window_s` emits one event.
    - zone_violation    — when a track's centroid is inside any zone
      with `kind: forbidden` (or legacy `forbidden: true`).
    - entry             — when a track first lands in a zone with
      `kind: entry`. Severity = info; powers the "Entrées" KPI.
    - exit              — when a track first lands in a zone with
      `kind: exit`. Severity = info; powers the "Sorties" KPI.

The consumer reads `detections` (not `tracks`) for now; the projected
upgrade is to add a ByteTrack stage between `detections` and `events`
so that real `track_id`s are used. Until then we approximate a track by
hashing `(camera_id, class_id, bbox_quantised)`.

Usage:
    python -m services.stream_processor.cep
    # optional: --zones infra/zones.example.yaml --stationary-seconds 30
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import signal
import sys
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class TrackPoint:
    timestamp_ms: int
    centroid: tuple[float, float]


@dataclass
class TrackState:
    points: deque[TrackPoint] = field(default_factory=lambda: deque(maxlen=2000))
    stationary_event_emitted_ms: int = 0
    last_zone: str | None = None


# Allowed values for Zone.kind. `forbidden` keeps the legacy behaviour
# (emits zone_violation). `entry` / `exit` drive the warehouse KPIs.
# `shelf` is a passive zone — useful for occupancy aggregates without
# firing events.
ZONE_KINDS = ("forbidden", "entry", "exit", "shelf")


@dataclass
class Zone:
    name: str
    forbidden: bool
    polygon: list[tuple[float, float]]  # (x, y) in normalized 0..1 coordinates
    kind: str = "forbidden"  # one of ZONE_KINDS


@dataclass
class CEPConfig:
    bootstrap_servers: str = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    input_topic: str = os.environ.get("KAFKA_DETECTIONS_TOPIC", "detections")
    output_topic: str = os.environ.get("KAFKA_EVENTS_TOPIC", "events")
    consumer_group: str = os.environ.get("KAFKA_CONSUMER_GROUP", "cep-processors")
    stationary_window_s: float = 30.0
    stationary_radius_px: float = 25.0
    # Re-emit cooldown so we don't spam the same stationary alert.
    stationary_cooldown_s: float = 60.0


def _centroid(detection: dict) -> tuple[float, float]:
    return ((detection["x1"] + detection["x2"]) / 2, (detection["y1"] + detection["y2"]) / 2)


def _approximate_track_id(camera_id: str, detection: dict) -> str:
    """Deterministic pseudo-track-id until ByteTrack lands.

    Quantises the centroid to a 32-px grid so consecutive frames of the
    same object map to the same key.
    """
    cx, cy = _centroid(detection)
    return f"{camera_id}:{detection['class_id']}:{int(cx // 32)}:{int(cy // 32)}"


def _is_stationary(points: list[TrackPoint], radius_px: float) -> bool:
    if len(points) < 2:
        return False
    xs = [p.centroid[0] for p in points]
    ys = [p.centroid[1] for p in points]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    return all(math.hypot(p.centroid[0] - cx, p.centroid[1] - cy) <= radius_px for p in points)


def _load_zones(path: Path | None) -> list[Zone]:
    if path is None or not path.is_file():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    zones: list[Zone] = []
    for entry in raw.get("zones", []):
        forbidden = bool(entry.get("forbidden", False))
        # `kind` may be set explicitly; otherwise derive from legacy
        # `forbidden` flag (True → forbidden, False → shelf).
        kind = entry.get("kind") or ("forbidden" if forbidden else "shelf")
        if kind not in ZONE_KINDS:
            logger.warning(
                "zone %r has unknown kind=%r, falling back to shelf", entry["name"], kind
            )
            kind = "shelf"
        # Keep `forbidden` consistent with `kind` so legacy callers stay happy.
        if kind == "forbidden":
            forbidden = True
        zones.append(
            Zone(
                name=entry["name"],
                forbidden=forbidden,
                polygon=[(p["x"], p["y"]) for p in entry["polygon"]],
                kind=kind,
            )
        )
    return zones


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """Standard ray-casting algorithm."""
    x, y = point
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _normalised_centroid(detection: dict, image_w: int, image_h: int) -> tuple[float, float]:
    cx, cy = _centroid(detection)
    return (cx / max(image_w, 1), cy / max(image_h, 1))


def evaluate_stationary(
    track_id: str,  # noqa: ARG001 — kept for API symmetry / future per-track state
    state: TrackState,
    now_ms: int,
    config: CEPConfig,
) -> bool:
    """Decide whether to emit a stationary_object event for this track."""
    window_start = now_ms - int(config.stationary_window_s * 1000)
    relevant = [p for p in state.points if p.timestamp_ms >= window_start]
    if len(relevant) < 3:
        return False
    if not _is_stationary(relevant, config.stationary_radius_px):
        return False
    # Cooldown — skipped when we have never emitted (sentinel value 0).
    if state.stationary_event_emitted_ms == 0:
        return True
    return (now_ms - state.stationary_event_emitted_ms) >= config.stationary_cooldown_s * 1000


def evaluate_zone_violation(
    detection: dict,
    image_w: int,
    image_h: int,
    zones: list[Zone],
) -> Zone | None:
    if not zones:
        return None
    nx, ny = _normalised_centroid(detection, image_w, image_h)
    for zone in zones:
        if zone.forbidden and _point_in_polygon((nx, ny), zone.polygon):
            return zone
    return None


def evaluate_zone_membership(
    detection: dict,
    image_w: int,
    image_h: int,
    zones: list[Zone],
) -> Zone | None:
    """Return the first zone whose polygon contains the centroid (any kind)."""
    if not zones:
        return None
    nx, ny = _normalised_centroid(detection, image_w, image_h)
    for zone in zones:
        if _point_in_polygon((nx, ny), zone.polygon):
            return zone
    return None


def make_event(
    *,
    event_type: str,
    severity: str,
    camera_id: str | None,
    track_id: str | None,
    payload: dict[str, str],
    timestamp_ms: int,
) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "severity": severity,
        "timestamp_ms": timestamp_ms,
        "camera_id": camera_id,
        "track_id": track_id,
        "payload": payload,
    }


def process_one(
    detection_message: dict,
    states: dict[str, TrackState],
    zones: list[Zone],
    config: CEPConfig,
) -> list[dict]:
    """Update state for one frame and return the events to emit."""
    emitted: list[dict] = []
    camera_id = detection_message["camera_id"]
    timestamp_ms = int(detection_message["timestamp_ms"])
    # We don't know the original image dims server-side, so use bbox-relative
    # normalisation: a zone polygon is defined in 0..1 of (x2-max, y2-max).
    # Estimate from the largest bbox seen in this batch.
    image_w = max((int(d.get("x2", 0)) for d in detection_message.get("detections", [])), default=1)
    image_h = max((int(d.get("y2", 0)) for d in detection_message.get("detections", [])), default=1)

    for detection in detection_message.get("detections", []):
        track_id = _approximate_track_id(camera_id, detection)
        state = states.setdefault(track_id, TrackState())
        state.points.append(TrackPoint(timestamp_ms=timestamp_ms, centroid=_centroid(detection)))

        if evaluate_stationary(track_id, state, timestamp_ms, config):
            state.stationary_event_emitted_ms = timestamp_ms
            emitted.append(
                make_event(
                    event_type="stationary_object",
                    severity="warning",
                    camera_id=camera_id,
                    track_id=track_id,
                    payload={
                        "class_name": detection.get("class_name", ""),
                        "centroid_x": str(state.points[-1].centroid[0]),
                        "centroid_y": str(state.points[-1].centroid[1]),
                        "window_seconds": str(config.stationary_window_s),
                    },
                    timestamp_ms=timestamp_ms,
                )
            )

        # Dispatch on the zone's kind: forbidden → critical violation;
        # entry/exit → info event used by the KPI tiles; shelf → silent.
        zone = evaluate_zone_membership(detection, image_w, image_h, zones)
        if zone is not None and state.last_zone != zone.name:
            state.last_zone = zone.name
            payload = {"zone": zone.name, "class_name": detection.get("class_name", "")}
            if zone.kind == "forbidden":
                emitted.append(
                    make_event(
                        event_type="zone_violation",
                        severity="critical",
                        camera_id=camera_id,
                        track_id=track_id,
                        payload=payload,
                        timestamp_ms=timestamp_ms,
                    )
                )
            elif zone.kind == "entry":
                emitted.append(
                    make_event(
                        event_type="entry",
                        severity="info",
                        camera_id=camera_id,
                        track_id=track_id,
                        payload=payload,
                        timestamp_ms=timestamp_ms,
                    )
                )
            elif zone.kind == "exit":
                emitted.append(
                    make_event(
                        event_type="exit",
                        severity="info",
                        camera_id=camera_id,
                        track_id=track_id,
                        payload=payload,
                        timestamp_ms=timestamp_ms,
                    )
                )
            # `shelf` is a passive zone — no event, just remembers presence.
    return emitted


def run(config: CEPConfig, zones: list[Zone], stop_after: int | None = None) -> int:
    """Consume `detections`, evaluate CEP rules, publish to `events`."""
    from confluent_kafka import Consumer, Producer

    consumer = Consumer(
        {
            "bootstrap.servers": config.bootstrap_servers,
            "group.id": config.consumer_group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([config.input_topic])
    producer = Producer({"bootstrap.servers": config.bootstrap_servers})

    states: dict[str, TrackState] = defaultdict(TrackState)
    running = True
    n_messages = 0
    n_events = 0

    def _shutdown(*_a: Any) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while running:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                logger.warning("consumer error: %s", msg.error())
                continue
            try:
                detection_msg = json.loads(msg.value().decode("utf-8"))
                events = process_one(detection_msg, states, zones, config)
                for evt in events:
                    producer.produce(
                        config.output_topic,
                        key=(evt["track_id"] or evt["event_id"]).encode(),
                        value=json.dumps(evt).encode(),
                    )
                    n_events += 1
                producer.poll(0)
                consumer.commit(msg, asynchronous=False)
                n_messages += 1
                if stop_after is not None and n_messages >= stop_after:
                    break
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to process message: %s", exc)
    finally:
        producer.flush(timeout=5.0)
        consumer.close()
    logger.info("processed %d detection messages, emitted %d events", n_messages, n_events)
    return n_events


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--zones", type=Path, default=None, help="Path to zones YAML config.")
    parser.add_argument("--stationary-seconds", type=float, default=30.0)
    parser.add_argument("--stationary-radius", type=float, default=25.0)
    parser.add_argument("--cooldown-seconds", type=float, default=60.0)
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    zones = _load_zones(args.zones)
    cfg = CEPConfig(
        stationary_window_s=args.stationary_seconds,
        stationary_radius_px=args.stationary_radius,
        stationary_cooldown_s=args.cooldown_seconds,
    )
    logger.info(
        "starting CEP: in=%s out=%s window=%ss radius=%spx zones=%d",
        cfg.input_topic,
        cfg.output_topic,
        cfg.stationary_window_s,
        cfg.stationary_radius_px,
        len(zones),
    )
    run(cfg, zones)
    return 0


if __name__ == "__main__":
    sys.exit(main())
