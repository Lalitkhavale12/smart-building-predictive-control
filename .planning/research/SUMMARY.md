# Project Research Summary

**Project:** Carbon- and Comfort-Aware Predictive Control for Smart Buildings
**Domain:** Simulated multi-room IoT smart building + MQTT + Python forecasting + predictive control + dashboard (greenfield academic project, ESP32/Wokwi, 4-member team)
**Researched:** 2026-09-29
**Confidence:** HIGH

## Executive Summary

This is a closed-loop predictive-control project, not a monitoring dashboard: a deterministic Python building simulator stands in for the physical building (per-room RC thermal model + timetables + weather + noise), thin virtual ESP32 nodes publish telemetry and receive actuation over MQTT, a Python forecaster predicts occupancy/demand 30–60 min ahead, and a rule-based predictive controller (pre-cool before arrival, early-off before departure, shift load to cheap/clean hours) beats three non-ML baselines on energy, cost, and CO₂ — subject to a hard comfort constraint (22–26 °C / 30–60 %RH). Experts build this as an emulator–controller split with a standardized `step()` signal interface, telemetry/command/status topic separation, and forecast-as-input (never forecast-as-controller), evaluated by a scenario × seed × controller × ablation harness reporting mean±std.

The recommended approach is deliberately boring where it should be: Python 3.12 pinned (TensorFlow ceiling), local Mosquitto 2.0.22, paho-mqtt 2.1.0 with VERSION2 API, NumPy 1R1C thermal model, scikit-learn HistGB/RF baselines plus one Keras-3 LSTM, Streamlit as the primary dashboard with ThingSpeak/Blynk kept to the syllabus screenshot. Build order is physics → contract → dumbest working loop → intelligence → economics → demo → polish: simulator + seeded CSV logging first, then `topics.py` + MQTT bridge, then baselines C1–C3 with the eval harness producing the first kWh number, then the forecaster + predictive controller C4, then carbon/tariff economics with multi-scenario multi-seed runs, and only last the Wokwi firmware + dashboard + LSTM/public-dataset polish.

The key risks are all credibility risks, and every one has a cheap prevention: temporal leakage inflating forecaster accuracy (chronological splits + walk-forward only), synthetic-only validation (public-dataset forecaster validation as a P1 deliverable, not stretch), single-seed victory claims (≥5 paired seeds + mean±std + significance before any claim), strawman baselines and comfort-blind savings (all three baselines before C4; comfort column in every table; Pareto curve required), a constant CO₂ factor that makes carbon-awareness mathematically vacuous (hourly time-varying series from day one), and an MQTT pipeline that demos fine and dies on 24h runs (QoS 1 + LWT + reconnect + decoupled intake as acceptance criteria). Full MPC/RL is explicitly gated as stretch — predictive rules capture ~90–95% of MPC's savings at a fraction of the risk.

## Key Findings

### Recommended Stack

Single-Python monolith (sim + forecast + control in one loop) on Python 3.12 with a local Mosquitto broker is the correct architecture at 2–5 rooms — no Docker, no TSDB, no GPU, no cloud dependency. The two hard version pins are Python 3.12 (TensorFlow CPU wheels stop at 3.12) and paho-mqtt 2.1.0 with `CallbackAPIVersion.VERSION2` (VERSION1 is deprecated/removed). Wokwi ESP32s stay as thin shims (physics lives in Python, never on the virtual node); Streamlit + Plotly is the evaluation dashboard while ThingSpeak/Blynk serves only the syllabus IoT-cloud screenshot.

**Core technologies:**
- Python 3.12.x: all services (simulator, ML, controller, dashboard) — TF supports only 3.9–3.12; 3.13+ breaks CPU wheels
- Eclipse Mosquitto 2.0.22 (Windows installer): local MQTT broker — identical broker on all 4 laptops, zero Docker
- paho-mqtt 2.1.0: Python pub/sub — only maintained client; must use VERSION2 callback API
- Wokwi + ESP32 Arduino (PubSubClient ≥2.8, DHT lib): virtual per-room sensor nodes — zero hardware, reproducible; Private Gateway for localhost broker
- scikit-learn 1.9.x (HistGradientBoostingRegressor + RandomForestRegressor): forecasting baselines — CPU-only, fast, strong on tabular data
- TensorFlow CPU + Keras 3.13.x: LSTM forecaster — canonical time-series tutorial path; tiny synthetic data needs no GPU
- Streamlit ≥1.50 + Plotly: primary live dashboard — ~100 lines of pure Python, no frontend work

