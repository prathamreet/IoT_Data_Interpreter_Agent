"""Synthetic multi-sensor stream.

Produces realistic temperature / vibration / pressure / humidity telemetry with
natural noise, a slow diurnal component, occasional dropouts, and scenario-driven
fault injection. No hardware required — this is the default data source.
"""

from __future__ import annotations

import math
import random
import time

from .base import DataSource, SensorReading, SensorSpec
from .scenarios import get_scenario

# Realistic industrial fleet. Locations are chosen so narration reads naturally.
DEFAULT_SENSORS: list[SensorSpec] = [
    SensorSpec("TEMP-01", "temperature", "°C", "Data Center — Aisle A",
               baseline=22.0, noise_sigma=0.40, min_phys=10, max_phys=60, diurnal_amp=1.0),
    SensorSpec("TEMP-02", "temperature", "°C", "Motor Unit M-12",
               baseline=46.0, noise_sigma=0.60, min_phys=20, max_phys=110, diurnal_amp=0.8),
    SensorSpec("TEMP-03", "temperature", "°C", "Cold Storage CS-1",
               baseline=4.0, noise_sigma=0.30, min_phys=-5, max_phys=25, diurnal_amp=0.4),
    SensorSpec("VIB-04", "vibration", "mm/s", "Conveyor Bearing B-7",
               baseline=2.1, noise_sigma=0.15, min_phys=0, max_phys=20, diurnal_amp=0.0),
    SensorSpec("PRES-02", "pressure", "kPa", "Hydraulic Line H-3",
               baseline=152.0, noise_sigma=1.20, min_phys=80, max_phys=250, diurnal_amp=0.0),
    SensorSpec("HUM-01", "humidity", "%RH", "Cleanroom CR-2",
               baseline=43.0, noise_sigma=0.80, min_phys=5, max_phys=95, diurnal_amp=1.2),
]


class SimulatedDataSource(DataSource):
    name = "simulator"

    def __init__(self, scenario: str = "nominal", seed: int | None = None):
        self._specs = list(DEFAULT_SENSORS)
        self._scenario = get_scenario(scenario)
        self._rng = random.Random(seed)
        self._t0 = time.time()

    # ── DataSource contract ───────────────────────────────────────────
    def specs(self) -> list[SensorSpec]:
        return list(self._specs)

    def poll(self) -> list[SensorReading]:
        now = time.time()
        elapsed = now - self._t0
        return [self._sample(spec, elapsed, now) for spec in self._specs]

    def set_scenario(self, name: str) -> bool:
        self._scenario = get_scenario(name)
        # Reset the clock so injected faults start fresh and are demo-visible.
        self._t0 = time.time()
        return True

    @property
    def scenario_name(self) -> str:
        return self._scenario.name

    # ── internals ─────────────────────────────────────────────────────
    def _sample(self, spec: SensorSpec, elapsed: float, now: float) -> SensorReading:
        eff = self._scenario.effects_for(spec.sensor_id, elapsed, self._rng)

        if eff["dropout"]:
            return SensorReading(
                sensor_id=spec.sensor_id, sensor_type=spec.sensor_type,
                value=None, unit=spec.unit, timestamp=now,
                location=spec.location, quality_hint="missing",
            )

        # Nominal signal: baseline + slow diurnal cycle.
        diurnal = spec.diurnal_amp * math.sin(elapsed / 90.0)
        base = spec.baseline + diurnal

        # Natural noise, optionally amplified by a fault (e.g. bearing wear).
        sigma = spec.noise_sigma * (1.0 + eff["extra_noise"])
        noise = self._rng.gauss(0.0, sigma)

        value = base + noise + eff["add"]
        quality = "ok"

        if eff["override"] is not None:
            # Stuck sensor — constant value, the malfunction fingerprint.
            value = eff["override"]
            quality = "noisy"

        # Clamp to physically plausible range; flag saturation.
        if value < spec.min_phys:
            value, quality = spec.min_phys, "noisy"
        elif value > spec.max_phys:
            value, quality = spec.max_phys, "noisy"

        return SensorReading(
            sensor_id=spec.sensor_id, sensor_type=spec.sensor_type,
            value=round(value, 3), unit=spec.unit, timestamp=now,
            location=spec.location, quality_hint=quality,
        )
