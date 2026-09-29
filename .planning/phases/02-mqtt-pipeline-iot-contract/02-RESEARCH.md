# Phase 02: mqtt-pipeline-iot-contract — Research

**Researched:** 2026-09-29
**Domain:** MQTT telemetry/command pipeline (paho-mqtt 2.1.0 / Mosquitto / ESP32 PubSubClient), brokerless test design
**Confidence:** HIGH (paho API + Mosquitto + PubSubClient + Wokwi verified against official docs this session; fake-broker shape is project judgment)

## Goal

Move telemetry (`BuildingSim` obs → JSON) and commands (`BasePolicy` action → sim step) between thin virtual ESP32 nodes and the controller over MQTT through one frozen topic contract, surviving reconnects and single-node death — with **zero broker required for tests** (no Mosquitto, no paho-mqtt installed on this machine; Python 3.14.6).

## User Constraints (from 02-CONTEXT.md — planner MUST honor)

### Locked Decisions
- **D-01:** Single source of truth `iot/topics.py`: `building/{room}/{telemetry|command/hvac|command/light|status}` with helpers `telemetry_topic(room)`, `command_topic(room, device)`, `status_topic(room)`
- **D-03:** Telemetry payload = JSON matching Phase-1 CSV columns (timestamp, T_in_C, T_out_C, RH_pct, occupancy, HVAC_state, power_kW, light_on); command payload = `{"hvac": "OFF|REDUCED|ON", "light": 0|1}`
- **D-04:** paho-mqtt 2.1.0 with `CallbackAPIVersion.VERSION2` pinned in requirements.txt; MQTT v3.1.1 default
- **D-05:** Local Mosquitto 2.0.22, `mosquitto.conf` checked in (listener 1883, anonymous for lab); public broker only as documented fallback
- **D-06:** Tests MUST run brokerless via an in-process fake; real-broker path is a marked integration test skipped when broker absent
- **D-07:** Python `Esp32Node` shim per room (publishes telemetry from `BuildingSim` obs, subscribes commands, applies to sim action) — physics stays in Python, node is a thin shim
- **D-08:** Arduino sketch `iot/esp32_node.ino` (PubSubClient + DHT stub) checked in for the Wokwi demo path, kept in sync with `topics.py` by a contract test; Wokwi run itself is manual, not in CI
- **D-10:** Telemetry QoS 0, commands QoS 1, `status` retained + LWT (`{"state":"offline"}`) per node; commands never retained
- **D-11:** Bridge reconnects with exponential backoff, resubscribes on reconnect; resubscribe covered by test with fake broker kill
- **D-12:** Forecasts are in-process function calls (Phase 4), never MQTT messages
- **D-13:** Kill-a-node test (one room stops, others flow) + packet-drop test (dropped telemetry never crashes bridge, gap visible in log)

### Agent's Discretion
Exact reconnect backoff schedule, JSON float precision, fake-broker implementation shape, `mosquitto.conf` TLS block commented for the Unit-3 security note.

### Deferred Ideas (OUT OF SCOPE)
None — controllers (Phase 3), forecaster (Phase 4), dashboard (Phase 6) untouched.

## Phase Requirements

| ID | Description (from REQUIREMENTS.md) | Research Support |
|----|-------------------------------------|------------------|
| IOT-01 | Publish per-room telemetry from virtual ESP32 over MQTT with `building/{room}/{telemetry\|command\|status}` topics | Topic design + telemetry payload schema + `Esp32Node` shim pattern |
| IOT-02 | Send AC/light commands back over MQTT with QoS1 + reconnect + LWT | QoS table, `will_set`, `reconnect_delay_set`, resubscribe-in-`on_connect` pattern |
| IOT-03 | Run local Mosquitto with single `topics.py` contract shared by sim, bridge, firmware | `mosquitto.conf` minimal content, sketch-contract test design |
| IOT-04 | Demonstrate fault tolerance (kill-a-node, packet drop) without pipeline collapse | Fake-broker kill/drop harness + LWT-retained status design |

## Key Questions (all answered)

