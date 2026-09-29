"""Wrapper + fake-broker tests (Phase 2 plan 01, IOT-01/02/04). Brokerless; never imports paho."""

import queue
import sys
import types

from iot import topics
from iot.mqtt_client import MqttClientWrapper, OFFLINE_PAYLOAD, default_client_factory
from tests.fakes import FakeBroker, FakeClient, topic_matches


def make_factory(broker):
    return lambda client_id: FakeClient(client_id, broker)


def make_pair(broker, **kw):
    node = MqttClientWrapper("node", client_factory=make_factory(broker), **kw)
    bridge = MqttClientWrapper("bridge", client_factory=make_factory(broker), **kw)
    return node, bridge


def test_default_factory_passes_version2_first_positional(monkeypatch):
    sentinel, recorded = object(), {}

    class FakePahoClient:
        def __init__(self, *args, **kwargs):
            recorded["args"], recorded["kwargs"] = args, kwargs

        def reconnect_delay_set(self, **kwargs):
            recorded["backoff"] = kwargs

    module = types.ModuleType("paho.mqtt.client")
    module.CallbackAPIVersion = types.SimpleNamespace(VERSION2=sentinel)
    module.Client = FakePahoClient
    monkeypatch.setitem(sys.modules, "paho", types.ModuleType("paho"))
    monkeypatch.setitem(sys.modules, "paho.mqtt", types.ModuleType("paho.mqtt"))
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", module)

    default_client_factory("probe")
    assert recorded["args"][0] is sentinel  # VERSION2 is the FIRST positional arg
    assert recorded["backoff"] == {"min_delay": 1, "max_delay": 30}


def test_telemetry_roundtrip_node_to_bridge_intake():
    broker = FakeBroker()
    node, bridge = make_pair(broker)
    bridge.subscribe(topics.WILDCARD_TELEMETRY, qos=0)
    bridge.connect()
    node.connect()
    node.publish(topics.telemetry_topic("classroom_A"), '{"T_in_C": 24.5}', qos=0)
    msg = bridge.inbox.get_nowait()
    assert msg.topic == "building/classroom_A/telemetry"
    assert b"24.5" in msg.payload


def test_command_publish_qos1_never_retained():
    broker = FakeBroker()
    node, bridge = make_pair(broker)
    bridge.subscribe(topics.command_filter("classroom_A"), qos=1)
    bridge.connect()
    node.connect()
    node.publish(topics.command_topic("classroom_A", "hvac"), '{"hvac": "ON"}', qos=1)
    assert ("building/classroom_A/command/hvac", b'{"hvac": "ON"}', 1, False) in broker.published
    assert bridge.inbox.get_nowait().payload == b'{"hvac": "ON"}'


def test_retained_status_replayed_to_late_subscriber():
    broker = FakeBroker()
    node, _ = make_pair(broker)
    node.set_will(topics.status_topic("classroom_A"), OFFLINE_PAYLOAD, qos=1, retain=True)
    node.connect()  # on_connect publishes retained online status
    late = MqttClientWrapper("late", client_factory=make_factory(broker))
    late.subscribe(topics.WILDCARD_STATUS, qos=1)
    late.connect()
    msg = late.inbox.get_nowait()
    assert msg.topic == "building/classroom_A/status"
    assert msg.payload == b'{"state":"online"}'
    assert msg.retain is True


def test_kill_client_fires_offline_will():
    broker = FakeBroker()
    node, bridge = make_pair(broker)
    node.set_will(topics.status_topic("classroom_B"), OFFLINE_PAYLOAD, qos=1, retain=True)
    node.connect()
    bridge.subscribe(topics.WILDCARD_STATUS, qos=1)
    bridge.connect()
    bridge.inbox.get_nowait()  # drain the retained online status
    broker.kill_client("node")
    msg = bridge.inbox.get_nowait()
    assert msg.topic == "building/classroom_B/status"
    assert msg.payload == OFFLINE_PAYLOAD.encode()
    assert broker.retained["building/classroom_B/status"][0] == OFFLINE_PAYLOAD.encode()
    assert node.disconnects and node.disconnects[-1].is_failure is True


def test_resubscribe_after_reconnect_renews_subscriptions():
    broker = FakeBroker()
    node, bridge = make_pair(broker)
    bridge.subscribe(topics.WILDCARD_TELEMETRY, qos=0)
    bridge.connect()
    node.connect()
    broker.kill_client("bridge")
    assert not any(c is bridge._client for c, _, _ in broker._subs)
    bridge.connect()  # reconnect re-fires on_connect, renewing subscriptions
    assert any(f == topics.WILDCARD_TELEMETRY for c, f, _ in broker._subs if c is bridge._client)
    node.publish(topics.telemetry_topic("office"), '{"T_in_C": 25.0}', qos=0)
    assert bridge.inbox.get_nowait().topic == "building/office/telemetry"


def test_on_message_with_full_queue_drops_and_counts_never_blocks():
    broker = FakeBroker()
    _, bridge = make_pair(broker, queue_maxsize=1)
    bridge.inbox.put_nowait("saturated")
    for _ in range(3):
        bridge._on_message(None, None, "overflow")  # must return immediately, never block
    assert bridge.dropped == 3
    assert bridge.inbox.get_nowait() == "saturated"
    with __import__("pytest").raises(queue.Empty):
        bridge.inbox.get_nowait()


def test_topic_wildcard_matching():
    assert topic_matches("building/+/telemetry", "building/lab/telemetry")
    assert not topic_matches("building/+/telemetry", "building/lab/command/hvac")
    assert topic_matches("building/lab/command/#", "building/lab/command/hvac")
    assert topic_matches("building/#", "building/lab/command/hvac")
