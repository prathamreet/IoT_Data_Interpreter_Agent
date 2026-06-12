"""Unit tests for the detection + data-quality core.

Run:  pytest          (requires numpy / pandas / scikit-learn installed)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.processing.anomaly import AnomalyDetector
from backend.processing.cleaning import assess_quality, impute
from backend.sources.base import SensorSpec


def test_point_spike_is_flagged():
    rng = np.random.default_rng(0)
    series = list(22 + rng.normal(0, 0.3, 40))
    series[-1] = 40.0  # sharp spike on the latest reading
    res = AnomalyDetector().analyze(pd.Series(series))
    assert res.is_anomaly
    assert res.direction == "high"
    assert res.severity_hint in {"moderate", "critical"}


def test_constant_signal_is_not_an_anomaly():
    res = AnomalyDetector().analyze(pd.Series([150.0] * 40))
    # A flat line is a malfunction signature, not a process anomaly.
    assert not res.is_anomaly


def test_stuck_sensor_is_quality_malfunction():
    spec = SensorSpec("X", "pressure", "kPa", "loc", 150, 1.0, 80, 250)
    q = assess_quality(pd.Series([150.0] * 30), spec)
    assert q.is_stuck
    assert q.status == "malfunction"
    assert q.confidence < 0.3


def test_missing_data_reduces_confidence():
    spec = SensorSpec("Y", "temperature", "°C", "loc", 22, 0.4, 0, 60)
    vals = [22.0, np.nan, 22.1, np.nan, np.nan, 21.9, np.nan, 22.2]
    q = assess_quality(pd.Series(vals), spec)
    assert q.missing_frac > 0.3
    assert q.confidence < 1.0


def test_impute_fills_gaps():
    s = pd.Series([1.0, np.nan, 3.0, np.nan, 5.0])
    filled = impute(s)
    assert not filled.isna().any()
    assert abs(filled.iloc[1] - 2.0) < 1e-6  # linear interpolation
