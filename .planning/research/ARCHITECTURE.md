# Architecture Research

**Domain:** IoT smart building simulation + predictive control (academic, simulation-only)
**Researched:** 2026-09-29
**Confidence:** HIGH (standard IoT layering + RC thermal simulation + MQTT telemetry/command conventions are well-established; MEDIUM on optimal Python module split, which is project judgment)

## Standard Architecture

### System Overview

Standard smart-building IoT systems use 4 layers (perception → network → middleware/processing → application), with a closed sense → decide → actuate loop. For this project the "physical building" is replaced by a deterministic simulator, and Wokwi ESP32 nodes are thin publishers/subscribers around it.

```
┌─────────────────────────────────────────────────────────────┐
│                    PERCEPTION (Sensing + Actuation)          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ Room ESP│  │ Room ESP│  │ Room ESP│  │ Room ESP│        │
│  │ 32 #1   │  │ 32 #2   │  │ 32 #3   │  │ 32 #N   │        │
│  │(Wokwi)  │  │(Wokwi)  │  │(Wokwi)  │  │(Wokwi)  │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │ publish    │ telemetry  │           │              │
│       │ subscribe  │ commands   │           │              │
├───────┴────────────┴────────────┴────────────┴──────────────┤
│                    TRANSPORT (MQTT broker)                   │
├─────────────────────────────────────────────────────────────┤
│  │              Mosquitto broker (single, local)            ││
│  │  building/room-<id>/telemetry  (device → cloud, QoS 0)  ││
│  │  building/room-<id>/command/*  (cloud → device, QoS 1)  ││
│  │  building/room-<id>/status     (LWT online/offline,     ││
│  │                                 retained)               ││
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│              PROCESSING (Python service = plant + brain)     │
│  ┌──────────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Building         │  │ Forecaster   │  │ Controller    │  │
│  │ simulator (plant)│→ │ (RF/GB +     │→ │ (5 policies:  │  │
│  │ RC thermal model │  │  LSTM)       │  │ fixed, rule,  │  │
│  │ + schedules +    │  │ 30–60 min    │  │ setback,      │  │
│  │ weather + noise  │  │ horizon      │  │ predictive)   │  │
│  └──────────────────┘  └──────────────┘  └───────────────┘  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Evaluation harness: scenarios × seeds × ablations, │    │
│  │  metrics (kWh, %, CO₂, ToU cost, comfort %), CSV    │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                    APPLICATION + STORAGE                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐   │
│  │ CSV/SQLite│  │ Thing-   │  │ Matplotlib graphs (report)│   │
│  │ log store │  │ Speak/   │  │ 24h profile, Pareto,      │   │
│  │ ( Pascal: │  │ Blynk    │  │ ablation, cumulative CO₂  │   │
│  │ ground    │  │ live     │  │                           │   │
│  │ truth)    │  │ dash     │  │                           │   │
│  └──────────┘  └──────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

Key structural decision: **the simulator is the plant, not the controller.** Everything else (ESP32, MQTT, forecaster, controller, dashboard) treats simulator output as if it were real sensor data, and simulator state advances only from controller commands + physics. This is the standard "emulator + controller" split used by Energym, PEPS/EnergyPlus+Python, and FastSim/MPC toolboxes — controller and plant communicate through a narrow, standardized signal interface (measurements in, setpoints out, per timestep).

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Building simulator (plant) | Owns ground truth: per-room indoor T/RH, HVAC power, occupancy; steps RC thermal model forward one timestep; injects weather, timetables, sensor noise, packet loss, sensor-failure faults | Python class `Simulator` with `step(action) -> observation`; 1R1C or 2R2C per room (repo `simulator/`); deterministic seeds; no ML, no MQTT inside — pure function of (state, action, disturbances) |
| Virtual ESP32 node (per room) | Thin edge shim: publishes telemetry JSON, subscribes to command topic, applies setpoint to "hardware" (i.e. forwards to simulator or lights LED in Wokwi demo) | Wokwi ESP32 + PubSubClient; one firmware template parameterized by room ID; publishes every 10–60 s simulated; QoS 0 telemetry, QoS 1 commands, LWT status |
| MQTT broker | Sole message bus; decouples sensing from processing; no business logic | Mosquitto, local, default port 1883; ACL per room subtree; no persistence needed (CSV is the store) |
| Telemetry/command topic tree | Contract between edge and cloud; enables per-room subscribe + fleet wildcard | `building/room-<id>/telemetry`, `building/room-<id>/command/hvac`, `building/room-<id>/command/light`, `building/room-<id>/status`; JSON payloads with `room_id`, `ts`, values |
| Forecaster | Predicts occupancy and demand 30–60 min ahead from history + time features; reports MAE/RMSE/R²; validated on synthetic + public dataset (UCI/ASHRAE) | scikit-learn RF/GB baseline + Keras/PyTorch LSTM; module `forecast/` with `train.py`, `predict.py`; horizon = N steps × dt; features: lagged T/RH/occupancy, hour-of-day, day-of-week |
| Controller | Maps (current observation + forecast + tariff + emission factor) → discrete action {ON, OFF, REDUCED} / setpoint per room; implements all 5 policies behind one interface | `control/policies.py` with `BasePolicy.step(obs, forecast, signals)`; predictive policy = pre-cool before predicted arrival, early-off before predicted departure, shed during high-carbon/price windows subject to comfort band |
| Signals (carbon + tariff) | Time-varying grid emission factor and ToU price series; inputs to controller cost function, not separate services | CSV series (`data/grid.csv`); constant-factor variant kept for ablation baseline |
| Store | Append-only log of every timestep: obs, forecast, action, energy, cost, CO₂, comfort flag; source for all metrics and graphs | CSV per run (`results/<scenario>/<seed>/<controller>.csv`) + SQLite optional; never query MQTT for history |
| Dashboard | Live view: current T/RH/occupancy/power per room, energy vs baseline, comfort %; screenshot is a deliverable | ThingSpeak (simplest: HTTP write from Python bridge) or Blynk; subscribes to telemetry + controller summary topics; read-only, never sends control directly |
| Evaluation harness | Runs scenarios × seeds × controllers × ablations, computes metrics, emits graphs + Pareto curve | `eval/run.py` + `eval/metrics.py` + `eval/plots.py`; multi-seed mean±std; ablation flags `--no-forecast`, `--no-carbon` |

## Recommended Project Structure

```
simulator/           # plant: ground truth physics
│   ├── building.py       # multi-room container, steps all zones
│   ├── thermal.py        # 1R1C/2R2C RC model (ISO 13790 style)
│   ├── occupancy.py      # timetables per scenario (weekday/weekend/heatwave/exam)
│   ├── weather.py        # outdoor T/RH + solar series generator
│   └── faults.py         # sensor noise, dropout, stuck-sensor injection
iot/                 # edge + transport contract
│   ├── esp32_firmware/   # single Wokwi template (room_id param)
│   ├── topics.py         # topic constants + payload schemas (single source of truth)
│   └── bridge.py         # MQTT ↔ simulator glue (sub telemetry, pub commands)
forecast/            # ML demand prediction
│   ├── features.py       # lag + calendar feature builder
│   ├── train.py          # RF/GB vs LSTM training + MAE/RMSE/R² report
│   ├── predict.py        # rolling-horizon inference API
│   └── validate_public.py# UCI/ASHRAE validation script
control/             # decision brain
│   ├── policies.py       # fixed, occupancy-rule, setback, predictive (+MPC stub)
│   ├── signals.py        # emission-factor + ToU tariff loader
│   └── comfort.py        # 22–26 °C / 30–60 % RH checker
eval/                # experiments + reporting
│   ├── run.py            # scenario × seed × controller × ablation runner
│   ├── metrics.py        # kWh, saved %, CO₂, cost, comfort %, robustness
│   └── plots.py          # 24h profile, savings bars, Pareto, ablation, cumulative CO₂
dashboard/           # application layer
│   └── thingspeak_push.py# bridge: summary → ThingSpeak/Blynk
data/                # inputs (never edited by code)
│   ├── weather/          # TMY-ish CSVs
│   ├── schedules/        # timetable CSVs per scenario
│   └── grid.csv          # emission factor + tariff series
results/             # outputs (git-ignored, per-run CSVs + PNGs)
config.py            # dt, horizon, comfort band, QoS, seeds (one place)
requirements.txt
```

### Structure Rationale

- **`simulator/` isolated with zero imports from `forecast/`, `control/`, `iot/`:** the plant must be swappable (synthetic → calibrated → public dataset replay) without touching the brain. Mirrors energym/FMU and PEPS `energyplus_simulator/` separation. This is the single most important boundary — violations (controller reaching into simulator internals) make baseline comparisons meaningless.
- **`iot/topics.py` as single source of truth:** topic strings and JSON schemas defined once, imported by firmware config, bridge, and dashboard. Prevents the #1 MQTT bug class: publisher/subscriber string drift (`room1` vs `room_1`, `temp` vs `temperature`).
- **`control/policies.py` behind one `step()` interface:** all 5 controllers comparable because they consume identical `(obs, forecast, signals)` and emit identical action dicts. Ablations become flag flips, not code forks.
- **`eval/` separate from `control/`:** metrics and plotting never live inside the controller; the controller returns actions, the harness scores them. Enables multi-seed mean±std without re-running control logic manually.
- **`config.py` centralizes magic numbers:** timestep dt, forecast horizon, comfort band, MQTT QoS, random seeds. Examiners and teammates change behavior in one file.

## Architectural Patterns

### Pattern 1: Emulator–Controller split with standardized step signals

**What:** Plant exposes `obs = env.step(action)`; controller exposes `action = policy(obs, forecast, signals)`. Both use pandas-friendly dicts/DataFrames; neither knows the other's internals. Time advances only via `step()`.
**When to use:** Always in this project — it is what makes "compare 5 controllers fairly" possible.
**Trade-offs:** Pro: identical evaluation for every controller; easy to replay public datasets through the same interface. Con: slight overhead vs inlining physics into the controller; worth it.

**Example:**
```python
# control/policies.py
class BasePolicy:
    def step(self, obs: dict, forecast: dict, signals: dict) -> dict:
        """obs: current room T/RH/occupancy/power; forecast: next-N-step occupancy/demand;
           signals: tariff + emission factor now + ahead. Returns {room_id: {'hvac': ..., 'light': ...}}"""
        raise NotImplementedError

