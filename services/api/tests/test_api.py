"""Unit tests for the FastAPI app (MLflow + Kafka mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from services.api.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_index_returns_endpoints_when_no_frontend(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("services.api.main.FRONTEND_DIR", tmp_path / "nope")
    r = client.get("/")
    assert r.status_code == 200
    # Either the dashboard HTML is served, or the JSON fallback.
    if r.headers["content-type"].startswith("application/json"):
        payload = r.json()
        assert "endpoints" in payload


def test_list_models_returns_registered_models() -> None:
    fake_version = MagicMock(
        version="3", current_stage="Production", run_id="RUN1", creation_timestamp=1000
    )
    fake_model = MagicMock(name="m", latest_versions=[fake_version])
    fake_model.name = "logivision-detector"
    mock_client = MagicMock()
    mock_client.search_registered_models.return_value = [fake_model]
    with patch("services.api.main._mlflow_client", return_value=mock_client):
        r = client.get("/api/registry/models")
    assert r.status_code == 200
    body = r.json()
    assert body["models"][0]["name"] == "logivision-detector"
    assert body["models"][0]["versions"][0]["stage"] == "Production"


def test_list_runs_returns_sorted_runs() -> None:
    exp = MagicMock()
    exp.experiment_id = "1"
    exp.name = "exp"
    run_a = MagicMock()
    run_a.info.run_id = "A"
    run_a.info.status = "FINISHED"
    run_a.info.start_time = 100
    run_a.data.metrics = {"val_map50": 0.7}
    run_a.data.tags = {"git_commit": "abc"}
    run_b = MagicMock()
    run_b.info.run_id = "B"
    run_b.info.status = "FINISHED"
    run_b.info.start_time = 200
    run_b.data.metrics = {"val_map50": 0.85}
    run_b.data.tags = {"git_commit": "def"}
    mock_client = MagicMock()
    mock_client.search_experiments.return_value = [exp]
    mock_client.search_runs.return_value = [run_a, run_b]
    with patch("services.api.main._mlflow_client", return_value=mock_client):
        r = client.get("/api/registry/runs?limit=10")
    assert r.status_code == 200
    runs = r.json()["runs"]
    # Sorted descending by start_time.
    assert runs[0]["run_id"] == "B"
    assert runs[1]["run_id"] == "A"


def test_get_run_404_when_missing() -> None:
    mock_client = MagicMock()
    mock_client.get_run.side_effect = RuntimeError("not found")
    with patch("services.api.main._mlflow_client", return_value=mock_client):
        r = client.get("/api/runs/UNKNOWN")
    assert r.status_code == 404


def test_drift_reports_lists_existing_files(tmp_path) -> None:
    target = tmp_path / "docs" / "mlops" / "drift"
    target.mkdir(parents=True)
    (target / "run_a.html").write_text("<html/>")
    (target / "run_a.json").write_text("{}")
    with patch("services.api.main.REPO_ROOT", tmp_path):
        r = client.get("/api/drift/reports")
    assert r.status_code == 200
    names = {report["name"] for report in r.json()["reports"]}
    assert names == {"run_a.html", "run_a.json"}


def test_benchmarks_endpoint_handles_missing_dir(tmp_path) -> None:
    with patch("services.api.main.REPO_ROOT", tmp_path):
        r = client.get("/api/benchmarks")
    assert r.status_code == 200
    assert r.json() == {"reports": []}


# ---------- client-facing endpoints (zones, cameras, anomalies, kpis, /me) ----------

import yaml as _yaml  # noqa: E402

from services.api.routers import client as client_router  # noqa: E402


def test_me_returns_operator_by_default(monkeypatch) -> None:
    monkeypatch.setattr(client_router, "LOGIVISION_ROLE", "operator")
    r = client.get("/api/me")
    assert r.status_code == 200
    assert r.json()["role"] == "operator"


def test_me_returns_admin_when_role_env_is_admin(monkeypatch) -> None:
    monkeypatch.setattr(client_router, "LOGIVISION_ROLE", "admin")
    r = client.get("/api/me")
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_zones_endpoint_serves_yaml(tmp_path, monkeypatch) -> None:
    zones_path = tmp_path / "zones.yaml"
    zones_path.write_text(
        _yaml.safe_dump(
            {
                "zones": [
                    {
                        "name": "entrance_dock",
                        "kind": "entry",
                        "category": "Réception",
                        "polygon": [
                            {"x": 0.0, "y": 0.0},
                            {"x": 0.25, "y": 0.0},
                            {"x": 0.25, "y": 0.2},
                            {"x": 0.0, "y": 0.2},
                        ],
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(client_router, "ZONES_FILE", zones_path)
    # Bust the LRU cache so the temp file is actually read.
    client_router._load_yaml_cached.cache_clear()
    r = client.get("/api/zones")
    assert r.status_code == 200
    zones = r.json()["zones"]
    assert len(zones) == 1
    z = zones[0]
    assert z["id"] == "entrance_dock"
    assert z["kind"] == "entry"
    assert z["category"] == "Réception"
    # polygon bbox (0..0.25 horizontally, 0..0.2 vertically) → width/height as %.
    assert z["x"] == 0.0
    assert z["y"] == 0.0
    assert z["width"] == 25.0
    assert z["height"] == 20.0
    # Mock occupancy is deterministic and bounded.
    assert 0 <= z["occupancy"] <= 100
    assert z["status"] in {"normal", "warning", "critical"}


def test_cameras_endpoint_serves_yaml(tmp_path, monkeypatch) -> None:
    cams_path = tmp_path / "cameras.yaml"
    cams_path.write_text(
        _yaml.safe_dump(
            {
                "cameras": [
                    {
                        "id": "CAM01",
                        "name": "Entrée",
                        "location": "Porte A",
                        "zone": "entrance_dock",
                        "resolution": "1920x1080",
                        "fps_target": 5,
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(client_router, "CAMERAS_FILE", cams_path)
    client_router._load_yaml_cached.cache_clear()
    # Bypass Kafka — return empty + degraded so cameras get status=offline/unknown.
    monkeypatch.setattr(client_router, "_peek_topic", lambda *_a, **_kw: ([], True))
    r = client.get("/api/cameras")
    assert r.status_code == 200
    body = r.json()
    assert body["degraded"] is True
    assert len(body["cameras"]) == 1
    cam = body["cameras"][0]
    assert cam["id"] == "CAM01"
    assert cam["resolution"] == "1920x1080"
    assert cam["status"] in {"online", "offline", "unknown"}


def test_anomalies_filters_info_severity(monkeypatch) -> None:
    fake_events = [
        {
            "event_id": "e1",
            "event_type": "zone_violation",
            "severity": "critical",
            "timestamp_ms": 1_700_000_000_000,
            "camera_id": "CAM01",
            "payload": {"zone": "forbidden_aisle", "class_name": "person"},
        },
        {
            "event_id": "e2",
            "event_type": "entry",  # info — must be filtered out
            "severity": "info",
            "timestamp_ms": 1_700_000_000_001,
            "camera_id": "CAM02",
            "payload": {"zone": "entrance_dock", "class_name": "box"},
        },
        {
            "event_id": "e3",
            "event_type": "stationary_object",
            "severity": "warning",
            "timestamp_ms": 1_700_000_000_002,
            "camera_id": "CAM03",
            "payload": {"zone": "shelf_A1", "class_name": "box"},
        },
    ]
    monkeypatch.setattr(client_router, "_peek_topic", lambda *_a, **_kw: (fake_events, False))
    r = client.get("/api/anomalies?n=10")
    assert r.status_code == 200
    body = r.json()
    assert body["degraded"] is False
    types = {a["eventType"] for a in body["anomalies"]}
    assert "entry" not in types
    assert types == {"zone_violation", "stationary_object"}


def test_entries_exits_returns_only_entry_exit_events(monkeypatch) -> None:
    fake_events = [
        {
            "event_id": "a",
            "event_type": "entry",
            "severity": "info",
            "timestamp_ms": 1,
            "camera_id": "C1",
            "payload": {"zone": "in", "class_name": "box"},
        },
        {
            "event_id": "b",
            "event_type": "exit",
            "severity": "info",
            "timestamp_ms": 2,
            "camera_id": "C1",
            "payload": {"zone": "out", "class_name": "box"},
        },
        {
            "event_id": "c",
            "event_type": "zone_violation",
            "severity": "critical",
            "timestamp_ms": 3,
            "camera_id": "C1",
            "payload": {"zone": "wall", "class_name": "p"},
        },
    ]
    monkeypatch.setattr(client_router, "_peek_topic", lambda *_a, **_kw: (fake_events, False))
    r = client.get("/api/entries-exits")
    assert r.status_code == 200
    items = r.json()["items"]
    assert {i["type"] for i in items} == {"entry", "exit"}


def test_kpis_returns_full_shape_when_kafka_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(client_router, "_peek_topic", lambda *_a, **_kw: ([], True))
    r = client.get("/api/kpis")
    assert r.status_code == 200
    body = r.json()
    # Must contain every field the frontend reads.
    for key in (
        "totalBoxes",
        "todayEntries",
        "todayExits",
        "activeAnomalies",
        "systemStatus",
        "camerasOnline",
        "totalCameras",
        "avgProcessingTime",
        "stockLevel",
        "degraded",
    ):
        assert key in body, f"missing KPI field: {key}"
    assert body["degraded"] is True
    assert body["systemStatus"] == "degraded"


# ---------- predictions / heatmap / insights (Phase A.3) ----------


def _stationary(track: str, zone: str, ts_ms: int, cx: float = 0.5, cy: float = 0.5) -> dict:
    return {
        "event_id": f"se-{track}-{ts_ms}",
        "event_type": "stationary_object",
        "severity": "warning",
        "timestamp_ms": ts_ms,
        "camera_id": "CAM01",
        "track_id": track,
        "payload": {"zone": zone, "centroid_x": str(cx), "centroid_y": str(cy)},
    }


def test_predict_returns_nothing_when_below_threshold() -> None:
    now = 1_700_000_000_000
    out = client_router._predict_from_events([_stationary("t1", "z1", now)], now)
    assert out["congestion"] == []
    assert out["collision"] == []


def test_predict_emits_congestion_when_threshold_met() -> None:
    now = 1_700_000_000_000
    events = [_stationary(f"t{i}", "shelf_A1", now - i * 1000) for i in range(3)]
    out = client_router._predict_from_events(events, now)
    assert len(out["congestion"]) == 1
    c = out["congestion"][0]
    assert c["zone"] == "shelf_A1"
    assert c["event_type"] == "congestion_forecast"
    assert c["eta_seconds"] > 0
    assert 0 < c["confidence"] <= 1.0


def test_predict_emits_collision_for_two_tracks_same_zone() -> None:
    now = 1_700_000_000_000
    events = [
        _stationary("t1", "aisle_B", now - 1000, cx=0.4, cy=0.5),
        _stationary("t2", "aisle_B", now - 500, cx=0.6, cy=0.5),
        _stationary("t1", "aisle_B", now, cx=0.5, cy=0.5),
    ]
    out = client_router._predict_from_events(events, now)
    assert len(out["collision"]) >= 1
    c = out["collision"][0]
    assert c["event_type"] == "collision_risk"
    assert {c["track_a"], c["track_b"]} == {"t1", "t2"}


def test_predict_emits_trajectory_hint_for_tracks_with_points() -> None:
    now = 1_700_000_000_000
    events = [
        _stationary("t1", "z", now - 4000, cx=0.10, cy=0.10),
        _stationary("t1", "z", now - 3000, cx=0.15, cy=0.12),
        _stationary("t1", "z", now - 2000, cx=0.20, cy=0.14),
    ]
    out = client_router._predict_from_events(events, now)
    assert len(out["trajectories"]) == 1
    t = out["trajectories"][0]
    assert t["track_id"] == "t1"
    assert t["speed_units_per_s"] > 0
    # Predicted point is in the extrapolated direction.
    assert t["predicted_point"]["x"] > 0.20


def test_predictions_endpoint_returns_buckets(monkeypatch) -> None:
    # The endpoint computes `now_ms` from real time and filters out events
    # older than CONGESTION_WINDOW_S, so anchor the fixture to "now".
    import time as _time

    now = int(_time.time() * 1000)
    events = [_stationary(f"t{i}", "shelf_A1", now - i * 1000) for i in range(3)]
    monkeypatch.setattr(client_router, "_peek_topic", lambda *_a, **_kw: (events, False))
    r = client.get("/api/predictions?n=20")
    assert r.status_code == 200
    body = r.json()
    assert "predictions" in body
    assert "buckets" in body
    assert "congestion" in body["buckets"]
    assert any(p["event_type"] == "congestion_forecast" for p in body["predictions"])


def test_heatmap_returns_cells_for_each_layer(monkeypatch) -> None:
    monkeypatch.setattr(client_router, "_peek_topic", lambda *_a, **_kw: ([], True))
    for layer in ("traffic", "shelf", "idle", "bottleneck", "worker"):
        r = client.get(f"/api/heatmap?layer={layer}&grid=12")
        # Inspect the last call's shape.
        body = r.json()
        assert r.status_code == 200, f"layer={layer} → {r.status_code}"
        assert body["layer"] == layer
        assert body["grid"] == 12
        # cell_size = 1/grid
        assert abs(body["cell_size"] - 1 / 12) < 1e-3
        # Cells are within [0..1] in both axes and value range.
        for c in body["cells"][:20]:
            assert 0.0 <= c["x"] <= 1.0
            assert 0.0 <= c["y"] <= 1.0
            assert 0.0 <= c["value"] <= 1.0


def test_heatmap_rejects_unknown_layer() -> None:
    r = client.get("/api/heatmap?layer=banana")
    assert r.status_code == 422  # pydantic regex validation


def test_insights_endpoint_always_has_at_least_one_chain(monkeypatch) -> None:
    # No events at all → demo fallback chain.
    monkeypatch.setattr(client_router, "_peek_topic", lambda *_a, **_kw: ([], True))
    r = client.get("/api/insights")
    assert r.status_code == 200
    body = r.json()
    assert len(body["insights"]) >= 1
    chain = body["insights"][0]
    assert "title" in chain
    assert "steps" in chain
    assert isinstance(chain["steps"], list) and len(chain["steps"]) >= 2
