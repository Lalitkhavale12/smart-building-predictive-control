"""MQTT <-> sim bridge (Phase 2, D-10/D-11).

Owns ONE wrapper on the background loop, subscribes (telemetry + status
wildcards) only via the wrapper's recorded-subscription path so every
reconnect renews them, and maps queued telemetry to a ``BasePolicy.step``
call. Commands publish QoS 1, never retained (duplicates are harmless:
absolute setpoints, never toggles). Inbound telemetry is range-validated;
corrupt input holds last-good without actuating and counts a gap. Sequence
gaps (seeded broker drops) are detected per room via sim-time timestamps.
"""

import datetime
import json

from iot import topics
from iot.mqtt_client import MqttClientWrapper

# Exponential backoff window (seconds) for reconnect storms.
RECONNECT_MIN_DELAY = 1
RECONNECT_MAX_DELAY = 30

# Inbound validation bounds (F-2): physics-adjacent sanity, not comfort logic.
T_IN_MIN, T_IN_MAX = -10.0, 60.0
RH_MIN, RH_MAX = 0.0, 100.0


def _parse_ts(value):
    try:
        return datetime.datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class TelemetryBridge:
    """Between ``BuildingSim`` and a ``BasePolicy``: obs→telemetry in, commands out."""

    def __init__(self, sim, policy, client_factory=None, client_id="bridge"):
        self.sim = sim
        self.policy = policy
        self.wrapper = MqttClientWrapper(client_id, client_factory=client_factory)
        self.wrapper.subscribe(topics.WILDCARD_TELEMETRY, qos=0)
        self.wrapper.subscribe(topics.WILDCARD_STATUS, qos=1)
        # Backoff on the real client; test doubles lack the method — skip there.
        real = self.wrapper._client
        if hasattr(real, "reconnect_delay_set"):
            real.reconnect_delay_set(
                min_delay=RECONNECT_MIN_DELAY, max_delay=RECONNECT_MAX_DELAY
            )
        self.last_good = {}  # room -> last valid telemetry dict
        self.last_ts = {}  # room -> last valid timestamp (gap detection)
        self.first_ts = {}  # room -> first valid timestamp (interior-gap span)
        self.last_action = {}  # room -> last published action (held on corrupt input)
        self.gap_count = 0  # corrupt + sequence-missed telemetry, never crashes
        self.received_count = 0

    def connect(self, host="localhost", port=1883, keepalive=60):
        self.wrapper.connect(host, port, keepalive)
        self.wrapper.start_loop()

    def _validate(self, data):
        """Range-check inbound telemetry; False = hold last-good, count a gap."""
        try:
            t_in = float(data["T_in_C"])
            rh = float(data["RH_pct"])
            occ = data["occupancy"]
        except (KeyError, TypeError, ValueError):
            return False
        if isinstance(occ, bool) or not isinstance(occ, int) or occ < 0:
            return False
        return (T_IN_MIN <= t_in <= T_IN_MAX) and (RH_MIN <= rh <= RH_MAX)

    def _drain(self):
        """Enqueue-free intake: parse + validate inbox, update last-good; returns fresh rooms."""
        fresh = set()
        while True:
            try:
                msg = self.wrapper.inbox.get_nowait()
            except Exception:
                break
            topic = getattr(msg, "topic", "")
            if not topic.endswith("/telemetry"):
                continue  # status chatter is observed, never actuated on
            try:
                data = json.loads(bytes(msg.payload).decode())
            except (ValueError, UnicodeDecodeError, AttributeError):
                self.gap_count += 1
                continue
            if not isinstance(data, dict) or not self._validate(data):
                self.gap_count += 1  # corrupt → hold last-good, never actuate
                continue
            room = data.get("room")
            if not isinstance(room, str):
                self.gap_count += 1
                continue
            ts = _parse_ts(data.get("timestamp"))
            if ts is not None and room in self.last_ts:
                missed = round((ts - self.last_ts[room]).total_seconds() / 60.0) - 1
                if missed > 0:
                    self.gap_count += missed  # seeded-drop sequence gap, counted not crashed
            if ts is not None:
                self.first_ts.setdefault(room, ts)
                self.last_ts[room] = ts
            self.last_good[room] = data
            self.received_count += 1
            fresh.add(room)
        return fresh

    def _obs_from_telemetry(self):
        return {
            room: {
                "T_in": float(data["T_in_C"]),
                "T_out": float(data["T_out_C"]),
                "RH": float(data["RH_pct"]),
                "occupancy": int(data["occupancy"]),
                "power_kW": float(data["power_kW"]),
            }
            for room, data in self.last_good.items()
        }

    def _publish_action(self, room, action_room):
        hvac, light = action_room.get("hvac"), action_room.get("light")
        if hvac not in topics.VALID_HVAC or light not in topics.VALID_LIGHT:
            return False  # network-originated garbage never reaches the sim
        self.wrapper.publish(
            topics.command_topic(room, "hvac"), json.dumps({"hvac": hvac}),
            qos=1, retain=False,
        )
        self.wrapper.publish(
            topics.command_topic(room, "light"), json.dumps({"light": light}),
            qos=1, retain=False,
        )
        self.last_action[room] = {"hvac": hvac, "light": light}
        return True

    def tick(self):
        """One control tick: intake → policy → commands → sim step. Returns action."""
        fresh = self._drain()
        obs = self._obs_from_telemetry()
        action = self.policy.step(obs) if obs else {}
        if not isinstance(action, dict):
            action = {}
        for room in fresh:
            if room in action and isinstance(action[room], dict):
                self._publish_action(room, action[room])
            # Rooms with corrupt input this tick: no publish (hold last setpoint).
        full_action = {
            room: dict(self.last_action.get(room, {"hvac": "OFF", "light": 0}))
            for room in self.sim.cfg.ROOMS
        }
        sim_obs = self.sim.step(full_action)
        return full_action, sim_obs
