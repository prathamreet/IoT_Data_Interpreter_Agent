"""Core data-ingestion contract.

Everything downstream (buffering, anomaly detection, narration) consumes
`SensorReading` objects and never cares where they came from. That is the
abstraction that makes real hardware a drop-in replacement for the simulator.
"""

from __future__ import annotations

import abc
import time
from dataclasses import asdict, dataclass, field


@dataclass
class SensorSpec:
    """Static description of a physical sensor / channel."""

    sensor_id: str
    sensor_type: str          # temperature | vibration | pressure | humidity | ...
    unit: str
    location: str
    baseline: float           # nominal expected value
    noise_sigma: float        # natural measurement noise (std dev)
    min_phys: float           # physically plausible floor
    max_phys: float           # physically plausible ceiling
    diurnal_amp: float = 0.0  # amplitude of a slow daily cycle (contextual)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SensorReading:
    """A single timestamped measurement.

    `value is None` represents a genuinely missing reading (dropout) — the
    pipeline handles that explicitly rather than silently skipping it.
    """

    sensor_id: str
    sensor_type: str
    value: float | None
    unit: str
    timestamp: float                       # epoch seconds
    location: str = "unspecified"
    quality_hint: str = "ok"               # ok | missing | noisy (source hint)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        # ISO timestamp is convenient for the UI; keep epoch too.
        d["ts_iso"] = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        return d


class DataSource(abc.ABC):
    """Abstract source of sensor readings.

    Implementations:
      • SimulatedDataSource  — synthetic multi-sensor streams (works now)
      • MQTTDataSource       — real hardware over MQTT (placeholder/stub)

    Contract: `poll()` returns the latest reading for each active sensor and
    is called on a fixed cadence by the engine. Keep it non-blocking.
    """

    name: str = "abstract"

    @abc.abstractmethod
    def specs(self) -> list[SensorSpec]:
        """Static metadata for every sensor this source exposes."""

    @abc.abstractmethod
    def poll(self) -> list[SensorReading]:
        """Return one fresh reading per active sensor since the last poll."""

    # Lifecycle hooks — override if the source needs connections/threads.
    def start(self) -> None:  # noqa: D401 - simple default
        """Open connections / spin up background consumers."""

    def stop(self) -> None:
        """Tear down connections cleanly."""

    # Optional: sources that can replay different conditions expose this.
    def set_scenario(self, name: str) -> bool:
        """Switch operating scenario if supported. Returns True if applied."""
        return False
