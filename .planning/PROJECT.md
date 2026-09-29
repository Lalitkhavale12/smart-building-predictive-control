# Carbon- and Comfort-Aware Predictive Control for Smart Buildings

## What This Is

Simulated multi-room smart building where virtual IoT sensors (ESP32 via Wokwi) track occupancy, temperature, humidity and energy use, an ML model forecasts occupancy and demand 30-60 minutes ahead, and a predictive controller sets HVAC and lighting to ON / OFF / reduced. Built for course MM0402A IoT and Sustainability (Group 5, Guide Prof. Vjaykumar Ghule) to beat fixed-schedule control on energy, cost and CO2 without breaking comfort.

## Core Value

Predict occupancy ahead to cut energy, cost and CO2 while keeping occupied rooms comfortable.

## Requirements

### Validated

- ✓ Seeded multi-room RC-thermal simulator with CSV logging, comfort metric, hourly carbon/ToU series — Phase 1 (27 tests green, verified PASS)
- ✓ IoT pipeline: virtual ESP32 shim → MQTT (topics.py contract, QoS1 commands, LWT) → bridge → dashboard-ready — Phase 2 (51 passed, verified PASS)
- ✓ Baselines C1 fixed-schedule, C2 occupancy-rule, C3 setback + comparison harness with first kWh numbers — Phase 3 (70 passed, verified PASS; hard gate cleared)

### Active

- [ ] IoT pipeline: virtual ESP32 nodes → MQTT → Python controller → dashboard
- [ ] ML occupancy and demand forecasting (RF/GB baseline vs LSTM) with MAE/RMSE/R2
- [ ] Predictive controller minimizing energy/cost/CO2 under comfort constraint
- [ ] Baseline comparison (fixed, occupancy-rule, setback vs proposed) with tradeoff reporting
- [ ] Public dataset validation (UCI Appliances or ASHRAE) for forecasting
- [ ] Carbon/cost awareness via time-varying emission factor and ToU tariff with load shifting
- [ ] Robustness to sensor failure and packet loss
- [ ] Dashboard showing live energy, comfort and savings

### Out of Scope

- Full MPC or RL controller in v1 — stretch goal, cut if time is tight
- Real hardware deployment — simulation + virtual ESP32 only
- Real-time chat / mobile app — not relevant to this academic build

## Context

- Idea doc: `smart_building_project_idea.md` — defines 5 controllers compared, 4 scenarios (weekday, weekend, heatwave, exam day), multi-seed mean±std, ablations, Pareto energy-vs-comfort curve.
- Metrics: kWh, energy saved %, CO2 = sum(kWh * hourly factor, CEA India figure), ToU cost, comfort % occupied time in 22-26C and 30-60% RH.
- Graphs required: 24h profile baseline vs proposed, savings by scenario/controller, tradeoff curve, cumulative CO2, predicted vs actual, ablation bars, dashboard screenshot.
- Syllabus mapping: Units 1-4 (architecture, sensors/actuators, ESP32 + MQTT security, MQTT vs HTTP vs CoAP) + Tutorials 1,2,3,4,6,7.
- Work split for 4 members: simulator/thermal, IoT pipeline, ML forecasting, controller/evaluation.
- Greenfield — no existing code, no codebase map.

## Constraints

- **Academic**: MM0402A IAS course project — must map to Units 1-4 and tutorials
- **Simulation-only**: Wokwi virtual ESP32, Mosquitto MQTT, ThingSpeak/Blynk dashboard — no physical rooms
- **Time**: Core deliverable is controllers 1-4 + metrics/graphs; MPC/RL is bonus
- **Tech**: Python service for forecasting + control, MQTT topics per room, RC thermal model
- **Evaluation**: Multiple scenarios, several random seeds, ablations with/without forecasting and carbon awareness

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Simulation + virtual ESP32 over real hardware | Reproducible, no lab access needed | — Pending |
| Predictive rule-based controller as contribution | Pre-cool/early-off from forecasts, simpler than MPC/RL | — Pending |
| Time-varying carbon + tariff | Enables load shifting vs constant-factor baseline | — Pending |
| Comfort as constraint with tradeoff curve | Treats comfort as first-class, not afterthought | — Pending |
| Standard granularity, parallel execution, YOLO | Auto-mode defaults for fast academic build | — Pending |
| Pull-down sanity band corrected 20-35→8-20 min | Plan band contradicted pinned R/C/Q arithmetic (13 min measured); fast pull-down is good for control | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-29 after initialization*
