<!-- GSD:project-start source:PROJECT.md -->

## Project

**Carbon- and Comfort-Aware Predictive Control for Smart Buildings**

Simulated multi-room smart building where virtual IoT sensors (ESP32 via Wokwi) track occupancy, temperature, humidity and energy use, an ML model forecasts occupancy and demand 30-60 minutes ahead, and a predictive controller sets HVAC and lighting to ON / OFF / reduced. Built for course MM0402A IoT and Sustainability (Group 5, Guide Prof. Vjaykumar Ghule) to beat fixed-schedule control on energy, cost and CO2 without breaking comfort.

**Core Value:** Predict occupancy ahead to cut energy, cost and CO2 while keeping occupied rooms comfortable.

### Constraints

- **Academic**: MM0402A IAS course project — must map to Units 1-4 and tutorials
- **Simulation-only**: Wokwi virtual ESP32, Mosquitto MQTT, ThingSpeak/Blynk dashboard — no physical rooms
- **Time**: Core deliverable is controllers 1-4 + metrics/graphs; MPC/RL is bonus
- **Tech**: Python service for forecasting + control, MQTT topics per room, RC thermal model
- **Evaluation**: Multiple scenarios, several random seeds, ablations with/without forecasting and carbon awareness

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12.x | All Python services (simulator, ML, controller, dashboard) | Sweet spot: TensorFlow officially supports Python 3.9–3.12, Keras 3 requires ≥3.11, Streamlit ≥1.50 supports 3.12. Python 3.13/3.14 break TF CPU wheels — pin 3.12 to avoid install hell on student laptops. |
| Eclipse Mosquitto (broker) | 2.0.22 (Windows installer) | MQTT broker, local | Industry-standard lightweight broker; MQTT 5/3.1.1; Windows x64 installer exists so all 4 members run the identical broker with zero Docker dependency. 2.1.x is newer but 2.0.x is the proven stable line. |
| paho-mqtt (Python MQTT client) | 2.1.0 | Python ↔ broker pub/sub (controller, simulator bridge, loggers) | The official Eclipse Python client; only maintained option. **Must use `CallbackAPIVersion.VERSION2`** — VERSION1 is deprecated and removed in 3.0. |
| Wokwi + ESP32 Arduino (PubSubClient + DHT sensor lib) | Wokwi web (no version); PubSubClient ≥2.8; DHTesp/DHT sensor lib latest | Virtual ESP32 sensor nodes per room | Zero hardware, browser-based, reproducible for evaluation; PubSubClient is the canonical Arduino MQTT client; documented Wokwi+MQTT pattern uses `Wokwi-GUEST` Wi-Fi and public/local broker. For local Mosquitto use the Wokwi IoT Private Gateway. |
| scikit-learn | 1.9.x | RF + Gradient Boosting forecasting baselines | Standard, CPU-only, installs in seconds, `RandomForestRegressor` + `HistGradientBoostingRegressor` cover the required "RF/GB baseline". Prefer **HistGradientBoostingRegressor** over legacy GradientBoostingRegressor — orders of magnitude faster past ~10k samples, per sklearn docs. |
| TensorFlow + Keras 3 | TF 2.x (CPU pip) + Keras 3.13.x | LSTM occupancy/demand forecaster | Official TF time-series tutorial path (`tf.keras.layers.LSTM`); Keras 3 is the maintained API (Keras 2 lives on only as `tf-keras`). CPU-only install keeps student laptops viable; dataset is small so GPU is unnecessary. |
| Streamlit | ≥1.50 (1.52+, Dec 2025 line) | Live energy/comfort/savings dashboard | Pure-Python dashboard in ~100 lines; `streamlit run` + Plotly charts; kills the need for any frontend work. ThingSpeak/Blynk stay as the syllabus IoT-cloud screenshot, but Streamlit is the primary evaluation dashboard. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | 2.x | RC thermal model math, scenario/noise generation | Always — the simulator core |
| pandas | 2.x | Timeseries frames, timetables, CSV logging, resampling | Always — data + evaluation plumbing |
| matplotlib | 3.x | All 6 required report graphs (24h profile, savings bars, Pareto, CO₂, predicted-vs-actual, ablation) | Always — report figures; raster + vector export |
| plotly | 5.x/6.x | Interactive dashboard charts inside Streamlit | Dashboard phase only (`st.plotly_chart`) |
| joblib | bundled w/ sklearn | Persist trained RF/GB models + scalers | ML phase — commit small models to repo |
| MQTT Explorer (desktop) | latest | Debug/inspect per-room topics during IoT bring-up | IoT phase — verifying pub/sub before wiring controller |
| ThingSpeak or Blynk (free tier) | cloud, no version | Syllabus IoT-cloud endpoint + dashboard screenshot | IoT phase — one channel per building metric; secondary to Streamlit |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| venv + requirements.txt (pip) | Per-member reproducible env | Pin `==` versions; one `requirements.txt` at repo root; Python 3.12 for all |
| Arduino IDE / Wokwi web editor | ESP32 firmware sketch | One sketch parameterized per room (room ID macro); share via Wokwi project link |
| mosquitto.conf (checked in) | Identical broker config everywhere | Local listener 1883, anonymous for lab simplicity + a commented TLS block for the Unit-3 security note |
| git + GitHub | 4-member collaboration | Work-split folders: `sim/`, `iot/`, `ml/`, `ctrl/` matching the member split |

## Installation

# Simulator + ML + controller + dashboard (Python 3.12)

# Dev / debug

# Broker (Windows, per member laptop) — download installer:

# https://mosquitto.org/files/binary/win64/mosquitto-2.0.22-install-windows-x64.exe

# ESP32 firmware (Arduino IDE Library Manager):

