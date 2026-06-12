"""Tool surface for the investigator agent.

Tools are thin, read-only views over live fleet state. The `view` argument is
any object implementing the small interface used below (the engine's
`FleetView`). Keeping tools read-only makes the agent safe to run on demand.
"""

from __future__ import annotations

import json

TOOL_SCHEMAS = [
    {
        "name": "list_sensors",
        "description": (
            "List every sensor in the fleet with its current value, location, "
            "data-quality status, and whether it is currently flagged anomalous. "
            "Call this first to get the overall picture."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_sensor_detail",
        "description": (
            "Get detailed diagnostics for one sensor: recent values, rolling "
            "baseline mean/std, z-score, IQR bounds, detection methods that "
            "fired, and a full data-quality assessment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"sensor_id": {"type": "string", "description": "e.g. VIB-04"}},
            "required": ["sensor_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "find_correlations",
        "description": (
            "Find other sensors trending in the same direction over the recent "
            "window as the given sensor — used to tell isolated faults from a "
            "shared root cause."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"sensor_id": {"type": "string"}},
            "required": ["sensor_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fleet_summary",
        "description": "High-level fleet KPIs: counts of healthy / degraded / anomalous sensors and the active scenario.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def execute_tool(name: str, tool_input: dict, view) -> str:
    """Dispatch a tool call to the live fleet view. Returns a JSON string."""
    try:
        if name == "list_sensors":
            return json.dumps(view.list_sensors(), default=str)
        if name == "fleet_summary":
            return json.dumps(view.fleet_summary(), default=str)
        if name == "get_sensor_detail":
            sid = (tool_input or {}).get("sensor_id", "")
            detail = view.get_sensor(sid)
            if detail is None:
                return json.dumps({"error": f"unknown sensor_id '{sid}'"})
            return json.dumps(detail, default=str)
        if name == "find_correlations":
            sid = (tool_input or {}).get("sensor_id", "")
            return json.dumps(view.find_correlations(sid), default=str)
        return json.dumps({"error": f"unknown tool '{name}'"})
    except Exception as exc:  # pragma: no cover - defensive
        return json.dumps({"error": f"tool '{name}' failed: {exc}"})
