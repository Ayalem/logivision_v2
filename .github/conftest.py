"""Mock pyflink modules so unit tests run without a Flink installation."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Liste de tous les sous-modules pyflink utilisés dans les jobs
PYFLINK_MODULES = [
    "pyflink",
    "pyflink.common",
    "pyflink.common.serialization",
    "pyflink.common.typeinfo",
    "pyflink.common.watermark_strategy",
    "pyflink.datastream",
    "pyflink.datastream.connectors",
    "pyflink.datastream.connectors.kafka",
    "pyflink.datastream.functions",
    "pyflink.datastream.state",
    "pyflink.datastream.window",
]

for mod in PYFLINK_MODULES:
    sys.modules[mod] = MagicMock()