See STACK.md for install commands, version-compatibility matrix, and per-member fallback plans (TF-install failure, gateway failure, ThingSpeak rate limits).

### Expected Features

The comparison IS the project: controllers C1–C4 (fixed schedule, occupancy-rule, setback, predictive) run through one harness producing kWh, saved-%, CO₂ (hourly factor), ToU cost, comfort-%, and the seven required report graphs. The highest-leverage artifact is the comparison harness itself — every required figure (24h profile, savings bars, Pareto, cumulative CO₂, predicted-vs-actual, ablation, dashboard screenshot) comes out of it. Public-dataset validation is the one independent branch (needs only the forecaster) and the MQTT pipeline is the other (needs only the message schema) — both parallelize.

**Must have (table stakes):**
- Seeded RC-thermal multi-room simulator + timetables/weather/noise — nothing runs without it
- MQTT pipeline (virtual ESP32 → Mosquitto → Python → dashboard) with shared schema — syllabus Units 1–4 hinge on this
- Controllers C1–C4 + comparison harness — the deliverable
- Forecaster RF/GB + LSTM with MAE/RMSE/R² — drives C4 and the ML section
- Metrics (kWh, saved-%, CO₂ hourly, ToU cost, comfort-%) + all required graphs — every claim needs these
- Time-varying carbon factor + ToU tariff with load shifting — the "carbon-aware" half of the title
- 4 scenarios × multi-seed mean±std + ablations + Pareto curve — credibility floor
- Protocol comparison + security note — syllabus compliance, near-zero cost

**Should have (competitive):**
- Public-dataset validation (UCI/ASHRAE forecaster run) — kills the synthetic-only objection
- Robustness tests (sensor failure, packet loss with measured deltas) — explicit objective, cheap fault flags
- Sensitivity sweep (emission factor, tariff, comfort band ±1 °C) — reuses Pareto machinery

**Defer (v2+):**
- MPC/RL Controller #5 — bonus only with leftover time; hard kill criterion if it doesn't beat C4 quickly
- DCV/ventilation optimization, per-user comfort learning — needs count-level occupancy data that doesn't exist
- Real hardware, mobile app, custom React dashboard, BACnet/BAS, campus scale — productization, no evaluation payoff; explicit don'ts

### Architecture Approach

