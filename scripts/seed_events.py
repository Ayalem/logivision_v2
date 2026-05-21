"""Seed the Kafka `events` topic with realistic warehouse events for demos.

Why this exists
---------------
Running the full grabber → inference → CEP pipeline locally needs a video
source, a YOLO model, and three terminals.  For dashboard demos we just
want events flowing into the `events` topic so:
  * /api/anomalies, /api/entries-exits, /api/kpis show real data
  * /ws/events pushes live cards into the operator activity feed
  * /api/predictions computes congestion + collision forecasts
  * the 3D twin's TrajectoryArrows + CollisionBeacons animate

Usage:
    uv run python scripts/seed_events.py                # default: 1 burst/s, forever
    uv run python scripts/seed_events.py --once         # one batch and exit
    uv run python scripts/seed_events.py --rate 0.3     # one burst every 0.3s
    uv run python scripts/seed_events.py --burst 4      # 4 events per burst
"""

from __future__ import annotations

import argparse
import json
import os
import random
import signal
import time
import uuid
from collections.abc import Iterator

ZONES_ENTRY = ["entrance_dock"]
ZONES_EXIT = ["exit_dock"]
ZONES_SHELF = ["shelf_A1", "shelf_A2", "shelf_A3", "shelf_A4"]
ZONES_FORBIDDEN = ["forbidden_aisle"]
CLASSES = ["carton", "palette", "chariot", "personne"]
CAMERAS = ["CAM01", "CAM02", "CAM03", "CAM04", "CAM05"]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _make_event(
    etype: str,
    severity: str,
    camera_id: str,
    track_id: str,
    zone: str,
    class_name: str,
    cx: float,
    cy: float,
) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": etype,
        "severity": severity,
        "timestamp_ms": _now_ms(),
        "camera_id": camera_id,
        "track_id": track_id,
        "payload": {
            "zone": zone,
            "class_name": class_name,
            "centroid_x": f"{cx:.3f}",
            "centroid_y": f"{cy:.3f}",
        },
    }


def burst(size: int) -> Iterator[dict]:
    """Yield `size` plausible events drawn from a weighted distribution.

    Weights:  entry 30% · exit 25% · stationary 25% · zone_violation 10% · shelf-move 10%
    """
    for _ in range(size):
        r = random.random()
        if r < 0.30:
            # Entry
            cam = random.choice(["CAM01", "CAM02"])
            track = f"{cam}:1:{random.randint(0,9)}:{random.randint(0,9)}"
            cx, cy = random.uniform(0.05, 0.22), random.uniform(0.04, 0.16)
            yield _make_event(
                "entry",
                "info",
                cam,
                track,
                random.choice(ZONES_ENTRY),
                random.choice(CLASSES[:3]),
                cx,
                cy,
            )
        elif r < 0.55:
            # Exit
            cam = random.choice(["CAM01", "CAM02"])
            track = f"{cam}:2:{random.randint(0,9)}:{random.randint(0,9)}"
            cx, cy = random.uniform(0.78, 0.97), random.uniform(0.04, 0.16)
            yield _make_event(
                "exit",
                "info",
                cam,
                track,
                random.choice(ZONES_EXIT),
                random.choice(CLASSES[:3]),
                cx,
                cy,
            )
        elif r < 0.80:
            # Stationary in a shelf (warning) — drives congestion forecasts.
            cam = random.choice(["CAM03", "CAM04"])
            zone = random.choice(ZONES_SHELF)
            base_x, base_y = {
                "shelf_A1": (0.17, 0.42),
                "shelf_A2": (0.47, 0.42),
                "shelf_A3": (0.17, 0.72),
                "shelf_A4": (0.47, 0.72),
            }[zone]
            track = f"{cam}:0:{random.randint(1,3)}:{random.randint(1,3)}"
            yield _make_event(
                "stationary_object",
                "warning",
                cam,
                track,
                zone,
                random.choice(CLASSES[:2]),
                base_x + random.uniform(-0.02, 0.02),
                base_y + random.uniform(-0.02, 0.02),
            )
        elif r < 0.90:
            # Critical zone violation (intrusion).
            cam = "CAM05"
            yield _make_event(
                "zone_violation",
                "critical",
                cam,
                f"{cam}:0:{random.randint(0,5)}:{random.randint(0,5)}",
                random.choice(ZONES_FORBIDDEN),
                "personne",
                random.uniform(0.72, 0.92),
                random.uniform(0.32, 0.82),
            )
        else:
            # Drifting object inside a shelf (non-critical).
            cam = random.choice(CAMERAS[:4])
            zone = random.choice(ZONES_SHELF)
            track = f"{cam}:0:{random.randint(4,9)}:{random.randint(4,9)}"
            yield _make_event(
                "stationary_object",
                "warning",
                cam,
                track,
                zone,
                "carton",
                random.uniform(0.1, 0.6),
                random.uniform(0.3, 0.85),
            )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--bootstrap", default=os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092"))
    p.add_argument("--topic", default=os.environ.get("KAFKA_EVENTS_TOPIC", "events"))
    p.add_argument("--rate", type=float, default=1.0, help="seconds between bursts")
    p.add_argument("--burst", type=int, default=3, help="events per burst")
    p.add_argument("--once", action="store_true", help="emit one burst and exit")
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    from confluent_kafka import Producer

    producer = Producer({"bootstrap.servers": args.bootstrap})

    running = True

    def _stop(*_a: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    sent = 0
    print(f"seeding {args.topic} on {args.bootstrap} — burst={args.burst} rate={args.rate}s")
    while running:
        for evt in burst(args.burst):
            producer.produce(
                args.topic,
                key=(evt["track_id"] or evt["event_id"]).encode(),
                value=json.dumps(evt).encode(),
            )
            sent += 1
        producer.poll(0)
        if args.once:
            break
        time.sleep(args.rate)

    producer.flush(timeout=5)
    print(f"sent {sent} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
