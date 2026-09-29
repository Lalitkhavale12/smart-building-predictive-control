# Phase 01: Simulator + Evaluation Foundation — Research

**Researched:** 2026-09-29
**Domain:** NumPy 1R1C building thermal simulation + seeded evaluation plumbing
**Confidence:** HIGH (physics params from published lecture notes; CEA factor from official CEA v21.0; RNG from NumPy docs; ToU slabs from MSEDCL tariff schedule)

## User Constraints (from CONTEXT.md — verbatim, planner MUST honor)

### Locked Decisions
- **D-01 / D-02:** 1R1C per room in pure NumPy: `T_in += dt/C*((T_out-T_in)/R + Q_occ + Q_hvac)` — start simple, spike 2R2C only if pull-down looks wrong. (1R1C selected, recommended default)
- **D-03:** HVAC as discrete levels (OFF / reduced / ON) with fixed Q_hvac per level, plus occupancy heat gain Q_occ per person.
- **D-04 / D-05:** 4 rooms (class/office pattern), 1-min sim timestep (1440 steps/day), control hook every 5 min for later phases.
- **D-06:** Outdoor temp = daily sinusoid + heatwave offset param + seeded noise; humidity random-walk bounded 30–70%.
- **D-07 / D-08:** `numpy.random.Generator(PCG64(seed))` everywhere, seed passed via CLI/config; same seed = identical CSV byte-for-byte. Explicit seed arg + ≥5 paired seeds in eval helper.
- **D-09 / D-10:** Hourly emission-factor + ToU tariff series built in Phase 1 as CSV (CEA India annual figure + transparent daily shape assumption, documented in code comment); carbon shifting itself claimed in Phase 5.
- **D-11 / D-12:** Comfort = % occupied time with 22–26 °C AND 30–60 % RH; computed per run, no comfort-blind tables allowed downstream.
- **D-13:** Per-step CSV: timestamp, room, T_in, T_out, RH, occupancy, HVAC_state, power_kW; summary helper gives mean±std over seeds.
- **D-14:** Expose `sim.step(action) -> obs` + `BasePolicy.step(obs) -> action` stub interface now so Phase 3 baselines plug in without refactor.
- Phase boundary: No MQTT, no ML, no controllers yet — physics + evaluation foundation only. First kWh number comes in Phase 3.

### Agent's Discretion (research recommends, planner decides)
- Exact R/C values per room, Q_hvac sizing, file layout under `sim/` — pick boring standard values, document pull-down/decay sanity numbers.
- Library versions pinned at setup (Python 3.12, numpy 2.x, pandas 2.x, matplotlib 3.x).

### Deferred Ideas (OUT OF SCOPE — ignore)
- None listed (discussion stayed in scope). MPC/RL, Wokwi firmware, dashboard all deferred to their phases — do NOT include in this phase.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SIM-01 | Multi-room 1R1C RC thermal model responding to outdoor temp, occupancy heat gain, HVAC power | 1R1C equation + R/C defaults + Q sizing in Findings §1–§2; explicit Euler update, stability check |
| SIM-02 | Configurable occupancy timetables, weather variation, sensor noise with seeded reproducibility | Timetable schema + weather model + RNG pattern in Findings §3–§5; config-file rule (never hardcode) |
| SIM-03 | Per-room telemetry logging to CSV with mean±std over seeds | CSV schema + eval helper spec in Findings §6 |
| SIM-04 | Comfort metric (% occupied time in 22–26 °C and 30–60 % RH) for every run | Comfort computation spec in Findings §7 |

## Goal

Build a reproducible 4-room building simulator (pure NumPy 1R1C physics, 1-min timestep) with seeded CSV logging, a first-class comfort metric, hourly carbon/ToU series, and a `step()`-based sim/policy interface that Phase 3 baselines plug into unchanged.

