# 🛰 IoT Data Interpreter Agent

### Builathon · Use Case #43 — Real-World Automation

> *"The future of IoT is not more dashboards. It's machines that explain themselves."*

An AI reasoning layer that sits on top of any sensor stream and turns raw
telemetry into **plain-English narratives, anomaly flags, and actionable
maintenance recommendations** — in real time.

This is a **fully working software prototype** that runs with **no hardware**.
Sensors are realistically simulated; real devices drop in behind a single
interface (see [Plug-and-play hardware](#-plug-and-play-hardware)).

---

## ✨ What it does (maps 1:1 to the PRD)

| PRD capability | In this prototype |
|---|---|
| 🔍 **Anomaly detection** (statistical + ML) | Z-score · IQR fence · Isolation Forest, fused by voting — [`processing/anomaly.py`](backend/processing/anomaly.py) |
| 🗣 **LLM narration** (summary, severity, root cause) | Grounded Claude call returning structured JSON — [`agent/narrator.py`](backend/agent/narrator.py) |
| 🔧 **Maintenance recommendations** | Prioritized action queue per anomaly, severity-tiered |
| 🛠 **Noisy / missing data handling** | Imputation + confidence scoring; **malfunction vs. real anomaly** separation — [`processing/cleaning.py`](backend/processing/cleaning.py) |
| 🤖 **Agentic reasoning** | Claude **tool-use loop** that inspects sensors, finds correlations, and writes an incident report — [`agent/investigator.py`](backend/agent/investigator.py) |
| 📊 **Visualization & reporting** | Live dashboard + downloadable HTML/PDF incident report |
| 🧪 **Evaluation** | Precision/Recall/F1 vs. a labeled golden dataset — [`evaluation/`](evaluation/) |

### Why this wins
- **It always works on stage.** No API key? The narrator and the agent fall back
  to a deterministic engine that uses the *real* computed statistics — the demo
  never goes blank. Add a key and the same UI lights up with live Claude reasoning.
- **Zero front-end build, no CDN.** The dashboard is hand-rendered (canvas charts,
  tiny markdown renderer) — it runs even on locked-down venue Wi-Fi. One command,
  one server, open the browser.
- **Genuinely agentic.** Not a single prompt — Claude calls real tools over live
  fleet state to reach a conclusion, and you can watch the tool trace.
- **Hardware-ready by design.** Everything consumes a `DataSource`. Swap the
  simulator for the MQTT source and real sensors flow in unchanged.

---

## 🚀 Quickstart

### Option A — Docker (recommended · no Python needed)
The whole app (backend + dashboard) runs in one container.

```bash
docker compose up --build
```
…then open **http://localhost:8000**. Stop with `Ctrl+C` (or `docker compose down`).

> 👉 Non-technical? Follow the friendly **[startup-guide.md](startup-guide.md)** —
> install Docker Desktop, run one command, open a web page. That's it.
>
> Port mapping lives in [`docker-compose.yml`](docker-compose.yml) (`"8000:8000"` →
> change the left number if 8000 is busy). An optional MQTT broker for the
> hardware path is included behind a profile: `docker compose --profile hardware up`.

### Option B — Local Python
**Prerequisite:** Python **3.10+** from [python.org](https://www.python.org/downloads/)
(on Windows tick **“Add python.exe to PATH”**; if `python` opens the Microsoft
Store, disable the alias in *Settings → Apps → Advanced app settings → App
execution aliases*).

```powershell
.\run.ps1        # Windows (PowerShell)
```
```bash
./run.sh         # macOS / Linux
```

…then open **http://127.0.0.1:8000**.

<details>
<summary>Manual setup (any OS)</summary>

```bash
python -m venv .venv
# Windows:  .\.venv\Scripts\Activate.ps1     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --port 8000
```
</details>

### Run with live Claude (optional)
The app runs fully **without** a key. To enable live narration + the agent:
```bash
cp .env.example .env        # then edit .env:
# ANTHROPIC_API_KEY=sk-ant-...
```
Restart. The header badge flips from **“Offline mode”** to **“Claude live”**.

---

## 🎬 60-second demo script (for judges)

1. Open the dashboard — six sensors stream live, all green.
2. Click **“HVAC failure — data center.”** Watch `TEMP-01` climb; within seconds
   an anomaly card appears, **narrated**: what, severity, likely cause, action.
   Note `HUM-01` is flagged as **correlated**.
3. Click **“Sensor malfunction.”** `PRES-02` freezes/drops out. The system calls
   it a **SENSOR FAULT**, *not* an equipment alarm — confidence scoring at work.
4. Hit **⚙ Deep Investigation.** The agent runs a **tool-use loop** over the
   fleet and returns a prioritized **incident report**; the tool calls are shown.
5. Hit **⤓ Report** → a clean HTML incident report opens (Print → Save as PDF).

---

## 🔌 Plug-and-play hardware

The whole system is hardware-agnostic — it only consumes `SensorReading`s from a
`DataSource`. To go live with real sensors:

1. `pip install paho-mqtt`
2. Point your sensors / gateway (Mosquitto, Azure IoT Hub, AWS IoT Core,
   Node-RED…) at an MQTT broker publishing JSON like:
   ```json
   { "sensor_id":"TEMP-01", "sensor_type":"temperature",
     "value":22.4, "unit":"°C", "location":"Aisle A" }
   ```
3. In `.env`: `DATA_SOURCE=mqtt`, `MQTT_HOST=...`, `MQTT_TOPIC=sensors/#`
4. Adapt `_parse_payload()` in [`backend/sources/mqtt_source.py`](backend/sources/mqtt_source.py)
   to your message schema.

**That's the entire integration — no other file changes.** Other transports
(Modbus, OPC-UA, serial/USB, REST) follow the same pattern: implement one class.

---

## 🧠 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Data source (DataSource)  ← simulator  |  MQTT (hardware)    │  sources/
└───────────────────────────┬──────────────────────────────────┘
                            │  SensorReading
┌───────────────────────────▼──────────────────────────────────┐
│  Processing:  rolling buffer → impute → quality → anomaly     │  processing/
│               (Z-score · IQR · Isolation Forest · confidence) │
└───────────────────────────┬──────────────────────────────────┘
                            │  analyses + edge-triggered alerts
┌───────────────────────────▼──────────────────────────────────┐
│  Engine: orchestrates, raises events, fans out over WebSocket │  engine.py
└──────────┬───────────────────────────────────┬───────────────┘
           │                                   │
┌──────────▼───────────┐          ┌────────────▼──────────────┐
│  Narrator (1 call)   │          │  Investigator (agent loop)│  agent/
│  grounded JSON  ↔ LLM│          │  Claude + tools  ↔  LLM   │
│  + deterministic     │          │  + deterministic fallback │
│    fallback          │          └────────────┬──────────────┘
└──────────┬───────────┘                       │
           └──────────────┬────────────────────┘
                          ▼
              Dashboard (WebSocket) + HTML report      frontend/ · reporting/
```

---

## 🧪 Evaluation & tests

```bash
python -m evaluation.make_golden     # (re)generate the labeled dataset
python -m evaluation.evaluate        # precision / recall / F1 per case + overall
pytest                               # unit tests for detection + quality
```

The golden dataset deliberately includes a **stuck-sensor** case to verify the
detector does *not* raise a process anomaly for a malfunction.

---

## ⚙ Configuration (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(empty)* | Enables live Claude. Empty = offline fallback. |
| `NARRATION_MODEL` | `claude-opus-4-8` | Model for per-anomaly narration |
| `INVESTIGATOR_MODEL` | `claude-opus-4-8` | Model for the agent |
| `INVESTIGATOR_EFFORT` | `high` | Agent reasoning effort (low/medium/high/max) |
| `TICK_INTERVAL` | `1.5` | Seconds between sensor samples |
| `WINDOW_SIZE` | `180` | Rolling window per sensor |
| `ANOMALY_CONTAMINATION` | `0.03` | Isolation Forest expected anomaly fraction |
| `DEFAULT_SCENARIO` | `nominal` | Starting scenario |
| `DATA_SOURCE` | `simulator` | `simulator` or `mqtt` |

---

## 📁 Project structure

```
backend/
  config.py            settings (env / .env)
  engine.py            orchestration + live FleetView for the agent
  main.py              FastAPI app: REST + WebSocket + serves the dashboard
  sources/             DataSource abstraction
    base.py            SensorReading + DataSource ABC   ← the hardware seam
    simulator.py       synthetic multi-sensor stream (works now)
    scenarios.py       scripted fault scenarios
    mqtt_source.py     real-hardware drop-in (placeholder)
  processing/
    buffer.py          rolling per-sensor buffers
    cleaning.py        imputation + confidence + malfunction detection
    anomaly.py         Z-score · IQR · Isolation Forest (voting)
  agent/
    llm.py             Claude client (graceful when no key)
    prompts.py         grounded system prompts (anti-hallucination)
    narrator.py        single-call structured narration + fallback
    tools.py           read-only tools over fleet state
    investigator.py    Claude tool-use loop + deterministic fallback
  reporting/report.py  self-contained HTML incident report
frontend/              dependency-free dashboard (index.html · styles.css · app.js)
evaluation/            golden dataset generator + P/R/F1 evaluator
tests/                 pytest unit tests
Dockerfile             single-container image (backend serves the dashboard)
docker-compose.yml     one-command run + port mapping (+ optional MQTT broker)
startup-guide.md       plain-English run guide for non-technical users
```

---

## 🧰 Tech stack
Python · FastAPI · WebSocket · pandas · NumPy · scikit-learn · Anthropic Claude
(`claude-opus-4-8`, adaptive thinking + structured outputs + tool use) ·
vanilla JS dashboard (no build step).

---

*Prototype for the Builathon. Hardware-ready, demo-proof, and explainable by design.*
#   I o T _ D a t a _ I n t e r p r e t e r _ A g e n t  
 