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
