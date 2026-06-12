"""Anomaly detection: statistical baselines + unsupervised ML, fused by voting.

Three independent detectors, combined to balance sensitivity and noise:
  • Z-score        — distance from the rolling mean (catches spikes & ramps)
  • IQR fence      — robust outlier bounds (resistant to skew)
  • Isolation Forest — unsupervised ML over (value, local slope) features

A reading is flagged when the z-score is strong, OR when at least two
detectors agree. A continuous 0..1 score drives the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

SEVERITY_ORDER = {"normal": 0, "low": 1, "moderate": 2, "critical": 3}


@dataclass
class AnomalyResult:
    is_anomaly: bool
    score: float                       # 0..1 combined anomaly strength
    severity_hint: str                 # normal | low | moderate | critical
    z_score: float
    baseline_mean: float
    baseline_std: float
    iqr_low: float
    iqr_high: float
    direction: str                     # high | low | none
    methods: list[str] = field(default_factory=list)
    iforest_score: float | None = None

    def to_dict(self) -> dict:
        return {
            "is_anomaly": self.is_anomaly,
            "score": round(self.score, 3),
            "severity_hint": self.severity_hint,
            "z_score": round(self.z_score, 2),
            "baseline_mean": round(self.baseline_mean, 3),
            "baseline_std": round(self.baseline_std, 3),
            "iqr_low": round(self.iqr_low, 3),
            "iqr_high": round(self.iqr_high, 3),
            "direction": self.direction,
            "methods": self.methods,
            "iforest_score": None if self.iforest_score is None else round(self.iforest_score, 3),
        }


def _normal_result(mean: float = 0.0) -> AnomalyResult:
    return AnomalyResult(
        is_anomaly=False, score=0.0, severity_hint="normal", z_score=0.0,
        baseline_mean=mean, baseline_std=0.0, iqr_low=mean, iqr_high=mean,
        direction="none", methods=[],
    )


class AnomalyDetector:
    def __init__(self, contamination: float = 0.03, min_points: int = 15):
        self.contamination = contamination
        self.min_points = min_points

    def analyze(self, imputed: pd.Series) -> AnomalyResult:
        clean = imputed.dropna()
        if len(clean) < self.min_points:
            return _normal_result(float(clean.mean()) if len(clean) else 0.0)

        values = clean.to_numpy(dtype="float64")
        n = len(values)
        last = float(values[-1])

        # Reference (expected) distribution = the EARLIER part of the window.
        # Scoring the latest reading against this — rather than the whole-window
        # mean — is what lets us catch gradual ramps and level shifts, not just
        # sharp local spikes (the mean would otherwise drift up with the trend).
        split = max(self.min_points, int(n * 0.6))
        ref = values[:split] if split < n else values[:-1]
        if len(ref) < max(5, self.min_points // 2):
            ref = values
        mean = float(np.mean(ref))
        std = float(np.std(ref))

        # ── Z-score vs. reference ─────────────────────────────────────
        z = (last - mean) / std if std > 1e-9 else 0.0

        # ── IQR fence (from the reference distribution) ───────────────
        q1, q3 = np.percentile(ref, [25, 75])
        iqr = q3 - q1
        low = float(q1 - 1.5 * iqr)
        high = float(q3 + 1.5 * iqr)
        iqr_flag = last < low or last > high

        # ── Isolation Forest over (value, local slope) ────────────────
        iforest_score = None
        iforest_flag = False
        try:
            slope = np.gradient(values)
            feats = np.column_stack([values, slope])
            model = IsolationForest(
                n_estimators=120, contamination=self.contamination,
                random_state=42,
            )
            model.fit(feats)
            # Higher = more anomalous. Normalise the last point's score to ~0..1.
            raw = -model.score_samples(feats)
            iforest_score = float(raw[-1])
            iforest_flag = bool(model.predict(feats)[-1] == -1)
        except Exception:  # pragma: no cover - ML is best-effort
            iforest_score = None

        # ── Fuse ──────────────────────────────────────────────────────
        methods: list[str] = []
        if abs(z) >= 3.0:
            methods.append("z-score")
        if iqr_flag:
            methods.append("iqr")
        if iforest_flag:
            methods.append("isolation-forest")

        is_anomaly = ("z-score" in methods) or (len(methods) >= 2)

        # Continuous score: strongest normalised signal across detectors.
        z_norm = min(abs(z) / 6.0, 1.0)
        if iqr > 1e-9 and iqr_flag:
            iqr_dist = max(low - last, last - high) / (1.5 * iqr + 1e-9)
            iqr_norm = min(max(iqr_dist, 0.0), 1.0)
        else:
            iqr_norm = 0.0
        if_norm = min(iforest_score / 0.75, 1.0) if iforest_score else 0.0
        score = float(max(z_norm, iqr_norm, if_norm)) if is_anomaly else float(z_norm * 0.5)

        # ── Heuristic severity (the LLM refines this; also the fallback) ─
        if not is_anomaly:
            severity = "normal"
        elif abs(z) >= 6.0 or score >= 0.85:
            severity = "critical"
        elif abs(z) >= 4.2 or score >= 0.6:
            severity = "moderate"
        else:
            severity = "low"

        direction = "high" if last >= mean else "low"

        return AnomalyResult(
            is_anomaly=is_anomaly, score=score, severity_hint=severity,
            z_score=z, baseline_mean=mean, baseline_std=std,
            iqr_low=low, iqr_high=high, direction=direction,
            methods=methods, iforest_score=iforest_score,
        )
