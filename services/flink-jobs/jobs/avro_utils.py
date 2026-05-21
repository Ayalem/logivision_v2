"""Avro (de)serialization utilities for Flink Kafka sources/sinks."""

from __future__ import annotations

import io
import json
from pathlib import Path

import fastavro
from pyflink.common.serialization import DeserializationSchema, SerializationSchema


def load_schema(name: str) -> dict:
    """Load an Avro schema from infra/kafka/schemas/."""
    schema_path = Path(__file__).parents[2] / "infra" / "kafka" / "schemas" / f"{name}.avsc"
    return json.loads(schema_path.read_text())


class AvroDeserializationSchema(DeserializationSchema):
    """Flink DeserializationSchema for Avro binary records."""

    def __init__(self, schema_name: str) -> None:
        self._schema_dict = load_schema(schema_name)
        self._schema = fastavro.parse_schema(self._schema_dict)

    def deserialize(self, message: bytes | None) -> dict | None:
        if message is None:
            return None
        try:
            buf = io.BytesIO(message)
            return fastavro.schemaless_reader(buf, self._schema)
        except Exception:
            # Return raw bytes as fallback for debugging
            return {"_raw": message.hex(), "_error": "deserialization_failed"}

    def is_end_of_stream(self, _next_record: dict | None) -> bool:
        return False

    def get_produced_type(self):
        from pyflink.common.typeinfo import Types

        return Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY())


class AvroSerializationSchema(SerializationSchema):
    """Flink SerializationSchema for Avro binary records."""

    def __init__(self, schema_name: str) -> None:
        self._schema_dict = load_schema(schema_name)
        self._schema = fastavro.parse_schema(self._schema_dict)

    def serialize(self, element: dict | None) -> bytes | None:
        if element is None:
            return None
        try:
            buf = io.BytesIO()
            fastavro.schemaless_writer(buf, self._schema, element)
            return buf.getvalue()
        except Exception as exc:
            # Fallback to JSON string on error
            return json.dumps({"_error": str(exc), "_original": str(element)}).encode()

    def get_serialized_type(self):
        from pyflink.common.typeinfo import Types

        return Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY())
