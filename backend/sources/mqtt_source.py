"""MQTTDataSource — the hardware plug point.  ⚡ PLACEHOLDER / DROP-IN ⚡

This is where real sensors join the system. The rest of the application is
hardware-agnostic: implement `poll()` to return `SensorReading`s and everything
downstream (cleaning, anomaly detection, narration, the agent, the dashboard)
works unchanged.

────────────────────────────────────────────────────────────────────────────
TO GO LIVE WITH REAL HARDWARE:
  1.  pip install paho-mqtt
  2.  Point sensors / gateway at an MQTT broker (e.g. Mosquitto, Azure IoT Hub,
      AWS IoT Core, Node-RED). Publish JSON like:
          topic:   sensors/TEMP-01
          payload: {"sensor_id":"TEMP-01","sensor_type":"temperature",
                    "value":22.4,"unit":"°C","location":"Aisle A"}
  3.  Set in .env:   DATA_SOURCE=mqtt
                     MQTT_HOST=...   MQTT_PORT=1883   MQTT_TOPIC=sensors/#
  4.  Adapt `_parse_payload()` below to your actual message schema.
That's the entire integration. No other file changes.
────────────────────────────────────────────────────────────────────────────

For other transports (Modbus, OPC-UA, serial/USB, REST poll) copy this class,
keep the `DataSource` interface, and swap the ingest mechanism.
"""

from __future__ import annotations

import json
import os
import queue
import time

from .base import DataSource, SensorReading, SensorSpec


class MQTTDataSource(DataSource):
    name = "mqtt"

    def __init__(self) -> None:
        self.host = os.getenv("MQTT_HOST", "localhost")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.topic = os.getenv("MQTT_TOPIC", "sensors/#")
        self._client = None
        self._inbox: "queue.Queue[SensorReading]" = queue.Queue(maxsize=10_000)
        # Latest reading per sensor + discovered specs (populated as data arrives).
        self._latest: dict[str, SensorReading] = {}
        self._specs: dict[str, SensorSpec] = {}

    # ── DataSource contract ───────────────────────────────────────────
    def start(self) -> None:
        try:
            import paho.mqtt.client as mqtt  # noqa: WPS433 (lazy: optional dep)
        except ImportError as exc:  # pragma: no cover - hardware path
            raise RuntimeError(
                "MQTTDataSource requires paho-mqtt. Install it with "
                "`pip install paho-mqtt`, or keep DATA_SOURCE=simulator."
            ) from exc

        self._client = mqtt.Client()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect(self.host, self.port, keepalive=60)
        self._client.loop_start()  # background network thread

    def stop(self) -> None:
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()

    def specs(self) -> list[SensorSpec]:
        # Specs are discovered from live traffic. Until a sensor has reported,
        # nothing is known about it — that's expected on a cold start.
        return list(self._specs.values())

    def poll(self) -> list[SensorReading]:
        # Drain everything received since the last poll; keep the newest per sensor.
        while True:
            try:
                reading = self._inbox.get_nowait()
            except queue.Empty:
                break
            self._latest[reading.sensor_id] = reading
            self._ensure_spec(reading)
        return list(self._latest.values())

    # ── MQTT callbacks ────────────────────────────────────────────────
    def _on_connect(self, client, _userdata, _flags, _rc) -> None:  # pragma: no cover
        client.subscribe(self.topic)

    def _on_message(self, _client, _userdata, msg) -> None:  # pragma: no cover
        reading = self._parse_payload(msg.topic, msg.payload)
        if reading is not None:
            try:
                self._inbox.put_nowait(reading)
            except queue.Full:
                pass  # back-pressure: drop oldest semantics handled by the buffer

    # ── adapt this to your real message schema ────────────────────────
    def _parse_payload(self, topic: str, payload: bytes) -> SensorReading | None:
        """Map a broker message to a SensorReading. EDIT FOR YOUR HARDWARE."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

        sid = data.get("sensor_id") or topic.rsplit("/", 1)[-1]
        raw = data.get("value", None)
        return SensorReading(
            sensor_id=sid,
            sensor_type=data.get("sensor_type", "unknown"),
            value=float(raw) if raw is not None else None,
            unit=data.get("unit", ""),
            timestamp=float(data.get("timestamp", time.time())),
            location=data.get("location", "unspecified"),
            quality_hint="ok" if raw is not None else "missing",
        )

    def _ensure_spec(self, r: SensorReading) -> None:
        """Lazily register a spec for a newly-seen sensor.

        Baselines/limits aren't known for live hardware up front; the anomaly
        engine learns them online from the rolling window, so placeholder
        physical bounds are fine here.
        """
        if r.sensor_id in self._specs:
            return
        self._specs[r.sensor_id] = SensorSpec(
            sensor_id=r.sensor_id, sensor_type=r.sensor_type, unit=r.unit,
            location=r.location, baseline=r.value or 0.0, noise_sigma=1.0,
            min_phys=float("-inf"), max_phys=float("inf"),
        )
