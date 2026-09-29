# Phase 02 Plan 01: MQTT Topic Contract + Client Wrapper + Fake Broker Summary

---
phase: 02-mqtt-pipeline-iot-contract
plan: "01"
subsystem: iot-contract
tags: [mqtt, paho-mqtt, topic-contract, test-double, mosquitto]
requires: [phase-01-sim-core]
provides: [iot-topics-contract, mqtt-wrapper, fake-broker, broker-config]
affects: [plan-02-node-bridge-sketch]
tech-stack:
  added: [paho-mqtt==2.1.0]
  patterns: [lazy-dependency-import, injectable-client-factory, in-process-fake-broker]
key-files:
  created: [iot/__init__.py, iot/topics.py, iot/mqtt_client.py, tests/fakes.py, tests/test_topics.py, tests/test_mqtt_client.py, tests/test_integration_mqtt.py, mosquitto.conf]
  modified: [requirements.txt]
decisions:
  - topics.py imports Q_HVAC from sim.config so VALID_HVAC mirrors the sim by construction
  - wrapper subscribe() records only; real subscribe calls live solely in _on_connect (reconnect renewal)
  - FakeBroker drop applies to *-suffix /telemetry topics via seeded default_rng
status: complete
actuals:
  tasks: 3
  commits: 3
  plan_head_before: eebba80
---

## One-liner

Frozen `building/{room}/...` topic contract with a VERSION2-only paho wrapper and a brokerless FakeBroker suite — 13 unit tests green, integration pair skips without a broker.

## What Was Built

**Task 1 (tracer) — `iot/topics.py` + `tests/test_topics.py` (commit `db5bb8e`):**
`telemetry_topic` / `command_topic` (asserts `hvac|light`) / `status_topic` / `command_filter`
helpers, `WILDCARD_TELEMETRY`/`WILDCARD_STATUS` bridge constants, `VALID_HVAC`
derived from `sim.config.Q_HVAC` (mirrors by construction, never a copied literal)
plus `VALID_LIGHT = (0, 1)`. Stdlib + sim.config only — no paho, no numpy.
5 tests: sample-room literals, bad-device assert, all 4 ROOMS slash-free, value-set
mirror, wildcard literals. `pytest tests/test_topics.py -q` → 5 passed.

**Task 2 — `iot/mqtt_client.py` + `tests/fakes.py` + `tests/test_mqtt_client.py` (commit `954aa95`):**
`MqttClientWrapper` with exactly the six-method surface
(connect/disconnect/publish/subscribe/set_will/start_loop), injectable
`client_factory`, default factory importing paho lazily and constructing
`mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)` first-positional with
`reconnect_delay_set(min_delay=1, max_delay=30)`. `_on_connect` uses
`connect_flags.session_present` attribute access + `reason_code.is_failure`
(never int equality or flag subscripts), subscribes only inside `_on_connect`,
publishes retained `{"state":"online"}`; `_on_message` is `put_nowait` with
drop-plus-count on `queue.Full`. `set_will`/`start_loop` degrade across the
`will_set`/`loop_start` (real) vs `set_will`/`start_loop` (fake) spelling.
`FakeBroker`: `+`/`#` matching, retained store with replay, `kill_client`
(subs vanish + stored will fires + failing-reason disconnect), seeded
`drop_rate` on `/telemetry` via `np.random.default_rng`. `FakeClient` mirrors
the six methods; `connect()` fires `_on_connect` with a non-failing reason stub.
8 tests: VERSION2-first-positional (sys.modules paho stub — no real import),
telemetry roundtrip, command QoS1 + retain-unset (asserted against the broker
record), retained-status replay to a late subscriber, kill→offline-will
(inbox + retained store + failing disconnect), resubscribe-after-reconnect,
full-queue drop-and-count, wildcard matching. 13 passed with topics tests.

**Task 3 — `mosquitto.conf` + pin + `tests/test_integration_mqtt.py` (commit `ad2746b`):**
Four live lines (`listener 1883`, `allow_anonymous true`, `persistence false`,
`max_queued_messages 1000`) + installer/run header + commented TLS block for the
Unit-3 note. `paho-mqtt==2.1.0` appended preserving Phase-1 pins. Integration
file marked `integration`: 1 s TCP probe of localhost:1883 → `pytest.skip`
when absent (plus paho-missing skip), else telemetry + QoS-1 command roundtrips
through the real default factory. `pytest tests/test_integration_mqtt.py -q` →
2 skipped (no broker on this machine, as expected).

## Verification Results

- `pytest tests/test_topics.py tests/test_mqtt_client.py -q` → **13 passed**, paho-mqtt installed or not (suite never imports paho; only lazy factory reference in `iot/mqtt_client.py:19`)
- `pytest tests/test_integration_mqtt.py -q` → **2 skipped** (no broker on localhost:1883)
- `pytest tests/ -q` (full) → **40 passed, 2 skipped in ~12 s** — Phase-1 suite stays green
- `pip install paho-mqtt==2.1.0` smoke test → **SUCCESS** (pure-Python wheel, clean on Python 3.14.6)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test compared bytes topic against str record**
- **Found during:** Task 2 verify (`test_command_publish_qos1_never_retained` failed)
- **Issue:** Expected tuple used `b"building/..."` for the topic, but the broker records topics as str.
- **Fix:** One-line expectation fix to str topic; implementation untouched.
- **Files modified:** tests/test_mqtt_client.py
- **Commit:** `954aa95` (folded into the task commit before pushing)

Otherwise: none — plan executed as written. No Rule 4 architectural questions arose.

## Package Install Record (T-02-SC)

`pip install paho-mqtt==2.1.0` run 2026-09-29 on Python 3.14.6 → `Successfully
installed paho-mqtt-2.1.0` (67 kB pure-Python wheel, no build step). Package
Legitimacy Audit from 02-RESEARCH.md holds (Eclipse project, PyPI latest =
2.1.0). Install is recorded but not load-bearing: unit tests pass identically
with and without paho installed.

## Known Stubs

None. Every helper, wrapper method, and fake-broker behavior in this plan is
wired and asserted; no placeholder values, TODOs, or unwired data sources.

## Threat Flags

None beyond the plan's register: anonymous localhost listener is accepted per
T-02-01 (lab only, TLS block commented); no secrets in payloads or code; no
new network listeners in Python (wrapper is a client).

## Self-Check: PASSED

- `iot/topics.py`, `iot/mqtt_client.py`, `tests/fakes.py`, `mosquitto.conf` exist on disk
- Commits `db5bb8e`, `954aa95`, `ad2746b` present in `git log`
- Re-ran full suite post-commit: 40 passed, 2 skipped
