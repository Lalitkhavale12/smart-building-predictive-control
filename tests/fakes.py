"""In-process MQTT test double (Phase 2, D-06).

FakeBroker: +/# matching, retained store replayed to new subscribers,
kill_client (drops without clean disconnect, fires stored will + non-zero
disconnect), seeded drop_rate discarding telemetry publishes. Synchronous
dispatch — deterministic, no threads. stdlib + numpy only; never imports paho.
"""

import numpy as np


def topic_matches(topic_filter, topic):
    """`+` matches one level, `#` matches the rest (must be last)."""
    f_parts, t_parts = topic_filter.split("/"), topic.split("/")
    for i, part in enumerate(f_parts):
        if part == "#":
            return True
        if i >= len(t_parts):
            return False
        if part == "+":
            continue
        if part != t_parts[i]:
            return False
    return len(f_parts) == len(t_parts)


class FakeMessage:
    """Duck-types the paho message members the wrapper touches."""

    def __init__(self, topic, payload, qos=0, retain=False):
        self.topic = topic
        self.payload = payload.encode() if isinstance(payload, str) else bytes(payload)
        self.qos = qos
        self.retain = retain


class _StubReason:
    """Duck-types the ReasonCode members the wrapper touches (.is_failure)."""

    def __init__(self, is_failure):
        self.is_failure = is_failure


class _StubFlags:
    session_present = False


class FakeBroker:
    def __init__(self, drop_rate=0.0, seed=0):
        self.drop_rate = drop_rate
        self._rng = np.random.default_rng(seed)
        self._subs = []  # (client, filter, qos)
        self.retained = {}  # topic -> (payload bytes, qos)
        self.published = []  # (topic, payload bytes, qos, retain) — full record
        self._clients = {}  # client_id -> FakeClient

    def _register(self, client):
        self._clients[client.client_id] = client

    def subscribe(self, client, topic_filter, qos=0):
        self._subs = [(c, f, q) for c, f, q in self._subs if not (c is client and f == topic_filter)]
        self._subs.append((client, topic_filter, qos))
        for topic, (payload, r_qos) in self.retained.items():
            if topic_matches(topic_filter, topic):
                client._deliver(FakeMessage(topic, payload, min(r_qos, qos), True))

    def publish(self, topic, payload, qos=0, retain=False):
        payload = payload.encode() if isinstance(payload, str) else bytes(payload)
        self.published.append((topic, payload, qos, retain))
        if retain:
            if payload == b"":
                self.retained.pop(topic, None)
            else:
                self.retained[topic] = (payload, qos)
        if topic.endswith("/telemetry") and self._rng.random() < self.drop_rate:
            return  # seeded telemetry drop: bridge must gap-count, never crash
        for client, filt, _ in list(self._subs):
            if topic_matches(filt, topic):
                client._deliver(FakeMessage(topic, payload, qos, retain))

    def kill_client(self, client_id):
        """Unexpected death: subs vanish, stored will fires, non-zero disconnect."""
        client = self._clients.pop(client_id, None)
        if client is None:
            return
        self._subs = [(c, f, q) for c, f, q in self._subs if c is not client]
        if client._will is not None:
            w_topic, w_payload, w_qos, w_retain = client._will
            self.publish(w_topic, w_payload, qos=w_qos, retain=w_retain)
        if client.on_disconnect is not None:
            client.on_disconnect(client, None, _StubFlags(), _StubReason(True), None)


class FakeClient:
    """Mirrors the wrapper's six methods; connect() fires on_connect (non-failing)."""

    def __init__(self, client_id, broker):
        self.client_id = client_id
        self._broker = broker
        self.on_connect = None
        self.on_message = None
        self.on_disconnect = None
        self._will = None
        broker._register(self)

    def set_will(self, topic, payload, qos=1, retain=True):
        self._will = (topic, payload, qos, retain)

    def connect(self, host="localhost", port=1883, keepalive=60):
        if self.on_connect is not None:
            self.on_connect(self, None, _StubFlags(), _StubReason(False), None)

    def disconnect(self):
        broker = self._broker
        broker._subs = [(c, f, q) for c, f, q in broker._subs if c is not self]
        broker._clients.pop(self.client_id, None)
        if self.on_disconnect is not None:
            self.on_disconnect(self, None, _StubFlags(), _StubReason(False), None)

    def publish(self, topic, payload, qos=0, retain=False):
        self._broker.publish(topic, payload, qos=qos, retain=retain)

    def subscribe(self, topic_filter, qos=0):
        self._broker.subscribe(self, topic_filter, qos=qos)

    def start_loop(self):
        return None

    def _deliver(self, msg):
        if self.on_message is not None:
            self.on_message(self, None, msg)
