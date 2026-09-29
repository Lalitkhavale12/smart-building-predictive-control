"""Bridge/node roundtrip tests (Phase 2 plan 02). Brokerless via FakeBroker."""

import json

import pytest

from iot import topics
from iot.bridge import RECONNECT_MAX_DELAY, RECONNECT_MIN_DELAY, TelemetryBridge
from iot.node import Esp32Node
from sim import config as cfg
from sim.policy import AlwaysOffPolicy
from sim.simulator import BuildingSim
from tests.fakes import FakeBroker, FakeClient

ROOM = "classroom_A"


def make_factory(broker):
    return lambda client_id: FakeClient(client_id, broker)


def make_loop(broker, room=ROOM, seed=0):
    sim = BuildingSim(rng=__import__("numpy").random.default_rng(seed))
    sim.reset(seed=seed)
    node = Esp32Node(room, client_factory=make_factory(broker))
    bridge = TelemetryBridge(sim, AlwaysOffPolicy(), client_factory=make_factory(broker))
    node.connect()
    bridge.connect()
    return sim, node, bridge


def test_telemetry_roundtrip_obs_to_bridge_last_good():
    broker = FakeBroker()
    sim, node, bridge = make_loop(broker)
    obs = sim.reset(seed=1)
    payload = node.publish_telemetry(obs[ROOM], hvac_state="OFF", light_on=0, step=7)
    assert list(payload) == [
        "timestamp", "room", "T_in_C", "T_out_C", "RH_pct",
        "occupancy", "HVAC_state", "power_kW", "light_on",
    ]
    assert payload["room"] == ROOM
    fresh = bridge._drain()
    assert ROOM in fresh
    stored = bridge.last_good[ROOM]
    assert stored["T_in_C"] == pytest.approx(round(float(obs[ROOM]["T_in"]), 4))
    assert stored["occupancy"] == int(obs[ROOM]["occupancy"])
    # Floats at 4-decimal precision: wire form carries at most 4 decimals.
    for key in ("T_in_C", "T_out_C", "RH_pct", "power_kW"):
        assert stored[key] == round(stored[key], 4)


def test_command_roundtrip_policy_to_node_receipt_and_sim_step():
    broker = FakeBroker()
    sim, node, bridge = make_loop(broker)
    obs = sim.reset(seed=2)
    node.publish_telemetry(obs[ROOM], step=0)
    minute_before = sim.minute
    action, _ = bridge.tick()
    assert action[ROOM] == {"hvac": "OFF", "light": 0}  # AlwaysOffPolicy
    assert sim.minute == minute_before + 1  # action drove BuildingSim.step
    received = node.poll_commands()
    assert received == {"hvac": "OFF", "light": 0}
    # Command publishes are QoS 1 and never retained (D-10).
    cmd_pubs = [p for p in broker.published if "/command/" in p[0]]
    assert cmd_pubs, "expected command publishes on the broker record"
    assert all(qos == 1 and retain is False for _, _, qos, retain in cmd_pubs)


def test_corrupt_payload_rejected_holding_last_good():
    broker = FakeBroker()
    sim, node, bridge = make_loop(broker)
    obs = sim.reset(seed=3)
    node.publish_telemetry(obs[ROOM], step=0)
    bridge._drain()
    good = dict(bridge.last_good[ROOM])
    gaps_before = bridge.gap_count
    bad_payloads = [
        "not-json{{{",
        json.dumps({"room": ROOM, "T_in_C": -999.0, "RH_pct": 55.0, "occupancy": 2}),
        json.dumps({"room": ROOM, "T_in_C": 24.0, "RH_pct": 150.0, "occupancy": 2}),
        json.dumps({"room": ROOM, "T_in_C": 24.0, "RH_pct": 55.0, "occupancy": -1}),
        json.dumps({"room": ROOM, "T_in_C": 24.0, "RH_pct": 55.0, "occupancy": 1.5}),
    ]
    for bad in bad_payloads:
        broker.publish(topics.telemetry_topic(ROOM), bad, qos=0)
    bridge._drain()  # must not raise
    assert bridge.last_good[ROOM] == good  # held, never actuated on garbage
    assert bridge.gap_count == gaps_before + len(bad_payloads)


def test_backoff_window_and_command_idempotency():
    assert (RECONNECT_MIN_DELAY, RECONNECT_MAX_DELAY) == (1, 30)
    broker = FakeBroker()
    _, node, bridge = make_loop(broker)
    assert set(cfg.Q_HVAC) >= {"OFF", "REDUCED", "ON"}
    for _ in range(3):  # QoS-1 duplicates: absolute setpoints, harmless repeats
        broker.publish(
            topics.command_topic(ROOM, "hvac"), json.dumps({"hvac": "ON"}), qos=1
        )
    assert node.poll_commands()["hvac"] == "ON"
    assert bridge.last_action.get(ROOM, {"hvac": "OFF"})["hvac"] in ("OFF", "ON")
