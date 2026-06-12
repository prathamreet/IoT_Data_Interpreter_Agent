"""Demo scenarios — scripted fault conditions injected over the live stream.

Each scenario is a named set of time-based "injections" applied on top of a
sensor's nominal baseline + noise. Switching scenarios at runtime (from the
dashboard) is what powers the live "watch the HVAC fail" demo moment.

These also serve as documented, repeatable fault signatures — the same shapes
the golden-dataset evaluator uses.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass
class Injection:
    """A single fault contribution applied to one sensor over a time window."""

    sensor_id: str
    kind: str            # ramp | step | spike | flatline | dropout | noise_ramp
    start: float         # seconds after scenario activation
    duration: float      # seconds (ramp/spike); 0 = open-ended (step/flatline)
    magnitude: float     # meaning depends on kind (units, or probability)

    def _progress(self, t: float) -> float:
        if t < self.start:
            return 0.0
        if self.duration <= 0:
            return 1.0
        return min(1.0, (t - self.start) / self.duration)

    def effect(self, t: float, rng: random.Random) -> dict:
        """Return effect dict: {add, override, dropout, extra_noise}."""
        eff = {"add": 0.0, "override": None, "dropout": False, "extra_noise": 0.0}
        if t < self.start:
            return eff

        if self.kind == "ramp":
            eff["add"] = self.magnitude * self._progress(t)
        elif self.kind == "step":
            eff["add"] = self.magnitude
        elif self.kind == "spike":
            # Transient Gaussian bump centred at `start` — a point anomaly.
            sigma = max(self.duration, 1.0) / 4.0
            eff["add"] = self.magnitude * math.exp(-((t - self.start) ** 2) / (2 * sigma**2))
        elif self.kind == "flatline":
            # Stuck sensor: hold a constant, suppress noise -> malfunction signature.
            eff["override"] = self.magnitude
        elif self.kind == "dropout":
            eff["dropout"] = rng.random() < self.magnitude
        elif self.kind == "noise_ramp":
            eff["extra_noise"] = self.magnitude * self._progress(t)
        return eff


@dataclass
class Scenario:
    name: str
    title: str
    description: str
    injections: list[Injection] = field(default_factory=list)

    @property
    def affected_sensors(self) -> list[str]:
        seen: list[str] = []
        for inj in self.injections:
            if inj.sensor_id not in seen:
                seen.append(inj.sensor_id)
        return seen

    def effects_for(self, sensor_id: str, t: float, rng: random.Random) -> dict:
        """Compose all injections touching `sensor_id` at time `t`."""
        merged = {"add": 0.0, "override": None, "dropout": False, "extra_noise": 0.0}
        for inj in self.injections:
            if inj.sensor_id != sensor_id:
                continue
            e = inj.effect(t, rng)
            merged["add"] += e["add"]
            merged["extra_noise"] += e["extra_noise"]
            merged["dropout"] = merged["dropout"] or e["dropout"]
            if e["override"] is not None:
                merged["override"] = e["override"]
        return merged


# ── Scenario catalogue ────────────────────────────────────────────────
SCENARIOS: dict[str, Scenario] = {
    "nominal": Scenario(
        name="nominal",
        title="Nominal operation",
        description="All sensors within normal bounds. Healthy baseline.",
        injections=[],
    ),
    "hvac_failure": Scenario(
        name="hvac_failure",
        title="HVAC failure — data center",
        description=(
            "Cooling loss in Aisle A. Inlet temperature climbs steadily and "
            "cleanroom humidity rises in correlation as dehumidification drops."
        ),
        injections=[
            Injection("TEMP-01", "ramp", start=8, duration=70, magnitude=13.0),
            Injection("HUM-01", "ramp", start=16, duration=70, magnitude=14.0),
        ],
    ),
    "bearing_wear": Scenario(
        name="bearing_wear",
        title="Bearing wear — conveyor",
        description=(
            "Early-stage bearing degradation on Conveyor B-7. Vibration trends "
            "upward with growing variance; the adjacent motor heats in step — a "
            "collective anomaly across two sensors."
        ),
        injections=[
            Injection("VIB-04", "ramp", start=8, duration=95, magnitude=5.0),
            Injection("VIB-04", "noise_ramp", start=8, duration=95, magnitude=1.6),
            Injection("TEMP-02", "ramp", start=30, duration=95, magnitude=7.0),
        ],
    ),
    "sensor_malfunction": Scenario(
        name="sensor_malfunction",
        title="Sensor malfunction — hydraulic line",
        description=(
            "Pressure transducer on Line H-3 stops responding (stuck reading) "
            "and intermittently drops out. This is a DATA-QUALITY fault, not a "
            "process anomaly — the agent should flag the sensor, not the asset."
        ),
        injections=[
            Injection("PRES-02", "flatline", start=18, duration=0, magnitude=152.0),
            Injection("PRES-02", "dropout", start=40, duration=0, magnitude=0.25),
        ],
    ),
    "cold_chain_breach": Scenario(
        name="cold_chain_breach",
        title="Cold-chain breach — cold storage",
        description=(
            "Cold Storage CS-1 door left ajar. Temperature rises out of the "
            "compliant band; a humidity spike accompanies the incursion."
        ),
        injections=[
            Injection("TEMP-03", "ramp", start=10, duration=50, magnitude=9.0),
            Injection("HUM-01", "spike", start=24, duration=18, magnitude=10.0),
        ],
    ),
}


def get_scenario(name: str) -> Scenario:
    return SCENARIOS.get(name, SCENARIOS["nominal"])


def scenario_catalogue() -> list[dict]:
    """Serializable list for the dashboard scenario switcher."""
    return [
        {
            "name": s.name,
            "title": s.title,
            "description": s.description,
            "affected_sensors": s.affected_sensors,
        }
        for s in SCENARIOS.values()
    ]
