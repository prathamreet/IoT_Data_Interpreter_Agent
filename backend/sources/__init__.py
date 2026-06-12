"""Data ingestion layer.

`DataSource` is the single seam between the agent and the physical world.
The simulator implements it today; `MQTTDataSource` is the drop-in for real
hardware. Pick one in `build_source()` (driven by config.DATA_SOURCE).
"""

from __future__ import annotations

from ..config import settings
from .base import DataSource, SensorReading, SensorSpec
from .simulator import SimulatedDataSource

__all__ = [
    "DataSource",
    "SensorReading",
    "SensorSpec",
    "SimulatedDataSource",
    "build_source",
]


def build_source(scenario: str | None = None) -> DataSource:
    """Factory that selects the active data source from configuration.

    This is the one place you switch from simulated data to live hardware.
    """
    kind = settings.data_source.lower()
    if kind == "mqtt":
        # Hardware path — see mqtt_source.py for the wiring checklist.
        from .mqtt_source import MQTTDataSource

        return MQTTDataSource()
    # Default: fully self-contained simulator (no hardware needed).
    return SimulatedDataSource(scenario or settings.default_scenario)
