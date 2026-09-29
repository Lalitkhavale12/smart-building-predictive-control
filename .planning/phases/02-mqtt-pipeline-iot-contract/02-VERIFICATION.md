# Phase 02: MQTT Pipeline + IoT Contract — Verification Report

**Phase goal:** Users can move telemetry and commands between virtual sensors and the controller over MQTT without collapse.
**Verified:** 2026-09-29
**Overall verdict:** PASS (4/4 criteria)

## Criterion verdicts

| # | Criterion (ROADMAP Phase 2) | Verdict | Evidence |
|---|---|---|---|
| 1 | Per-room telemetry arrives from virtual ESP32 over `building/{room}/{telemetry\|command\|status}` topics (IOT-01) | PASS | `iot/topics.py` helpers (`telemetry_topic`/`command_topic`/`status_topic` + wildcards) — read, no paho dep; `iot/node.py:publish_telemetry` QoS 0, CSV-column-ordered JSON — read; `tests/test_topics.py` 5 passed + `test_telemetry_roundtrip_obs_to_bridge_last_good` passed; smoke: 240 msgs received over 60 steps, 0 gaps |
| 2 | AC/light command sent back over MQTT moves the room + survives broker reconnects (IOT-02) | PASS | `iot/bridge.py:_publish_action` QoS 1 never-retained + `tick()` → `sim.step` — read; `iot/node.py:poll_commands` merges hvac/light — read; `test_command_roundtrip_policy_to_node_receipt_and_sim_step`, `test_resubscribe_after_reconnect_renews_subscriptions`, `test_backoff_window_and_command_idempotency` passed; smoke: bridge-published `{"hvac":"ON"}` picked up by node (`after ON: {'hvac':'ON','light':0}`); reconnect resubscribe covered by wrapper `_on_connect` path + fault test |
| 3 | Local Mosquitto path (`mosquitto.conf`) + one shared `topics.py` contract (IOT-03) | PASS | `mosquitto.conf` (listener 1883, anonymous lab, commented TLS block) — read; `iot/esp32_node.ino` checked in; `test_topic_literals_match_topics_helpers`, `test_buffer_512_and_payload_fits`, `test_commands_never_retained_repo_wide`, `test_no_forecast_topics_under_iot` all passed; `requirements.txt` pins `paho-mqtt==2.1.0`, wrapper uses `CallbackAPIVersion.VERSION2` (test with sys.modules stub passed) |
| 4 | Kill-a-node / packet-drop keeps pipeline running (IOT-04) | PASS | `tests/test_faults.py` 3/3 passed: kill-a-node (3 survivors × 3 cycles, offline retained status, `sim.minute==3`), seeded 10% drop × 200 msgs (zero exceptions, exact gap count), resubscribe-after-kill (subs renewed, flow resumes); bridge `_drain` counts gaps, never crashes (corrupt → hold last-good, tested) |

## Commands run

1. `python -m pytest tests/ -q` → **51 passed, 2 skipped in ~12 s** (skips = `tests/test_integration_mqtt.py`, no broker on this machine — by design per D-06).
2. `python -m pytest tests/test_faults.py tests/test_sketch_contract.py tests/test_bridge.py tests/test_mqtt_client.py tests/test_topics.py -v` → **24 passed** (all Phase-2 tests enumerated green).
3. Live smoke (FakeBroker + BuildingSim + AlwaysOffPolicy, 60 steps, 4 rooms): `minute: 60, received: 240, gaps: 0`; node default `{'hvac':'OFF','light':0}`; after bridge-published ON command → `{'hvac':'ON','light':0}` → **SMOKE OK** (telemetry flow + command roundtrip confirmed).
   - Note: smoke used `BuildingSim()` + `reset(seed=7)` and `AlwaysOffPolicy()` (no ctor args) — SUMMARY's shorthand constructor spellings differ, implementation signatures govern.

## Issues

None blocking. Minor notes (non-blocking):
- `python` on this machine is 3.14 (stack pins 3.12 for TF in Phase 4); Phase-2 code is unaffected (sim emits a RuntimeWarning only). No action.
- Integration tests skip without a local broker — expected per D-06; real-broker path unverified on this machine but the marked skip is the designed behavior, not a gap.
- Wokwi run is manual demo per D-09 (sketch + contract test only in CI) — accepted by context decision, not a gap.

## Requirements coverage

IOT-01 ✓ (criterion 1), IOT-02 ✓ (criterion 2), IOT-03 ✓ (criterion 3), IOT-04 ✓ (criterion 4). No orphaned requirements.
