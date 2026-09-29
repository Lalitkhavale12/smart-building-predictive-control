"""Fault-tolerance tests (Phase 2 plan 02, D-11/D-13/D-14, T-02-07/T-02-08).

Numbers not adjectives: room counts, gap counts, subscription-set membership.
Brokerless — FakeBroker kill/drop hooks only; no new source files.
"""

import numpy as np

from iot import topics
from iot.bridge import TelemetryBridge
from iot.mqtt_client import OFFLINE_PAYLOAD
from iot.node import Esp32Node
from sim import config as cfg
from sim.policy import AlwaysOffPolicy
from sim.simulator import BuildingSim
from tests.fakes import FakeBroker, FakeClient

ROOMS = list(cfg.ROOMS)
assert len(ROOMS) == 4


def make_factory(broker):
    return lambda client_id: FakeClient(client_id, broker)


def make_fleet(broker, seed=0):
    sim = BuildingSim(rng=np.random.default_rng(seed))
    obs = sim.reset(seed=seed)
    nodes = {room: Esp32Node(room, client_factory=make_factory(broker)) for room in ROOMS}
    bridge = TelemetryBridge(sim, AlwaysOffPolicy(), client_factory=make_factory(broker))
    for node in nodes.values():
        node.connect()
    bridge.connect()
    # Drain retained online statuses so later inbox reads are exactly the test's.
    while not bridge.wrapper.inbox.empty():
        bridge.wrapper.inbox.get_nowait()
    return sim, obs, nodes, bridge


def cycle(sim, obs, nodes, bridge, step, rooms):
    """One telemetry-to-command cycle for the given rooms; returns actions."""
    for room in rooms:
        nodes[room].publish_telemetry(obs[room], step=step)
    action, obs = bridge.tick()
    for room in rooms:
        assert nodes[room].poll_commands() == action[room]
    return action, obs


def test_kill_a_node_survivors_keep_flowing_with_offline_status():
    broker = FakeBroker()
    sim, obs, nodes, bridge = make_fleet(broker)
    dead = ROOMS[1]
    broker.kill_client(nodes[dead].wrapper.client_id)  # unexpected death: LWT fires
    survivors = [r for r in ROOMS if r != dead]
    for step in range(3):  # three full cycles post-kill, zero exceptions
        _, obs = cycle(sim, obs, nodes, bridge, step, survivors)
    assert len(survivors) == 3
    assert broker.retained[topics.status_topic(dead)][0] == OFFLINE_PAYLOAD.encode()
    assert sim.minute == 3  # loop never stalled


def test_seeded_packet_drop_survives_with_counted_gaps():
    broker = FakeBroker(drop_rate=0.1, seed=7)
    sim = BuildingSim(rng=np.random.default_rng(11))
    obs = sim.reset(seed=11)
    node = Esp32Node(ROOMS[0], client_factory=make_factory(broker))
    bridge = TelemetryBridge(sim, AlwaysOffPolicy(), client_factory=make_factory(broker))
    node.connect()
    bridge.connect()
    while not bridge.wrapper.inbox.empty():
        bridge.wrapper.inbox.get_nowait()
    sent = 200
    for step in range(sent):
        node.publish_telemetry(obs[ROOMS[0]], step=step)
    bridge._drain()  # must not raise on any drop pattern
    received = bridge.received_count
    dropped = sent - received
    assert received > 0 and dropped > 0  # seeded drop actually dropped something
    # Interior-gap accounting is exact: span(first..last) - received == gaps.
    span_minutes = round(
        (bridge.last_ts[ROOMS[0]] - bridge.first_ts[ROOMS[0]]).total_seconds() / 60.0
    ) + 1
    assert bridge.gap_count == span_minutes - received  # exact interior-gap match
    assert 0 <= dropped - bridge.gap_count <= 4  # only edge drops escape counting


def test_resubscribe_after_kill_renews_subscription_set():
    broker = FakeBroker()
    sim, obs, nodes, bridge = make_fleet(broker)
    broker.kill_client("bridge")
    assert not any(c is bridge.wrapper._client for c, _, _ in broker._subs)
    assert bridge.wrapper.disconnects and bridge.wrapper.disconnects[-1].is_failure
    bridge.connect()  # reconnect re-fires on_connect, renewing subscriptions
    filters = {f for c, f, _ in broker._subs if c is bridge.wrapper._client}
    assert topics.WILDCARD_TELEMETRY in filters
    assert topics.WILDCARD_STATUS in filters
    room = ROOMS[0]
    nodes[room].publish_telemetry(obs[room], step=0)
    assert bridge._drain() == {room}  # flow resumes post-resubscribe
