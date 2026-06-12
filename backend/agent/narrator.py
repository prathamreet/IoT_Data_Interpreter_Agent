"""Narration engine — turns one detected anomaly into operator-ready language.

Primary path: a single grounded Claude call returning structured JSON.
Fallback path: a deterministic, data-driven template that is genuinely useful.
The fallback is what guarantees the demo works with no API key.
"""

from __future__ import annotations

import json

from ..config import settings
from .llm import get_async_client
from .prompts import NARRATOR_SYSTEM

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "severity": {"type": "string", "enum": ["Low", "Moderate", "Critical"]},
        "root_cause": {"type": "string"},
        "recommended_action": {"type": "string"},
        "confidence_note": {"type": "string"},
    },
    "required": ["summary", "severity", "root_cause", "recommended_action", "confidence_note"],
    "additionalProperties": False,
}

_SEVERITY_FROM_HINT = {
    "normal": "Low", "low": "Low", "moderate": "Moderate", "critical": "Critical",
}

_CAUSE_BY_TYPE = {
    ("temperature", "high"): "elevated thermal load or loss of cooling",
    ("temperature", "low"): "overcooling or a drop in process load",
    ("vibration", "high"): "mechanical wear, imbalance, or misalignment",
    ("vibration", "low"): "reduced mechanical load or a stalled drive",
    ("pressure", "high"): "a downstream blockage or restriction",
    ("pressure", "low"): "a leak, pump degradation, or supply loss",
    ("humidity", "high"): "loss of dehumidification or moisture ingress",
    ("humidity", "low"): "over-drying or environmental-control drift",
}


async def narrate(context: dict) -> dict:
    """Return narration dict for a single anomaly context."""
    client = get_async_client()
    if client is not None:
        try:
            resp = await client.messages.create(
                model=settings.narration_model,
                max_tokens=800,
                system=NARRATOR_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": (
                        "Narrate this detected anomaly. Structured data follows:\n\n"
                        + json.dumps(context, indent=2)
                    ),
                }],
                output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            )
            text = next((b.text for b in resp.content if b.type == "text"), "")
            data = json.loads(text)
            data["used_llm"] = True
            return data
        except Exception:
            # Any API/parse failure → fall through to the deterministic path.
            pass
    return _fallback(context)


def _fallback(context: dict) -> dict:
    sid = context.get("sensor_id", "?")
    stype = context.get("sensor_type", "sensor")
    unit = context.get("unit", "")
    loc = context.get("location", "unspecified")
    value = context.get("current_value")
    baseline = context.get("baseline_mean", 0.0) or 0.0
    z = context.get("z_score", 0.0)
    direction = context.get("direction", "high")
    methods = context.get("methods", []) or ["statistical thresholds"]
    dq = context.get("data_quality", {}) or {}
    status = dq.get("status", "healthy")
    confidence = dq.get("confidence", 1.0)
    reasons = dq.get("reasons", [])
    correlated = context.get("correlated", []) or []

    dir_word = "above" if direction == "high" else "below"
    pct = 0.0
    if baseline:
        pct = abs((float(value) - baseline) / abs(baseline) * 100.0) if value is not None else 0.0

    val_str = f"{float(value):.2f} {unit}" if value is not None else "no current reading"
    summary = (
        f"{stype.title()} sensor {sid} at {loc} is reading {val_str}, "
        f"{pct:.0f}% {dir_word} its {baseline:.2f} {unit} baseline "
        f"(z-score {z:.1f}). Flagged by {', '.join(methods)}."
    )

    is_malfunction = status == "malfunction"
    if is_malfunction:
        severity = "Moderate"
        root_cause = (
            f"Likely a SENSOR malfunction ({'; '.join(reasons)}) rather than a "
            f"genuine process change — these readings are not currently trustworthy."
        )
    else:
        severity = _SEVERITY_FROM_HINT.get(context.get("severity_hint", "low"), "Low")
        cause = _CAUSE_BY_TYPE.get((stype, direction), "a deviation from the expected operating range")
        root_cause = f"Consistent with {cause} (hypothesis)."
        if correlated:
            ids = ", ".join(c["sensor_id"] for c in correlated)
            root_cause += f" Correlated movement on {ids} points to a shared root cause."

    if is_malfunction:
        action = ("Verify and, if needed, replace the sensor and check wiring/power "
                  "before trusting these readings. Suppress equipment alarms for this channel.")
    elif severity == "Critical":
        action = ("Dispatch an inspection now and prepare to isolate or de-rate the "
                  "affected asset. Escalate to the on-call engineer.")
    elif severity == "Moderate":
        action = "Schedule an inspection within 24 hours and add this sensor to the active watch list."
    else:
        action = "Continue monitoring. No immediate action required."

    confidence_note = (
        f"Data quality: {status} (confidence {confidence:.0%}). "
        f"{reasons[0] if reasons else 'nominal data quality'}."
    )

    return {
        "summary": summary,
        "severity": severity,
        "root_cause": root_cause,
        "recommended_action": action,
        "confidence_note": confidence_note,
        "used_llm": False,
    }