**Primary recommendation:** One `sim/` package (config + thermal + occupancy + weather + runner + metrics + grid signals), explicit-Euler 1R1C with R ≈ 30 °C/kW / C ≈ 0.12 kWh/K per room (τ ≈ 3.6 h), `np.random.default_rng(seed)` threaded through everything, CSV as the experiment record, comfort computed per run from day one.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| RC thermal integration | Python sim process (`sim/`) | — | Pure local compute; no service boundary at 4 rooms × 1440 steps |
| Occupancy/weather scenario generation | Python sim process (`sim/`) | — | Deterministic functions of (t, seed, scenario name); config-driven |
| Telemetry logging + summary stats | Python sim process (CSV + pandas) | — | CSV is the experiment record; no DB at this scale |
| Comfort scoring | Python sim process (`sim/metrics.py`) | — | Must be computed per run from the same CSV every downstream table reads |
| Carbon/ToU series | Static CSV under `sim/` or `data/` | — | Time-varying input series, not a service; consumed by controller in Phase 5 |
| Policy interface stub | Python (`sim/policy.py`) | — | In-process ABC; MQTT/ML attach in later phases without refactor |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.x | All sim code | TF ceiling (3.9–3.12); 3.13+ breaks TF CPU wheels — pin 3.12 for all members [CITED: tensorflow.org install matrix, via STACK.md] |
| numpy | 2.x (pin `==2.4.6` or latest 2.4.x at setup; verified 2.5.3 latest, 2.4.x line current) [VERIFIED: PyPI via `pip index versions`] | 1R1C integration, scenario/noise generation | Only dependency the physics needs |
| pandas | 2.x (pin `==2.3.3` or latest 2.x at setup; verified 2.3.3 latest in 2.x line, 3.0.x is a new major — stay on 2.x per project decision) [VERIFIED: PyPI via `pip index versions`] | Timetable frames, CSV logging, resampling, mean±std helper | Data + evaluation plumbing |
| matplotlib | 3.x (pin `==` at setup; 3.10.8 installed locally) | Sanity plots (pull-down, decay, 24h profile) | Report figures later; sanity plots now |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (stdlib) `argparse` + `dataclasses`/`toml` | stdlib | `--seed`, `--scenario`, `--days` CLI; config objects | Always — seed must be a CLI arg, never a global |
| pytest | 8.x | Sanity-number tests (pull-down, decay, determinism) | Validation Architecture below |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure-NumPy 1R1C | EnergyPlus / OpenStudio | Certified engine at 10x setup cost; kills timeline — never in v1 |
| CSV logging | InfluxDB / TimescaleDB | Pure overhead at 4 rooms × 1440 steps/day; CSV + pandas is sufficient |
| `default_rng` | legacy `RandomState` / `np.random.seed` | Global state causes cross-module interference; `RandomState` is MT19937 legacy — use `default_rng` (PCG64) [CITED: numpy.org/doc/stable/reference/random/generator.html] |

