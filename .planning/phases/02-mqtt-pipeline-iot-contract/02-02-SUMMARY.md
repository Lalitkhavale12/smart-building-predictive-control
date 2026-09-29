# Phase 02 Plan 02: Node Shim + Bridge Loop + Sketch + Faults Summary

---
phase: 02-mqtt-pipeline-iot-contract
plan: "02"
subsystem: iot-pipeline
tags: [mqtt, bridge, esp32, fault-tolerance, contract-test]
requires: [phase-01-sim-core, plan-01-iot-contract]
provides: [esp32-node-shim, telemetry-bridge, firmware-sketch, fault-proofs]
affects: [phase-03-controllers]
tech-stack:
  added: []
  patterns: [thin-node-shim, last-good-hold, timestamp-gap-counting, sketch-contract-test]
key-files:
  created: [iot/node.py, iot/bridge.py, iot/esp32_node.ino, tests/test_bridge.py, tests/test_sketch_contract.py, tests/test_faults.py]
  modified: []
decisions:
  - bridge publishes two per-device command messages (hvac + light JSON) QoS1 never-retained; node merges both plus combined payloads
  - sequence gaps detected via sim-time timestamp deltas per room (schema has no seq field); edge drops bounded by tolerance
  - bridge tick steps the sim itself with held setpoints for rooms lacking fresh valid telemetry
status: complete
actuals:
  tasks: 3
  commits: 3
  plan_head_before: ad2746b
---

## One-liner

Brokerless MQTT vertical slice proven: sim obs → telemetry → AlwaysOffPolicy → QoS-1 commands → sim step, with sketch pinned to `topics.py` and kill/drop/resubscribe faults green — 11 new tests, full suite 51 passed.

## What Was Built

**Task 1 (tracer) — `iot/node.py` + `iot/bridge.py` + `tests/test_bridge.py` (commit `6a58814`):**
`Esp32Node(room, factory)` owns one wrapper, registers the retained offline LWT before connect, subscribes its room command wildcard, publishes `TELEMETRY_COLUMNS`-ordered JSON (sim-time stamp from `sim_timestamp(step)`, room in topic and payload, floats rounded to 4 decimals) at QoS 0, and merges per-device/combined command payloads into `last_command` via non-blocking `poll_commands()`.
`TelemetryBridge(sim, policy, factory)` owns one wrapper, subscribes telemetry+status wildcards (renewed every reconnect via the wrapper path), validates inbound ranges (T_in −10…60 °C, RH 0…100, occupancy non-negative int) holding last-good and counting a gap on corrupt input, detects sequence gaps per room via sim-time deltas, publishes absolute-setpoint commands QoS 1 never-retained (idempotent duplicates), and exposes `tick()` = drain → `BasePolicy.step` → publish fresh-room commands → `BuildingSim.step` with held setpoints for stale rooms. 4 tests: key-order/precision roundtrip, AlwaysOff command roundtrip driving `sim.minute`, 5-way corrupt rejection holding last-good, backoff-window + QoS-1 idempotency.

**Task 2 — `iot/esp32_node.ino` + `tests/test_sketch_contract.py` (commit `33e1eaf`):**
Sketch parameterized by `ROOM_ID` with full topic literals, Wokwi-GUEST/channel-6 Wi-Fi, `host.wokwi.internal` Private Gateway host plus LAN-broker/`test.mosquitto.org` fallback comment, `setBufferSize(512)`, telemetry QoS 0 note, command-wildcard subscribe QoS 1, retained online publish + offline LWT in the `connect(id,user,pass,willTopic,willQos,willRetain,willMsg)` overload, DHT stub comment; no forecast string anywhere. 4 contract tests: literal-vs-helper equality for the sketch ROOM_ID, 512 B buffer + sample payload fits, repo-wide commands-never-retained (code lines only), no-forecast under `iot/`.

**Task 3 — `tests/test_faults.py` (commit `bf8f8b0`):**
3 numeric fault tests over `FakeBroker` + as-built node/bridge: kill-a-node (4-room fleet, kill room 2 → 3 survivors × 3 cycles green, retained status reads offline, `sim.minute == 3`); seeded 10 % drop × 200 msgs (zero exceptions, `gap_count == span − received` exactly, edge-drop slack ≤ 4); resubscribe-after-kill (bridge subs vanish on kill, failing disconnect recorded, reconnect renews both wildcards, flow resumes). Required a one-line bridge addition (`first_ts` per room for the interior-gap span).

## Verification Results

- `pytest tests/test_bridge.py -q` → **4 passed**
- `pytest tests/test_sketch_contract.py -q` → **4 passed**
- `pytest tests/test_faults.py -q` → **3 passed**
- `pytest tests/ -q -m "not integration"` → **51 passed, 2 deselected in ~10 s** (Phase-1 suite intact, under 60 s)
- `pytest tests/test_integration_mqtt.py -q` → **2 skipped** (no broker, as designed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Contract test matched its own comment line**
- **Found during:** Task 2 verify (`test_commands_never_retained_repo_wide` failed on `tests/test_sketch_contract.py:48`)
- **Issue:** The retain-scan regex hit the test's own explanatory comment containing "retain=True" + "command".
- **Fix:** Excluded `#`-comment lines from the scan; implementation untouched.
- **Files modified:** tests/test_sketch_contract.py
- **Commit:** `33e1eaf` (folded before commit)

**2. [Rule 3 - Blocking] Drop test needed first-timestamp span from the bridge**
- **Found during:** Task 3 (exact interior-gap assertion needs first..last span, bridge only kept last)
- **Issue:** Without `first_ts`, the test could not compute `span − received` exactly.
- **Fix:** One-line `first_ts.setdefault(room, ts)` in `bridge._drain`; no behavior change to existing paths.
- **Files modified:** iot/bridge.py
- **Commit:** `6a58814` (bridge committed once, with the tracer task)

Otherwise: none — plan executed as written. No Rule 4 architectural questions arose.

## Known Stubs

None. Node/bridge/sketch paths are all wired and asserted; the DHT read and Wokwi run are explicitly manual-demo (D-09), not stubs. No TODO/FIXME/placeholder strings in new files.

## Threat Flags

None beyond the plan's register: T-02-05 mitigated (range validation + last-good hold + test), T-02-06 mitigated (repo-wide retain test green), T-02-07/T-02-08 mitigated (kill/drop tests with numeric assertions), T-02-09 accepted (Wokwi-GUEST + local host only, nothing secret committed).

## Self-Check: PASSED

- `iot/node.py`, `iot/bridge.py`, `iot/esp32_node.ino`, `tests/test_bridge.py`, `tests/test_sketch_contract.py`, `tests/test_faults.py` exist on disk
- Commits `6a58814`, `33e1eaf`, `bf8f8b0` present in `git log`
- Post-commit full suite re-ran: 51 passed, 2 deselected; integration 2 skipped