Standard 4-layer IoT layering (perception → transport → processing → application) with the simulator as the plant: everything else treats simulator output as real sensor data, and time advances only via `sim.step(action)`. The three load-bearing boundaries are `simulator/` with zero imports from brain code (controller reaching into physics internals invalidates every comparison), `iot/topics.py` as the single source of topic/schema truth (kills the #1 MQTT bug class: publisher/subscriber string drift), and `control/policies.py` behind one `step(obs, forecast, signals)` interface (all five controllers comparable; ablations become flag flips). Forecasts travel as in-process function calls, never MQTT topics; commands are QoS 1 non-retained; only `status`/LWT is retained; the dashboard is read-only and the CSV log (never MQTT) is the experiment record.

**Major components:**
1. Building simulator (plant) — ground truth T/RH/occupancy/power; `step(action) -> observation`; 1R1C per room; seeded; no ML, no MQTT inside
2. MQTT edge + contract (Wokwi ESP32s, Mosquitto, `topics.py`, bridge) — thin publishers/subscribers; `building/{room}/{telemetry|command/*|status}`; QoS 0 telemetry / QoS 1 commands / retained LWT status
3. Forecaster (RF/GB + LSTM, 30–60 min horizon) — pure `history → future` function; validated synthetic + public data; never actuates
4. Controller (5 policies behind `BasePolicy.step`) — predictive = pre-cool/early-off + carbon/price shifting within comfort band
5. Evaluation harness + store — scenarios × seeds × ablations; metrics (kWh, %, CO₂, cost, comfort); CSV per run; all graphs + Pareto
6. Dashboard (ThingSpeak/Blynk live view + Streamlit + matplotlib report figures) — read-only consumer of summary topics

### Critical Pitfalls

Top risks ordered by ability to silently invalidate results (see PITFALLS.md for all 10 + recovery costs):

1. **Temporal leakage in forecasting (CRITICAL)** — random shuffled splits report 0.95+ then collapse to 0.61–0.88 on real futures. Avoid: chronological split only, walk-forward validation, scalers fit on train partition, split-by-time before windowing, leakage checklist per model.
2. **Synthetic-only validation (CRITICAL)** — controller wins by exploiting invented simulator regularities. Avoid: public-dataset forecaster validation as a P1 deliverable from week 1 of the ML phase; honest synthetic-vs-real side-by-side numbers.
3. **Single-seed conclusions (CRITICAL)** — 2%+ seed-to-seed swings flip small wins. Avoid: fixed seed set (≥5, paired across controllers), mean±std with error bars everywhere, paired significance test before claiming victory.
4. **MPC/RL overreach (CRITICAL)** — half the semester burned on a non-converging optimizer with no baselines. Avoid: lock MPC as stretch at scoping; baselines 1–3 running before any MPC code; calendar kill criterion.
5. **Comfort as afterthought (CRITICAL)** — 30% "savings" at 29 °C occupied. Avoid: comfort metric implemented in the simulator phase; every results table gated on the comfort column; Pareto curve + heatwave adversarial scenario required.
6. **Constant CO₂ factor (HIGH)** — flat factor makes load-shifting mathematically meaningless. Avoid: hourly time-varying emission series + ToU tariffs from day one; carbon ablation must show shifted load in the 24h profile.
7. **Strawman baselines (HIGH)** — beating only fixed-schedule with 35% while a timer switch gets most of it. Avoid: all three non-ML baselines before C4; headline framed as savings-over-strongest-baseline; forecast on/off ablation mandatory.
8. **MQTT that demos but dies in evaluation (HIGH)** — QoS 0 + no LWT + blocking callbacks fail 24h runs. Avoid: QoS 1 + idempotent control, LWT + retained status, reconnect with backoff, decoupled intake buffer, kill-a-node/packet-loss test actually run.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Simulator + Evaluation Foundation
**Rationale:** Nothing predictive, economic, or comparative can start until synthetic data flows; physics-first is the unanimous build-order recommendation and the dependency root of every feature chain.
**Delivers:** `simulator/` (1R1C thermal + timetables + weather + noise/faults) + `config.py` + seeded CSV logging + comfort metric + hourly carbon/ToU series + thermal sanity numbers (pull-down, overnight decay, time constant) + ±20% parameter sensitivity check.
**Addresses:** RC thermal model, metrics groundwork, comfort definition, carbon/ToU tables, multi-seed plumbing.
**Avoids:** Pitfalls 5 (comfort afterthought), 6 (constant CO₂), 9 (uncalibrated thermal); tech-debt traps of hardcoded timetables and flat emission factor.

### Phase 2: MQTT Pipeline + IoT Contract
**Rationale:** Needs only the message schema, so it parallelizes with Phase 1 once `topics.py` exists; must be production-grade before 24h evaluation runs depend on it. Parallelizable branch — second owner starts here with mocked payloads.
**Delivers:** `iot/topics.py` (single source of truth) + `bridge.py` (MQTT ↔ simulator loopback verified without Wokwi) + Mosquitto config checked in + one parameterized Wokwi ESP32 firmware + QoS 1 / LWT / reconnect / decoupled intake buffer.
**Uses:** Mosquitto 2.0.22, paho-mqtt 2.1.0 VERSION2, PubSubClient (raised buffer size for JSON).
**Avoids:** Pitfall 7 (MQTT fragility); integration gotchas on topic drift, blocking callbacks, retained-command staleness.

### Phase 3: Baselines + Comparison Harness (first kWh number)
**Rationale:** Cheapest working end-to-end loop and the project's heartbeat; baselines are the yardstick that must exist before any ML claim. Hard gate: no controller-4 work until C1–C3 are merged and one scenario × one seed produces a kWh comparison.
**Delivers:** Controllers C1–C3 (fixed, occupancy-rule with 15-min hysteresis, setback) + `eval/run.py` + `eval/metrics.py` + first 24h-profile graph on one scenario, one seed.
**Addresses:** Fixed-schedule / occupancy-rule / setback baselines, energy + savings-% + comfort-% reporting.
**Avoids:** Pitfalls 8 (strawman baselines), 4 (MPC before baselines); establishes the harness that later phases reuse for free.

### Phase 4: Forecasting + Predictive Controller
**Rationale:** Strict dependency order — forecaster requires simulator data, C4 requires the forecaster; the ML contribution (pre-cool/early-off from forecasts) is the project's core claim and its ablation is the core ML justification.
**Delivers:** `forecast/` (features + RF/GB vs LSTM training with persistence baseline, chronological + walk-forward protocol, per-horizon MAE/RMSE/R²) + predictive policy C4 + forecast on/off ablation + predicted-vs-actual chart.
**Uses:** scikit-learn HistGB/RF, TensorFlow/Keras-3 LSTM (CPU), Python 3.12 env pinned in week 1.
**Avoids:** Pitfalls 1 (leakage), 10 (unfair bake-off), 2 (simulator-data-only training — public-dataset validation starts here in parallel); recovery rule: corrected-honest metrics beat inflated-fake.

### Phase 5: Carbon Economics + Full Evaluation Rigor
**Rationale:** Economics (cost/CO₂ shifting) layers onto a working C4; rigor (scenarios × seeds × ablations × Pareto) converts working code into defensible results. This phase produces every number the report grades.
**Delivers:** Carbon/ToU shifting verified (load-shift visible in 24h profile) + 4 scenarios × ≥5 paired seeds with mean±std + significance + carbon on/off ablation + Pareto tradeoff curve + robustness tests (kill-a-node, packet loss) + public-dataset validation table + sensitivity sweep.
**Addresses:** Carbon/ToU shifting, multi-scenario + multi-seed, ablations, Pareto, robustness, public validation.
**Avoids:** Pitfalls 2, 3, 5, 6 verification gates; "looks done but isn't" checklist items 3–9.

### Phase 6: Dashboard + Report Polish
**Rationale:** Demo layer consumes the stable contract and never defines it — building it last avoids dependency inversion (the most common schedule failure). Runs in parallel with Phase 5's long experiment batches.
**Delivers:** Streamlit primary dashboard + ThingSpeak/Blynk screenshot path + all seven required report figures + protocol-comparison and security notes + one-command reproduction (pinned env + seeds).
**Addresses:** Live dashboard, required graphs, syllabus Units 3–4 write-ups, reproducibility.
**Avoids:** UX pitfalls (screenshot-afterthought, no-baseline dashboard, missing staleness indicators); tech-debt trap of dashboard reading simulator state directly.

### Phase Ordering Rationale

- **Dependencies dictate order:** simulator → forecaster → C4 is a hard chain; carbon shifting requires C4; Pareto/ablation/scenarios all require the harness — so the harness (Phase 3) is deliberately built early with dumb controllers.
- **Grouping follows architecture boundaries:** plant (Phase 1), contract/transport (Phase 2), brain-baseline + scoring (Phase 3), brain-intelligence (Phase 4), economics + rigor (Phase 5), application/polish (Phase 6) — each phase owns one module split from ARCHITECTURE.md.
- **Risk is front-loaded where it's cheapest:** comfort metric, hourly carbon series, and seed plumbing land in Phase 1 (LOW recovery cost) instead of as report-time rescues (MEDIUM–HIGH); MPC is gated out at scoping so it can never starve C1–C4.
- **Parallelism is explicit:** Phase 2 (schema-only) overlaps Phase 1; public-dataset validation (forecaster-only) overlaps Phases 4–5; Phase 6 overlaps Phase 5's batch runs — matching the 4-member work split (`sim/`, `iot/`, `ml/`, `ctrl/`).

### Research Flags

Phases likely needing deeper research during planning (`--research-phase` recommended):
- **Phase 4 (Forecasting):** horizon/window design, walk-forward protocol details, LSTM-vs-HistGB tuning budgets, UCI vs ASHRAE adapter assumptions — sparse, error-prone, methodology-heavy.
- **Phase 5 (Carbon evaluation):** exact CEA emission-factor value/year to cite, hourly profile construction method, average-vs-marginal accounting choice — needs source verification, not inference.

Phases with standard patterns (skip research-phase):
- **Phase 2 (MQTT pipeline):** QoS/LWT/reconnect/topic-hierarchy conventions are settled (AWS IoT + mqtt-smarthome patterns); implement from contract.
- **Phase 3 (Baselines + harness):** fixed/rule/setback controllers + mean±std harness are textbook; no research needed.
- **Phase 6 (Dashboard + report):** Streamlit + matplotlib + ThingSpeak push are commodity patterns.
- **Phase 1 (Simulator):** 1R1C RC modeling is standard practice; only the sanity-check numbers need judgment, not research.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core pins verified against official docs/PyPI: paho-mqtt 2.1.0 + VERSION2, sklearn HistGB guidance, TF Python 3.9–3.12 matrix, Keras 3.13, Mosquitto 2.0.22 installers, Streamlit 1.50+ release notes |
| Features | HIGH | Grounded in idea doc + PROJECT.md cross-checked against LBNL/UCSD field studies, ENERGY STAR SHEMS criteria, BuildingIQ/Verdant commercial references, ASHRAE Ch. 65 |
| Architecture | HIGH | 4-layer IoT reference architectures + AWS/mqtt-smarthome topic conventions + Energym/PEPS module splits all converge; MEDIUM only on the exact Python folder split, which is project judgment |
| Pitfalls | HIGH | Cross-checked across leakage/equifinality/MPC/carbon-accounting/seed-variance literature with named studies, measured effect sizes, and recovery costs |

**Overall confidence:** HIGH

### Gaps to Address

- **Exact CEA emission factor (value, year, publication):** research recommends the mechanism (hourly shape) but the citable number must be nailed during Phase 1/5 planning — handle by assigning the metrics owner to source and cite it before any CO₂ code runs.
- **UCI Appliances vs ASHRAE subset choice:** both validate the forecaster; decision hinges on granularity and occupancy-ground-truth availability — handle by time-boxing a dataset spike in early Phase 4 and documenting adapter assumptions.
- **Wokwi Private Gateway operability on all 4 laptops:** community-pattern evidence (MEDIUM), not official guarantee — handle via the STACK.md fallback (shared-LAN broker or `test.mosquitto.org` re-point, contract unchanged) tested in Phase 2.
- **LSTM tuning budget vs payoff:** literature warns wins under 2–3% with overlapping std should lose to RF/GB on simplicity — handle by fixing equal tuning budgets upfront in Phase 4 and preferring the simpler model on ties.
- **Plotly/Streamlit/numpy minor versions:** standard-ecosystem knowledge — handle by pinning `==` versions in `requirements.txt` at setup time (week 1).

## Sources

### Primary (HIGH confidence)
- Eclipse Paho Python docs + changelog — paho-mqtt 2.1.0, VERSION2 API, Python ≥3.7
- scikit-learn 1.9.x ensemble docs — HistGB vs RF guidance
- tensorflow.org install matrix (Python 3.9–3.12) + LSTM time-series tutorial path
- PyPI Keras 3.13.x — multi-backend, Python ≥3.11 requirements
- Mosquitto release history — 2.0.22 stable line + 2.1.x, Windows x64 installers
- Streamlit 2025 release notes (1.50–1.52, Python floor changes)
- Springer SN Computer Science IoT reference architecture — 4-layer perception/network/middleware/application
- AWS IoT MQTT topic-design whitepaper — telemetry/command separation, QoS, LWT patterns
- mqtt-smarthome Architecture.md — status/set/command + retain-flag conventions
- Energym building-simulation benchmark library — Gym-style `step(obs)` plant/controller split
- Kapoor & Narayanan leakage taxonomy (Patterns 2023); Weng et al. (2026) walk-forward occupancy study; Bergmeir (2023) forecast-evaluation methodology; Straub et al. (2023) calibration equifinality; seed-variance literature (Shchur et al.)

### Secondary (MEDIUM confidence)
- Wokwi ESP32-WiFi docs + community PubSubClient/DHT22 MQTT projects — Wokwi-GUEST Wi-Fi, Private Gateway for localhost (cross-checked across 3+ projects)
- PEPS repo module split; FastSim/Arroyo MPC toolbox block architecture; ISO 13790 5R1C / grey-box RC practice
- LBNL occupancy-control field evaluations; UCSD BuildSys savings figures; ENERGY STAR SHEMS criteria; BuildingIQ predictive optimization; Verdant setback references; ASHRAE Ch. 65 occupant-centric controls; JHU decision-focused HVAC learning
- MQTT QoS measurement studies (Gruener MAYHEM, Palmese MQTT-SN, MDPI Sensors 2025 livestock-housing QoS 0/1/2 comparison)

### Tertiary (LOW confidence)
- numpy/pandas/matplotlib/plotly exact minor versions — pin at setup; needs validation on student laptops
- sMPC 94–95%-of-MPC savings figures (Bursill thesis + related studies) — directionally reliable, exact numbers context-dependent

---
*Research completed: 2026-09-29*
*Ready for roadmap: yes*