**Installation:**

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install "numpy==2.4.6" "pandas==2.3.3" "matplotlib==3.10.7" pytest==8.*
```

**Version verification (run at setup, this session's observation):** `pip index versions numpy` → latest 2.5.3, 2.4.6 available [VERIFIED: PyPI]; `pip index versions pandas` → latest 3.0.6, latest 2.x is 2.3.3 [VERIFIED: PyPI]. Local env runs Python 3.14.6 — **wrong interpreter for this project**; Phase 1 setup must install Python 3.12.x first (see Environment Availability).

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| numpy | PyPI | 20 yrs | ~150M+/mo | github.com/numpy/numpy | OK | Approved |
| pandas | PyPI | 17 yrs | ~100M+/mo | github.com/pandas-dev/pandas | OK | Approved |
| matplotlib | PyPI | 22 yrs | ~50M+/mo | github.com/matplotlib/matplotlib | OK | Approved |
| pytest | PyPI | 20 yrs | ~40M+/mo | github.com/pytest-dev/pytest | OK | Approved |

**Packages removed due to SLOP verdict:** none.
**Packages flagged as suspicious (SUS):** none.
No postinstall scripts of concern (all four are source-built wheels with no network postinstall behavior) [ASSUMED — standard ecosystem knowledge; planner may spot-check with `pip show -f` at setup].

## Key Questions (answered)

1. What R/C/Q values give physically plausible room behavior, and what sanity numbers prove it?
2. How is the 1-min/5-min timestep split structured so Phase 3 control hooks work without refactor?
3. What occupancy/weather/noise models are realistic yet simple, and how is seeding plumbed?
4. What exact CSV schema + summary helper satisfies SIM-03 and downstream phases?
5. How is comfort computed (SIM-04) and how is it gated into every downstream table?
6. How are hourly carbon/ToU CSVs constructed from the CEA figure (D-09)?
7. What does the `sim.step` / `BasePolicy` stub interface look like (D-14)?

## Findings

### 1. Thermal model: exact equation, units, integration

**Use explicit Euler at dt = 60 s — no solver library** [ASSUMED — standard practice for lumped-RC at 1-min steps; stability margin computed below]:

```python
# sim/thermal.py — per room, per step (dt in hours = 1/60)
T_in += dt_h / C * ((T_out - T_in) / R + Q_occ + Q_hvac)
# Units: T [°C], R [°C/kW], C [kWh/°C], Q [kW, +heating/-cooling], dt_h [h]
# Source form: C·dT_in/dt = (T_out-T_in)/R + Q_gains  [CITED: kevinjkircher.com DER-buildings-1.pdf; sites.inferlab.org Lecture-6 §8.7]
```

- **Cooling sign convention:** Q_hvac is NEGATIVE for cooling (heat removed), Q_occ POSITIVE (~0.1 kW/person sensible heat [ASSUMED — ~100 W/person is the standard textbook value; cite ASHRAE Fundamentals Ch.18 in code comment]).
- **Stability:** explicit Euler is stable iff `dt_h < 2·τ`. With τ ≈ 3.6 h and dt_h = 1/60 h, margin is ~400x — unconditionally safe [ASSUMED — arithmetic from recommended defaults below].
- **Equifinality warning:** many (R,C) pairs fit one curve but diverge outside it; therefore fix params to documented values + run a ±20 % sensitivity sweep on R, C, Q_hvac showing headline behavior doesn't hinge on exact guesses [CITED: PITFALLS.md Pitfall 9; Straub et al. 2023].

### 2. R/C/Q defaults with sanity numbers (agent's discretion — recommended)

Scale from published anchors: house-scale C ≈ 2.2–3.2 kWh/°C with R ≈ 2.5 °C/kW [CITED: kevinjkircher.com DER-buildings-1.pdf §§14,25]; room air-only C ≈ 52 kJ/K (≈0.014 kWh/K) for a 4×4×2.7 m room with UA ≈ 7 W/K [CITED: sites.inferlab.org Lecture-6 §8.7]; lightweight-building τ ≈ 2–5 h [CITED: same, §8.7.3]. A classroom/office room (one exterior wall + furnishings multiplier ~8–10× air-only) lands here:

| Param | Recommended default | Unit | Basis |
|-------|--------------------|------|-------|
| R (per room) | 30 | °C/kW (≡ UA ≈ 33 W/K) | One exterior wall + window + infiltration for ~50 m² room [ASSUMED — scaled from cited anchors] |
| C (per room) | 0.12 | kWh/°C (≈ 430 kJ/K) | Air + furnishings/shallow mass, ~100–150 m³ room [ASSUMED — scaled from cited anchors] |
| τ = R·C | **3.6 h** | h | Inside lightweight 2–5 h band ✓ |
| Q_hvac ON (cooling) | −3.5 | kW thermal | ~1-ton split AC sensible capacity; REDUCED = −1.2, OFF = 0 [ASSUMED] |
| Q_occ | +0.10 | kW/person | ~100 W/person sensible [ASSUMED — ASHRAE Fundamentals] |
| COP (electrical conversion) | 3.0 | — | `power_kW = |Q_hvac|/COP + P_light`; 1.5-ton split ≈ 1.5 kW electrical at full load [ASSUMED] |
| P_light | 0.20 | kW/room when occupied & lights on | Fluorescent/LED classroom load [ASSUMED] |

**Sanity numbers the plan must assert as tests (compute in code, print at startup):**

| Check | Expected (with defaults) | Failing symptom |
|-------|--------------------------|-----------------|
| Pull-down 30 → 24 °C, ON, empty room | ~20–35 min | 2 min (C too small) or 6 h (Q too small/C too big) |
| Overnight free decay (OFF, T_out − T_in = 4 K) | ~1.0–1.2 °C/h initial drift | Room tracks outdoor in <1 h (R too small) or never moves (R huge) |
| Steady-state offset, ON vs 38 °C outdoor | Holds 24 °C with duty < 100 % | Cannot hold setpoint even continuous ON → Q undersized for heatwave scenario |
| Occupancy kick (30 students enter, HVAC OFF) | +0.5–1.5 °C over 30 min (3 kW gain into C=0.12) | No visible effect → Q_occ dropped/sign error |

- **Per-room variation:** vary R ±15 % and C ±15 % across the 4 rooms (corner vs interior) with values in `config.py`, NOT hardcoded [ASSUMED — judgment; kills the "all rooms identical" synthetic look].
- **2R2C spike trigger (D-01):** only if pull-down shows single-exponential behavior the report can't defend — 1R1C misses the fast-air/slow-wall overshoot split [CITED: inferlab Lecture-6 2R2C exercise]. Default: do NOT build 2R2C in this phase.

### 3. Occupancy timetable design

**Config-file day-type tables, never hardcoded timetables** (hardcoded timetables = never-acceptable tech debt [CITED: PITFALLS.md Tech Debt table]):

```python
# sim/timetables.py — occupancy count per room, 1-min resolution generated from blocks
TIMETABLES = {
  "classroom_A": [("08:00","09:30",28), ("09:45","11:15",32), ...],  # gaps = empty
  "office_B":    [("09:00","18:00", "poisson(4)"), ...],              # stochastic fill
}
# Scenarios (Phase 1 builds weekday + weekend + heatwave; exam-day optional stub):
#   weekday: normal blocks + ±10 min seeded jitter on edges + 5 % random absence
#   weekend: 1 room occupied 10:00–14:00 (5 people), rest empty
#   heatwave: weekday occupancy + Tout offset +4 °C (see §4)
```

- **Stochastic deviations use the sim RNG** (late arrivals, early departures) so seeds change them reproducibly; deterministic sharp-edge lookup tables make forecasting trivially easy and must be avoided [CITED: PITFALLS.md Pitfall 2].
- **Room pattern (4 rooms):** 2 classrooms (0–32 people, block schedule) + 1 office (0–6, 9–18h with lunch dip) + 1 lab/seminar (0–15, irregular blocks) [ASSUMED — satisfies "class/office pattern" from CONTEXT with enough diversity for later ablations].

### 4. Weather model

```python
# sim/weather.py
T_out(t) = T_mean + A * sin(2π*(t_hours - 9)/24) + heatwave_offset + noise
# T_mean=31, A=4.0 (Pune warm-day shape: min ~27 °C @ ~05:00, max ~35 °C @ ~15:00) [ASSUMED — representative, not measured]
# heatwave_offset: 0 normal / +4 heatwave scenario (CLI/scenario flag) [ASSUMED]
# noise: rng.normal(0, 0.3) per step [ASSUMED]
# RH: bounded random walk RH += rng.normal(0,0.4), clipped to [30,70] % [per D-06]; NO physics coupling to T
#      (document as simplification in code comment — real psychrometrics deferred, never needed in v1)
```

### 5. Seeded RNG pattern (SIM-02 reproducibility)

```python
# One generator per simulator run, passed down — never globals, never np.random.seed
rng = np.random.default_rng(seed)          # Generator(PCG64) [CITED: numpy.org/doc/stable/reference/random/generator.html]
sim = BuildingSim(config, rng=rng)         # occupancy.py, weather.py, faults draw from this rng only
# CLI:  python -m sim.run --scenario weekday --days 1 --seed 7 --out results/weekday/seed07/
# Eval helper loops seeds [0,1,2,3,4] (≥5 paired seeds per D-08), identical seeds reused by every
# controller in later phases for paired comparison [CITED: PITFALLS.md Pitfall 3].
```

- **Byte-for-byte rule:** same (code, config, seed) → identical CSV. Achieve by: single RNG stream consumed in fixed order (rooms looped in sorted order, weather before occupancy each step — document the order); float formatting fixed (`%.4f`); no dict-iteration order dependence, no timestamps from wall-clock (sim-time only) [ASSUMED — standard determinism practice].
- **Do NOT use:** `np.random.seed()` + `np.random.*` globals (side-effect prone, discouraged by NumPy NEP 19) [CITED: blog.scientific-python.org/numpy/numpy-rng/].

### 6. CSV schema + summary helper (SIM-03)

**Per-step per-room CSV** (exact columns, this order — D-13 + `power_kW` + light state needed by SIM-03 "light" telemetry):

```csv
timestamp,room,T_in_C,T_out_C,RH_pct,occupancy,HVAC_state,power_kW,light_on
2026-01-15T00:00:00,classroom_A,27.3421,28.1043,55.2103,0,OFF,0.0000,0
```

- `timestamp`: ISO-8601 sim-time from run start date + step index (no wall-clock). `HVAC_state ∈ {OFF, REDUCED, ON}` (extend later, never rename). `power_kW`: electrical (`|Q_hvac|/COP + light`). `%.4f` floats.
- **Files:** `results/<scenario>/seed<NN>/telemetry.csv` (one file per seed, all rooms — simpler than per-room files; pandas `groupby('room')` downstream) + `results/<scenario>/seed<NN>/run_meta.json` (seed, git hash, config snapshot, package versions) [ASSUMED — layout judgment].
- **Summary helper** `sim/summary.py`: loads N seed CSVs → per (scenario, room) mean±std of: mean T_in, energy kWh, comfort % (see §7). Prints a table + writes `summary.csv`. This is the Phase-3-harness embryo — keep the function signature stable (`summarize(scenario_dir) -> DataFrame`) [ASSUMED].
- **Scale check:** 1440 steps × 4 rooms = 5760 rows/day/seed — trivially pandas-sized; no chunking, no DB [ASSUMED — arithmetic].

### 7. Comfort computation (SIM-04)

```python
# sim/metrics.py
def comfort_flag(T_in, RH, occupied):
    return occupied & (22.0 <= T_in <= 26.0) & (30.0 <= RH <= 60.0)
