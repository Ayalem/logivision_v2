"""Unit tests for the CEP processor (Kafka not required)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml

from services.stream_processor.cep import (
    CEPConfig,
    TrackPoint,
    TrackState,
    Zone,
    _approximate_track_id,
    _centroid,
    _is_stationary,
    _load_zones,
    _point_in_polygon,
    evaluate_stationary,
    evaluate_zone_membership,
    evaluate_zone_violation,
    process_one,
)

# ---------- helpers ----------


def _det(x1: float, y1: float, x2: float, y2: float, class_id: int = 0) -> dict:
    return {
        "class_id": class_id,
        "class_name": "box",
        "confidence": 0.9,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
    }


# ---------- geometry ----------


def test_centroid_is_bbox_centre() -> None:
    assert _centroid(_det(10, 10, 30, 30)) == (20.0, 20.0)


def test_approximate_track_id_quantises_to_32px_grid() -> None:
    a = _approximate_track_id("CAM1", _det(0, 0, 31, 31))  # centroid (15.5, 15.5) → grid (0,0)
    b = _approximate_track_id("CAM1", _det(2, 2, 33, 33))  # centroid (17.5, 17.5) → grid (0,0)
    assert a == b
    c = _approximate_track_id("CAM1", _det(64, 0, 95, 31))  # centroid (79.5, 15.5) → grid (2,0)
    assert c != a


def test_is_stationary_true_for_small_radius_points() -> None:
    points = [TrackPoint(t * 1000, (100 + i * 0.5, 100 + i * 0.5)) for i, t in enumerate(range(5))]
    assert _is_stationary(points, radius_px=10)


def test_is_stationary_false_for_moving_points() -> None:
    points = [TrackPoint(t * 1000, (t * 100.0, 100)) for t in range(5)]
    assert not _is_stationary(points, radius_px=10)


def test_point_in_polygon_square() -> None:
    sq = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    assert _point_in_polygon((0.5, 0.5), sq)
    assert not _point_in_polygon((1.5, 0.5), sq)


# ---------- rule helpers ----------


def test_evaluate_stationary_needs_a_window() -> None:
    cfg = CEPConfig(stationary_window_s=10, stationary_radius_px=5)
    state = TrackState()
    # 1 point is not enough.
    state.points.append(TrackPoint(timestamp_ms=1000, centroid=(100.0, 100.0)))
    assert not evaluate_stationary("t1", state, now_ms=2000, config=cfg)


def test_evaluate_stationary_triggers_then_cools_down() -> None:
    cfg = CEPConfig(stationary_window_s=10, stationary_radius_px=5, stationary_cooldown_s=30)
    state = TrackState()
    # 4 points all clustered → stationary.
    for ms in (1000, 3000, 5000, 9000):
        state.points.append(TrackPoint(timestamp_ms=ms, centroid=(100.0, 100.0)))
    assert evaluate_stationary("t1", state, now_ms=9000, config=cfg) is True
    state.stationary_event_emitted_ms = 9000  # simulate emit
    # Another nearby point at 12000 — still within cooldown of 30 s.
    state.points.append(TrackPoint(timestamp_ms=12000, centroid=(100.0, 100.0)))
    assert evaluate_stationary("t1", state, now_ms=12000, config=cfg) is False


def test_evaluate_zone_violation_triggers_in_forbidden() -> None:
    zones = [
        Zone(name="aisle", forbidden=True, polygon=[(0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)])
    ]
    inside = _det(800, 100, 900, 200)  # cx=850/1000=0.85 → inside (image_w=1000)
    out = _det(100, 100, 200, 200)
    assert evaluate_zone_violation(inside, 1000, 1000, zones) is not None
    assert evaluate_zone_violation(out, 1000, 1000, zones) is None


def test_evaluate_zone_violation_ignores_allowed_zones() -> None:
    zones = [Zone(name="ok", forbidden=False, polygon=[(0, 0), (1, 0), (1, 1), (0, 1)])]
    assert evaluate_zone_violation(_det(10, 10, 20, 20), 100, 100, zones) is None


# ---------- end-to-end (in-process) ----------


def test_process_one_emits_stationary_after_repeated_centroid() -> None:
    cfg = CEPConfig(stationary_window_s=10, stationary_radius_px=5, stationary_cooldown_s=60)
    states: dict = defaultdict(TrackState)
    msg = {
        "camera_id": "CAM1",
        "timestamp_ms": 1000,
        "detections": [_det(100, 100, 130, 130)],
    }
    # Feed the same detection 4 times — exactly one event is emitted across
    # the burst (the others are suppressed by the cooldown).
    all_events: list[dict] = []
    for t in (1000, 3000, 5000, 9000):
        msg["timestamp_ms"] = t
        all_events.extend(process_one(msg, states, zones=[], config=cfg))
    stationary = [e for e in all_events if e["event_type"] == "stationary_object"]
    assert len(stationary) == 1


def test_process_one_emits_zone_violation_once_per_zone_entry() -> None:
    zones = [
        Zone(name="z1", forbidden=True, polygon=[(0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)])
    ]
    cfg = CEPConfig()
    states: dict = defaultdict(TrackState)
    msg = {
        "camera_id": "C",
        "timestamp_ms": 1000,
        "detections": [_det(700, 100, 900, 300)],  # cx=800 / max(900)=0.888 → inside
    }
    events_1 = process_one(msg, states, zones, cfg)
    # Re-fire on the same track → no new event (last_zone caches).
    events_2 = process_one(msg, states, zones, cfg)
    assert any(e["event_type"] == "zone_violation" for e in events_1)
    assert not any(e["event_type"] == "zone_violation" for e in events_2)


# ---------- zones loader ----------


def test_load_zones_parses_yaml(tmp_path: Path) -> None:
    p = tmp_path / "zones.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "zones": [
                    {
                        "name": "danger",
                        "forbidden": True,
                        "polygon": [
                            {"x": 0.1, "y": 0.1},
                            {"x": 0.9, "y": 0.1},
                            {"x": 0.9, "y": 0.9},
                            {"x": 0.1, "y": 0.9},
                        ],
                    }
                ]
            }
        )
    )
    zones = _load_zones(p)
    assert len(zones) == 1
    assert zones[0].name == "danger"
    assert zones[0].forbidden is True
    assert len(zones[0].polygon) == 4


def test_load_zones_handles_missing_file(tmp_path: Path) -> None:
    assert _load_zones(tmp_path / "nope.yaml") == []
    assert _load_zones(None) == []


# ---------- kind dispatch (entry / exit / shelf) ----------


def test_load_zones_reads_kind_field(tmp_path: Path) -> None:
    p = tmp_path / "zones.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "zones": [
                    {
                        "name": "in",
                        "kind": "entry",
                        "polygon": [
                            {"x": 0, "y": 0},
                            {"x": 1, "y": 0},
                            {"x": 1, "y": 1},
                            {"x": 0, "y": 1},
                        ],
                    },
                    {
                        "name": "out",
                        "kind": "exit",
                        "polygon": [
                            {"x": 0, "y": 0},
                            {"x": 1, "y": 0},
                            {"x": 1, "y": 1},
                            {"x": 0, "y": 1},
                        ],
                    },
                    {
                        "name": "wall",
                        "kind": "forbidden",
                        "polygon": [
                            {"x": 0, "y": 0},
                            {"x": 1, "y": 0},
                            {"x": 1, "y": 1},
                            {"x": 0, "y": 1},
                        ],
                    },
                ]
            }
        )
    )
    zones = _load_zones(p)
    by_name = {z.name: z for z in zones}
    assert by_name["in"].kind == "entry"
    assert by_name["out"].kind == "exit"
    assert by_name["wall"].kind == "forbidden"
    # forbidden flag stays consistent with kind so legacy callers work.
    assert by_name["wall"].forbidden is True
    assert by_name["in"].forbidden is False


def test_load_zones_defaults_kind_from_legacy_forbidden(tmp_path: Path) -> None:
    p = tmp_path / "zones.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "zones": [
                    {
                        "name": "legacy_forbidden",
                        "forbidden": True,
                        "polygon": [
                            {"x": 0, "y": 0},
                            {"x": 1, "y": 0},
                            {"x": 1, "y": 1},
                            {"x": 0, "y": 1},
                        ],
                    },
                    {
                        "name": "legacy_allowed",
                        "forbidden": False,
                        "polygon": [
                            {"x": 0, "y": 0},
                            {"x": 1, "y": 0},
                            {"x": 1, "y": 1},
                            {"x": 0, "y": 1},
                        ],
                    },
                ]
            }
        )
    )
    zones = _load_zones(p)
    assert zones[0].kind == "forbidden"
    assert zones[1].kind == "shelf"  # safe default for non-forbidden legacy zones


def test_evaluate_zone_membership_returns_first_match() -> None:
    zones = [
        Zone(name="a", forbidden=False, polygon=[(0, 0), (0.5, 0), (0.5, 1), (0, 1)], kind="entry"),
        Zone(name="b", forbidden=False, polygon=[(0.5, 0), (1, 0), (1, 1), (0.5, 1)], kind="exit"),
    ]
    # cx=200/1000=0.2 → inside "a"
    assert evaluate_zone_membership(_det(150, 100, 250, 200), 1000, 1000, zones).name == "a"
    # cx=750/1000=0.75 → inside "b"
    assert evaluate_zone_membership(_det(700, 100, 800, 200), 1000, 1000, zones).name == "b"


def test_process_one_emits_entry_event_for_entry_zone() -> None:
    # Narrow zone 0..0.25 so only the target carton (nx≈0.1) lands inside;
    # the calibration detection that fixes image_w sits at nx≈0.5 (outside).
    zones = [
        Zone(
            name="dock_in",
            forbidden=False,
            polygon=[(0, 0), (0.25, 0), (0.25, 1), (0, 1)],
            kind="entry",
        ),
    ]
    cfg = CEPConfig()
    states: dict = defaultdict(TrackState)
    msg = {
        "camera_id": "CAM1",
        "timestamp_ms": 1000,
        # target carton cx=40, calibration carton cx=100; image_w=max(x2)=200
        # → target nx=0.2 inside entry zone, calibration nx=0.5 outside.
        "detections": [_det(20, 20, 60, 60, class_id=1), _det(50, 0, 200, 200, class_id=2)],
    }
    events = process_one(msg, states, zones, cfg)
    entries = [e for e in events if e["event_type"] == "entry"]
    assert len(entries) == 1
    assert entries[0]["severity"] == "info"
    assert entries[0]["payload"]["zone"] == "dock_in"
    # Re-firing on the same track: dedupe via last_zone.
    events2 = process_one(msg, states, zones, cfg)
    assert not any(e["event_type"] == "entry" for e in events2)


def test_process_one_emits_exit_event_for_exit_zone() -> None:
    # Narrow zone 0.75..1.0 so only the target carton lands inside.
    zones = [
        Zone(
            name="dock_out",
            forbidden=False,
            polygon=[(0.75, 0), (1, 0), (1, 1), (0.75, 1)],
            kind="exit",
        ),
    ]
    cfg = CEPConfig()
    states: dict = defaultdict(TrackState)
    msg = {
        "camera_id": "CAM1",
        "timestamp_ms": 2000,
        # target cx=170, calibration cx=100; image_w=max(x2)=200
        # → target nx=0.85 inside, calibration nx=0.5 outside.
        "detections": [_det(140, 50, 200, 90, class_id=1), _det(0, 0, 200, 200, class_id=2)],
    }
    events = process_one(msg, states, zones, cfg)
    exits = [e for e in events if e["event_type"] == "exit"]
    assert len(exits) == 1
    assert exits[0]["severity"] == "info"
    assert exits[0]["payload"]["zone"] == "dock_out"


def test_process_one_shelf_kind_emits_no_event() -> None:
    zones = [
        Zone(name="rack", forbidden=False, polygon=[(0, 0), (1, 0), (1, 1), (0, 1)], kind="shelf"),
    ]
    cfg = CEPConfig()
    states: dict = defaultdict(TrackState)
    msg = {
        "camera_id": "CAM1",
        "timestamp_ms": 3000,
        "detections": [_det(40, 40, 60, 60), _det(0, 0, 100, 100)],
    }
    events = process_one(msg, states, zones, cfg)
    # No CEP event types are emitted for shelf zones.
    assert all(e["event_type"] not in {"entry", "exit", "zone_violation"} for e in events)
