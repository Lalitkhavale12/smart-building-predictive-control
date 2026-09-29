# Feature Research: Carbon- and Comfort-Aware Predictive Control for Smart Buildings

**Domain:** Smart building IoT energy optimization (simulated, academic)
**Researched:** 2026-09-29
**Confidence:** HIGH (idea doc + PROJECT.md + EMIS field literature + ENERGY STAR SHEMS criteria + commercial predictive-optimization products)

## Feature Landscape

### Table Stakes (Users Expect These)

Features evaluators, users, and the literature assume exist. Missing these = project feels incomplete or comparison feels rigged.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-room sensing (temperature, humidity, occupancy, light, power) | Every EMIS/BMS product starts here; syllabus Units 1–2 require sensors/actuators | LOW | Virtual ESP32 per room in Wokwi; publish on MQTT topics e.g. `building/room1/sensors`. One message schema shared by all rooms. |
| MQTT telemetry pipeline with per-room topics | MQTT is the default IoT pub/sub choice (Unit 4); Mosquitto + ThingSpeak/Blynk is the standard academic stack | LOW | Mosquitto broker, QoS 0 for telemetry, retained last-will for disconnect detection. Short MQTT-vs-HTTP-vs-CoAP note satisfies Unit 4. |
| Actuation loop (HVAC setpoint/level + light ON/OFF/dim) | Sensing without actuation is monitoring, not control; Verdant/BuildingIQ all close the loop | LOW | Commands back over MQTT (`building/room1/actuation`). Three discrete levels (ON/OFF/reduced) keep thermal model tractable. |
| Fixed-schedule baseline controller | The "traditional" reference every paper compares against (LBNL field studies, UCSD BuildSys work) | LOW | Weekday 08:00–18:00 style schedule; trivial to implement, anchors all savings % claims. |
| Occupancy-rule baseline ("off if empty 15 min") | Reviewers reject single-weak-baseline comparisons; reactive rule is the fair simple rival | LOW | Hysteresis timer avoids flapping. This is Controller #2 in the idea doc — non-negotiable. |
| Setpoint-setback baseline | Common practical strategy in real buildings (Verdant intelligent setbacks); expected third baseline | LOW | Night/weekend setback band; cheap to add once fixed schedule exists. |
| Live dashboard (energy, comfort, savings) | ENERGY STAR SHEMS criteria demand "energy information for users"; every commercial product has single-pane-of-glass | MEDIUM | ThingSpeak or Blynk: live kWh, room comfort status, savings vs baseline. A screenshot is a required graph. |
| Energy + savings-% reporting | kWh and (baseline−proposed)/baseline×100 is the universal scoreboard | LOW | Log per-timestep power; aggregate per scenario. |
| 24h energy profile graph (baseline vs proposed) | Standard figure in every occupancy-control paper; guide/examiner expects it | LOW | Matplotlib; one line per controller. |
| Comfort metric (% occupied time in band) | Comfort-as-afterthought is the documented flaw this project fixes; 22–26 °C / 30–60 %RH band | LOW | Compute from simulator ground truth, not noisy sensor values. |
| Protocol comparison note (MQTT vs HTTP vs CoAP) | Explicit Unit 4 + tutorial requirement | LOW | Half-page write-up + why MQTT chosen; no implementation needed. |
| Basic IoT security note (MQTT auth/TLS) | Unit 3 requirement; any ESP32→broker pipeline needs it mentioned | LOW | Username/password + TLS flag on Mosquitto; document, don't over-engineer. |

### Differentiators (Competitive Advantage)