comfort_pct = 100 * comfort_flag.sum() / occupied_steps  # per room per run; guard div-by-zero (empty room → NaN, not 100 %)
```

- Band 22–26 °C / 30–60 % RH is the locked guide default (D-11/D-12) — implement exactly this, add ±1 °C sensitivity sweep in Phase 5, never retune the band to make results pass [CITED: PITFALLS.md Pitfall 5].
- **Gating rule for all downstream tables:** every results table row carries a comfort column; any run violating the comfort floor is marked failed, not celebrated. Pareto curve required in Phase 5 [CITED: PITFALLS.md Pitfall 5].
- Humidity note: since RH is an uncoupled random walk (§4), comfort-RH failures are noise-driven — acceptable in Phase 1; document that RH realism improves only if a coupled model is ever adopted [ASSUMED].

### 8. Hourly carbon + ToU series construction (D-09)

**Citable annual anchor:** CEA CO₂ Baseline Database v21.0 (Nov 2025): **weighted-average grid EF = 0.710 tCO₂/MWh for FY 2024–25** (0.727 in FY 2023–24) [VERIFIED: cea.nic.in User_Guide_V_21.0.pdf Table S + CDM baseline page]. Use `0.710 kgCO₂/kWh` as the series mean. (Operating margin 0.961 / build margin 0.512 are reported for context; the project uses the average series consistently for decisions AND accounting — state this choice in the code comment to avoid the average-vs-marginal trap [CITED: PITFALLS.md Pitfall 6].)

**Daily shape (modelled approximation — the entire point is time variation; a flat 0.710 makes load-shifting vacuous):**

```python
# sim/grid.py builds data/grid_hourly.csv with 24 rows: hour, ef_kg_per_kwh, price_rs_per_kwh
# EF shape (multiplier on 0.710, mean-normalized to 1.0): solar dip 10–16h ×0.80, evening fossil peak 18–23h ×1.18,
#   night ×1.02, morning ×0.95  [ASSUMED — transparent assumption, documented in code comment + report]
# ToU price (MSEDCL LT/HT commercial classic 4-slab adders on ~Rs 9/kWh base EC):
#   22:00–06:00  −1.50 | 06:00–09:00 & 12:00–18:00  +0.00 | 09:00–12:00  +0.80 | 18:00–22:00  +1.10  (Rs/kWh)
#   [CITED: MSEDCL approved tariff schedule FY24–25, LT-II/HT-I ToD tables]
# NOTE: MERC's MYT Order (Case 217/2024, Mar 2025) redesigns slabs toward solar-hours 09:00–17:00 rebate /
#   peak 17:00–24:00 surcharge for FY25–30. Phase 1 uses the classic 4-slab table (stable, citable, simple);
#   adopting the MYT redesign is a documented Phase-5 option, not Phase-1 work [CITED: MERC MYT Order press note].
```

- **File:** `data/grid_hourly.csv` (24 rows) written by `sim/grid.py --ef-base 0.710 --shape default`; consumed in Phase 5. Phase 1 only verifies: series mean == 0.710 ± 0.001 and carbon ablation hook exists (flat-vs-varying flag) [ASSUMED — test spec].
- **No-scalar rule:** `grep -rn "EMISSION_FACTOR\s*=\s*[0-9]"` must return nothing — a scalar constant anywhere is the Pitfall-6 warning sign [CITED: PITFALLS.md Pitfall 6].

### 9. `sim.step` + `BasePolicy` stub interface (D-14)

```python
# sim/simulator.py
class BuildingSim:
    def __init__(self, config, rng): ...
    def reset(self, seed: int) -> dict: ...          # fresh state, returns initial obs
    def step(self, action: dict) -> dict: ...        # THE only place sim-time advances
    # action: {room_id: {"hvac": "OFF"|"REDUCED"|"ON", "light": 0|1}}
    # obs:    {room_id: {"T_in": f, "T_out": f, "RH": f, "occupancy": n, "power_kW": f}}
    # Control hook: step() applies action for 1 min; Phase 3 calls policy every 5th step (hold action between)