# PubSubClient + "DHT sensor library" (Adafruit) + "DHTesp" alternative

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Pure-NumPy RC thermal model | EnergyPlus / OpenStudio | Only if a guide explicitly demands a certified engine — 10x setup cost, kills the 4-member timeline |
| scikit-learn HistGB + RF | XGBoost / LightGBM | If HistGB underfits badly AND a member already knows XGBoost; otherwise extra native dependency for marginal gain on small data |
| TensorFlow/Keras LSTM | PyTorch LSTM | If the ML member already knows PyTorch; both fine, but TF has the canonical time-series tutorial the report can cite |
| Streamlit (primary) | ThingSpeak/Blynk only | Syllabus requires the IoT-cloud comparison — do ThingSpeak/Blynk for the screenshot, Streamlit for real evaluation |
| Local Mosquitto | HiveMQ Cloud / test.mosquitto.org | Only as fallback if local install fails; public brokers add latency/flakiness that poisons multi-seed experiments |
| CSV logging | InfluxDB / TimescaleDB | Never in v1 — CSV + pandas covers 4 rooms × 1-min steps trivially; time-series DB is pure overhead |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| paho-mqtt 1.x / VERSION1 callback API | Deprecated; breaks on upgrade to 3.0; every tutorial copy-pastes the old `Client()` signature | paho-mqtt 2.1.0 with `CallbackAPIVersion.VERSION2` |
| Python 3.13/3.14 for this project | No TF CPU wheels for 3.13+ in the supported matrix; members will burn days on install errors | Python 3.12.x for everyone |
| Full MPC / RL libs in v1 (cvxpy, stable-baselines3) | Stretch goal per PROJECT.md; MPC/RL doubles controller + tuning work and risks the core deliverable | Rule-based predictive controller (pre-cool / early-off from forecasts); MPC/RL only if controllers 1–4 done early |
| EnergyPlus / TRNSYS simulator | Certified but heavyweight; needs IDF modeling skills nobody on the team has; overkill for demonstrating control savings | NumPy RC model (1R1C per room): `T_in += dt/C*( (T_out-T_in)/R + Q_occ + Q_hvac )` |
| Grafana + InfluxDB dashboard | Real-ops stack; needs two more services per laptop; zero report value over Streamlit | Streamlit + Plotly |
| HTTP polling / CoAP for telemetry | Syllabus Unit-4 asks for the *comparison*, not the implementation; polling wastes the ESP32 loop and complicates QoS/last-will | MQTT everywhere (QoS 1, retained setpoints, LWT for sensor-failure robustness test) |
| Blynk legacy / ThingSpeak as sole dashboard | Rate limits + cloud dependence make multi-seed batch runs flaky; weak plotting for Pareto/ablation figures | ThingSpeak/Blynk for the IoT-cloud screenshot; Streamlit + matplotlib for evaluation |
| TensorFlow GPU on Windows native | Needs WSL2 + CUDA setup per laptop; dataset is tiny (synthetic + UCI), CPU trains in minutes | `pip install tensorflow` CPU; note WSL2-GPU path in report as future work |

## Stack Patterns by Variant

- Point that ESP32 at the shared local Mosquitto via the member hosting the broker (same LAN), or temporarily at `test.mosquitto.org`
- Because simulation continuity matters more than broker locality; re-point topics, change nothing else
- That member works on RF/GB + controller code (pure sklearn/numpy), ML member owns LSTM training and commits the `.keras` file + predictions CSV
- Because LSTM training is a one-machine job; inference/notebook review needs no TF if predictions are checked in
- Demo on Streamlit (local, unlimited); show ThingSpeak channel screenshot from an earlier successful run
- Because the grade depends on the live demo working, not on which cloud carried it

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| tensorflow (CPU pip) | Python 3.9–3.12 only | Hard ceiling — the reason for the Python 3.12 pin |
| keras 3.13.x | Python ≥3.11; TF ≥2.16 / torch ≥2.1 / jax | Consistent with Python 3.12; save models in `.keras` format |
| scikit-learn 1.9.x | numpy 2.x, scipy, joblib | Standard trio; no conflicts with TF/Streamlit |
| paho-mqtt 2.1.0 | Python ≥3.7; Mosquitto 2.0.x/2.1.x (MQTT 3.1.1/5) | Use MQTT v3.1.1 default; v5 only if the security note needs reason codes |
| streamlit ≥1.50 | Python 3.10+ (3.9 dropped in 1.51) | Fine on 3.12; Altair 6 / Plotly charts supported |
| PubSubClient | Arduino-ESP32 core in Wokwi | Default MQTT max packet 256B — raise `setBufferSize()` for JSON payloads with 6+ fields |

## Sources

- Eclipse Paho Python docs + changelog (paho-mqtt 2.1.0, VERSION2 API, Python ≥3.7) — HIGH
- scikit-learn 1.9.x ensemble docs (HistGB vs RF guidance) — HIGH
- Mosquitto blog/DIY (2.0.22 Jul-2025; 2.1.x line to 2.1.2 Feb-2026; Windows x64 installers) — HIGH
- Streamlit 2025 release notes (1.50–1.52, Python 3.9 dropped) — HIGH
- tensorflow.org install matrix (Python 3.9–3.12) + time-series tutorial (LSTM path) — HIGH
- PyPI keras 3.13.x (multi-backend, Python ≥3.11, TF ≥2.16) — HIGH
- Wokwi ESP32-WiFi docs + Wokwi PubSubClient/DHT22 MQTT projects (Wokwi-GUEST, Private Gateway for localhost) — MEDIUM (community patterns, cross-checked across 3+ projects)
- numpy/pandas/matplotlib/plotly versions — MEDIUM (standard ecosystem knowledge, pin `==` at setup time)

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
