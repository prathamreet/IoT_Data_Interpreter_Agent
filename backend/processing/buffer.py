"""Rolling per-sensor time-series buffers backed by pandas.

Keeps the most recent `window` samples per sensor (missing readings preserved
as NaN so the cleaning/quality layer can reason about gaps explicitly).
"""

from __future__ import annotations

from collections import deque

import numpy as np
import pandas as pd

from ..sources.base import SensorReading


class SensorBuffer:
    def __init__(self, sensor_id: str, window: int = 180):
        self.sensor_id = sensor_id
        self.window = window
        self._ts: deque[float] = deque(maxlen=window)
        self._vals: deque[float] = deque(maxlen=window)

    def append(self, ts: float, value: float | None) -> None:
        self._ts.append(ts)
        self._vals.append(np.nan if value is None else float(value))

    def __len__(self) -> int:
        return len(self._vals)

    def series(self) -> pd.Series:
        """Recent values indexed by timestamp; gaps are NaN."""
        return pd.Series(list(self._vals), index=list(self._ts), dtype="float64")

    def latest(self) -> float | None:
        for v in reversed(self._vals):
            if not np.isnan(v):
                return float(v)
        return None

    def recent(self, n: int) -> list[float]:
        """Last `n` values (NaN dropped) — handy for compact LLM context."""
        clean = [v for v in self._vals if not np.isnan(v)]
        return [round(v, 3) for v in clean[-n:]]


class FleetBuffer:
    """Collection of per-sensor buffers for the whole fleet."""

    def __init__(self, window: int = 180):
        self.window = window
        self._buffers: dict[str, SensorBuffer] = {}

    def ingest(self, reading: SensorReading) -> SensorBuffer:
        buf = self._buffers.get(reading.sensor_id)
        if buf is None:
            buf = SensorBuffer(reading.sensor_id, self.window)
            self._buffers[reading.sensor_id] = buf
        buf.append(reading.timestamp, reading.value)
        return buf

    def get(self, sensor_id: str) -> SensorBuffer | None:
        return self._buffers.get(sensor_id)

    def sensor_ids(self) -> list[str]:
        return list(self._buffers.keys())
