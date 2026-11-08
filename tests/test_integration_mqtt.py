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


def _publish_until_recv(publisher, topic, payload, qos, receiver,
                        expected_topic, deadline=10.0):
    """Publish (retrying) until the receiver's inbox gets the topic.

    The broker SUBSCRIBE from _on_connect is async — a single publish can
    win the race and be dropped (QoS 0). Retrying separates product-path
    failures (never arrives) from timing luck (arrives late).
    """
    import queue

    end = time.time() + deadline
    while time.time() < end:
        publisher.publish(topic, payload, qos=qos)
        try:
            msg = receiver.inbox.get(timeout=0.5)
            assert msg.topic == expected_topic
            return msg
        except queue.Empty:
            continue
    raise AssertionError(f"no {expected_topic} after {deadline}s of publishes")


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
        _publish_until_recv(node, topics.telemetry_topic("office"), payload,
                            0, bridge, "building/office/telemetry")
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
        msg = _publish_until_recv(bridge, topics.command_topic("lab", "light"),
                                  '{"light": 1}', 1, node,
                                  "building/lab/command/light")
        assert json.loads(msg.payload) == {"light": 1}
    finally:
        node.disconnect()
        bridge.disconnect()