Features that set this build apart. Align with core value: *predict ahead to cut energy/cost/CO₂ without breaking comfort.*

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| 30–60 min occupancy + demand forecasting (RF/GB vs LSTM) | Turns reactive control into predictive: pre-cool before arrival, early-off before departure (ASHRAE Ch. 65 occupant-centric pattern) | MEDIUM | RF/GB baseline is fast and strong on tabular data; LSTM is the "deep" comparison. Report MAE/RMSE/R². Horizon matches RC thermal time constant. |
| Predictive rule-based controller (pre-cool / early-off) | The project's contribution (Controller #4); captures most of MPC's gain at a fraction of complexity — LBNL field results show optimal start/stop + midday ramp-down deliver the bulk of savings | MEDIUM | Rules keyed off forecast + time-to-arrival/departure; simpler to debug and explain than MPC/RL. |
| Time-varying carbon factor + ToU tariff with load shifting | Constant-factor CO₂ is the known weakness; BuildingIQ-style price/carbon-aware shifting is the commercial SOTA move | MEDIUM | CEA India emission factor curve + ToU slabs; shift pre-cooling to cheap/clean hours. Enables "CO₂ avoided" and "operating cost" metrics. |
| Energy-vs-comfort Pareto tradeoff curve | Treats comfort as first-class constraint; no surveyed student build does this — strongest report figure | LOW | Sweep comfort band / aggressiveness; plot savings % vs comfort %. Cheap once multi-controller eval exists. |
| Multi-scenario evaluation (weekday, weekend, heatwave, exam day) | Proves generality, not overfitting to one timetable; mirrors LBNL multi-condition field methodology | MEDIUM | Scenario = timetable + weather trace. Heatwave stresses pre-cooling; exam day stresses unusual occupancy. |
| Multi-seed mean±std reporting | Single-run numbers are not credible; randomness in noise/timetables must be averaged | LOW | 5+ seeds per scenario; trivial loop once simulator is seeded. |
| Ablation study (with/without forecasting, with/without carbon awareness) | Attributes gains to the right cause — answers "is the forecast actually helping?" | LOW | 2×2 ablation bars; near-zero marginal cost, high examiner value. |
| Public-dataset validation (UCI Appliances or ASHRAE) | Synthetic-only forecasting is the top credibility risk; external validation kills it | MEDIUM | Validate forecaster off-simulator; even a compact subset run counts. |
| RC thermal model simulator | Gives control decisions realistic consequences (pre-cooling actually stores energy in mass); physics + data hybrid is the current research direction (JHU DFL work) | MEDIUM | 1R1C per room is enough; outdoor temp + occupancy heat gain + HVAC power inputs. |
| Robustness testing (sensor failure, packet loss) | Real deployments degrade; fault tolerance is an explicit objective and rare in coursework | LOW | Drop/mask sensor streams at fixed rates; report savings/comfort delta. |
| Cumulative CO₂-avoided + savings-by-scenario/controller charts | Turns metrics into the required report figures directly | LOW | Matplotlib; reuse eval logs. |
| Predicted-vs-actual occupancy/demand overlay | Proves the forecaster works before the controller gets credit | LOW | One chart; doubles as ML-section evidence. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems for this scope.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full MPC / RL controller in v1 | Sounds most "advanced"; matches latest papers | Needs identified plant model or long training, tuning-heavy, debugging nightmare on a course timeline; risks rushing controllers 1–4 | Ship predictive rule-based v1; MPC/RL as stretch Controller #5 only if time remains (already in Out of Scope) |
| Real hardware deployment | "Real" feels more impressive than simulation | No lab access, irreproducible, wiring/debugging eats the semester; evaluation across 4 scenarios × seeds impossible | Wokwi virtual ESP32 + seeded simulator; reproducible by examiner in one command |
| Mobile app / real-time chat control | Seems like product polish | Zero evaluation value; not in syllabus; drains IoT-pipeline owner for weeks | ThingSpeak/Blynk dashboard screenshot satisfies the application layer |
| Per-user personalized comfort learning | True comfort is personal | Needs per-occupant data that doesn't exist; privacy issues (camera/thermal identity concerns in COSSY-style systems); scope explosion | Fixed band (22–26 °C / 30–60 %RH) as constraint + Pareto curve over band width |
| Full BMS/BAS integration (BACnet/Modbus drivers) | "Enterprise realism" | Driver hell; commercial EMIS platforms spend teams on this; nothing to do with the research question | MQTT-only actuation inside the simulator; note BACnet as future work |
| Sub-second real-time control loop | "Real-time" sounds rigorous | Thermal time constants are minutes; fast loops add flapping without benefit | 1–5 min control timestep aligned with forecast horizon |
| Custom dashboard web app (React etc.) | Full control over visuals | Rebuilds what ThingSpeak/Blynk give free; frontend work steals from ML/controller quality | ThingSpeak/Blynk + Matplotlib report figures |
| Ventilation-rate / CO₂-driven DCV optimization | ASHRAE-realistic IAQ control | Requires occupancy-count accuracy the binary simulator doesn't provide; second research project hiding inside | Binary occupancy → ON/OFF/reduced; list DCV as future work |
| Multi-building / campus scale | Bigger seems better | Multiplies simulator + eval cost; single-building multi-room already exercises every mechanism | N-room single building; note campus as scaling discussion, not implementation |

