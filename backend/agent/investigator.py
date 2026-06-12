"""The agentic investigator — a real Claude tool-use loop.

Claude is given read-only tools over live fleet state and reasons across them to
produce a prioritized incident report (the "senior reliability engineer" moment
from the PRD). Falls back to a deterministic report when no API key is present.
"""

from __future__ import annotations

from ..config import settings
from .llm import get_async_client
from .prompts import INVESTIGATOR_SYSTEM
from .tools import TOOL_SCHEMAS, execute_tool


async def investigate(view, focus: str | None = None, max_iters: int = 6) -> dict:
    """Run the investigation. Returns report + the agent's tool-call trace."""
    client = get_async_client()
    if client is None:
        return _fallback_report(view, focus)

    kickoff = "Investigate the current state of the sensor fleet and produce your incident report."
    if focus:
        kickoff += f" Pay particular attention to: {focus}."

    messages: list[dict] = [{"role": "user", "content": kickoff}]
    steps: list[dict] = []
    report = ""

    try:
        for _ in range(max_iters):
            resp = await client.messages.create(
                model=settings.investigator_model,
                max_tokens=4000,
                system=INVESTIGATOR_SYSTEM,
                messages=messages,
                tools=TOOL_SCHEMAS,
                thinking={"type": "adaptive"},
                output_config={"effort": settings.investigator_effort},
            )
            text = "".join(b.text for b in resp.content if b.type == "text")
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": resp.content})

            if not tool_uses:
                report = text
                break

            tool_results = []
            for tu in tool_uses:
                out = execute_tool(tu.name, tu.input, view)
                steps.append({"tool": tu.name, "input": tu.input})
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu.id, "content": out,
                })
            messages.append({"role": "user", "content": tool_results})
        else:
            # Out of iterations — force a final text wrap-up (no more tools).
            resp = await client.messages.create(
                model=settings.investigator_model,
                max_tokens=4000,
                system=INVESTIGATOR_SYSTEM,
                messages=messages + [{"role": "user", "content": "Provide your final incident report now."}],
                tools=TOOL_SCHEMAS,
                tool_choice={"type": "none"},
            )
            report = "".join(b.text for b in resp.content if b.type == "text")

        return {
            "report_markdown": report or "_No report produced._",
            "steps": steps,
            "used_llm": True,
            "model": settings.investigator_model,
        }
    except Exception as exc:  # network / API failure → deterministic report
        fb = _fallback_report(view, focus)
        fb["note"] = f"LLM unavailable ({exc.__class__.__name__}); generated deterministic report."
        return fb


def _fallback_report(view, focus: str | None) -> dict:
    """Deterministic incident report assembled directly from fleet state."""
    summary = view.fleet_summary()
    sensors = view.list_sensors()

    affected = [s for s in sensors if s.get("is_anomaly") or s.get("status") != "healthy"]
    steps = [{"tool": "list_sensors", "input": {}}, {"tool": "fleet_summary", "input": {}}]

    lines: list[str] = []
    lines.append("# Incident Report — Fleet Investigation")
    lines.append("")
    n_anom = summary.get("anomalous", 0)
    n_degr = summary.get("degraded", 0)
    lines.append("## Executive summary")
    if not affected:
        lines.append(
            f"All {summary.get('total', 0)} sensors are within normal bounds under the "
            f"`{summary.get('scenario', 'nominal')}` scenario. No action required."
        )
    else:
        lines.append(
            f"{n_anom} sensor(s) flagged anomalous and {n_degr} showing degraded data "
            f"quality under the `{summary.get('scenario', 'nominal')}` scenario. "
            f"Details and recommended actions below."
        )
    lines.append("")

    if affected:
        lines.append("## Findings")
        for s in affected:
            steps.append({"tool": "get_sensor_detail", "input": {"sensor_id": s["sensor_id"]}})
            malfunction = s.get("status") == "malfunction"
            sev = "Moderate" if malfunction else _sev_word(s.get("severity_hint", "low"))
            tag = "SENSOR FAULT" if malfunction else "PROCESS ANOMALY"
            lines.append(
                f"- **{s['sensor_id']}** ({s.get('sensor_type')}, {s.get('location')}) — "
                f"**{sev}** · {tag}. Reading {s.get('value')} {s.get('unit','')}, "
                f"z-score {s.get('z_score')}, methods: {', '.join(s.get('methods', []) or ['—'])}. "
                f"Data quality: {s.get('status')}."
            )
        lines.append("")

        # Correlation pass.
        lines.append("## Root-cause assessment")
        for s in affected:
            if s.get("status") == "malfunction":
                lines.append(
                    f"- **{s['sensor_id']}** is most consistent with a **sensor malfunction**, "
                    f"not a real process change — treat its readings as untrusted until verified."
                )
                continue
            corr = view.find_correlations(s["sensor_id"])
            steps.append({"tool": "find_correlations", "input": {"sensor_id": s["sensor_id"]}})
            if corr:
                ids = ", ".join(c["sensor_id"] for c in corr)
                lines.append(
                    f"- **{s['sensor_id']}** moves together with {ids}; a shared root cause is "
                    f"likely rather than an isolated fault."
                )
            else:
                lines.append(f"- **{s['sensor_id']}** shows an isolated deviation; no correlated signal found.")
        lines.append("")

        lines.append("## Recommended actions")
        for s in affected:
            if s.get("status") == "malfunction":
                lines.append(f"1. **{s['sensor_id']}** — verify/replace the sensor; suppress equipment alarms for this channel.")
            else:
                sev = _sev_word(s.get("severity_hint", "low"))
                if sev == "Critical":
                    lines.append(f"1. **{s['sensor_id']}** — inspect now; prepare to isolate the asset (within 1h).")
                elif sev == "Moderate":
                    lines.append(f"2. **{s['sensor_id']}** — schedule inspection within 24h; add to watch list.")
                else:
                    lines.append(f"3. **{s['sensor_id']}** — monitor; no immediate action.")
    if focus:
        lines.append("")
        lines.append(f"_Focus requested: {focus}_")

    return {
        "report_markdown": "\n".join(lines),
        "steps": steps,
        "used_llm": False,
        "model": "deterministic-fallback",
    }


def _sev_word(hint: str) -> str:
    return {"normal": "Low", "low": "Low", "moderate": "Moderate", "critical": "Critical"}.get(hint, "Low")
