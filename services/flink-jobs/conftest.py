"""Mock pyflink before any job module is imported."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock


def _mock_pyflink() -> None:
    mods = [
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
    for mod in mods:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()


_mock_pyflink()
