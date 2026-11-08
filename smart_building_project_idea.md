# A Carbon- and Comfort-Aware Predictive Control Framework for Energy Optimization in Smart Buildings using IoT

**Course:** MM0402A IoT and Sustainability (IAS)
**Group:** 5
**Guide:** Prof. Vjaykumar Ghule

---

## In two lines

We build a simulated smart building where virtual IoT sensors track occupancy, temperature and energy use, and an AI model predicts demand to decide when the AC and lights should be ON, OFF or reduced. We then compare it against normal fixed-schedule control to show how much energy, cost and CO₂ it saves without making the rooms uncomfortable.

---

## Problem statement

Buildings consume a large share of electricity, and much of it is wasted because HVAC and lighting run on fixed schedules or simple rules. They don't anticipate occupancy, and they ignore how clean or expensive the grid is at a given hour. Existing occupancy-based controllers are reactive and are usually judged only on energy saved, with comfort and carbon treated as afterthoughts.

This project builds an IoT-based framework that senses room conditions, predicts occupancy and energy demand, and sets HVAC and lighting to ON, OFF or reduced. It does this while keeping comfort within limits and shifting load to cheaper, lower-carbon hours.

---

## Objectives

1. Build a simulated multi-room building with a thermal model, so control decisions have realistic consequences.
2. Implement an IoT pipeline: ESP32 sensor nodes → MQTT → controller → dashboard.
3. Train ML models to forecast occupancy and energy demand 30–60 minutes ahead.
4. Design a controller that minimizes energy, cost and CO₂ subject to a comfort constraint.
5. Compare it against several baselines and report the energy vs comfort trade-off.

---

## System architecture

| Layer | What it does |
|---|---|
| Sensing | Virtual ESP32 nodes per room (Wokwi) publishing temperature, humidity, occupancy, light level, HVAC state and power |
| Communication | MQTT broker (e.g., Mosquitto) with topics per room; short comparison of MQTT vs HTTP vs CoAP |
| Processing | Python service holding the forecasting models and the controller |
| Actuation | AC setpoint/level and light dimming commands sent back over MQTT |
| Application | ThingSpeak or Blynk dashboard showing live energy, comfort and savings |
| Building simulator | RC thermal model: indoor temperature responds to outdoor temperature, occupancy heat gain and HVAC power |

---

## Method

- **Data:** synthetic data from the simulator using realistic class/office timetables, weather variation and sensor noise. Validate the forecasting part on a public dataset (UCI Appliances Energy Prediction or ASHRAE).
- **Forecasting:** baseline (Random Forest or Gradient Boosting) compared with an LSTM or similar. Report MAE, RMSE and R².
- **Controller:** rule-based predictive policy that pre-cools before predicted arrival and switches off before predicted departure. Optional extension to MPC or RL if time permits.
- **Carbon and cost awareness:** time-varying grid emission factor and a time-of-use tariff, so the controller can shift flexible load.

---

## Controllers compared

| # | Controller | Purpose |
|---|---|---|
| 1 | Fixed schedule | Traditional baseline |
| 2 | Occupancy rule ("off if empty 15 min") | Fair, simple baseline |
| 3 | Setpoint setback | Common practical strategy |
| 4 | **Proposed predictive controller** | Our contribution |
| 5 | MPC or RL (optional) | Stretch goal |

---

## Metrics

- **Energy:** kWh
- **Energy saved %** = (baseline − proposed) / baseline × 100
- **CO₂ avoided** = Σ kWh × hourly emission factor (cite the latest CEA figure for India)
- **Operating cost:** using a time-of-use tariff
- **Comfort:** % of occupied time within, e.g., 22–26 °C and 30–60% humidity
- **Robustness:** performance when a sensor fails or packets drop

---

## Experiments

1. Scenarios: weekday, weekend, heatwave, exam day.
2. Run each with several random seeds; report mean ± standard deviation.
3. Ablation: with/without occupancy forecasting, with/without carbon awareness.
4. Energy vs comfort trade-off curve (Pareto plot).
5. Sensitivity to emission factor, tariff and comfort band.

---

## Graphs to include

- 24-hour energy profile, baseline vs proposed
- Savings % by scenario and controller
- Energy vs comfort trade-off curve
- Cumulative CO₂ avoided
- Predicted vs actual occupancy and demand
- Ablation bar chart
- Dashboard screenshot

---

## What is new compared with the basic version

| Basic idea | Improved version |
|---|---|
| One weak baseline (fixed schedule) | Four or five baselines including a simple occupancy rule |
| ML predicts demand with no clear role | Forecasts occupancy ahead to drive pre-cooling and early shut-off |
| CO₂ = kWh × constant | Time-varying carbon and tariff with load shifting |
| Comfort undefined | Comfort as a constraint with a trade-off curve |
| Simulated data only | Thermal model plus public dataset validation |
| IoT layer implied | ESP32, MQTT, dashboard, fault tolerance, security note |
| Single run | Multiple scenarios, seeds and ablations |

---

## Mapping to the syllabus

- **Unit 1:** IoT architecture, communication models
- **Unit 2:** sensors, actuators, smart objects
- **Unit 3:** ESP32, IoT security for the MQTT link
- **Unit 4:** MQTT vs HTTP vs CoAP, protocol choice
- **Tutorials 1, 2, 3, 4, 6, 7:** architecture, choosing things, protocol and microcontroller comparison, mini design project, simulation

---

## Suggested work split (4 members)

1. **Simulator and thermal model:** building, rooms, weather and occupancy patterns
2. **IoT pipeline:** ESP32 in Wokwi, MQTT, dashboard
3. **ML forecasting:** models and public dataset validation
4. **Controller and evaluation:** baselines, metrics, graphs, report writing

---

## Scope

The core deliverable is controllers 1–4, plus the metrics and graphs. MPC or RL is a bonus; cut it if time is tight rather than rushing everything.