# eval/run.py
obs = sim.reset(seed=seed)
for t in timeline:
    fc = forecaster.predict(history, horizon=H)
    act = policy.step(obs, fc, signals.at(t))
    obs = sim.step(act)   # only place time advances
    log.write(t, obs, fc, act)
```

### Pattern 2: Telemetry / command / status topic separation

**What:** Three disjoint topic subtrees per room: `telemetry` (device→cloud, frequent, QoS 0, non-retained), `command/*` (cloud→device, infrequent, QoS 1, non-retained), `status` (online/offline via LWT, retained). Payloads are JSON with `room_id` + `ts` + values.
**When to use:** Every MQTT design in this project; matches AWS IoT best practice (`dt/` vs `cmd/`) and mqtt-smarthome (`status` vs `set`) conventions.
**Trade-offs:** Pro: no command loops, clear ACLs, wildcard-friendly (`building/+/telemetry` for the forecaster, `building/room-1/command/#` per ESP32). Con: more topics to document — solved by `topics.py`.

**Example:**
```python
# iot/topics.py
TELEMETRY = "building/{room}/telemetry"      # {"room_id","ts","temp_c","rh","occ","power_w"}
HVAC_CMD  = "building/{room}/command/hvac"   # {"room_id","ts","mode":"ON|OFF|REDUCED","setpoint_c":24}
LIGHT_CMD = "building/{room}/command/light"  # {"room_id","ts","level":0-100}
STATUS    = "building/{room}/status"          # "online"/"offline" (LWT, retained)
```

### Pattern 3: Forecast-as-input, not forecast-as-controller

**What:** Forecaster is a pure function `history → future occupancy/demand`; it never decides actions. The predictive policy consumes forecasts alongside current obs and price/carbon signals. Ablation = replace forecast with naive persistence or zeros.
**When to use:** When ML must have a "clear role" (examiner criterion): pre-cool before predicted arrival, early-off before predicted departure, shift flexible load to low-carbon windows.
**Trade-offs:** Pro: ablation with/without forecasting is trivial and honest; forecaster can be validated independently on public data. Con: rule-based predictive policy leaves optimality on the table vs MPC — acceptable per scope (MPC is stretch).

## Data Flow

### Request Flow (one closed-loop timestep)

```
Simulator state (T_in, occupancy, weather, t)
     ↓  (sample + noise, or replay)
ESP32 publish → building/room-<id>/telemetry  (QoS 0, 10–60 s)
     ↓  (bridge subscribes building/+/telemetry)
Python history buffer (append obs)
     ↓
Forecaster.predict(history) → 30–60 min occupancy/demand
     ↓  (+ signals.at(t): tariff, emission factor)
Policy.step(obs, forecast, signals) → {hvac, light} per room
     ↓  (publish)
building/room-<id>/command/hvac + command/light  (QoS 1)
     ↓  (ESP32 subscribed; bridge forwards to simulator)
Simulator.step(action) → next state + energy_kwh
     ↓  (append)
CSV log row {t, obs, forecast, action, kWh, cost, CO₂, comfort_ok}
     ↓  (periodic push)
ThingSpeak/Blynk dashboard + eval metrics/graphs
```

### State Management

```
Simulator = sole owner of physical state (T_in per room, HVAC on/off).
History buffer = sole owner of temporal state (last-N obs for forecaster).
Controller = stateless per step (no hidden memory except optional timers e.g. "empty-15-min" counter, kept in policy object, reset per run).
CSV log = sole owner of experiment record (never reconstruct from MQTT).
```

### Key Data Flows

1. **Telemetry flow (fast, loss-tolerant):** simulator → ESP32 → MQTT → bridge → history. QoS 0; a dropped packet is acceptable because the next reading arrives within a minute. Fault-injection (dropout %) happens here.
2. **Command flow (slow, loss-intolerant):** policy → MQTT → ESP32 → simulator. QoS 1; commands are infrequent (setpoint changes only) and must arrive. No retained commands (stale setpoints on reconnect are a classic bug — ESP32 must request fresh state via `status` re-announce).
3. **Forecast flow (in-process, not over MQTT):** history → forecaster → policy. Keep this as Python function calls, NOT MQTT topics — putting forecasts on the bus adds latency and serialization with zero benefit at this scale.
4. **Evaluation flow (offline):** CSV logs → metrics → PNGs + tables. Runs after simulation, never interleaved with control.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 2–5 rooms (this project) | Monolith Python process (sim + forecast + control in one loop) + local Mosquitto is correct. No edge gateway, no cloud, no TSDB beyond CSV. |
| 20–50 rooms | Split simulator from controller process; replace CSV with SQLite/TimescaleDB; add retained `status` dashboard with LWT. MQTT still single broker. |
| 100+ rooms / campus | Per-floor brokers bridged, shared subscriptions, TSDB + Grafana, controller sharded per zone with ADMM-style coordinator (see PEPS `building_coordinator`). Out of scope — do not build. |

### Scaling Priorities

1. **First bottleneck:** Wokwi ESP32 real-time fidelity — virtual nodes cannot usefully publish sub-second data and cannot run the physics. Fix by keeping physics in Python and ESP32s as thin shims (already the recommendation); do not attempt to simulate RC equations on the ESP32.
2. **Second bottleneck:** LSTM training time on long horizons. Fix by training RF/GB first (fast, strong baseline), LSTM only if time permits; inference stays cheap either way.

## Anti-Patterns

### Anti-Pattern 1: Physics inside the controller or dashboard

**What people do:** Compute indoor temperature update inside the policy function or push setpoints straight from Blynk buttons to the simulator.
**Why it's wrong:** Breaks fair comparison (each controller gets different physics), bypasses MQTT contract, makes results unreproducible.
**Do this instead:** All physics in `simulator/`; all decisions in `control/`; dashboard is read-only.

### Anti-Pattern 2: Single flat MQTT topic per building

**What people do:** Publish all rooms to `building/data` with room buried in payload, or use inconsistent names (`room1/temp` vs `room_1/temperature`).
**Why it's wrong:** Controller cannot subscribe per-room; wildcards useless; ACLs impossible; debugging requires payload inspection.
**Do this instead:** `building/{room}/{telemetry|command/*|status}` hierarchy from `topics.py`; room identity in BOTH topic and payload.

### Anti-Pattern 3: Forecasts over MQTT + retained commands

**What people do:** Publish predictions to MQTT topics and retain last command so reconnecting devices "catch up."
**Why it's wrong:** Forecast serialization adds failure modes for an in-process call; retained commands fire stale setpoints (e.g. night setback applied at noon reconnect).
**Do this instead:** Forecasts = function calls; commands non-retained QoS 1; presence via retained `status` + LWT only.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Mosquitto MQTT | Pub/sub via paho-mqtt; bridge process owns the single client connection | Local broker, no auth for v1 (note TLS/username as security write-up for Unit 3 syllabus); document QoS choices |
| ThingSpeak / Blynk | One-way HTTP push from `dashboard/thingspeak_push.py` reading summary topics | ThingSpeak rate limit (~15 s) dictates push cadence; Blynk if needing lower latency; neither sends control |
| UCI Appliances / ASHRAE dataset | Offline CSV replay through `forecast/validate_public.py` | Validates forecaster only, not the closed loop; cite dataset + columns used |
| Wokwi ESP32 | Firmware template flashed per room_id; serial monitor for demo | Keep firmware <150 lines; all tuning (thresholds, intervals) via command payloads, not reflash |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| simulator ↔ bridge | Direct Python calls (`sim.step()`) | Bridge translates MQTT JSON ↔ sim dicts; simulator never imports MQTT |
| bridge ↔ forecaster/controller | In-process history buffer + function calls | Same process for v1; split into services only if scaling |
| forecaster ↔ controller | `predict(history) -> forecast dict` | Controller never trains; forecaster never actuates — ablation seam |
| controller ↔ eval harness | `policy.step()` actions → CSV log | Harness swaps policies without code change; seeds fixed per run |
| Python ↔ dashboard | MQTT summary topics + HTTP push | Dashboard reads only; no control path back |

## Suggested Build Order (dependencies between components)

```
1. simulator + config + CSV log     (nothing depends on nothing; unblocks everything)
        ↓
2. topics.py + bridge (MQTT loopback without Wokwi: publish fake telemetry, verify commands round-trip)
        ↓
3. baseline controllers (fixed, rule, setback) + eval harness + 1 scenario, 1 seed
        ↓  (first end-to-end kWh number — the project's heartbeat)
4. forecaster (RF/GB on synthetic data) + predictive policy + ablations
        ↓
5. carbon/tariff signals + cost/CO₂ metrics + multi-scenario × multi-seed runs
        ↓
6. Wokwi ESP32 firmware + ThingSpeak dashboard (demo layer; do last — it consumes the stable contract, never defines it)
        ↓
7. LSTM + public-dataset validation + Pareto/sensitivity graphs (report polish; parallelizable with 6)
```

Rationale: physics → contract → dumbest working loop → intelligence → economics → demo → polish. The most common failure is starting with Wokwi/dashboard (visible but dependency-inverted); every week without a running `sim.step()` loop is a week with no measurable progress.

## Sources

- HIGH — Springer SN Computer Science reference architecture for IoT-enabled smart buildings (4-layer perception/network/middleware/application + sense→analyze→decide→actuate data flow).
- HIGH — IIT Delhi reference architecture for smart/software-defined buildings (hardware/network/management/application-service layering; BMS/BOS resource + data management split).
- HIGH — AWS IoT whitepaper on designing MQTT topics (telemetry `dt/` vs command `cmd/` separation, per-device hierarchy, QoS guidance, LWT/status patterns).
- HIGH — mqtt-smarthome Architecture.md convention (`status` vs `set` vs `command`, retain-flag rules, connected-status enum) — directly applicable to room telemetry vs setpoint topics.
- HIGH — Energym (open-source building simulation + controller benchmark library, Gym-style `step(obs)` interface, multi-model boilerplate) — structural model for simulator/eval split.
- MEDIUM — PEPS repo (EnergyPlus + Python API: `energyplus_simulator` / `controllers` / `building_coordinator` module split) — validates recommended `simulator/` vs `control/` vs `eval/` boundaries.
- MEDIUM — FastSim / Arroyo et al. MPC toolbox paper (predictor + observer + optimizer block architecture, grey-box RC controller models, pandas signal interface) — validates forecast-as-input pattern.
- MEDIUM — 1R1C/2R2C RC thermal modeling practice (ISO 13790 5R1C Hour model; RCBldEng 7R1C/7R2C; rubenmulero grey-box RC + occupancy + NordPool pricing simulator) — confirms per-room lumped RC + occupancy heat gain + price-signal pattern.
- MEDIUM — Community MQTT topic pattern catalogs (device-centric vs location-centric vs standardized telemetry/command/status; wildcard and ACL planning) — confirms `building/{room}/{telemetry,command,status}` choice.

---
*Architecture research for: Carbon- and Comfort-Aware Predictive Control for Smart Buildings*
*Researched: 2026-09-29*
