"""The orchestration engine — the reasoning layer between raw data and humans.

Each tick:  poll source → buffer → impute → assess quality → detect anomalies →
raise/clear alerts (edge-triggered) → narrate new alerts → broadcast to clients.

It also implements the read-only `FleetView` the investigator agent's tools use,
so the same live state powers the dashboard and the agent.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque

from .agent.narrator import narrate
from .config import settings
from .processing.anomaly import AnomalyDetector
from .processing.buffer import FleetBuffer
from .processing.cleaning import assess_quality, impute
from .sources import build_source


def _sanitize(obj):
    """Recursively replace NaN/Inf with None so payloads are valid JSON."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


class Engine:
    def __init__(self) -> None:
        self.source = build_source()
        self.fleet = FleetBuffer(window=settings.window_size)
        self.detector = AnomalyDetector(contamination=settings.contamination)
        self.specs = {s.sensor_id: s for s in self.source.specs()}
        self.analyses: dict[str, dict] = {}
        self._active: dict[str, tuple | None] = {}
        self._streak: dict[str, int] = {}
        self.events: deque[dict] = deque(maxlen=60)
        self.actions: dict[str, dict] = {}
        self._clients: set = set()
        self._task: asyncio.Task | None = None
        self._running = False
        self.scenario = getattr(self.source, "scenario_name", settings.default_scenario)

    # ── lifecycle ─────────────────────────────────────────────────────
    async def start(self) -> None:
        self.source.start()
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        self.source.stop()

    async def _loop(self) -> None:
        while self._running:
            try:
                self._tick()
                await self._broadcast(self.snapshot_message())
            except Exception as exc:  # pragma: no cover - keep the loop alive
                print(f"[engine] tick error: {exc}")
            await asyncio.sleep(settings.tick_interval)

    # ── per-tick processing ───────────────────────────────────────────
    def _tick(self) -> None:
        readings = self.source.poll()
        for r in readings:
            self.specs.setdefault(r.sensor_id, None)
            buf = self.fleet.ingest(r)
            spec = self.specs.get(r.sensor_id)

            series = buf.series()
            imputed = impute(series)
            quality = assess_quality(series, spec)
            anomaly = self.detector.analyze(imputed)

            # Build aligned series for plotting (NaN -> None = gap on chart).
            times = [time.strftime("%H:%M:%S", time.localtime(t)) for t in series.index]
            vals = [None if (v != v) else round(float(v), 3) for v in series.tolist()]

            self.analyses[r.sensor_id] = {
                "sensor_id": r.sensor_id,
                "sensor_type": r.sensor_type,
                "unit": r.unit,
                "location": r.location,
                "value": r.value,
                "quality": quality.to_dict(),
                "anomaly": anomaly.to_dict(),
                "times": times[-90:],
                "series": vals[-90:],
            }
            self._evaluate_alert(r.sensor_id)

    _SEV_RANK = {"normal": 0, "low": 1, "moderate": 2, "critical": 3}

    def _alert_signature(self, sid: str) -> tuple | None:
        a = self.analyses[sid]
        if a["quality"]["status"] == "malfunction":
            return ("malfunction",)
        if a["anomaly"]["is_anomaly"]:
            return ("anomaly", a["anomaly"]["severity_hint"])
        return None

    def _evaluate_alert(self, sid: str) -> None:
        sig = self._alert_signature(sid)

        # Persistence filter: confirm an anomaly across 2 consecutive ticks to
        # suppress single-sample noise blips. Malfunctions surface immediately.
        if sig is not None and sig[0] == "anomaly":
            self._streak[sid] = self._streak.get(sid, 0) + 1
            if self._streak[sid] < 2:
                sig = None
        else:
            self._streak[sid] = 0

        prev = self._active.get(sid)
        if sig is None:
            if prev is not None:
                self._active.pop(sid, None)
                self._schedule_broadcast({"type": "resolved", "sensor_id": sid, "ts": time.time()})
            return

        self._active[sid] = sig  # always track the latest state
        if prev is None or sig[0] != prev[0]:
            self._raise_event(sid, kind=sig[0])
            return
        # Same kind: only re-raise an anomaly when its severity escalates.
        if sig[0] == "anomaly" and self._SEV_RANK.get(sig[1], 0) > self._SEV_RANK.get(prev[1], 0):
            self._raise_event(sid, kind=sig[0])

    def _raise_event(self, sid: str, kind: str) -> None:
        a = self.analyses[sid]
        ts = time.time()
        event = {
            "id": f"{sid}-{int(ts * 1000)}",
            "sensor_id": sid,
            "sensor_type": a["sensor_type"],
            "location": a["location"],
            "unit": a["unit"],
            "value": a["value"],
            "kind": kind,  # anomaly | malfunction
            "severity_hint": a["anomaly"]["severity_hint"],
            "z_score": a["anomaly"]["z_score"],
            "methods": a["anomaly"]["methods"],
            "status": a["quality"]["status"],
            "ts": ts,
            "ts_iso": time.strftime("%H:%M:%S", time.localtime(ts)),
            "narration": None,
            "severity": None,
            "used_llm": None,
        }
        self.events.appendleft(event)
        # Broadcast immediately (narration pending), then narrate asynchronously.
        self._schedule_broadcast({"type": "event", "event": event})
        asyncio.create_task(self._narrate_event(event))

    async def _narrate_event(self, event: dict) -> None:
        context = self._narration_context(event)
        narration = await narrate(context)
        event["narration"] = narration
        event["severity"] = narration.get("severity")
        event["used_llm"] = narration.get("used_llm")
        self._register_action(event)
        await self._broadcast({"type": "event_narrated", "event": event})

    def _narration_context(self, event: dict) -> dict:
        """Build grounded context for the narrator.

        Prefers live analysis; degrades gracefully to the event snapshot if the
        sensor's analysis was reset (e.g. a scenario switch) mid-narration.
        """
        sid = event["sensor_id"]
        a = self.analyses.get(sid)
        if a is None:
            return {
                "sensor_id": sid,
                "sensor_type": event["sensor_type"],
                "unit": event["unit"],
                "location": event["location"],
                "current_value": event["value"],
                "baseline_mean": 0.0,
                "baseline_std": 0.0,
                "z_score": event["z_score"],
                "direction": "high",
                "methods": event.get("methods", []),
                "severity_hint": event.get("severity_hint", "low"),
                "recent_values": [],
                "data_quality": {"status": event.get("status", "healthy"),
                                 "confidence": 1.0, "reasons": []},
                "correlated": [],
            }
        buf = self.fleet.get(sid)
        return {
            "sensor_id": sid,
            "sensor_type": a["sensor_type"],
            "unit": a["unit"],
            "location": a["location"],
            "current_value": a["value"],
            "baseline_mean": a["anomaly"]["baseline_mean"],
            "baseline_std": a["anomaly"]["baseline_std"],
            "z_score": a["anomaly"]["z_score"],
            "direction": a["anomaly"]["direction"],
            "methods": a["anomaly"]["methods"],
            "severity_hint": a["anomaly"]["severity_hint"],
            "recent_values": (buf.recent(12) if buf else []),
            "data_quality": a["quality"],
            "correlated": self.find_correlations(sid),
        }

    def _register_action(self, event: dict) -> None:
        narration = event.get("narration") or {}
        self.actions[event["sensor_id"]] = {
            "id": event["id"],
            "sensor_id": event["sensor_id"],
            "location": event["location"],
            "severity": event.get("severity") or "Low",
            "kind": event["kind"],
            "action": narration.get("recommended_action", "Monitor."),
            "status": "open",
            "ts_iso": event["ts_iso"],
        }

    # ── FleetView interface (used by the investigator's tools) ────────
    def list_sensors(self) -> list[dict]:
        out = []
        for sid, a in self.analyses.items():
            out.append({
                "sensor_id": sid,
                "sensor_type": a["sensor_type"],
                "location": a["location"],
                "unit": a["unit"],
                "value": a["value"],
                "status": a["quality"]["status"],
                "is_anomaly": a["anomaly"]["is_anomaly"],
                "severity_hint": a["anomaly"]["severity_hint"],
                "z_score": a["anomaly"]["z_score"],
                "methods": a["anomaly"]["methods"],
            })
        return out

    def get_sensor(self, sid: str) -> dict | None:
        a = self.analyses.get(sid)
        if a is None:
            return None
        buf = self.fleet.get(sid)
        return {
            "sensor_id": sid,
            "sensor_type": a["sensor_type"],
            "location": a["location"],
            "unit": a["unit"],
            "current_value": a["value"],
            "recent_values": buf.recent(20) if buf else [],
            "baseline_mean": a["anomaly"]["baseline_mean"],
            "baseline_std": a["anomaly"]["baseline_std"],
            "z_score": a["anomaly"]["z_score"],
            "iqr_low": a["anomaly"]["iqr_low"],
            "iqr_high": a["anomaly"]["iqr_high"],
            "anomaly_methods": a["anomaly"]["methods"],
            "is_anomaly": a["anomaly"]["is_anomaly"],
            "severity_hint": a["anomaly"]["severity_hint"],
            "data_quality": a["quality"],
        }

    def find_correlations(self, sid: str) -> list[dict]:
        base = self.analyses.get(sid)
        if base is None:
            return []
        bdir = base["anomaly"]["direction"]
        out = []
        for other, a in self.analyses.items():
            if other == sid:
                continue
            an = a["anomaly"]
            if abs(an["z_score"]) >= 2.0 and an["direction"] == bdir:
                out.append({
                    "sensor_id": other,
                    "direction": an["direction"],
                    "z_score": an["z_score"],
                })
        return out

    def fleet_summary(self) -> dict:
        statuses = [a["quality"]["status"] for a in self.analyses.values()]
        anomalies = [a for a in self.analyses.values() if a["anomaly"]["is_anomaly"]]
        return {
            "total": len(self.analyses),
            "healthy": statuses.count("healthy"),
            "degraded": statuses.count("degraded"),
            "malfunction": statuses.count("malfunction"),
            "anomalous": len(anomalies),
            "scenario": self.scenario,
        }

    # ── snapshots & messaging ─────────────────────────────────────────
    def kpis(self) -> dict:
        s = self.fleet_summary()
        confidences = [a["quality"]["confidence"] for a in self.analyses.values()]
        avg_conf = sum(confidences) / len(confidences) if confidences else 1.0
        open_actions = [x for x in self.actions.values() if x["status"] == "open"]
        return {
            **s,
            "avg_confidence": round(avg_conf, 3),
            "open_actions": len(open_actions),
            "llm_enabled": settings.llm_enabled,
        }

    def snapshot_message(self) -> dict:
        return {
            "type": "snapshot",
            "ts": time.time(),
            "scenario": self.scenario,
            "kpis": self.kpis(),
            "sensors": list(self.analyses.values()),
        }

    def hello_message(self) -> dict:
        from .agent.llm import llm_available
        from .sources.scenarios import scenario_catalogue

        return {
            "type": "hello",
            "llm_enabled": llm_available(),
            "narration_model": settings.narration_model,
            "scenario": self.scenario,
            "scenarios": scenario_catalogue(),
            "snapshot": self.snapshot_message(),
            "events": list(self.events)[:20],
            "actions": list(self.actions.values()),
        }

    # ── scenario control ──────────────────────────────────────────────
    def set_scenario(self, name: str) -> bool:
        ok = self.source.set_scenario(name)
        if ok:
            self.scenario = name
            # Fresh start so the new fault is clearly visible and old alerts clear.
            self.fleet = FleetBuffer(window=settings.window_size)
            self.analyses.clear()
            self._active.clear()
            self._streak.clear()
        return ok

    # ── websocket fan-out ─────────────────────────────────────────────
    def add_client(self, ws) -> None:
        self._clients.add(ws)

    def remove_client(self, ws) -> None:
        self._clients.discard(ws)

    def _schedule_broadcast(self, message: dict) -> None:
        asyncio.create_task(self._broadcast(message))

    async def _broadcast(self, message: dict) -> None:
        if not self._clients:
            return
        payload = _sanitize(message)
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


engine = Engine()
