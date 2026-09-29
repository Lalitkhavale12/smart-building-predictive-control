"""Real-broker gate (Phase 2 plan 01, D-06).

Skips cleanly when no broker listens on localhost:1883 (this machine has
none) or when paho-mqtt is not installed. Never runs in the default suite —
select explicitly: pytest tests/test_integration_mqtt.py -q
"""

import json
import socket
import time

import pytest

from iot import topics
from iot.mqtt_client import MqttClientWrapper

pytestmark = pytest.mark.integration


def _require_broker():
    try:
        with socket.create_connection(("localhost", 1883), timeout=1):
            pass
    except OSError:
        pytest.skip("no broker on localhost:1883")
    try:
        import paho.mqtt.client  # noqa: F401
    except ImportError:
        pytest.skip("paho-mqtt not installed")


def _recv(wrapper, timeout=5.0):
    import queue

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            return wrapper.inbox.get(timeout=0.2)
        except queue.Empty:
            continue
    raise AssertionError("timed out waiting for broker message")


def test_telemetry_roundtrip_real_broker():
    _require_broker()
    node = MqttClientWrapper("it-node")
    bridge = MqttClientWrapper("it-bridge")
    bridge.subscribe(topics.WILDCARD_TELEMETRY, qos=0)
    node.connect()
    bridge.connect()
    node.start_loop()
    bridge.start_loop()
    try:
        payload = json.dumps({"room": "office", "T_in_C": 25.0})
        node.publish(topics.telemetry_topic("office"), payload, qos=0)
        assert _recv(bridge).topic == "building/office/telemetry"
    finally:
        node.disconnect()
        bridge.disconnect()


def test_command_qos1_real_broker():
    _require_broker()
    node = MqttClientWrapper("it-node-cmd")
    bridge = MqttClientWrapper("it-bridge-cmd")
    node.subscribe(topics.command_filter("lab"), qos=1)
    node.connect()
    bridge.connect()
    node.start_loop()
    bridge.start_loop()
    try:
        bridge.publish(topics.command_topic("lab", "light"), '{"light": 1}', qos=1)
        msg = _recv(node)
        assert msg.topic == "building/lab/command/light"
        assert json.loads(msg.payload) == {"light": 1}
    finally:
        node.disconnect()
        bridge.disconnect()
