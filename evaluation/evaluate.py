"""Evaluate the anomaly detector against the labeled golden dataset.

Run:  python -m evaluation.evaluate
Streams each labeled series through the detector point-by-point (exactly as it
runs live) and reports precision / recall / F1 per case and overall.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from backend.processing.anomaly import AnomalyDetector  # noqa: E402

WINDOW = 180
WARMUP = 15
DATA = ROOT / "data" / "golden_dataset.json"


def _load() -> dict:
    if not DATA.exists():
        from evaluation.make_golden import main as gen
        gen()
    return json.loads(DATA.read_text(encoding="utf-8"))


def _score(series, labels, detector) -> tuple[int, int, int, int]:
    tp = fp = fn = tn = 0
    n = len(series)
    for i in range(WARMUP, n):
        window = series[max(0, i - WINDOW + 1): i + 1]
        res = detector.analyze(pd.Series(window, dtype="float64"))
        pred, lab = res.is_anomaly, bool(labels[i])
        if pred and lab:
            tp += 1
        elif pred and not lab:
            fp += 1
        elif (not pred) and lab:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def _prf(tp, fp, fn) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


def main() -> None:
    data = _load()
    detector = AnomalyDetector()
    TP = FP = FN = TN = 0

    print("\n  Anomaly Detection — Golden Dataset Evaluation")
    print("  " + "-" * 68)
    print(f"  {'case':<26}{'P':>7}{'R':>7}{'F1':>7}   {'TP/FP/FN/TN'}")
    print("  " + "-" * 68)

    for c in data["cases"]:
        tp, fp, fn, tn = _score(c["series"], c["labels"], detector)
        TP, FP, FN, TN = TP + tp, FP + fp, FN + fn, TN + tn
        p, r, f1 = _prf(tp, fp, fn)
        print(f"  {c['name']:<26}{p:>7.2f}{r:>7.2f}{f1:>7.2f}   {tp}/{fp}/{fn}/{tn}")

    print("  " + "-" * 68)
    P, R, F1 = _prf(TP, FP, FN)
    acc = (TP + TN) / (TP + FP + FN + TN) if (TP + FP + FN + TN) else 0.0
    print(f"  {'OVERALL':<26}{P:>7.2f}{R:>7.2f}{F1:>7.2f}   {TP}/{FP}/{FN}/{TN}")
    print(f"\n  Accuracy: {acc:.1%}   Precision: {P:.1%}   Recall: {R:.1%}   F1: {F1:.2f}\n")


if __name__ == "__main__":
    main()
