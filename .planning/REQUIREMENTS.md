# Requirements: Carbon- and Comfort-Aware Predictive Control for Smart Buildings

**Defined:** 2026-09-29
**Core Value:** Predict occupancy ahead to cut energy, cost and CO2 while keeping occupied rooms comfortable.

## v1 Requirements

### Simulator

- [ ] **SIM-01**: User can run multi-room building simulation with 1R1C RC thermal model responding to outdoor temp, occupancy heat gain and HVAC power
- [ ] **SIM-02**: User can configure realistic occupancy timetables, weather variation and sensor noise with seeded reproducibility
- [ ] **SIM-03**: User can log per-room telemetry (temp, humidity, occupancy, light, HVAC state, power) to CSV with mean±std over seeds
- [ ] **SIM-04**: User can compute comfort metric (% occupied time in 22-26C and 30-60% RH) for every run

### IoT Pipeline

- [ ] **IOT-01**: User can publish per-room telemetry from virtual ESP32 (Wokwi) over MQTT with topics `building/{room}/{telemetry|command|status}`
- [ ] **IOT-02**: User can send AC setpoint/level and light dimming commands back over MQTT with QoS1 + reconnect + LWT
- [ ] **IOT-03**: User can run local Mosquitto broker with single `topics.py` contract shared by sim, bridge and firmware
- [ ] **IOT-04**: User can demonstrate fault tolerance (kill-a-node, packet drop) without pipeline collapse

### Forecasting

- [ ] **FOR-01**: User can forecast occupancy 30-60 min ahead with chronological split and walk-forward evaluation
- [ ] **FOR-02**: User can forecast energy demand 30-60 min ahead reporting MAE, RMSE and R2 vs persistence baseline
- [ ] **FOR-03**: User can compare RF/HistGB baseline against LSTM with fixed tuning budget (prefer simpler on tie)
- [ ] **FOR-04**: User can validate forecaster on public dataset (UCI Appliances or ASHRAE subset)

### Controller

- [ ] **CTL-01**: User can run fixed-schedule baseline controller (C1 traditional)
- [ ] **CTL-02**: User can run occupancy-rule baseline (C2 off if empty 15 min)
- [ ] **CTL-03**: User can run setpoint-setback baseline (C3 common practical strategy)
- [ ] **CTL-04**: User can run proposed predictive controller (C4 pre-cool before arrival, early-off before departure) via `BasePolicy.step()` interface
- [ ] **CTL-05**: User can apply time-varying grid emission factor and ToU tariff for load shifting
- [ ] **CTL-06**: User can enforce comfort constraint with tradeoff visibility (no comfort-blind savings claims)

### Evaluation

- [x] **EVAL-01**: User can run scenarios weekday, weekend, heatwave and exam day with >=5 paired seeds reporting mean±std
- [x] **EVAL-02**: User can report energy kWh, energy saved %, CO2 avoided (hourly factor), operating cost (ToU)
- [x] **EVAL-03**: User can run ablations with/without forecasting and with/without carbon awareness
- [ ] **EVAL-04**: User can generate energy-vs-comfort Pareto curve and all required graphs (24h profile, savings by scenario/controller, cumulative CO2, predicted vs actual, ablation bars)

### Dashboard

- [ ] **DASH-01**: User can view live energy, comfort and savings on dashboard (Streamlit primary + ThingSpeak/Blynk syllabus screenshot)
- [ ] **DASH-02**: User can compare MQTT vs HTTP vs CoAP briefly with protocol choice rationale and MQTT security note

## v2 Requirements

### Advanced Control

- **ADV-01**: User can run MPC controller as stretch goal with kill-criterion date
- **ADV-02**: User can run RL controller as stretch goal only with leftover time

### Extended Analysis

- **EXT-01**: User can run sensitivity analysis to emission factor, tariff and comfort band
- **EXT-02**: User can export full report artifacts with all graphs and tables

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real hardware deployment | Simulation + virtual ESP32 only, no lab access |
| Mobile app | Web/dashboard-first, not relevant to academic value |
| Per-user comfort learning | High complexity, threatens controllers 1-4 timeline |
| Full MPC/RL in v1 | Captures ~90-95% savings via rules; gated as stretch |
| Docker / TSDB / GPU infra | Single-Python monolith sufficient for 2-5 rooms |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SIM-01 | Phase 1 | Pending |
| SIM-02 | Phase 1 | Pending |
| SIM-03 | Phase 1 | Pending |
| SIM-04 | Phase 1 | Pending |
| IOT-01 | Phase 2 | Complete |
| IOT-02 | Phase 2 | Complete |
| IOT-03 | Phase 2 | Complete |
| IOT-04 | Phase 2 | Complete |
| FOR-01 | Phase 4 | Complete |
| FOR-02 | Phase 4 | Complete |
| FOR-03 | Phase 4 | Complete |
| FOR-04 | Phase 4 | Complete |
| CTL-01 | Phase 3 | Complete |
| CTL-02 | Phase 3 | Complete |
| CTL-03 | Phase 3 | Complete |
| CTL-04 | Phase 4 | Complete |
| CTL-05 | Phase 5 | Pending |
| CTL-06 | Phase 5 | Pending |
| EVAL-01 | Phase 5 | Complete |
| EVAL-02 | Phase 5 | Complete |
| EVAL-03 | Phase 5 | Complete |
| EVAL-04 | Phase 5 | Pending |
| DASH-01 | Phase 6 | Pending |
| DASH-02 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-29*
*Last updated: 2026-09-29 after initial definition*
