# Phase 2: MQTT Pipeline + IoT Contract - Context

**Gathered:** 2026-09-29
**Status:** Ready for planning

## Phase Boundary

Virtual ESP32 telemetry and AC/light commands move between the simulator and a controller policy over MQTT through one shared topic contract, surviving reconnects and node failures. No real ML, no real controllers yet — Phase 3 plugs C1–C3 into the `BasePolicy` side of this pipeline. No dashboard (Phase 6).

## Implementation Decisions

[--auto] Selected all gray areas: Topic contract, Client library, Broker strategy, ESP32 virtualization, QoS/reliability, Fault tolerance.

### Topic contract
- **D-01:** Single source of truth `iot/topics.py`: `building/{room}/{telemetry|command/hvac|command/light|status}` with helpers `telemetry_topic(room)`, `command_topic(room, device)`, `status_topic(room)`
- **D-02:** [auto] Topic shape — Q: "Flat or hierarchical?" → Selected: "Hierarchical `building/{room}/...`" (recommended default)
- **D-03:** Telemetry payload = JSON matching Phase-1 CSV columns (timestamp, T_in_C, T_out_C, RH_pct, occupancy, HVAC_state, power_kW, light_on); command payload = `{"hvac": "OFF|REDUCED|ON", "light": 0|1}`

### Client library & broker
- **D-04:** paho-mqtt 2.1.0 with `CallbackAPIVersion.VERSION2` pinned in requirements.txt; MQTT v3.1.1 default
- **D-05:** [auto] Broker — Q: "Local Mosquitto or public?" → Selected: "Local Mosquitto 2.0.22, `mosquitto.conf` checked in (listener 1883, anonymous for lab), public broker only as documented fallback" (recommended default)
- **D-06:** Machine has no broker and no paho-mqtt installed — tests MUST run brokerless via an in-process fake; real-broker path verified by a marked integration test skipped when broker absent

### ESP32 virtualization
- **D-07:** Python `Esp32Node` shim per room (publishes telemetry from `BuildingSim` obs, subscribes commands, applies to sim action) — physics stays in Python, virtual node is a thin shim
- **D-08:** Arduino sketch `iot/esp32_node.ino` (PubSubClient + DHT stub) checked in for the Wokwi demo path, kept in sync with `topics.py` by a contract test; Wokwi run itself is manual, not in CI
- **D-09:** [auto] Wokwi wiring — Q: "Wokwi in CI?" → Selected: "No — sketch checked in + contract test, Wokwi run is manual demo" (recommended default)

### QoS & reliability
- **D-10:** Telemetry QoS 0, commands QoS 1, `status` retained + LWT (`{"state":"offline"}`) per node; commands never retained
- **D-11:** Bridge reconnects with exponential backoff, resubscribes on reconnect; resubscribe covered by test with fake broker kill
- **D-12:** [auto] Forecasts over MQTT? — Q: "Forecasts on the bus?" → Selected: "No — forecasts are in-process function calls (Phase 4), never MQTT messages" (recommended default)

### Fault tolerance
- **D-13:** Kill-a-node test: stopping one room's node keeps other rooms flowing; packet-drop test: dropped telemetry never crashes bridge, gap visible in log
- **D-14:** [auto] Acceptance — Q: "What proves robustness?" → Selected: "QoS1 + reconnect + LWT + kill-a-node with numbers, not 'demo worked'" (recommended default)

### the agent's Discretion
- Exact reconnect backoff schedule, JSON float precision, fake-broker implementation shape
- mosquitto.conf TLS block commented for the Unit-3 security note

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope
- `.planning/PROJECT.md` — core value, constraints
- `.planning/REQUIREMENTS.md` — IOT-01..04 definitions
- `.planning/ROADMAP.md` Phase 2 — goal + 4 success criteria
- `smart_building_project_idea.md` — IoT pipeline layer, MQTT vs HTTP vs CoAP note
- `.planning/phases/01-simulator-evaluation-foundation/01-CONTEXT.md` — sim.step/policy.step interface this pipeline wraps

### Research
- `.planning/research/SUMMARY.md` — boring-first MQTT guidance
- `.planning/research/STACK.md` — Mosquitto 2.0.22, paho-mqtt 2.1.0 VERSION2, Wokwi Private Gateway note
- `.planning/research/ARCHITECTURE.md` — topic/QoS patterns, forecast-as-input (never over MQTT), build order
- `.planning/research/PITFALLS.md` — MQTT fragility on 24h runs, decoupled intake

## Existing Code Insights

### Reusable Assets
- `sim/simulator.py` BuildingSim `reset(seed)`/`step(action)` — bridge drives this loop
- `sim/policy.py` BasePolicy/AlwaysOffPolicy — command side plugs a policy in
- `sim/config.py` room list + PAIRED_SEEDS — topics derived from room list

### Established Patterns
- `np.random.default_rng(seed)` threading; byte-for-byte determinism for sim core (MQTT timing excluded from determinism claim)
- Single-Python monolith; bridge runs in-process against sim, not as a separate service

### Integration Points
- `iot/bridge.py` sits between `BuildingSim` and `BasePolicy`: obs→telemetry pub, command sub→action
- `iot/topics.py` imported by bridge, node shim, and sketch-contract test — the one contract all 4 members build against

## Specific Ideas

No specific requirements — open to standard approaches. Keep the node thin and the contract frozen early.

## Deferred Ideas

None — discussion stayed within phase scope. Controllers (Phase 3), forecaster (Phase 4), dashboard (Phase 6) untouched.

---

*Phase: 2-MQTT Pipeline + IoT Contract*
*Context gathered: 2026-09-29*
