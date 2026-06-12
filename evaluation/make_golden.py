"""Generate a labeled golden dataset of anomalies (stdlib only).

Run:  python -m evaluation.make_golden
Writes data/golden_dataset.json — point-labeled time series the evaluator
scores the detector against. Deterministic (seeded) for reproducibility.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "golden_dataset.json"


def _case(name, stype, unit, n, baseline, sigma, fault, seed, note):
    rng = random.Random(seed)
    series, labels = [], []
    for i in range(n):
        add, lab = fault(i)
        v = baseline + rng.gauss(0.0, sigma) + add
        series.append(round(v, 3))
        labels.append(bool(lab))
    return {
        "name": name, "sensor_type": stype, "unit": unit,
        "note": note, "series": series, "labels": labels,
    }


def _spike(spikes: dict):
    return lambda i: (spikes[i], True) if i in spikes else (0.0, False)


def _ramp(start: int, per: float, thresh: float):
    def f(i):
        if i < start:
            return 0.0, False
        add = (i - start) * per
        return add, add >= thresh
    return f


def _step(start: int, mag: float):
    def f(i):
        if i < start:
            return 0.0, False
        return mag, True  # a sustained out-of-band level stays anomalous
    return f


def _zero():
    return lambda i: (0.0, False)


def build() -> dict:
    cases = [
        _case("temp_point_spike", "temperature", "°C", 60, 22.0, 0.40,
              _spike({30: 12.0, 31: 9.0, 46: 10.0}), 1,
              "Three transient point anomalies on an otherwise healthy signal."),
        _case("vibration_bearing_ramp", "vibration", "mm/s", 72, 2.1, 0.15,
              _ramp(36, 0.16, 0.45), 2,
              "Gradual bearing-wear ramp; anomalous once it clears ~3σ of the noise floor."),
        _case("hvac_temp_ramp", "temperature", "°C", 72, 22.0, 0.40,
              _ramp(28, 0.22, 1.2), 3,
              "Cooling-loss ramp in a data center; anomalous past ~3σ."),
        _case("pressure_flatline", "pressure", "kPa", 60, 152.0, 0.0,
              _zero(), 4,
              "Stuck transducer (malfunction) — must NOT be flagged as a process anomaly."),
        _case("humidity_nominal", "humidity", "%RH", 60, 43.0, 0.80,
              _zero(), 5,
              "Healthy baseline — pure noise, no anomalies."),
        _case("pressure_step", "pressure", "kPa", 64, 152.0, 1.20,
              _step(36, 18.0), 6,
              "Sustained step change to an out-of-band level."),
    ]
    return {
        "description": "Labeled anomaly golden dataset for detector evaluation.",
        "cases": cases,
    }


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    pts = sum(len(c["series"]) for c in data["cases"])
    print(f"Wrote {OUT}  ({len(data['cases'])} cases, {pts} labeled points)")


if __name__ == "__main__":
    main()