## Feature Dependencies

```
[Predictive controller (C4)]
    └──requires──> [Occupancy/demand forecaster]
                       └──requires──> [Simulator with timetables + noise]
                                          └──requires──> [RC thermal model]
[Carbon/ToU load shifting]
    └──requires──> [Predictive controller (C4)]
                       └──requires──> [Time-varying emission + tariff tables]
[Baselines C1–C3 + comparison harness]
    └──requires──> [Simulator + metrics (kWh, comfort %)]
[Pareto tradeoff curve]
    └──requires──> [Comparison harness + comfort-band sweep]
[Ablation bars] ──requires──> [Comparison harness + forecast/carbon toggles]
[Multi-scenario + multi-seed eval] ──requires──> [Seeded simulator + harness]
[Public-dataset validation] ──requires──> [Forecaster] (independent of simulator)
[MQTT pipeline + dashboard] ──requires──> [Sensor/actuation message schema]
[Robustness tests] ──requires──> [Comparison harness + fault-injection flags]

[Dashboard] ──enhances──> [All eval features] (visibility, demo, screenshots)
[Predicted-vs-actual chart] ──enhances──> [Forecaster credibility]

[MPC/RL (C5)] ──conflicts──> [v1 timeline] (cut if tight; must not delay C1–C4)
[Real hardware] ──conflicts──> [Reproducible multi-seed eval]
```

### Dependency Notes

- **Predictive controller requires forecaster; forecaster requires simulator:** the build order is simulator → forecaster → C4. Nothing predictive can start until synthetic data flows.
- **Baselines require simulator + metrics first:** C1–C3 are cheap but meaningless without kWh/comfort logging — build the harness once, reuse for all five controllers.
- **Pareto/ablation/scenario eval all require the comparison harness:** the harness is the highest-leverage artifact; every required graph comes out of it.
- **Public-dataset validation is the one independent branch:** it needs only the forecaster, so the ML owner can parallelize simulator-data training with UCI/ASHRAE validation.
- **MQTT + dashboard requires only the message schema:** the IoT owner can mock sensor payloads before the simulator is done — second parallelizable branch.
- **MPC/RL conflicts with v1 timeline:** hard rule — C1–C4 + graphs first; C5 only consumes leftover time.

## MVP Definition

### Launch With (v1)

Minimum viable academic deliverable — what validates the core claim.

- [ ] Seeded RC-thermal multi-room simulator with timetables/weather/noise — without it nothing else runs
- [ ] MQTT pipeline (virtual ESP32 → Mosquitto → Python → dashboard) with schema — syllabus Units 1–4 hinge on this
- [ ] Controllers C1–C4 (fixed, occupancy-rule, setback, predictive) — the comparison IS the project
- [ ] Forecaster RF/GB + LSTM with MAE/RMSE/R² — drives C4 and the ML section
- [ ] Metrics: kWh, saved %, CO₂ (hourly factor), ToU cost, comfort % — every claim needs these
- [ ] Required graphs: 24h profile, savings by scenario/controller, Pareto curve, cumulative CO₂, predicted-vs-actual, ablation bars, dashboard screenshot — the report is graded on these
- [ ] Time-varying carbon + tariff load shifting — the "carbon-aware" half of the title
- [ ] 4 scenarios × multi-seed mean±std + ablations — credibility floor
- [ ] Protocol comparison + security note — syllabus compliance, near-zero cost

### Add After Validation (v1.x)

Features to add once core comparison is green.

- [ ] Public-dataset validation (UCI/ASHRAE) — trigger: simulator forecaster working; kills the synthetic-only objection
- [ ] Robustness tests (sensor failure, packet loss) — trigger: harness stable; explicit objective, cheap fault flags
- [ ] Sensitivity sweep (emission factor, tariff, comfort band) — trigger: Pareto curve done; reuses sweep machinery