1. **Exact VERSION2 callback signatures?** Answered — `on_connect(client, userdata, ConnectFlags, ReasonCode, properties)`, `on_disconnect(client, userdata, DisconnectFlags, ReasonCode, properties)`, `on_publish` gains `(mid, reason_code, properties)`, `on_message` unchanged. [CITED: eclipse.dev/paho client docs]
2. **How to test MQTT logic with no broker installed?** Answered — injectable client wrapper + in-process `FakeBroker` (retained store, `+`/`#` matching, LWT-on-kill, seeded drop); real-broker test marked `integration` and skipped without a broker.
3. **LWT + retained status pattern?** Answered — `will_set(status_topic, '{"state":"offline"}', qos=1, retain=True)` before `connect()`; publish `{"state":"online"}` retained on every (re)connect.
4. **Minimal `mosquitto.conf` for Mosquitto 2.0.x?** Answered — `listener 1883` + `allow_anonymous true` + `persistence false` + commented TLS block (4 lines).
5. **ESP32 sketch buffer sizing?** Answered — PubSubClient default max packet is 256 B incl. header; call `setBufferSize(512)`; note PubSubClient can only *publish* QoS 0.
6. **Wokwi → localhost broker path?** Answered — Private Gateway (F1 → Enable Private Wokwi IoT Gateway, `host.wokwi.internal`); public gateway cannot reach localhost.

## Findings

### F-1: paho-mqtt 2.1.0 VERSION2 API (pinned, prescriptive)

`paho-mqtt==2.1.0` is the latest release on PyPI [VERIFIED: `pip index versions paho-mqtt` → 2.1.0 top of list, 2026-09-29]. Pure-Python wheel — no compiler needed on student laptops [ASSUMED: no native extensions in the published wheel; install smoke-test is a Wave-0 task].

