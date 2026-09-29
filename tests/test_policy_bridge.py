"""C-policy behind the MQTT bridge: compatibility assertion, not the eval path.

Drives C2 (the stateful policy — most interface surface) through
TelemetryBridge.tick() with the Phase-2 FakeBroker double for 30 sim-minutes.
Never runs the matrix through the bridge (D-08).
"""

import json

import numpy as np

from ctrl.baselines import OccupancyRulePolicy
from iot import topics
from iot.bridge import TelemetryBridge
from iot.node import Esp32Node
from sim import config as cfg
from sim.simulator import BuildingSim
from tests.fakes import FakeBroker, FakeClient


def make_factory(broker):
    return lambda client_id: FakeClient(client_id, broker)


def test_c2_policy_behind_bridge_30min():
    broker = FakeBroker()
    factory = make_factory(broker)
    sim = BuildingSim(rng=np.random.default_rng(0), scenario="weekday")
    obs = sim.reset(seed=0)
    nodes = {room: Esp32Node(room, client_factory=factory) for room in cfg.ROOMS}
    bridge = TelemetryBridge(sim, OccupancyRulePolicy(), client_factory=factory)
    for node in nodes.values():
        node.connect()
    bridge.connect()

    for _ in range(30):
        for room, node in nodes.items():
            last = bridge.last_action.get(room, {"hvac": "OFF", "light": 0})
            node.publish_telemetry(obs[room], hvac_state=last["hvac"],
                                   light_on=last["light"], step=sim.minute)
        action, obs = bridge.tick()  # must not raise; advances sim by 1 min

    assert sim.minute == 30
    for topic, payload, qos, _ in broker.published:
        if "/command/" not in topic:
            continue
        data = json.loads(bytes(payload).decode())
        if topic.endswith("/hvac"):
            assert data["hvac"] in topics.VALID_HVAC
        else:
            assert data["light"] in topics.VALID_LIGHT
    assert any("/command/" in topic for topic, *_ in broker.published)
