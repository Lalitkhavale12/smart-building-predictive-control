"""Virtual ESP32 node shim (Phase 2, D-07).

Thin shim only — physics stays in ``sim``. Each instance owns one
:class:`MqttClientWrapper`: it publishes telemetry JSON (keys in
``TELEMETRY_COLUMNS`` order, sim-time stamps, floats at 4-decimal precision)
built from a ``BuildingSim`` per-room obs, and subscribes to its room command
wildcard, merging ``hvac``/``light`` setpoints into ``last_command``.
"""

import json

from iot import topics
from iot.mqtt_client import OFFLINE_PAYLOAD, MqttClientWrapper
from sim.logger import TELEMETRY_COLUMNS, sim_timestamp

DEFAULT_ACTION = {"hvac": "OFF", "light": 0}


class Esp32Node:
    """One virtual ESP32 for ``room`` over an injected wrapper."""

    def __init__(self, room, client_factory=None, client_id=None):
        self.room = room
        self.wrapper = MqttClientWrapper(
            client_id or f"esp32-{room}", client_factory=client_factory
        )
        # LWT registered BEFORE connect (wills never fire on clean disconnect).
        self.wrapper.set_will(
            topics.status_topic(room), OFFLINE_PAYLOAD, qos=1, retain=True
        )
        self.wrapper.subscribe(topics.command_filter(room), qos=1)
        self.last_command = dict(DEFAULT_ACTION)

    def connect(self, host="localhost", port=1883, keepalive=60):
        """Connect + start background loop (fires retained online status)."""
        self.wrapper.connect(host, port, keepalive)
        self.wrapper.start_loop()

    def publish_telemetry(self, obs_room, hvac_state="OFF", light_on=0, step=0):
        """Serialize one per-room obs to CSV-matching JSON, telemetry QoS 0."""
        payload = {
            "timestamp": sim_timestamp(step),
            "room": self.room,
            "T_in_C": round(float(obs_room["T_in"]), 4),
            "T_out_C": round(float(obs_room["T_out"]), 4),
            "RH_pct": round(float(obs_room["RH"]), 4),
            "occupancy": int(obs_room["occupancy"]),
            "HVAC_state": str(hvac_state),
            "power_kW": round(float(obs_room["power_kW"]), 4),
            "light_on": int(light_on),
        }
        assert list(payload) == TELEMETRY_COLUMNS  # key order matches CSV schema
        self.wrapper.publish(
            topics.telemetry_topic(self.room), json.dumps(payload), qos=0, retain=False
        )
        return payload

    def poll_commands(self):
        """Drain inbox command messages into ``last_command`` (non-blocking)."""
        prefix = f"building/{self.room}/command/"
        while True:
            try:
                msg = self.wrapper.inbox.get_nowait()
            except Exception:
                break
            if not getattr(msg, "topic", "").startswith(prefix):
                continue
            try:
                data = json.loads(bytes(msg.payload).decode())
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            # Accept per-device ({"hvac": ...} / {"light": ...}) or combined payloads.
            if "hvac" in data and data["hvac"] in topics.VALID_HVAC:
                self.last_command["hvac"] = data["hvac"]
            if "light" in data and data["light"] in topics.VALID_LIGHT:
                self.last_command["light"] = data["light"]
        return dict(self.last_command)

    def current_action(self):
        """Sim-step action dict entry for this room (held setpoint)."""
        return dict(self.last_command)