# sim/policy.py
class BasePolicy(ABC):
    @abstractmethod
    def step(self, obs: dict) -> dict: ...           # Phase-1 stub: obs-only (e.g. AlwaysOffPolicy for smoke tests)
# Phase-3/4 extension path (do NOT build now): step(self, obs, forecast=None, signals=None) with None-defaults,
# so C1–C4 keep one interface and ablations become flag flips [CITED: ARCHITECTURE.md Pattern 1 + §114 boundary rule].
```

- **Hard boundary:** `sim/` imports NOTHING from future `ctrl/`/`ml/`/`iot/` — controller reaching into physics internals invalidates every comparison [CITED: ARCHITECTURE.md Structure Rationale]. Enforce with a test that fails on forbidden imports [ASSUMED — cheap `grep`/import test].
- **File layout under `sim/`** (agent's discretion — recommended): `config.py` (all magic numbers: dt, R/C per room, Q levels, comfort band, seeds) + `thermal.py` + `occupancy.py` (timetables) + `weather.py` + `grid.py` + `simulator.py` + `policy.py` + `metrics.py` (comfort, kWh) + `summary.py` + `run.py` (CLI) [ASSUMED — follows ARCHITECTURE.md `simulator/` split, renamed to `sim/` per CONTEXT work-split folders].

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ODE integration | Custom solver / scipy.integrate | Explicit Euler one-liner at dt=60 s | τ/dt ≈ 200+; solver machinery buys nothing, adds dependency |
| RNG plumbing | Own PRNG / global seeding | `np.random.default_rng(seed)` threaded as arg | PCG64 + SeedSequence mixing; globals break paired-seed comparisons |
| CSV + stats | Custom log format / SQLite | pandas `read_csv` + `groupby.mean/std` | 5760 rows/day; DB is pure overhead in v1 |
| Config | Hardcoded timetables/constants | `config.py` + day-type tables | Hardcoded constants are never-acceptable debt; scenarios must be addable without code edits |
| Carbon/price series | Scalar `EF = 0.82` constant | 24-row hourly CSV, mean = 0.710 | Scalar makes Phase-5 shifting mathematically meaningless |

**Key insight:** every "temporary" shortcut in this phase (flat carbon factor, hardcoded timetable, unseeded noise) becomes a credibility defect in the final report — the cheap prevention now is the expensive rescue later.

## Common Pitfalls (phase-relevant subset)

### Pitfall A: Uncalibrated thermal model (equifinality)
**What goes wrong:** arbitrary R/C that "runs" but cools in 2 min or 6 h. **Avoid:** §2 sanity-number tests as phase exit criteria + ±20 % sweep. **Warning signs:** nobody can state τ; pull-down numbers undocumented [CITED: PITFALLS.md Pitfall 9].

### Pitfall B: Comfort as afterthought
**What goes wrong:** energy-only tables; band retuned to pass. **Avoid:** comfort metric implemented in THIS phase, band locked at 22–26/30–60, every table gated [CITED: PITFALLS.md Pitfall 5].

### Pitfall C: Constant CO₂ factor
**What goes wrong:** `EMISSION_FACTOR = 0.82` scalar kills carbon-awareness math. **Avoid:** hourly CSV from day one (§8); grep-test for scalars [CITED: PITFALLS.md Pitfall 6].

### Pitfall D: Unseeded / single-seed runs
**What goes wrong:** 2 %+ seed swings flip small wins; reruns irreproducible. **Avoid:** CLI `--seed` + fixed ≥5-seed eval helper + run_meta.json [CITED: PITFALLS.md Pitfall 3].

### Pitfall E: Physics-controller entanglement
**What goes wrong:** policy reads sim internals; baselines incomparable. **Avoid:** `sim.step`/`BasePolicy` boundary + forbidden-import test [CITED: ARCHITECTURE.md].

## Code Examples

### Minimal sim loop (the pattern every later phase reuses)

```python
# Source pattern: ARCHITECTURE.md §Pattern 1 (emulator-controller split)
from sim.simulator import BuildingSim
from sim.policy import AlwaysOffPolicy   # Phase-1 smoke stub
import numpy as np

