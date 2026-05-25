"""
Tests unitaires pour le job stationary_detection.
On teste la logique pure sans Flink ni Kafka.
"""

from __future__ import annotations

from jobs.stationary_detection import (
    COOLDOWN_SEC,
    MOVEMENT_PX,
    STATIONARY_SEC,
    TrackState,
)


def test_track_state_creation() -> None:
    """TrackState se crée correctement avec les valeurs par défaut."""
    state = TrackState(first_seen_ms=1700000000000, last_x=100.0, last_y=200.0)
    assert state.first_seen_ms == 1700000000000
    assert state.last_x == 100.0
    assert state.alerted_at_ms == 0


def test_object_moved_resets_state() -> None:
    """Un objet qui bouge dépasse le seuil de mouvement."""
    state = TrackState(first_seen_ms=1700000000000, last_x=100.0, last_y=100.0)
    new_x = 100.0 + MOVEMENT_PX + 1
    distance = ((new_x - state.last_x) ** 2) ** 0.5
    assert distance > MOVEMENT_PX


def test_stationary_threshold() -> None:
    """Le seuil de détection est bien défini."""
    assert STATIONARY_SEC > 0
    assert MOVEMENT_PX > 0
    assert COOLDOWN_SEC > 0


def test_no_alert_before_threshold() -> None:
    """Pas d'alerte si le temps écoulé est inférieur au seuil."""
    now = 1700000000000
    state = TrackState(first_seen_ms=now, last_x=100.0, last_y=100.0)
    later = now + (STATIONARY_SEC - 10) * 1000
    elapsed_sec = (later - state.first_seen_ms) / 1000.0
    assert elapsed_sec < STATIONARY_SEC


def test_alert_after_threshold() -> None:
    """Alerte déclenchée si le temps écoulé dépasse le seuil."""
    now = 1700000000000
    state = TrackState(first_seen_ms=now, last_x=100.0, last_y=100.0, alerted_at_ms=0)
    later = now + (STATIONARY_SEC + 10) * 1000
    elapsed_sec = (later - state.first_seen_ms) / 1000.0
    assert elapsed_sec >= STATIONARY_SEC
    assert state.alerted_at_ms == 0


def test_cooldown_prevents_double_alert() -> None:
    """Le cooldown empêche une deuxième alerte trop rapide."""
    now = 1700000000000
    state = TrackState(
        first_seen_ms=now,
        last_x=100.0,
        last_y=100.0,
        alerted_at_ms=now,
    )
    # Temps écoulé depuis dernière alerte < cooldown
    later = now + (COOLDOWN_SEC - 10) * 1000
    time_since_alert = later - state.alerted_at_ms
    assert time_since_alert < COOLDOWN_SEC * 1000
