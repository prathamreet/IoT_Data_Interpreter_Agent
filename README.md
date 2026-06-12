# IoT Data Interpreter Agent

### Builathon - Use Case #43 - Real-World Automation

> "The future of IoT is not more dashboards. It's machines that explain themselves."

An AI reasoning layer that sits on top of any sensor stream and turns raw telemetry into plain-English narratives, anomaly flags, and actionable maintenance recommendations in real time.

This is a fully working software prototype that runs with no hardware. Sensors are realistically simulated; real devices drop in behind a single interface (see the Plug-and-play hardware section).

---

## Core Capabilities

| PRD Capability | In this Prototype |
|---|---|
| Anomaly detection (statistical + ML) | Z-score, IQR fence, and Isolation Forest fused by voting - [backend/processing/anomaly.py](file:///e:/development/cg/backend/processing/anomaly.py) |
| LLM narration (summary, severity, root cause) | Grounded Claude call returning structured JSON - [backend/agent/narrator.py](file:///e:/development/cg/backend/agent/narrator.py) |
| Maintenance recommendations | Prioritized action queue per anomaly, severity-tiered |
| Noisy / missing data handling | Imputation + confidence scoring; malfunction vs. real anomaly separation - [backend/processing/cleaning.py](file:///e:/development/cg/backend/processing/cleaning.py) |
| Agentic reasoning | Claude tool-use loop that inspects sensors, finds correlations, and writes an incident report - [backend/agent/investigator.py](file:///e:/development/cg/backend/agent/investigator.py) |
| Visualization & reporting | Live dashboard + downloadable HTML/PDF incident report |
| Evaluation | Precision/Recall/F1 vs. a labeled golden dataset - [evaluation/](file:///e:/development/cg/evaluation/) |

### Key Design Benefits

* **Robust Offline Fallback:** When no API key is provided, the narrator and the agent fall back to a deterministic engine that uses computed statistics. The dashboard updates without interruption. When an API key is provided, the UI utilizes live Claude reasoning.
* **Lightweight Front-End:** The dashboard is rendered without heavy dependencies (using canvas charts and a minimal markdown parser), running efficiently even under restricted network conditions.
* **Agentic Reasoning Loop:** Rather than static prompting, Claude uses interactive tools over live fleet states to investigate anomalies and log traces.
* **Hardware-Agnostic Interface:** All data intake consumes the `DataSource` interface. Swapping the simulator for an MQTT source allows physical sensors to integration seamlessly.

---

## Quickstart

### Option A - Docker (Recommended)

The application (backend + dashboard) runs inside a single container.

```bash
docker compose up --build
```

Access the dashboard at **http://localhost:8000**. Stop execution with `Ctrl+C` (or run `docker compose down`).

> [!NOTE]
> Review [startup-guide.md](file:///e:/development/cg/startup-guide.md) for step-by-step instructions on installing Docker Desktop and running the container.
> Port mapping is defined in [docker-compose.yml](file:///e:/development/cg/docker-compose.yml) (`8000:8000`). If port 8000 is occupied, modify the host port. An optional MQTT broker profile is available: `docker compose --profile hardware up`.

### Option B - Local Python Setup

**Prerequisites:** Python 3.10+ installed and added to your system path.

Run the launcher script:

* **Windows (PowerShell):**
  ```powershell
  .\run.ps1
  ```
* **macOS / Linux (Bash):**
  ```bash
  ./run.sh
  ```

Access the application at **http://127.0.0.1:8000**.

<details>
<summary>Manual Setup Instructions (All Operating Systems)</summary>

```bash
python -m venv .venv
# Activate virtual environment
# Windows: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
uvicorn backend.main:app --port 8000
```
</details>

### Run with Live Claude (Optional)

The application runs in offline fallback mode by default. To enable live Claude narration and investigation:

1. Copy the template configuration file:
   ```bash
   cp .env.example .env
   ```
2. Edit the [.env](file:///e:/development/cg/.env) file and add your API key:
   ```env
   ANTHROPIC_API_KEY=sk-ant-...
   ```
3. Restart the application. The header badge will update from "Offline mode" to "Claude live".

---

## Demonstration Script

1. Open the dashboard. Multiple sensors will stream data under nominal conditions.
2. Select the "HVAC failure - data center" scenario. Observe `TEMP-01` rising. Within a few seconds, an anomaly card will appear containing generated narration of the issue, severity classification, and recommended resolution steps. The `HUM-01` sensor will also be marked as correlated.
3. Select the "Sensor malfunction" scenario. The `PRES-02` sensor will experience dropouts. The cleaning module will label this as a sensor fault rather than a process equipment alarm, maintaining high confidence metrics.
4. Click the "Deep Investigation" button. The agent will execute a tool-use loop over the fleet and output a detailed incident report, detailing tool logs.
5. Click "Report" to generate and download a clean HTML incident report, suitable for saving to PDF.

---

## Plug-and-Play Hardware Integration

The system consumes `SensorReading` instances from a `DataSource` interface. To connect hardware:

1. Install the MQTT client library:
   ```bash
   pip install paho-mqtt
   ```
2. Publish sensor telemetry to your MQTT broker (e.g., Mosquitto, Azure IoT Hub, AWS IoT Core) as JSON:
   ```json
   {
     "sensor_id": "TEMP-01",
     "sensor_type": "temperature",
     "value": 22.4,
     "unit": "°C",
     "location": "Aisle A"
   }
   ```
3. Configure the following variables in your [.env](file:///e:/development/cg/.env) file:
   ```env
   DATA_SOURCE=mqtt
   MQTT_HOST=localhost
   MQTT_TOPIC=sensors/#
   ```
4. Adjust the parsing logic in `_parse_payload()` inside [backend/sources/mqtt_source.py](file:///e:/development/cg/backend/sources/mqtt_source.py) to map to your specific telemetry schema.

---

## Architecture Diagram

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
│──────────────────────┘                       │
           └──────────────┬────────────────────┘
                          ▼
              Dashboard (WebSocket) + HTML report      frontend/ · reporting/
```

---

## Evaluation and Testing

Run the following commands in the root of the project to validate logic:

* **Generate Golden Dataset:**
  ```bash
  python -m evaluation.make_golden
  ```
* **Run Evaluation Metrics:** Calculate precision, recall, and F1 scores against labeled scenarios.
  ```bash
  python -m evaluation.evaluate
  ```
* **Run Unit Tests:** Test anomaly detection and data cleaning algorithms.
  ```bash
  pytest
  ```

The evaluation suite verifies that sensor malfunctions (such as frozen values) do not trigger process equipment alerts.

---

## Configuration Reference

The following settings can be configured via environment variables or a local [.env](file:///e:/development/cg/.env) file:

| Variable | Default Value | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(empty)* | Enables live Claude agent reasoning and narration. |
| `NARRATION_MODEL` | `claude-opus-4-8` | Model used for generating short-form anomaly summaries. |
| `INVESTIGATOR_MODEL` | `claude-opus-4-8` | Model used for the multi-step agent. |
| `INVESTIGATOR_EFFORT` | `high` | Reasoning effort parameter for the investigator agent. |
| `TICK_INTERVAL` | `1.5` | Sampling period in seconds between simulator updates. |
| `WINDOW_SIZE` | `180` | Size of the rolling buffer window per sensor. |
| `ANOMALY_CONTAMINATION` | `0.03` | Contamination ratio for the Isolation Forest classifier. |
| `DEFAULT_SCENARIO` | `nominal` | Starting simulator failure scenario. |
| `DATA_SOURCE` | `simulator` | Raw input source (`simulator` or `mqtt`). |

---

## Project Structure

* [backend/](file:///e:/development/cg/backend/)
  * [backend/config.py](file:///e:/development/cg/backend/config.py): Application settings loader.
  * [backend/engine.py](file:///e:/development/cg/backend/engine.py): Fleet state orchestrator and agent context interface.
  * [backend/main.py](file:///e:/development/cg/backend/main.py): FastAPI server routing REST APIs, WebSockets, and static frontend assets.
  * [backend/sources/](file:///e:/development/cg/backend/sources/): Modules managing telemetry input.
    * [backend/sources/base.py](file:///e:/development/cg/backend/sources/base.py): Base class defining the `DataSource` interface.
    * [backend/sources/simulator.py](file:///e:/development/cg/backend/sources/simulator.py): Simulated fleet generator.
    * [backend/sources/scenarios.py](file:///e:/development/cg/backend/sources/scenarios.py): Specific incident injection sequences.
    * [backend/sources/mqtt_source.py](file:///e:/development/cg/backend/sources/mqtt_source.py): Physical device integration wrapper.
  * [backend/processing/](file:///e:/development/cg/backend/processing/): Metric cleaning and classifier pipelines.
    * [backend/processing/buffer.py](file:///e:/development/cg/backend/processing/buffer.py): Thread-safe rolling sensor queue.
    * [backend/processing/cleaning.py](file:///e:/development/cg/backend/processing/cleaning.py): Imputation, confidence indices, and sensor failure heuristics.
    * [backend/processing/anomaly.py](file:///e:/development/cg/backend/processing/anomaly.py): Ensemble voting classifier for anomalous reading detection.
  * [backend/agent/](file:///e:/development/cg/backend/agent/): Core AI logical units.
    * [backend/agent/llm.py](file:///e:/development/cg/backend/agent/llm.py): API interface with client handling and local mock defaults.
    * [backend/agent/prompts.py](file:///e:/development/cg/backend/agent/prompts.py): System instructions and prompt guidelines.
    * [backend/agent/tools.py](file:///e:/development/cg/backend/agent/tools.py): Investigator query tools over fleet state.
    * [backend/agent/narrator.py](file:///e:/development/cg/backend/agent/narrator.py): Summary generator.
    * [backend/agent/investigator.py](file:///e:/development/cg/backend/agent/investigator.py): Investigator agent execution loop.
  * [backend/reporting/report.py](file:///e:/development/cg/backend/reporting/report.py): Single-file document layout renderer.
* [frontend/](file:///e:/development/cg/frontend/): Dashboard visual resources (HTML, CSS, JS).
* [evaluation/](file:///e:/development/cg/evaluation/): Precision, recall, and F1 diagnostic suite.
* [tests/](file:///e:/development/cg/tests/): Unit test cases.
* [Dockerfile](file:///e:/development/cg/Dockerfile): Visualizer and API environment builder.
* [docker-compose.yml](file:///e:/development/cg/docker-compose.yml): Deployment container orchestrator.
* [startup-guide.md](file:///e:/development/cg/startup-guide.md): Easy-to-follow guide for environment initialization.

---

## Technology Stack

* **Language:** Python
* **Web Framework:** FastAPI, WebSocket
* **Data & Machine Learning:** pandas, NumPy, scikit-learn
* **AI reasoning:** Anthropic Claude API (adaptive thinking, tool-use)
* **Frontend:** HTML5, CSS3, Vanilla JavaScript (zero external dependencies)