sim = BuildingSim(config, rng=np.random.default_rng(7))
obs = sim.reset(seed=7)
policy = AlwaysOffPolicy()
for t in range(1440):                    # 1 day × 1-min steps
    action = policy.step(obs) if t % 5 == 0 else action  # 5-min control hook (hold between)
    obs = sim.step(action)               # only place time advances
    log.write(t, obs, action)
```

### Comfort + energy summary

```python
# sim/metrics.py — per-room, per-run; summary.py aggregates mean±std over seeds
occupied = df["occupancy"] > 0
in_band = df["T_in_C"].between(22.0, 26.0) & df["RH_pct"].between(30.0, 60.0)
comfort_pct = 100.0 * (occupied & in_band).sum() / max(occupied.sum(), 1)
energy_kwh = (df["power_kW"] * (1/60)).sum()   # 1-min steps → kWh
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `np.random.seed` + globals | `default_rng(seed)` instances passed as args | NumPy 1.17 (NEP 19) | Reproducibility without global side effects |
| Flat annual CO₂ factor | Hourly time-varying EF series | Carbon-aware computing literature 2022–24 | Load-shifting claims become measurable |
| pandas 1.x / numpy 1.x | numpy 2.x / pandas 2.x | 2024 | Phase pins the 2.x lines; pandas 3.x is a new major — stay on 2.x |
| VERSION1 paho callbacks | VERSION2 API | paho-mqtt 2.x | Irrelevant to Phase 1 (no MQTT), noted for Phase 2 |