### Future Consideration (v2+)

Features to defer until the core is demonstrated.

- [ ] MPC/RL Controller #5 — why defer: bonus per idea doc; only with leftover time
- [ ] DCV / ventilation optimization — why defer: needs count-level occupancy, second project
- [ ] BACnet/BAS integration, mobile app, campus scale — why defer: productization, not research; no evaluation payoff

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Simulator + RC thermal model | HIGH | MEDIUM | P1 |
| MQTT pipeline + schema | HIGH | LOW | P1 |
| Baselines C1–C3 | HIGH | LOW | P1 |
| Forecaster (RF/GB vs LSTM) | HIGH | MEDIUM | P1 |
| Predictive controller C4 | HIGH | MEDIUM | P1 |
| Metrics (kWh/saved/CO₂/cost/comfort) | HIGH | LOW | P1 |
| Required graphs + dashboard | HIGH | LOW–MEDIUM | P1 |
| Carbon/ToU load shifting | HIGH | MEDIUM | P1 |
| Multi-scenario + multi-seed + ablation | HIGH | LOW | P1 |
| Pareto tradeoff curve | HIGH | LOW | P1 |
| Protocol + security notes | MEDIUM | LOW | P1 |
| Public-dataset validation | HIGH | MEDIUM | P2 |
| Robustness tests | MEDIUM | LOW | P2 |
| Sensitivity sweep | MEDIUM | LOW | P2 |
| MPC/RL Controller #5 | MEDIUM | HIGH | P3 |
| Mobile app / custom dashboard | LOW | HIGH | P3 (don't) |
| Real hardware | LOW | HIGH | P3 (don't) |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration (or explicit don't)

## Competitor Feature Analysis

| Feature | Commercial / Research Reference | Academic Baseline | Our Approach |
|---------|---------------------------------|-------------------|--------------|
| Occupancy-reactive HVAC | Verdant intelligent setbacks; ENERGY STAR SHEMS vacancy-shutoff | Occupancy-rule C2 | Match it as baseline, then beat it with prediction |
| Predictive optimization (weather + occupancy + price) | BuildingIQ Predictive Energy Optimization; LBNL occupancy-based optimal start/stop + midday ramp-down | Absent | C4: forecast-driven pre-cool/early-off + ToU/carbon shifting — core contribution |
| Single-pane-of-glass dashboard | LBNL EMIS field platforms; Danfoss HVAC 4.0 cloud | ThingSpeak screenshot | ThingSpeak/Blynk live energy + comfort + savings |
| Savings attribution (what caused the gain) | LBNL ECM-level decomposition | Single savings % | Ablation (forecast on/off × carbon on/off) + Pareto curve |
| Rigor (scenarios, seeds, external data) | LBNL multi-condition field evals; JHU physics+AI hybrid validation | Single run, synthetic only | 4 scenarios × seeds mean±std + UCI/ASHRAE validation + thermal model |
| Comfort guarantee | COSSY comfort-aware ventilation; ASHRAE Ch. 65 occupant-centric controls | Undefined | Comfort-as-constraint + tradeoff curve |

## Sources

- Idea doc + PROJECT.md (5 controllers, 4 scenarios, metrics, graphs, syllabus mapping, work split)
- LBNL field evaluations of occupancy-based HVAC optimal control (floor-by-floor occupancy, optimal start/stop, midday ramp-down)
- UCSD BuildSys occupancy-driven energy management (10–15% savings from fine-grained occupancy control)
- ENERGY STAR SHEMS criteria (occupancy optimization, automations, user energy info, ToU/demand-response grid services)
- BuildingIQ Predictive Energy Optimization (weather + occupancy + price forecasting into HVAC setpoints)
- Verdant intelligent setbacks + night occupancy + humidity control (commercial setback reference)
- ASHRAE Handbook Ch. 65 occupant-centric sensing & controls (reactive vs predictive/MPC framing)
- JHU Decision-Focused Learning for HVAC cost forecasting (physics + AI hybrid direction)

---
*Feature research for: Carbon- and Comfort-Aware Predictive Control for Smart Buildings*
*Researched: 2026-09-29*
