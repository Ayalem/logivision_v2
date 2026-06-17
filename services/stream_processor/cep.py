"""Complex Event Processing on the `detections` stream → emits `events`.

`services/flink-jobs/` holds the production Flink jobs (stationary_detection,
zone_violation, kpi_aggregator). Running a full Flink cluster locally is heavy; this module
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
    # bbox dimensions captured at this frame — needed for the box-falling
    # rule which compares aspect-ratio over time (a box that "tips" goes
    # from tall-and-narrow to flat-and-wide in <1 s).
    width: float = 0.0
    height: float = 0.0


@dataclass
class TrackState:
    points: deque[TrackPoint] = field(default_factory=lambda: deque(maxlen=2000))
    # "Never emitted" sentinel is -1, not 0: timestamp_ms=0 is a legitimate
    # value (epoch-relative streams, tests), and a real emission at t=0 must
    # not be mistaken for "never fired" on the next message.
    stationary_event_emitted_ms: int = -1
    last_zone: str | None = None
    # Cooldown for falling events so a single fall doesn't spam the topic
    # across the 1-second window we evaluate it on.
    falling_event_emitted_ms: int = -1
    # Cooldown for ML trajectory anomalies (one fall shouldn't re-fire
    # on every scored window of its aftermath).
    trajectory_anomaly_emitted_ms: int = -1


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
    # Track-count capacity used to turn raw occupancy into a bounded 0..1
    # ratio — the quantity the congestion LSTM was trained on.
    capacity: int = 10


@dataclass
class CEPConfig:
    bootstrap_servers: str = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    input_topic: str = os.environ.get("KAFKA_DETECTIONS_TOPIC", "detections")
    output_topic: str = os.environ.get("KAFKA_EVENTS_TOPIC", "events")
    occupancy_topic: str = os.environ.get("KAFKA_OCCUPANCY_TOPIC", "zone-occupancy")
    consumer_group: str = os.environ.get("KAFKA_CONSUMER_GROUP", "cep-processors")
    # Zone-occupancy snapshots: one message per zone every
    # `occupancy_snapshot_s`; a track stops counting toward a zone after
    # `occupancy_idle_expiry_s` without a sighting.
    occupancy_snapshot_s: float = float(os.environ.get("OCCUPANCY_SNAPSHOT_S", "300"))
    occupancy_idle_expiry_s: float = 30.0
    # ── Anomaly detection mode ──────────────────────────────────────────
    #   ae    → GRU autoencoder is the primary detector; the stationary/
    #           falling rules still run but emit severity=info with
    #           payload.source=rule-baseline (article comparison data —
    #           the dashboard's anomaly feed skips info severity).
    #   rules → legacy behaviour, rules at full severity (also the
    #           automatic fallback when the AE artifact fails to load).
    #   both  → rules at full severity AND AE events (debug).
    anomaly_mode: str = os.environ.get("ANOMALY_MODE", "ae")
    trajectory_anomaly_cooldown_s: float = 10.0
    stationary_window_s: float = 30.0
    stationary_radius_px: float = 25.0
    # Re-emit cooldown so we don't spam the same stationary alert.
    stationary_cooldown_s: float = 60.0
    # ── Falling-box rule (T1.D) ─────────────────────────────────────────
    # A box "tips over" within ~0.5 s: its aspect-ratio (h/w) flips from
    # >1 to <1 AND its centroid_y jumps downward. We evaluate this on a
    # 1-s sliding window per track.
    falling_window_s: float = 1.0
    falling_aspect_delta_min: float = 0.6  # |Δ(h/w)| must exceed this
    falling_centroid_y_delta_min: float = 0.10  # normalised (frame %)
    falling_cooldown_s: float = 10.0


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
                capacity=int(entry.get("capacity", 10)),
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
    # Cooldown — skipped when we have never emitted (sentinel value -1).
    if state.stationary_event_emitted_ms < 0:
        return True
    return (now_ms - state.stationary_event_emitted_ms) >= config.stationary_cooldown_s * 1000


def evaluate_falling(
    state: TrackState,
    now_ms: int,
    config: CEPConfig,
    frame_height: int = 1,
) -> bool:
    """Decide whether to emit a `box_falling` event for this track.

    Signature of a fall (the rule we ship in v0; ML upgrade documented as
    future work):

        1. Within a 1-second sliding window we have ≥ 2 trackpoints with
           non-zero width and height.
        2. The aspect ratio (height / width) **flips** by at least
           `falling_aspect_delta_min` (default 0.6). Tall-and-narrow → flat-
           and-wide is the classic tipping pattern.
        3. The centroid moves **downward** in absolute terms by at least
           `falling_centroid_y_delta_min` of the frame height (default 10 %).
        4. Cooldown `falling_cooldown_s` (10 s) prevents re-firing on the
           continuation of the same fall.

    All three signals together — anything weaker triggers too many false
    positives on slow shape-changes (a forklift turning) or pure drops
    (a box on a conveyor going down a chute).
    """
    window_start = now_ms - int(config.falling_window_s * 1000)
    pts = [p for p in state.points if p.timestamp_ms >= window_start]
    pts = [p for p in pts if p.width > 0 and p.height > 0]
    if len(pts) < 2:
        return False

    # Aspect ratio = height / width. A tall standing box has h/w > 1;
    # after tipping flat-side-up, h/w < 1. We compare the OLDEST and
    # NEWEST point in the window — using only the extremes makes the
    # threshold meaningful regardless of how many intermediate frames
    # the worker produced.
    oldest, newest = pts[0], pts[-1]
    ar_old = oldest.height / max(1e-6, oldest.width)
    ar_new = newest.height / max(1e-6, newest.width)
    if abs(ar_new - ar_old) < config.falling_aspect_delta_min:
        return False

    # Frame-relative vertical drop. Positive Δy = downward in image coords.
    centroid_dy = (newest.centroid[1] - oldest.centroid[1]) / max(1, frame_height)
    if centroid_dy < config.falling_centroid_y_delta_min:
        return False

    # Cooldown
    if state.falling_event_emitted_ms < 0:
        return True
    return (now_ms - state.falling_event_emitted_ms) >= config.falling_cooldown_s * 1000


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


class ZoneOccupancyAggregator:
    """Tracks live per-zone occupancy and emits periodic ratio snapshots.

    Counts distinct tracks currently inside each zone (a track expires
    after `occupancy_idle_expiry_s` without a sighting) and every
    `occupancy_snapshot_s` produces one message per zone for the
    `zone-occupancy` topic:

        {"timestamp_ms", "zone", "occupied_tracks", "capacity", "ratio"}

    `ratio` is bounded 0..1 (occupied/capacity) — the exact quantity the
    congestion LSTM was trained on (Parking Birmingham occupancy ratios),
    which is what makes the domain transfer defensible. Uses event time
    (message timestamps), so offline replays produce a faithful history.
    """

    def __init__(self, zones: list[Zone], config: CEPConfig):
        self._zones = zones
        self._config = config
        # zone name → {track_id → last_seen_ms}
        self._presence: dict[str, dict[str, int]] = {z.name: {} for z in zones}
        self._last_snapshot_ms = 0

    def observe(self, zone_name: str | None, track_id: str, now_ms: int) -> None:
        """Record one sighting. `zone_name=None` removes the track everywhere."""
        for name, tracks in self._presence.items():
            if name == zone_name:
                tracks[track_id] = now_ms
            else:
                tracks.pop(track_id, None)

    def maybe_snapshot(self, now_ms: int) -> list[dict]:
        """Return one snapshot per zone if the interval elapsed, else []."""
        if self._last_snapshot_ms == 0:
            self._last_snapshot_ms = now_ms
            return []
        if now_ms - self._last_snapshot_ms < self._config.occupancy_snapshot_s * 1000:
            return []
        self._last_snapshot_ms = now_ms
        expiry_ms = int(self._config.occupancy_idle_expiry_s * 1000)
        snapshots: list[dict] = []
        for zone in self._zones:
            tracks = self._presence[zone.name]
            for tid, seen in list(tracks.items()):
                if now_ms - seen > expiry_ms:
                    del tracks[tid]
            capacity = max(1, zone.capacity)
            snapshots.append(
                {
                    "timestamp_ms": now_ms,
                    "zone": zone.name,
                    "occupied_tracks": len(tracks),
                    "capacity": capacity,
                    "ratio": round(min(1.0, len(tracks) / capacity), 4),
                }
            )
        return snapshots


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
    occupancy: ZoneOccupancyAggregator | None = None,
    scorer: Any | None = None,
) -> list[dict]:
    """Update state for one frame and return the events to emit.

    `scorer` is an `anomaly_scorer.AnomalyScorer` (or None). With
    `anomaly_mode="ae"` and a loaded scorer, the GRU-AE is the primary
    anomaly detector and the stationary/falling rules are demoted to
    severity=info baseline events. Without a scorer the rules keep full
    severity regardless of the configured mode (graceful fallback).
    """
    emitted: list[dict] = []
    camera_id = detection_message["camera_id"]
    timestamp_ms = int(detection_message["timestamp_ms"])

    mode = config.anomaly_mode if config.anomaly_mode in ("ae", "rules", "both") else "ae"
    ae_active = mode in ("ae", "both") and scorer is not None and scorer.available
    demote_rules = mode == "ae" and ae_active
    # Prefer the true frame dimensions when the worker passed them through;
    # fall back to the legacy bbox-extent estimate for older payloads
    # (zone polygons are defined in 0..1 of the frame).
    image_w = int(detection_message.get("width") or 0) or max(
        (int(d.get("x2", 0)) for d in detection_message.get("detections", [])), default=1
    )
    image_h = int(detection_message.get("height") or 0) or max(
        (int(d.get("y2", 0)) for d in detection_message.get("detections", [])), default=1
    )

    for detection in detection_message.get("detections", []):
        # Prefer the real ByteTrack track_id from the worker (integer);
        # fall back to the legacy hash-quantised string for older payloads.
        real_tid = detection.get("track_id")
        track_id = (
            f"{camera_id}:{int(real_tid)}"
            if isinstance(real_tid, int)
            else _approximate_track_id(camera_id, detection)
        )
        state = states.setdefault(track_id, TrackState())
        bbox_w = max(0.0, float(detection.get("x2", 0)) - float(detection.get("x1", 0)))
        bbox_h = max(0.0, float(detection.get("y2", 0)) - float(detection.get("y1", 0)))
        state.points.append(
            TrackPoint(
                timestamp_ms=timestamp_ms,
                centroid=_centroid(detection),
                width=bbox_w,
                height=bbox_h,
            )
        )

        if evaluate_stationary(track_id, state, timestamp_ms, config):
            state.stationary_event_emitted_ms = timestamp_ms
            payload = {
                "class_name": detection.get("class_name", ""),
                "centroid_x": str(state.points[-1].centroid[0]),
                "centroid_y": str(state.points[-1].centroid[1]),
                "window_seconds": str(config.stationary_window_s),
            }
            if demote_rules:
                payload["source"] = "rule-baseline"
            emitted.append(
                make_event(
                    event_type="stationary_object",
                    severity="info" if demote_rules else "warning",
                    camera_id=camera_id,
                    track_id=track_id,
                    payload=payload,
                    timestamp_ms=timestamp_ms,
                )
            )

        # Box-falling — a tipping carton flips its aspect ratio AND drops.
        # We can only evaluate this when the bbox dims are non-zero, which
        # is always the case for real worker output but may be skipped in
        # synthetic test payloads.
        if bbox_w > 0 and bbox_h > 0 and evaluate_falling(state, timestamp_ms, config, image_h):
            state.falling_event_emitted_ms = timestamp_ms
            ar_now = bbox_h / max(1e-6, bbox_w)
            payload = {
                "class_name": detection.get("class_name", ""),
                "centroid_x": f"{state.points[-1].centroid[0]:.3f}",
                "centroid_y": f"{state.points[-1].centroid[1]:.3f}",
                "aspect_ratio_now": f"{ar_now:.3f}",
                "window_seconds": str(config.falling_window_s),
            }
            if demote_rules:
                payload["source"] = "rule-baseline"
            emitted.append(
                make_event(
                    event_type="box_falling",
                    severity="info" if demote_rules else "critical",
                    camera_id=camera_id,
                    track_id=track_id,
                    payload=payload,
                    timestamp_ms=timestamp_ms,
                )
            )

        # ── ML trajectory anomaly (primary detector in `ae` mode) ──────
        if ae_active:
            cooldown_over = (
                state.trajectory_anomaly_emitted_ms < 0
                or (timestamp_ms - state.trajectory_anomaly_emitted_ms)
                >= config.trajectory_anomaly_cooldown_s * 1000
            )
            if cooldown_over:
                result = scorer.score_track(
                    track_id, state, timestamp_ms, math.hypot(image_w, image_h)
                )
                if result is not None:
                    state.trajectory_anomaly_emitted_ms = timestamp_ms
                    emitted.append(
                        make_event(
                            event_type="trajectory_anomaly",
                            severity=result.severity,
                            camera_id=camera_id,
                            track_id=track_id,
                            payload={
                                "class_name": detection.get("class_name", ""),
                                "centroid_x": f"{state.points[-1].centroid[0]:.3f}",
                                "centroid_y": f"{state.points[-1].centroid[1]:.3f}",
                                "score": f"{result.score:.5f}",
                                "threshold": f"{result.threshold:.5f}",
                                "dominant_feature": result.dominant_feature,
                                "model_version": result.model_version,
                            },
                            timestamp_ms=timestamp_ms,
                        )
                    )

        # Dispatch on the zone's kind: forbidden → critical violation;
        # entry/exit → info event used by the KPI tiles; shelf → silent.
        zone = evaluate_zone_membership(detection, image_w, image_h, zones)
        if occupancy is not None:
            occupancy.observe(zone.name if zone else None, track_id, timestamp_ms)
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
    occupancy = ZoneOccupancyAggregator(zones, config) if zones else None

    scorer = None
    if config.anomaly_mode in ("ae", "both"):
        from services.stream_processor.anomaly_scorer import AnomalyScorer

        scorer = AnomalyScorer()
        if not scorer.available:
            logger.warning(
                "ANOMALY_MODE=%s but the trajectory-AE artifact is unavailable — "
                "falling back to rules mode (run notebook 08 to train it).",
                config.anomaly_mode,
            )
            scorer = None
        else:
            logger.info("Anomaly mode: %s (trajectory AE loaded)", config.anomaly_mode)

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
                events = process_one(detection_msg, states, zones, config, occupancy, scorer)
                for evt in events:
                    producer.produce(
                        config.output_topic,
                        key=(evt["track_id"] or evt["event_id"]).encode(),
                        value=json.dumps(evt).encode(),
                    )
                    n_events += 1
                if occupancy is not None:
                    for snap in occupancy.maybe_snapshot(int(detection_msg["timestamp_ms"])):
                        producer.produce(
                            config.occupancy_topic,
                            key=snap["zone"].encode(),
                            value=json.dumps(snap).encode(),
                        )
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
