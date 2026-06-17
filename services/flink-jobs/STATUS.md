# Flink jobs — current status

> **Short version:** the PyFlink code is correct, but its message schema does
> not yet match what our `inference_worker` actually emits. The single-process
> Python implementation in `services/stream_processor/cep.py` is what's wired
> into the dashboard today. The Flink jobs here are the production target.

## What's correct
- `stationary_detection.py` — proper `KeyedProcessFunction` with `ValueState`,
  reset-on-movement + alert-once semantics.
- `zone_violation.py` — point-in-polygon (ray-casting) over keyed streams.
- `detection_enrichment.py` — zone-name lookup + republish.
- `kpi_aggregator.py` — `TumblingEventTimeWindows` (1 min / 5 min / 1 h) with
  an `AggregateFunction` and a `ProcessWindowFunction`.
- Each job builds its own `KafkaSource` / `KafkaSink` correctly.

## What's broken (schema gap)

| File | Expected detection shape | Topic out | Coord system |
|---|---|---|---|
| `stationary_detection.py` | `{object_id, label, x, y, confidence, timestamp}` | `events` | absolute px |
| `zone_violation.py` | same | `events` | absolute px |
| `detection_enrichment.py` | same | `tracks` | absolute px |
| `kpi_aggregator.py` | same | **`kpis`** ⚠ | — |

But our real producer (`services/inference_worker/worker.py`) emits one
message per **frame** to `detections`:

```json
{
  "frame_id": "uuid",
  "camera_id": "CAM03",
  "timestamp_ms": 1779363389657,
  "model_version": "fallback:.../yolov8n.pt",
  "inference_ms": 333.7,
  "frame_uri": "s3://frames/CAM03/20260520/<uuid>.jpg",
  "detections": [
    { "class_id": 2, "class_name": "car",
      "confidence": 0.27,
      "x1": 1550, "y1": 474, "x2": 1856, "y2": 661 }
  ]
}
```

→ A Flink job consuming this with `Detection.from_json` will raise
`KeyError: 'object_id'` on the very first record.

Additional gaps:
- **No Flink cluster orchestration.** The Dockerfile builds a job image, but
  there is no `docker-compose` running a JobManager + TaskManager. The Make
  target to submit the JAR/.py is missing.
- **KPI topic mismatch.** The dashboard reads `/api/topics/events/...`, not
  a `kpis` topic. Either change `TOPIC_OUT` to `events` or have the FastAPI
  layer subscribe to `kpis`.
- **No `track_id`.** Stationary detection keys on `object_id`. Our pipeline
  doesn't have real tracks until ByteTrack lands (Phase 2.5); today we use
  `_approximate_track_id` (hashed bbox-quantised key) in the Python CEP.

## What it would take to make Flink the live engine

1. Add an **adapter `MapFunction`** at the start of each pipeline that
   explodes one inference message into N per-detection rows, mapping
   `(camera_id, class_id, ⌊cx/32⌋, ⌊cy/32⌋)` → `object_id` and `(cx, cy)` →
   `(x, y)`. ~50 lines per job.
2. Switch all jobs' `TOPIC_OUT` to `events` (the dashboard's sole sink).
3. Rewrite alert payloads to match `cep.make_event(...)` shape:
   `{event_id, event_type, severity, camera_id, track_id, payload, timestamp_ms}`.
4. Add `infra/docker-compose/docker-compose.flink.yml` with JobManager,
   TaskManager (2 slots), checkpoint dir, savepoint dir, REST UI on `:8081`.
5. Replace `make cep` with `make flink-up && make flink-submit` once the
   jobs pass an end-to-end test against a sample inference output.

Estimated effort: 1 day for the adapter + compose, half a day for tests
and dashboard wiring.

## Recommended path for the soutenance

- **Demo with the Python CEP** (today, working end-to-end).
- **Defend the Flink jobs as the production architecture** — code is here,
  schema gap is documented, upgrade path is explicit.
- This matches the roadmap in ONBOARDING.md, which positions the single-process
  CEP as the academic demo and the PyFlink jobs as the deployment target.
