"""FastAPI application — REST + WebSocket + the served dashboard.

Run:  uvicorn backend.main:app --reload
Then open http://127.0.0.1:8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent.investigator import _fallback_report, investigate
from .config import settings
from .engine import _sanitize, engine
from .models import InvestigateRequest, ReportRequest, ScenarioRequest
from .reporting import build_html_report

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await engine.start()
    try:
        yield
    finally:
        await engine.stop()


app = FastAPI(title="IoT Data Interpreter Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Static assets (css/js) for the dashboard.
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── dashboard ─────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ── REST API ──────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "llm_enabled": settings.llm_enabled,
            "narration_model": settings.narration_model}


@app.get("/api/state")
async def state():
    return JSONResponse(_sanitize(engine.hello_message()))


@app.post("/api/scenario")
async def set_scenario(req: ScenarioRequest):
    ok = engine.set_scenario(req.scenario)
    return {"ok": ok, "scenario": engine.scenario}


@app.post("/api/investigate")
async def api_investigate(req: InvestigateRequest):
    focus = req.focus or ""
    if req.sensor_id:
        focus = (focus + " " if focus else "") + f"sensor {req.sensor_id}"
    result = await investigate(engine, focus=focus or None)
    return JSONResponse(_sanitize(result))


@app.post("/api/report")
async def api_report(req: ReportRequest):
    md = req.report_markdown
    if not md:
        md = _fallback_report(engine, None)["report_markdown"]
    html = build_html_report({
        "report_markdown": md,
        "used_llm": req.used_llm,
        "model": req.model or "—",
        "kpis": engine.kpis(),
        "sensors": list(engine.analyses.values()),
        "actions": list(engine.actions.values()),
        "scenario": engine.scenario,
    })
    return HTMLResponse(
        html, headers={"Content-Disposition": "attachment; filename=incident_report.html"}
    )


@app.get("/api/report.html", response_class=HTMLResponse)
async def api_report_quick():
    fb = _fallback_report(engine, None)
    return HTMLResponse(build_html_report({
        "report_markdown": fb["report_markdown"],
        "used_llm": False,
        "model": fb["model"],
        "kpis": engine.kpis(),
        "sensors": list(engine.analyses.values()),
        "actions": list(engine.actions.values()),
        "scenario": engine.scenario,
    }))


# ── WebSocket live feed ───────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    engine.add_client(ws)
    try:
        await ws.send_json(_sanitize(engine.hello_message()))
        while True:
            # We don't need inbound messages; this keeps the socket open.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        engine.remove_client(ws)
