"""AnomalyScorer + ANOMALY_MODE wiring in process_one."""

from __future__ import annotations

from dataclasses import dataclass

from services.stream_processor.anomaly_scorer import ARTIFACT_PATH, AnomalyScorer, ScoreResult
from services.stream_processor.cep import CEPConfig, TrackPoint, TrackState, process_one
from services.stream_processor.trajectory_features import WINDOW

# ── AnomalyScorer behaviour ─────────────────────────────────────────────


def _track_state(n_points: int, step_ms: int = 200) -> TrackState:
    state = TrackState()
    for i in range(n_points):
        state.points.append(
            TrackPoint(timestamp_ms=i * step_ms, centroid=(100.0 + i, 100.0), width=40, height=40)
        )
    return state


def test_scorer_unavailable_without_artifact(tmp_path) -> None:
    scorer = AnomalyScorer(artifact_path=tmp_path / "missing.pt")
    assert scorer.available is False
    assert scorer.score_track("t1", _track_state(WINDOW + 5), 10_000, 1000.0) is None


def test_scorer_skips_short_tracks() -> None:
    scorer = AnomalyScorer()
    if not scorer.available:  # artifact not trained in this checkout
        return
    assert scorer.score_track("t1", _track_state(WINDOW // 2), 10_000, 1000.0) is None


def test_scorer_enforces_per_track_stride() -> None:
    scorer = AnomalyScorer()
    if not scorer.available:
        return
    state = _track_state(WINDOW + 5)
    now = state.points[-1].timestamp_ms
    scorer.score_track("t1", state, now, 1000.0)  # consumes the stride slot
    # Second call within 1 s must be suppressed regardless of the score.
    assert scorer.score_track("t1", state, now + 100, 1000.0) is None


def test_scorer_real_artifact_round_trip() -> None:
    """With the committed artifact, scoring runs end-to-end and returns a
    well-formed result or None — never crashes."""
    scorer = AnomalyScorer()
    if not scorer.available:
        return
    state = _track_state(WINDOW + 10)
    out = scorer.score_track("t-roundtrip", state, state.points[-1].timestamp_ms, 1000.0)
    if out is not None:
        assert out.severity in {"warning", "critical"}
        assert out.score >= out.threshold
        assert out.dominant_feature


# ── process_one mode wiring (stub scorer — no ML involved) ──────────────


@dataclass
class _StubScorer:
    result: ScoreResult | None
    available: bool = True

    def score_track(self, *_a, **_kw) -> ScoreResult | None:
        return self.result


def _stationary_message(ts_ms: int) -> dict:
    return {
        "camera_id": "CAM01",
        "timestamp_ms": ts_ms,
        "width": 1280,
        "height": 720,
        "detections": [
            {
                "class_id": 0,
                "class_name": "box",
                "confidence": 0.9,
                "x1": 100,
                "y1": 100,
                "x2": 140,
                "y2": 140,
                "track_id": 7,
            }
        ],
    }


def _drive_stationary(config: CEPConfig, scorer=None) -> list[dict]:
    """Feed 35 s of a perfectly still track; collect all emitted events."""
    states: dict[str, TrackState] = {}
    emitted: list[dict] = []
    for i in range(36):
        emitted += process_one(_stationary_message(i * 1000), states, [], config, None, scorer)
    return emitted


def test_rules_mode_emits_full_severity() -> None:
    config = CEPConfig(anomaly_mode="rules")
    events = _drive_stationary(config, scorer=_StubScorer(result=None))
    stationary = [e for e in events if e["event_type"] == "stationary_object"]
    assert stationary and stationary[0]["severity"] == "warning"
    assert "source" not in stationary[0]["payload"]


def test_ae_mode_demotes_rules_to_baseline() -> None:
    config = CEPConfig(anomaly_mode="ae")
    events = _drive_stationary(config, scorer=_StubScorer(result=None))
    stationary = [e for e in events if e["event_type"] == "stationary_object"]
    assert stationary and stationary[0]["severity"] == "info"
    assert stationary[0]["payload"]["source"] == "rule-baseline"


def test_ae_mode_without_scorer_falls_back_to_full_severity_rules() -> None:
    config = CEPConfig(anomaly_mode="ae")
    events = _drive_stationary(config, scorer=None)
    stationary = [e for e in events if e["event_type"] == "stationary_object"]
    assert stationary and stationary[0]["severity"] == "warning"


def test_ae_mode_emits_trajectory_anomaly_with_cooldown() -> None:
    config = CEPConfig(anomaly_mode="ae", trajectory_anomaly_cooldown_s=10.0)
    stub = _StubScorer(
        result=ScoreResult(score=0.9, threshold=0.6, severity="critical", dominant_feature="speed")
    )
    events = _drive_stationary(config, scorer=stub)
    anomalies = [e for e in events if e["event_type"] == "trajectory_anomaly"]
    assert anomalies, "stub scorer above threshold must emit"
    first = anomalies[0]
    assert first["severity"] == "critical"
    assert first["payload"]["dominant_feature"] == "speed"
    assert first["payload"]["model_version"] == "trajectory-ae-v1"
    # 36 s of firing with a 10 s cooldown → at most 4 events.
    assert len(anomalies) <= 4


def test_both_mode_keeps_rules_at_full_severity_and_emits_ae() -> None:
    config = CEPConfig(anomaly_mode="both")
    stub = _StubScorer(
        result=ScoreResult(score=0.7, threshold=0.6, severity="warning", dominant_feature="accel")
    )
    events = _drive_stationary(config, scorer=stub)
    stationary = [e for e in events if e["event_type"] == "stationary_object"]
    anomalies = [e for e in events if e["event_type"] == "trajectory_anomaly"]
    assert stationary and stationary[0]["severity"] == "warning"
    assert anomalies


def test_artifact_path_is_repo_relative() -> None:
    assert ARTIFACT_PATH.is_absolute()
    assert ARTIFACT_PATH.parts[-4:] == ("ml", "artifacts", "trajectory_ae", "model.pt")
