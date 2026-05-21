# ADR 004: Flink Job Design for Phase 2 Streaming

## Status
Accepted

## Context
Phase 2 requires replacing the direct HTTP inference calls with a Kafka + Flink streaming pipeline.

## Decision
1. Use PyFlink DataStream API for all stream processing jobs
2. Adopt Avro binary serialization with Schema Registry (Apicurio)
3. Implement ByteTrack for multi-object tracking before enrichment
4. Use Flink keyed state for per-track state management
5. Sink KPIs to both Kafka (real-time) and ClickHouse (analytics)

## Consequences
- Positive: Type-safe message contracts, scalable processing, exactly-once semantics via checkpoints
- Negative: PyFlink has limited Python ecosystem support; some operations require Java interop
- Tech debt: `services/stream_processor/cep.py` removed in favor of Flink jobs

## Migration Notes
- 2024-05-21: Removed `cep.py` dual implementation
- 2024-05-21: Added Avro schemas and ByteTrack job
