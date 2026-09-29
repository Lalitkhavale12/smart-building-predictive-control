"""Testable MQTT client wrapper (Phase 2, D-04/D-06).

The ONLY module that references paho — imported lazily inside the default
factory so the unit suite collects with paho-mqtt not installed. Bridge and
node shims talk to :class:`MqttClientWrapper`, never to paho directly.

Conventions: MQTT v3.1.1 default (never opt into v5); ``on_message`` only
enqueues into a stdlib queue — control logic never runs in the callback.
"""

import queue

ONLINE_PAYLOAD = '{"state":"online"}'
OFFLINE_PAYLOAD = '{"state":"offline"}'


def default_client_factory(client_id):
    """Real-client factory: lazy paho import, VERSION2 first positional arg."""
    import paho.mqtt.client as mqtt  # lazy: unit tests run without paho installed

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    return client


class MqttClientWrapper:
    """Six-method surface: connect, disconnect, publish, subscribe, set_will, start_loop."""

    def __init__(self, client_id, client_factory=None, queue_maxsize=1000):
        factory = client_factory or default_client_factory
        self.client_id = client_id
        self._client = factory(client_id)
        # Recorded by subscribe(), effected ONLY inside _on_connect so every
        # reconnect renews subscriptions (D-11). Callers subscribe before connect().
        self._subscriptions = []
        self.inbox = queue.Queue(maxsize=queue_maxsize)
        self.dropped = 0
        self.disconnects = []
        self._status_topic = None
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def set_will(self, topic, payload, qos=1, retain=True):
        """LWT registration — must precede connect(); wills never fire on clean disconnect."""
        self._status_topic = topic
        if hasattr(self._client, "will_set"):  # real paho spells it will_set
            self._client.will_set(topic, payload, qos=qos, retain=retain)
        else:  # test double mirrors the wrapper's own verb
            self._client.set_will(topic, payload, qos=qos, retain=retain)

    def connect(self, host="localhost", port=1883, keepalive=60):
        return self._client.connect(host, port, keepalive)

    def disconnect(self):
        return self._client.disconnect()

    def publish(self, topic, payload, qos=0, retain=False):
        # Commands use QoS 1 at-least-once; duplicates are harmless because
        # setpoints are absolute (OFF|REDUCED|ON, 0|1), never toggles/deltas.
        return self._client.publish(topic, payload, qos=qos, retain=retain)

    def subscribe(self, topic_filter, qos=0):
        self._subscriptions.append((topic_filter, qos))
        return None

    def start_loop(self):
        if hasattr(self._client, "loop_start"):  # real paho: background thread + auto-reconnect
            return self._client.loop_start()
        return self._client.start_loop()

    # -- CallbackAPIVersion.VERSION2 signatures (VERSION1 rc/flags forms forbidden) --

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties):
        _ = connect_flags.session_present  # attribute access, never flags["session present"]
        if reason_code.is_failure:  # ReasonCode flag, never `rc == 0` int equality
            return
        for topic_filter, qos in self._subscriptions:
            client.subscribe(topic_filter, qos=qos)
        if self._status_topic is not None:
            client.publish(self._status_topic, ONLINE_PAYLOAD, qos=1, retain=True)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        self.disconnects.append(reason_code)

    def _on_message(self, client, userdata, msg):
        try:
            self.inbox.put_nowait(msg)
        except queue.Full:
            self.dropped += 1  # full intake drops plus counts, never blocks the loop thread
