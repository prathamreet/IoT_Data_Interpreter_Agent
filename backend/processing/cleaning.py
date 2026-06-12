"""Noisy / missing data handling and confidence scoring.

Two responsibilities:
  • impute()         — fill gaps so detection has a continuous signal
  • assess_quality() — score data trustworthiness and, crucially, separate a
                       malfunctioning SENSOR from a genuine process anomaly.

That separation is a core requirement: a stuck or dropping-out sensor must be
flagged as a data-quality fault, not raised as an equipment alarm.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..sources.base import SensorSpec


def impute(series: pd.Series) -> pd.Series:
    """Forward-fill, then linear-interpolate, then back-fill remaining gaps."""
    if series.empty:
        return series
    filled = series.interpolate(method="linear", limit_direction="both")
    return filled.ffill().bfill()


@dataclass
class DataQuality:
    confidence: float                 # 0..1 trust in the current reading
    status: str                       # healthy | degraded | malfunction
    missing_frac: float
    is_stuck: bool = False
    out_of_range: bool = False
    noisy: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "confidence": round(self.confidence, 3),
            "status": self.status,
            "missing_frac": round(self.missing_frac, 3),
            "is_stuck": self.is_stuck,
            "out_of_range": self.out_of_range,
            "noisy": self.noisy,
            "reasons": self.reasons,
        }


def assess_quality(series: pd.Series, spec: SensorSpec | None) -> DataQuality:
    n = len(series)
    if n == 0:
        return DataQuality(confidence=0.0, status="degraded", missing_frac=1.0,
                           reasons=["no data yet"])

    missing = int(series.isna().sum())
    missing_frac = missing / n
    clean = series.dropna()
    reasons: list[str] = []

    # Stuck / flatline detection — the classic malfunction fingerprint.
    is_stuck = False
    if len(clean) >= 12:
        tail = clean.tail(15)
        if float(tail.std(ddof=0)) < 1e-6:
            is_stuck = True
            reasons.append("reading frozen (no variance over last 15 samples)")

    # Out-of-physical-range — only meaningful when finite bounds are known.
    out_of_range = False
    last = float(clean.iloc[-1]) if len(clean) else float("nan")
    if spec is not None and np.isfinite(spec.min_phys) and np.isfinite(spec.max_phys):
        if len(clean) and (last < spec.min_phys or last > spec.max_phys):
            out_of_range = True
            reasons.append(f"value {last:.2f} outside physical range "
                           f"[{spec.min_phys}, {spec.max_phys}]")

    # Excess short-term noise relative to the sensor's known noise floor.
    noisy = False
    if spec is not None and spec.noise_sigma > 0 and len(clean) >= 6:
        jitter = float(clean.diff().abs().tail(20).mean())
        if jitter > spec.noise_sigma * 4.0:
            noisy = True
            reasons.append("elevated sample-to-sample jitter")

    if missing_frac > 0.30:
        reasons.append(f"{missing_frac:.0%} of recent samples missing")

    # Status precedence: malfunction > degraded > healthy.
    if is_stuck or out_of_range:
        status = "malfunction"
    elif missing_frac > 0.30 or noisy:
        status = "degraded"
    else:
        status = "healthy"

    confidence = 1.0 - missing_frac * 0.7
    if noisy:
        confidence -= 0.2
    if status == "malfunction":
        confidence = min(confidence, 0.15)
    confidence = float(max(0.0, min(1.0, confidence)))

    if not reasons:
        reasons.append("nominal data quality")

    return DataQuality(
        confidence=confidence, status=status, missing_frac=missing_frac,
        is_stuck=is_stuck, out_of_range=out_of_range, noisy=noisy, reasons=reasons,
    )
