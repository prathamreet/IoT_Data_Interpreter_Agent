"""Render a self-contained HTML incident report.

No templating dependency and no headless-browser requirement: the output is a
single styled HTML document. Operators open it directly; "Print → Save as PDF"
produces the PDF deliverable described in the PRD.
"""

from __future__ import annotations

import html
import re
import time


def _md_to_html(md: str) -> str:
    """Tiny Markdown subset → HTML (headings, bold, bullet lists, paragraphs)."""
    lines = md.splitlines()
    out: list[str] = []
    in_list = False

    def inline(text: str) -> str:
        text = html.escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        return text

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if line.startswith("### "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif re.match(r"^\s*(?:[-*]|\d+\.)\s+", line):
            if not in_list:
                out.append("<ul>"); in_list = True
            item = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line)
            out.append(f"<li>{inline(item)}</li>")
        else:
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


_SEV_COLOR = {"Critical": "#ef4444", "Moderate": "#f59e0b", "Low": "#10b981"}


def build_html_report(payload: dict) -> str:
    kpis = payload.get("kpis", {})
    sensors = payload.get("sensors", [])
    actions = payload.get("actions", [])
    generated = time.strftime("%Y-%m-%d %H:%M:%S")
    scenario = payload.get("scenario", "nominal")
    used_llm = payload.get("used_llm", False)
    model = payload.get("model", "–")
    report_html = _md_to_html(payload.get("report_markdown", "_No findings._"))

    rows = []
    for s in sensors:
        an = s.get("anomaly", {})
        q = s.get("quality", {})
        flag = "🔴" if an.get("is_anomaly") else ("🟠" if q.get("status") != "healthy" else "🟢")
        rows.append(
            f"<tr><td>{flag} {html.escape(s['sensor_id'])}</td>"
            f"<td>{html.escape(s.get('sensor_type',''))}</td>"
            f"<td>{html.escape(s.get('location',''))}</td>"
            f"<td>{s.get('value')}</td>"
            f"<td>{an.get('z_score')}</td>"
            f"<td>{html.escape(q.get('status',''))}</td></tr>"
        )
    sensor_table = "\n".join(rows)

    action_items = []
    for a in actions:
        color = _SEV_COLOR.get(a.get("severity", "Low"), "#10b981")
        action_items.append(
            f"<li><span class='pill' style='background:{color}'>{html.escape(a.get('severity',''))}</span> "
            f"<strong>{html.escape(a.get('sensor_id',''))}</strong> – {html.escape(a.get('action',''))}</li>"
        )
    actions_html = "\n".join(action_items) or "<li>No open actions.</li>"

    engine_badge = (
        f"Claude ({html.escape(str(model))})" if used_llm else "Deterministic engine (offline)"
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>IoT Incident Report — {generated}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&display=swap" rel="stylesheet">
<style>
  :root {{
    --ink: #0e0f0c;
    --body: #454745;
    --muted: #868685;
    --line: #e8ebe6;
    --accent: #9fe870;
    --accent-bg: #e2f6d5;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    font-family: 'Inter', system-ui, Arial, sans-serif;
    color: var(--ink);
    max-width: 880px;
    margin: 0 auto;
    padding: 40px 32px;
    line-height: 1.6;
    background-color: #ffffff;
    -webkit-font-smoothing: antialiased;
  }}
  header {{
    border-bottom: 2px solid var(--ink);
    padding-bottom: 20px;
    margin-bottom: 30px;
  }}
  h1 {{
    font-size: 28px;
    font-weight: 900;
    margin: 0 0 6px;
    letter-spacing: -0.5px;
  }}
  h2 {{
    font-size: 20px;
    font-weight: 900;
    margin: 32px 0 12px;
    border-left: 4px solid var(--accent);
    padding-left: 12px;
    letter-spacing: -0.3px;
  }}
  h3 {{
    font-size: 16px;
    font-weight: 700;
    margin: 20px 0 8px;
  }}
  .meta {{
    color: var(--body);
    font-size: 13.5px;
    font-weight: 500;
  }}
  .badge {{
    display: inline-block;
    background-color: var(--accent-bg);
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 9999px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 700;
  }}
  .kpis {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin: 24px 0;
  }}
  .kpi {{
    flex: 1;
    min-width: 130px;
    background-color: var(--line);
    border-radius: 16px;
    padding: 16px;
  }}
  .kpi .n {{
    font-size: 26px;
    font-weight: 900;
    color: var(--ink);
    letter-spacing: -0.5px;
  }}
  .kpi .l {{
    font-size: 11px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-top: 4px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 14.5px;
  }}
  th, td {{
    text-align: left;
    padding: 10px 12px;
    border-bottom: 1px solid var(--line);
  }}
  th {{
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .06em;
  }}
  code {{
    background-color: var(--line);
    padding: 2px 6px;
    border-radius: 6px;
    font-size: 13px;
  }}
  ul {{
    padding-left: 24px;
  }}
  li {{
    margin: 6px 0;
    color: var(--body);
  }}
  .pill {{
    color: var(--ink);
    border-radius: 9999px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 700;
    margin-right: 8px;
    display: inline-block;
  }}
  footer {{
    margin-top: 48px;
    padding-top: 20px;
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-size: 12.5px;
    font-weight: 500;
    line-height: 1.5;
  }}
  @media print {{
    body {{ padding: 0; }}
  }}
</style></head>
<body>
  <header>
    <h1>IoT Data Interpreter – Incident Report</h1>
    <div class="meta">Generated {generated} · Scenario: <code>{html.escape(scenario)}</code>
      · <span class="badge">{engine_badge}</span></div>
  </header>

  <div class="kpis">
    <div class="kpi"><div class="n">{kpis.get('total','–')}</div><div class="l">Sensors</div></div>
    <div class="kpi"><div class="n">{kpis.get('anomalous','–')}</div><div class="l">Anomalous</div></div>
    <div class="kpi"><div class="n">{kpis.get('malfunction','–')}</div><div class="l">Malfunction</div></div>
    <div class="kpi"><div class="n">{int(kpis.get('avg_confidence',1)*100)}%</div><div class="l">Avg confidence</div></div>
  </div>

  {report_html}

  <h2>Maintenance action queue</h2>
  <ul>{actions_html}</ul>

  <h2>Sensor snapshot</h2>
  <table>
    <thead><tr><th>Sensor</th><th>Type</th><th>Location</th><th>Value</th><th>Z-score</th><th>Data quality</th></tr></thead>
    <tbody>{sensor_table}</tbody>
  </table>

  <footer>IoT Data Interpreter Agent · Builathon Use Case #43 – Real-World Automation.
  This report was generated automatically from live sensor telemetry.</footer>
</body></html>"""
