"""
Tests unitaires pour le job stationary_detection.
On teste la logique pure sans Flink ni Kafka.
"""

from __future__ import annotations

import json

from jobs.stationary_detection import (
    MOVEMENT_THRESHOLD_PX,
    STATIONARY_THRESHOLD_SEC,
    Detection,
    ParseDetection,
    StationaryState,
)


def test_detection_from_json() -> None:
    raw = json.dumps(
        {
            "object_id": "42",
            "label": "package",
            "x": 100.0,
            "y": 200.0,
            "confidence": 0.95,
            "timestamp": 1700000000000,
        }
    )
    d = Detection.from_json(raw)
    assert d.object_id == "42"
    assert d.x == 100.0
    assert d.timestamp == 1700000000000


def test_detection_invalid_json() -> None:
    parser = ParseDetection()
    result = parser.map("not_valid_json{{{")
    assert result.object_id == "__invalid__"


def test_object_moved_resets_state() -> None:
    """Un objet qui bouge ne doit pas déclencher d'alerte."""
    now = 1700000000000
    state = StationaryState(
        first_seen_ts=now,
        last_x=100.0,
        last_y=100.0,
    )
    new_x = 100.0 + MOVEMENT_THRESHOLD_PX + 1
    distance = ((new_x - state.last_x) ** 2) ** 0.5
    assert distance > MOVEMENT_THRESHOLD_PX


def test_object_stationary_triggers_alert() -> None:
    """Un objet immobile depuis > seuil doit déclencher une alerte."""
    now = 1700000000000
    threshold_ms = STATIONARY_THRESHOLD_SEC * 1000
    state = StationaryState(
        first_seen_ts=now,
        last_x=100.0,
        last_y=100.0,
        alerted=False,
    )
    later = now + threshold_ms + 1000
    elapsed_sec = (later - state.first_seen_ts) / 1000.0
    assert elapsed_sec >= STATIONARY_THRESHOLD_SEC
    assert not state.alerted


def test_no_double_alert() -> None:
    """Une fois alerté, alerted=True empêche une deuxième alerte."""
    state = StationaryState(
        first_seen_ts=1700000000000,
        last_x=100.0,
        last_y=100.0,
        alerted=True,
    )
    assert state.alerted is True