**Deprecated/outdated:** `RandomState` (legacy MT19937 — do not use for new code); scalar emission-factor math; hardcoded timetables.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | R=30 °C/kW, C=0.12 kWh/K per room (τ≈3.6 h) | §2 | Sanity tests fail → retune R/C within cited bands; low cost (config-only change) |
| A2 | Q_hvac ON=−3.5 / REDUCED=−1.2 kW thermal; COP=3.0; P_light=0.2 kW | §2 | Heatwave scenario unholdable → resize Q; electrical kWh scales with COP — document both |
| A3 | Q_occ=0.10 kW/person; weather T_mean=31/A=4.0/noise σ=0.3; RH uncoupled walk | §2–§4 | Report reviewer questions realism → cite ASHRAE + document as simplification; Phase-5 sensitivity covers ±20 % |
| A4 | Per-room ±15 % R/C variation; 4-room class/office pattern | §2–§3 | Guide wants different split → timetable/config edit only |
| A5 | EF daily-shape multipliers (solar ×0.80, evening ×1.18) | §8 | Shape challenged → replace 24 multipliers, mean still 0.710; ablation math unaffected |
| A6 | telemetry.csv single-file-per-seed layout + run_meta.json | §6 | Phase 3 prefers per-room files → pandas groupby makes either consumable; trivial |
| A7 | No-postinstall-risk + minor pin versions | Stack | `pip install` friction on member laptops → adjust `==` pins at setup |

## Open Questions

1. **Exact Python 3.12.x patch + member laptop install path?**
   - What we know: project pins 3.12 (TF ceiling); this machine has 3.14.6.
   - Recommendation: planner adds a Wave-0 task "install Python 3.12.x + venv + `pip install -r requirements.txt`" with the `==` pins; verify `python --version` in CI/smoke test.