Mandatory construction (VERSION1 is deprecated, removed in 3.0) [CITED: https://github.com/eclipse-paho/paho.mqtt.python/blob/master/docs/migrations.rst]:

```python
import paho.mqtt.client as mqtt

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # positional, FIRST arg — no other required args
# protocol defaults to MQTTv311 (v3.1.1) — keep it; do not opt into v5 [CITED: client docs, protocol param default]
# reconnect_on_failure defaults True — keep it
```

VERSION2 callback signatures to use (all verified against the official client module docs [CITED: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html]):

```python
def on_connect(client, userdata, connect_flags, reason_code, properties):
    # connect_flags: ConnectFlags(session_present: bool) — attribute access, NOT flags["session present"]
    # reason_code: ReasonCode — comparable to int AND by name; use .is_failure
    if reason_code.is_failure:
        return  # loop thread retries automatically; just log
    client.subscribe("building/+/telemetry", qos=0)   # resubscribe HERE — renews on every reconnect
    client.subscribe("building/+/status", qos=1)
    client.publish(status_topic(room), '{"state":"online"}', qos=1, retain=True)

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    # reason_code == 0  <=>  our own disconnect() call; anything else = unexpected drop (log it)
    ...

def on_message(client, userdata, msg):
    # UNCHANGED across API versions: msg.topic (str), msg.payload (bytes), msg.qos, msg.retain
    ...

def on_publish(client, userdata, mid, reason_code, properties):
    ...  # v2 adds reason_code+properties; only needed if tracking QoS1 command acks
```

Migration traps to avoid (the #1 source of copy-paste bugs — every tutorial shows the old form):
- **Old:** `def on_connect(client, userdata, flags, rc)` with `rc == 0` int check and `flags["session present"]`. **New:** `connect_flags.session_present` attribute, `reason_code` is a `ReasonCode` object [CITED: migrations.rst].
- `Client()` with no args now means VERSION1 — the deprecation warning fires at construction. Always pass `CallbackAPIVersion.VERSION2` explicitly.
- `on_subscribe` v2 signature is `(client, userdata, mid, reason_code_list, properties)` — `reason_code_list` replaces `granted_qos` [CITED: client docs].

Reconnect + LWT primitives:

```python
client.will_set(f"building/{room}/status", payload='{"state":"offline"}', qos=1, retain=True)
# MUST be called before connect(); wills are NOT sent on a clean disconnect() [CITED: will_set docs]
client.reconnect_delay_set(min_delay=1, max_delay=30)  # exponential backoff, resets on successful CONNACK [CITED: client docs]
client.connect("localhost", 1883, keepalive=60)
client.loop_start()   # background thread handles network + auto-reconnect; NEVER loop_forever in the bridge
# ...
client.disconnect(); client.loop_stop()  # disconnect BEFORE loop_stop so on_disconnect runs cleanly
```

**Prescription:** bridge owns ONE client, uses `loop_start()`, subscribes only inside `on_connect`, publishes commands with `publish(topic, payload, qos=1, retain=False)`. `on_message` does nothing but `queue.put()` — control logic never runs in the callback (PITFALLS Pitfall 7: a slow tick must never stall intake).

### F-2: Topic + payload contract (`iot/topics.py`)

```python
# iot/topics.py — single source of truth; bridge, node shim, AND sketch-contract test import this
def telemetry_topic(room): return f"building/{room}/telemetry"
def command_topic(room, device):  # device in ("hvac", "light")
    assert device in ("hvac", "light")
    return f"building/{room}/command/{device}"
def status_topic(room): return f"building/{room}/status"
```

- Room identity in BOTH topic and payload (`room` field) — matches Phase-1 `logger.py` `room` column [VERIFIED: sim/logger.py:21-24, `TELEMETRY_COLUMNS` read this session].
- Room names come from `sim/config.py::ROOMS` = `("classroom_A", "classroom_B", "office", "lab")` [VERIFIED: sim/config.py:14 read this session]; rooms contain underscores, never slashes — no wildcard-escape hazard.
- Wildcards: bridge subscribes `building/+/telemetry` and `building/+/status`; each node subscribes `building/{room}/command/#`.
- Telemetry JSON keys mirror `TELEMETRY_COLUMNS` order (`timestamp,room,T_in_C,T_out_C,RH_pct,occupancy,HVAC_state,power_kW,light_on`) with `timestamp` from `sim_timestamp(step)` (sim-time ISO-8601, never wall-clock) [VERIFIED: sim/logger.py:27-32]. Float precision: `%.4f` to match the CSV logger (agent's discretion — aligning with the logger kills float-diff bugs in bridge-vs-CSV comparisons).
- Command JSON: `{"hvac": "OFF|REDUCED|ON", "light": 0|1}` — values must be members of `sim/config.py::Q_HVAC` keys `("OFF","REDUCED","ON")` [VERIFIED: sim/config.py:43-44] and light in `(0,1)` per `BasePolicy.step` contract [VERIFIED: sim/policy.py:13-21].
- Bridge validates inbound telemetry ranges (`T_in` −10…60 °C, `RH` 0…100, `occupancy` ≥ 0 int); corrupt → log + hold last-good value, never crash, never actuate on garbage (PITFALLS security row).

### F-3: QoS / retained / LWT table (locked by D-10)

| Flow | Topic | QoS | Retained | Rationale |
|------|-------|-----|----------|-----------|
| Telemetry (node → bridge) | `building/{room}/telemetry` | 0 | No | 1-min cadence; a dropped sample is replaced 60 s later; QoS 1 doubles traffic for zero control value |
| Command (bridge → node) | `building/{room}/command/{hvac,light}` | 1 | **Never** | Infrequent + loss-intolerant; retained commands fire stale setpoints on reconnect (classic bug — ARCHITECTURE.md anti-pattern 3) |
| Status (node → all) | `building/{room}/status` | 1 | **Yes** | `{"state":"online"}` on (re)connect; LWT `{"state":"offline"}` on unexpected death — only retained topic in the system |

QoS 1 duplicates are possible (at-least-once) — commands are idempotent by construction (absolute `OFF|REDUCED|ON` + `0|1`, not toggles/deltas), so duplicates are harmless. This is the documented QoS-1 sweet-spot justification; keep the one-line comment in code.

### F-4: Fake-broker-for-tests design (D-06 — the load-bearing piece)

No broker and no paho-mqtt on this machine [VERIFIED: `python -c "import paho.mqtt.client"` → ModuleNotFoundError, 2026-09-29]. Therefore:

1. **Seam first:** `iot/mqtt_client.py` wraps the real client behind a 6-method interface (`connect, disconnect, publish, subscribe, set_will, start_loop`) with injectable `client_factory`. Bridge and `Esp32Node` talk ONLY to this wrapper — never `import paho` directly. `paho-mqtt==2.1.0` goes in `requirements.txt` but is imported lazily inside the default factory so the test suite collects without it installed.
2. **`tests/fakes.py::FakeBroker`** (in-process, ~80 lines, stdlib only):
   - `subscribe(client, topic_filter, qos)` / `publish(topic, payload, qos, retain)` with `+`/`#` matching (implement `topic_matches_sub` semantics: `+` = one level, `#` = rest).
   - Retained store: `dict[topic] = payload`; deliver retained messages to new subscribers immediately (this is what makes the status test meaningful).
   - `kill_client(client_id)`: drops the client WITHOUT calling its `disconnect()` — triggers registered LWT publish + fires `on_disconnect` with non-zero reason. This is the resubscribe test hook.
   - Seeded drop: `FakeBroker(drop_rate=0.1, rng=np.random.default_rng(seed))` silently discards telemetry publishes; bridge must expose a `dropped_gap_count` the test asserts on.
   - Synchronous dispatch (no threads) — deterministic, fast, debuggable.
3. **`FakeClient`** mimics the wrapper's 6 methods + `on_connect/on_message/on_disconnect` attributes; `connect()` fires `on_connect` with a stub `reason_code` exposing `.is_failure == False` (duck-type the two members we touch — never import paho in tests).
4. **Test list (all brokerless, < 5 s total):** topic-helper unit tests; telemetry roundtrip (node pub → bridge intake queue); command roundtrip (policy action → node received, QoS 1); resubscribe-after-kill (`kill_client` → `on_connect` re-fires → subscriptions renewed, assert via broker-side subscription set); kill-a-node (room B killed → rooms A/C/D still flow + B's retained status reads `offline`); packet-drop (10 % seeded drop over 200 msgs → zero exceptions, gap counter == dropped count ± delivery); retained-commands-never (assert no publish call in the codebase passes `retain=True` on a command topic — grep-test like Phase 1's no-scalar-EF test); sketch-contract test (regex-extract topic literals from `iot/esp32_node.ino`, assert they match `topics.py` output for a sample room); payload-validation test (T_in = −999 → rejected, last-good held).
5. **Real-broker gate:** `tests/test_integration_mqtt.py` marked `@pytest.mark.integration`, tries `socket.create_connection(("localhost", 1883), timeout=1)` and `pytest.skip()`s when absent; runs the identical roundtrip suite against the real client factory when a broker exists. Never in the default `pytest` run.

### F-5: `mosquitto.conf` minimal content (checked in at repo root or `iot/`)

```conf
# Local lab broker — Mosquitto 2.0.22 (https://mosquitto.org/files/binary/win64/).
# Run: mosquitto -c mosquitto.conf -v
listener 1883
allow_anonymous true
persistence false
max_queued_messages 1000
# --- Unit-3 security note (disabled for lab; enable for any LAN beyond localhost) ---
#listener 8883
#cafile C:/mosquitto/certs/ca.crt
#certfile C:/mosquitto/certs/server.crt
#keyfile C:/mosquitto/certs/server.key
#require_certificate false
```

Notes: Mosquitto ≥ 2.0 needs an explicit `listener` line for anything beyond localhost and explicit auth choice — `listener 1883` + `allow_anonymous true` is the documented local-lab combination [CITED: mosquitto.conf man page; community note "In Mosquitto 2.0 and up, you must choose your authentication options explicitly"]. `persistence false` is correct because CSV (never the broker) is the experiment record [CITED: project ARCHITECTURE.md state-management rule]. Anonymous + no-TLS is acceptable ONLY for localhost lab use — the commented TLS block plus one paragraph in the report is the Unit-3 security note (PITFALLS security row).

### F-6: ESP32 sketch notes (`iot/esp32_node.ino`, PubSubClient)

- WiFi: `WiFi.begin("Wokwi-GUEST", "", 6)` — open AP, channel 6 skips the ~4 s scan [CITED: docs.wokwi.com/guides/esp32-wifi].
- Buffer: PubSubClient default max packet is **256 bytes including header**, adjustable via `MQTT_MAX_PACKET_SIZE` or `client.setBufferSize(size)` [CITED: knolleary/pubsubclient README]. Telemetry JSON (~9 fields ≈ 180–200 B [ASSUMED: byte estimate from the D-03 schema, not measured]) fits but leaves no headroom — call `client.setBufferSize(512)` in `setup()` unconditionally. Cheap insurance, one line.
- QoS asymmetry that MUST shape the sketch: PubSubClient can only **publish** QoS 0 but can **subscribe** at QoS 0/1 [CITED: PubSubClient README forks]. So the node publishes telemetry QoS 0 (consistent with D-10) and subscribes `building/{ROOM_ID}/command/#` at QoS 1 — the broker still delivers commands with QoS 1 semantics broker→bridge side. Do not attempt QoS 1 publish from the sketch; the library cannot do it.
- LWT: `client.connect(clientId, nullptr, nullptr, statusTopic, 1, true, "{\"state\":\"offline\"}")` (willTopic, willQoS, willRetain, willMessage overload) + publish `online` retained after connect; standard `if (!client.connected()) reconnect()` with backoff in `loop()` + `client.loop()` every iteration [ASSUMED: exact overload arg order — verify against PubSubClient.h at implementation time; contract test only checks topic strings, not C++ API].
- One sketch parameterized by `#define ROOM_ID "..."` per room; DHT side is a stub (physics lives in Python per D-07 — the sketch is a demo-path artifact, kept honest by the contract test, never by CI execution).
- MQTT 3.1.1 default, keepalive 15 s default [CITED: PubSubClient README] — fine as-is.

### F-7: Wokwi Private Gateway note (localhost broker path)

- Browser Wokwi cannot reach `localhost` through the public gateway. For the local-Mosquitto demo: run the gateway binary, then F1 → "Enable Private Wokwi IoT Gateway" (`ws://localhost:9011`); from inside the simulation, the member laptop is `host.wokwi.internal`, so the sketch uses `client.setServer("host.wokwi.internal", 1883)` [CITED: docs.wokwi.com/guides/esp32-wifi + wokwi/wokwigw README].
- Fallbacks (contract unchanged, re-point one hostname): same-LAN member broker IP, or `test.mosquitto.org` [CITED: project STACK.md variant plan].
- Risk flag: current Wokwi docs note the Private Gateway is a paying-users feature [CITED: wokwi-docs esp32-wifi.md excerpt] — confirm access at Phase-2 start; if unavailable, the LAN-broker fallback is the primary demo path. Wokwi run stays manual (D-09); nothing Wokwi-shaped enters CI.

## Package Legitimacy Audit

| Package | Registry | Age | Source Repo | Verdict | Disposition |
|---------|----------|-----|-------------|---------|-------------|
| `paho-mqtt==2.1.0` | PyPI (latest = 2.1.0, confirmed via `pip index versions`) | 10+ yrs (Eclipse project) | github.com/eclipse-paho/paho.mqtt.python | OK | Approved — sole new dependency |

- No other new packages: JSON handling is stdlib `json`, buffering is stdlib `queue`, tests need only the already-installed `pytest 8.4.2` [VERIFIED: installed versions printed this session]. `numpy` (RNG for seeded drop) already required.
- No `postinstall` risk class applies (PyPI wheels for pure-Python packages run no install scripts; `pip install` failure mode on Python 3.14 is the only residual — Wave-0 task: `pip install paho-mqtt==2.1.0` smoke test; pure-Python makes breakage unlikely [ASSUMED]).
- Packages removed (SLOP): none. Flagged (SUS): none.

## Risks

| # | Risk | Likelihood | Impact | Mitigation (cheap, in-phase) |
|---|------|-----------|--------|------------------------------|
| R-1 | Tutorial copy-paste of VERSION1 signatures (`flags["session present"]`, int `rc`) breaks on 2.1.0 | HIGH | MEDIUM | Snippets F-1 are the normative reference; add a test asserting `CallbackAPIVersion.VERSION2` is passed at wrapper construction |
| R-2 | `paho-mqtt` fails to install on Python 3.14 | LOW | MEDIUM | Wave-0 smoke install; tests never import paho (lazy factory), so unit suite is immune regardless |
| R-3 | Retained-command staleness (reconnect replays yesterday's setpoint) | LOW (by design) | HIGH | D-10 bans retained commands + the grep-test enforces it; sketch publishes commands never |
| R-4 | Blocking work creeps into `on_message`, stalling intake on 4-room bursts | MEDIUM | MEDIUM | Wrapper enqueues only; add a test asserting `on_message` returns with a blocked consumer (queue full → drop + count, never block) |
| R-5 | Sketch/`topics.py` drift (`room1` vs `classroom_A`) | MEDIUM | MEDIUM | Contract test parses the `.ino` — drift fails CI, not the demo |
| R-6 | Private Gateway paywall blocks the localhost demo | MEDIUM | LOW | LAN-broker / `test.mosquitto.org` fallback re-points one hostname; demo is manual, never a gate |
| R-7 | PubSubClient 256 B truncation if telemetry schema grows | LOW | MEDIUM | `setBufferSize(512)` from day one; sketch-contract test asserts payload builds under 512 B |

## Open Questions

1. **Backoff schedule values** (agent's discretion): recommend `min_delay=1, max_delay=30` — matches `reconnect_delay_set` defaults shape, caps reconnect storms at 30 s without slowing lab iteration. No user input needed.
2. **Command QoS-1 ack tracking**: `on_publish` + `wait_for_publish()` available if Phase 3 wants delivery confirmation; Phase 2 fire-and-forget QoS 1 is sufficient. Defer.
3. **paho on 3.14**: one-command verification at plan start (`pip install paho-mqtt==2.1.0`); pure-Python ⇒ expected clean.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | paho-mqtt 2.1.0 wheel is pure-Python, installs cleanly on 3.14 | F-1 / Audit | LOW — Wave-0 smoke test; unit tests immune via lazy import |
| A2 | Telemetry JSON ≈ 180–200 B (fits 256 B, 512 B headroom justified) | F-6 | LOW — `setBufferSize(512)` covers 2.5× growth regardless |
| A3 | PubSubClient `connect()` LWT overload arg order as sketched | F-6 | LOW — sketch is manual-demo only; verify against PubSubClient.h during implementation |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ | 3.14.6 | — (3.12 pins are a team-venv concern, per Phase-1 precedent) |
| pytest / numpy / pandas | fake-broker tests (seeded drop) | ✓ | 8.4.2 / 2.4.3 / 3.0.1 | — |
| paho-mqtt | real-broker path only | ✗ (not installed) | 2.1.0 on PyPI | lazy import — unit tests never touch it |
| Mosquitto broker | integration test only | ✗ (no broker) | 2.0.22 installer URL in STACK.md | `FakeBroker` for all unit tests; integration test skips |

**Missing with no fallback:** none — D-06's brokerless rule is satisfiable as designed.

## Validation Architecture

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 (already installed) |
| Config file | none — see existing `tests/` layout (flat, `test_*.py`) |
| Quick run command | `pytest tests/ -q -m "not integration"` |
| Full suite command | `pytest tests/ -q` (integration skips without broker; Phase-1 suite must stay green < 60 s) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| IOT-01 | Telemetry pub per room on `building/{room}/telemetry` with CSV-matching JSON | unit (fake broker) | `pytest tests/test_topics.py tests/test_bridge.py -q` | ❌ Wave 0 |
| IOT-02 | Commands QoS 1 + reconnect resubscribe + LWT offline/online | unit (fake kill) | `pytest tests/test_bridge.py::test_resubscribe_after_kill -q` | ❌ Wave 0 |
| IOT-03 | `topics.py` contract shared; sketch in sync; mosquitto.conf checked in | unit (contract test) | `pytest tests/test_sketch_contract.py -q` | ❌ Wave 0 |
| IOT-04 | Kill-a-node isolation + packet-drop survival with gap counts | unit (fake kill/drop) | `pytest tests/test_faults.py -q` | ❌ Wave 0 |
| IOT-01..04 | Same flows against a real broker when present | integration | `pytest tests/test_integration_mqtt.py -q` (skips sans broker) | ❌ Wave 0 |

### Wave 0 Gaps
- [ ] `iot/topics.py` + `iot/mqtt_client.py` + `iot/node.py` + `iot/bridge.py` — implementation (not test gaps, planner's scope)
- [ ] `tests/fakes.py` — FakeBroker + FakeClient harness
- [ ] `tests/test_topics.py`, `tests/test_bridge.py`, `tests/test_faults.py`, `tests/test_sketch_contract.py`
- [ ] `iot/esp32_node.ino` + `mosquitto.conf` — checked-in artifacts the contract test pins
- [ ] Framework install: `pip install paho-mqtt==2.1.0` smoke test (real-path only; unit suite needs nothing new)

## Security Domain (ASVS L1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | Partial | Anonymous allowed ONLY on localhost lab broker; commented TLS block documents the production step (Unit-3 note) |
| V4 Access Control | No | Single-tenant lab; no ACLs in v1 (noted as future work in report) |
| V5 Input Validation | **Yes** | Range-check all inbound telemetry (T/RH/occupancy); corrupt → log + last-good hold; `--out`-style traversal N/A (no new file paths from network input) |
| V6 Cryptography | No (lab) | No hand-rolled crypto; TLS is config, not code |
| V9 Communications | Yes | Commands QoS 1 + never retained; LWT retained status only; no secrets in payloads or committed code |

Threat notes carried from Phase 1: no new network listeners in Python (bridge is a client, not a server); `run_meta`-style logging must never capture broker credentials (there are none in v1).

## Sources

### Primary (HIGH confidence)
- Eclipse paho-mqtt official client docs (client.py API reference — VERSION2 signatures, `will_set`, `reconnect_delay_set`, `loop_start`) — fetched full-text this session
- Eclipse paho-mqtt `docs/migrations.rst` (1.x→2.0 callback migration, `ConnectFlags.session_present`, `ReasonCode`) — via web search excerpts
- knolleary/pubsubclient README (256 B default, `setBufferSize`, MQTT 3.1.1, keepalive 15 s) + forks confirming publish-QoS0-only / subscribe-QoS0-or-1
- Wokwi ESP32-WiFi docs + wokwi/wokwigw README (Wokwi-GUEST + channel 6, Private Gateway F1 flow, `host.wokwi.internal`, public gateway can't reach localhost)
- Mosquitto `mosquitto.conf` man page (listener/allow_anonymous/persistence semantics; 2.0+ explicit-auth requirement)
- PyPI via `pip index` (paho-mqtt 2.1.0 current) + local `python --version` (3.14.6) + installed pytest/numpy/pandas versions

### Secondary (MEDIUM confidence)
- Project research corpus: SUMMARY.md / STACK.md / ARCHITECTURE.md / PITFALLS.md (Pitfall 7 MQTT fragility, QoS-1 99.2 %/~150 ms field figures)
- In-repo sources read this session: `sim/config.py` (ROOMS, Q_HVAC, comfort band), `sim/policy.py` (BasePolicy contract), `sim/logger.py` (TELEMETRY_COLUMNS, sim-time stamps)

### Tertiary (LOW confidence — see Assumptions Log)
- Telemetry byte-size estimate; PubSubClient LWT overload order; paho-on-3.14 install smoothness

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — paho 2.1.0 currency verified on PyPI; API from official docs fetched verbatim
- Architecture: HIGH — topic/QoS/LWT conventions converge across AWS IoT, mqtt-smarthome, and project ARCHITECTURE.md
- Pitfalls: HIGH — grounded in PITFALLS.md Pitfall 7 + integration-gotcha table
- Fake-broker design: MEDIUM — standard test-double pattern, but shape is project judgment (agent's discretion)

**Research date:** 2026-09-29
**Valid until:** 30 days (stable domain — MQTT 3.1.1 semantics and paho 2.x API move slowly)
