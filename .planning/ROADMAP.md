# Roadmap: Carbon- and Comfort-Aware Predictive Control for Smart Buildings

## Overview

Physics first, then contract, then dumbest working loop, then intelligence, then economics, then demo: a seeded RC-thermal simulator grounds everything, an MQTT pipeline carries telemetry and commands, three non-ML baselines plus a comparison harness produce the first kWh number, forecasting drives the predictive controller C4, carbon/ToU economics with full scenario × seed × ablation rigor produce every reportable number, and a dashboard plus report polish ship the demo.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Simulator + Evaluation Foundation** - Seeded multi-room RC-thermal simulator with CSV logging, comfort metric, and hourly carbon/ToU series
- [ ] **Phase 2: MQTT Pipeline + IoT Contract** - Virtual ESP32 telemetry over MQTT with shared topic contract, QoS1 commands, and fault tolerance
- [ ] **Phase 3: Baselines + Comparison Harness** - Controllers C1–C3 with eval harness producing the first kWh comparison
- [ ] **Phase 4: Forecasting + Predictive Controller** - Occupancy/demand forecaster driving predictive controller C4 with forecast ablation
- [ ] **Phase 5: Carbon Economics + Full Evaluation Rigor** - Load shifting verified plus scenarios × seeds × ablations × Pareto producing every report number
- [ ] **Phase 6: Dashboard + Report Polish** - Live dashboard, all required graphs, protocol comparison, and one-command reproduction

## Phase Details

### Phase 1: Simulator + Evaluation Foundation
**Goal**: Users can run a reproducible multi-room building simulation that logs telemetry and scores comfort
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: SIM-01, SIM-02, SIM-03, SIM-04
**Success Criteria** (what must be TRUE):
  1. User can run a multi-room simulation and see room temperatures respond to outdoor weather, occupancy heat, and HVAC power ← SIM-01 ✓
  2. User can re-run with the same seed and get identical telemetry, varying timetables/weather/noise by seed ← SIM-02 ✓
  3. User can open a CSV log with per-room temp, humidity, occupancy, HVAC state, and power, summarized as mean±std over seeds ← SIM-03 ✓
  4. User can read a comfort score (% occupied time in 22–26°C and 30–60% RH) for every run ← SIM-04 ✓
**Plans**: TBD

### Phase 2: MQTT Pipeline + IoT Contract
**Goal**: Users can move telemetry and commands between virtual sensors and the controller over MQTT without collapse
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: IOT-01, IOT-02, IOT-03, IOT-04
**Success Criteria** (what must be TRUE):
  1. User can see per-room telemetry arrive from a virtual ESP32 over `building/{room}/{telemetry|command|status}` topics ← IOT-01 ✓
  2. User can send an AC setpoint or light dimming command back over MQTT and watch the room respond, surviving broker reconnects ← IOT-02 ✓
  3. User can start the local Mosquitto broker and run sim, bridge, and firmware against one shared `topics.py` contract ← IOT-03 ✓
  4. User can kill a node or drop packets and watch the pipeline keep running without collapse ← IOT-04 ✓
**Plans**: TBD

### Phase 3: Baselines + Comparison Harness
**Goal**: Users can compare three non-ML baseline controllers on energy and comfort through one harness
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: CTL-01, CTL-02, CTL-03
**Success Criteria** (what must be TRUE):
  1. User can run the fixed-schedule controller (C1) and get a kWh number for a scenario ← CTL-01 ✓
  2. User can run the occupancy-rule controller (C2) and see it beat fixed-schedule by switching off empty rooms ← CTL-02 ✓
  3. User can run the setback controller (C3) and compare all three side-by-side in one 24h-profile comparison ← CTL-03 ✓
**Plans**: TBD

### Phase 4: Forecasting + Predictive Controller
**Goal**: Users can predict occupancy and demand ahead and watch the predictive controller act on those forecasts
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: FOR-01, FOR-02, FOR-03, FOR-04, CTL-04
**Success Criteria** (what must be TRUE):
  1. User can see 30–60 min occupancy forecasts evaluated walk-forward without leakage ← FOR-01 ✓
  2. User can read demand forecasts with MAE/RMSE/R² next to a persistence baseline ← FOR-02 ✓
  3. User can see the RF/HistGB vs LSTM comparison with the simpler model preferred on ties ← FOR-03 ✓
  4. User can see the forecaster validated on a public dataset (UCI Appliances or ASHRAE subset) ← FOR-04 ✓
  5. User can run predictive controller C4 and watch it pre-cool before arrivals and switch off early before departures via `BasePolicy.step()` ← CTL-04 ✓
**Plans**: TBD

### Phase 5: Carbon Economics + Full Evaluation Rigor
**Goal**: Users can see load shifted to cheap/clean hours and trust every claimed number via full scenario × seed × ablation rigor
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: CTL-05, CTL-06, EVAL-01, EVAL-02, EVAL-03, EVAL-04
**Success Criteria** (what must be TRUE):
  1. User can see load visibly shifted to cheap/clean hours in the 24h profile under time-varying emission factor and ToU tariff ← CTL-05 ✓
  2. User can read every results table with a comfort column — no savings claim without its comfort cost ← CTL-06 ✓
  3. User can run weekday, weekend, heatwave, and exam-day scenarios with ≥5 paired seeds reported as mean±std ← EVAL-01 ✓
  4. User can read energy kWh, saved %, CO₂ avoided (hourly factor), and ToU operating cost for every controller ← EVAL-02 ✓
  5. User can see ablation bars proving what forecasting adds and what carbon-awareness adds, plus the energy-vs-comfort Pareto curve and all required graphs ← EVAL-03, EVAL-04 ✓
**Plans**: TBD

### Phase 6: Dashboard + Report Polish
**Goal**: Users can watch live energy, comfort, and savings and reproduce every report artifact
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: DASH-01, DASH-02
**Success Criteria** (what must be TRUE):
  1. User can open the dashboard and watch live energy, comfort, and savings update (Streamlit primary plus ThingSpeak/Blynk syllabus screenshot) ← DASH-01 ✓
  2. User can read the brief MQTT vs HTTP vs CoAP comparison with protocol choice rationale and MQTT security note ← DASH-02 ✓
  3. User can reproduce all required graphs and the report from a pinned env plus seed set with one command ← DASH-01 ✓
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Simulator + Evaluation Foundation | 3/3 | ✓ Complete | 2026-09-29 |
| 2. MQTT Pipeline + IoT Contract | 0/TBD | Not started | - |
| 3. Baselines + Comparison Harness | 0/TBD | Not started | - |
| 4. Forecasting + Predictive Controller | 0/TBD | Not started | - |
| 5. Carbon Economics + Full Evaluation Rigor | 0/TBD | Not started | - |
| 6. Dashboard + Report Polish | 0/TBD | Not started | - |