2. **Classroom occupancy maxima (28–32 realistic for the guide's rooms?)**
   - What we know: pattern only ("class/office").
   - Recommendation: proceed with §3 defaults; confirm with guide during Phase 1; changing maxima is a config edit.
3. **Adopt MERC MYT FY25–30 ToU redesign now or in Phase 5?**
   - What we know: classic 4-slab adders citable and simple; MYT redesign shifts to solar-hour rebate/peak surcharge.
   - Recommendation: classic slabs in Phase 1 (this research), MYT variant as Phase-5 documented option.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All sim code (TF ceiling) | ✗ (3.14.6 installed) | — | Install 3.12.x side-by-side; do NOT run Phase 1 on 3.14 |
| numpy / pandas / matplotlib | Physics + logging + plots | ✓ | 2.4.3 / 3.0.1 / 3.10.8 | Fresh 3.12 venv with `==` pins (pandas 2.x, not 3.x) |
| Mosquitto / MQTT | Nothing in Phase 1 | n/a | — | Out of scope (Phase 2) |
| TF / sklearn | Nothing in Phase 1 | n/a | — | Out of scope (Phase 4) |

**Missing dependencies with no fallback:** Python 3.12 interpreter — planner must add Wave-0 install task.
**Missing dependencies with fallback:** none.

## Validation Architecture

*(nyquist_validation: true in config — section required. Greenfield: no test infra exists.)*

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | none — see Wave 0 (`tests/` + install task) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -q` (same; suite is small and fast) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| SIM-01 | Pull-down 30→24 °C in ~20–35 min at ON | unit (thermal) | `pytest tests/test_thermal.py::test_pulldown_time -x` | ❌ Wave 0 |
| SIM-01 | Free-decay drift ~1 °C/h at ΔT=4 K; τ≈3.6 h | unit (thermal) | `pytest tests/test_thermal.py::test_decay_rate -x` | ❌ Wave 0 |
| SIM-01 | Holds 24 °C vs 38 °C outdoor at duty <100 % | unit (thermal) | `pytest tests/test_thermal.py::test_heatwave_hold -x` | ❌ Wave 0 |
| SIM-02 | Same seed → byte-identical CSV (run twice, diff) | unit (determinism) | `pytest tests/test_reproducibility.py::test_same_seed_identical -x` | ❌ Wave 0 |
| SIM-02 | Different seeds → different noise draws | unit | `pytest tests/test_reproducibility.py::test_diff_seed_differs -x` | ❌ Wave 0 |
| SIM-03 | CSV schema exact columns/order; 1440×4 rows/day | unit | `pytest tests/test_logging.py::test_schema_and_rowcount -x` | ❌ Wave 0 |
| SIM-03 | summary helper mean±std over 5 seeds | unit | `pytest tests/test_logging.py::test_summary_stats -x` | ❌ Wave 0 |
| SIM-04 | Comfort % correct on synthetic frame (incl. empty-room NaN) | unit | `pytest tests/test_metrics.py::test_comfort_pct -x` | ❌ Wave 0 |
| D-09 | grid CSV mean EF == 0.710 ± 0.001; no scalar EF in code | unit + grep | `pytest tests/test_grid.py -x` + `grep -rn "EMISSION_FACTOR\s*=\s*[0-9]" sim/` (expect empty) | ❌ Wave 0 |
| D-14 | `sim/` imports nothing from ctrl/ml/iot (boundary) | unit (import guard) | `pytest tests/test_boundaries.py -x` | ❌ Wave 0 |
| SIM-01..04 | ±20 % R/C/Q sweep changes comfort/energy < threshold (document) | smoke (slow-ish, ~1 min) | `python -m sim.sensitivity --help` run in CI | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -q` + one 1-day Pluto run `python -m sim.run --scenario weekday --days 1 --seed 0`
- **Phase gate:** full suite green + sanity numbers printed + sample CSV + determinism proof before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_thermal.py` — pull-down/decay/hold (SIM-01)
- [ ] `tests/test_reproducibility.py` — determinism (SIM-02)
- [ ] `tests/test_logging.py` — schema + summary (SIM-03)
- [ ] `tests/test_metrics.py` — comfort (SIM-04)
- [ ] `tests/test_grid.py` + `tests/test_boundaries.py` — D-09, D-14
- [ ] Framework install: `pip install pytest==8.*` in the 3.12 venv

## Security Domain

*(security_enforcement: true — section required. ASVS L1. Phase 1 has no network, auth, or secrets.)*

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No users/services in Phase 1 |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | Local-only sim process |
| V5 Input Validation | Partial | CLI args (`--seed int`, `--days >0`, scenario ∈ {weekday, weekend, heatwave}) validated with `argparse` choices/ranges; timetable blocks validated (start<end, counts ≥0) at load |
| V6 Cryptography | No | No secrets; run_meta.json holds versions/git hash only (never keys) |

**Known threat patterns:** none applicable (no transport, no untrusted input — timetable CSVs are author-controlled). Carry-forward note for Phase 2: anonymous-broker + hardcoded-credential + unvalidated-payload mistakes [CITED: PITFALLS.md Security Mistakes].

## Project Constraints (from AGENTS.md)

- Academic MM0402A project; simulation-only (no physical rooms); controllers 1–4 + metrics/graphs are the core deliverable, MPC/RL is bonus (excluded from this phase).
- Python service for forecasting + control; MQTT topics per room (Phase 2, not here); RC thermal model (this phase).
- Evaluation: multiple scenarios, several random seeds, ablations (ablations run in Phase 5; this phase builds the seed/plumbing they need).
- Stack pins honored: Python 3.12, numpy 2.x, pandas 2.x, matplotlib 3.x; paho-mqtt 2.1.0/VERSION2 noted for Phase 2 only.
- "What NOT to use" honored: no EnergyPlus, no TSDB/Grafana, no HTTP polling, no MPC/RL libs, no GPU-TF in this phase.

## Sources

### Primary (HIGH confidence)
- Kircher, Purdue ME 597 DER-buildings-1/2 lecture notes (kevinjkircher.com) — 1R1C equation, C ≈ 2.2–3.2 kWh/°C + R ≈ 2.5 °C/kW house anchors, 100 W/person-class internal gains.
- InferLab Course 12-770 Lecture-6 notes (sites.inferlab.org) — 1R1C derivation, τ bands (lightweight 2–5 h), room air C ≈ 52 kJ/K example, 2R2C fast/slow constants.
- CEA CO₂ Baseline Database v21.0 User Guide (cea.nic.in, Nov 2025) — weighted-average EF 0.710 tCO₂/MWh FY2024–25 (Table S).
- NumPy v2.5 docs (numpy.org) — `default_rng`/`Generator(PCG64)` constructor + reproducibility semantics.
- Scientific-Python blog "Best Practices for NumPy RNG" (2024, NEP 19) — no-global-RNG rule.
- MSEDCL approved tariff schedule FY24–25 — LT-II/HT-I 4-slab ToD adders (−1.50/0/+0.80/+1.10 Rs/kWh).
- Project ground truth: CONTEXT.md (01), REQUIREMENTS.md (SIM-01..04), PITFALLS.md, ARCHITECTURE.md, SUMMARY.md, STACK.md (via AGENTS.md).

### Secondary (MEDIUM confidence)
- MERC MYT Order Case 217/2024 press note + SKV case update (Mar–Apr 2025) — ToD redesign direction (solar-hour rebate, 17–24h peak); Phase-5 option.
- PyPI registry (`pip index versions`, this session) — numpy 2.5.3/2.4.x, pandas 3.0.6/2.3.3 availability.

### Tertiary (LOW confidence — see Assumptions Log)
- Exact R/C/Q/COP/light defaults, weather means, EF daily-shape multipliers — engineering judgment scaled from HIGH sources; guarded by sanity tests + ±20 % sweep.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pins verified against PyPI this session; Python 3.12 ceiling per project research.
- Architecture: HIGH — emulator-controller split + step() interface converge across Energym/PEPS/AWS-IoT sources in ARCHITECTURE.md.
- Pitfalls: HIGH — phase-relevant subset cited directly from PITFALLS.md with named studies.
- Physics defaults: MEDIUM — anchors cited, room-scale values scaled by judgment (tagged [ASSUMED], guarded by tests).

**Research date:** 2026-09-29
**Valid until:** 30 days (stable domain; re-check CEA factor annually — v22.0 for FY25–26 lands ~Nov 2026).
