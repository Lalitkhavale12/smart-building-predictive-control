# Phase 05: Carbon Economics + Full Evaluation — Research

**Researched:** 2026-09-30
**Domain:** Evaluation rigor + carbon/ToU economics on a frozen simulator/controller/forecaster stack
**Confidence:** HIGH (nearly all claims read from repo source this session; physics-of-overshoot reasoning marked where assumed)

## User Constraints (from 05-CONTEXT.md — verbatim)

### Locked Decisions
- **D-01:** Investigate before claiming: sweep C4 pre-cool/early-off thresholds + plant-size sensitivity (Q_hvac ON −3.5 kW is the suspect) and report what moves the ablation gap; tuning changes must be constructor params, never hardcoded
- **D-02:** Thresholds first (cheap, controller-owned); plant-size sensitivity as documented analysis, not a silent remodel
- **D-03:** Comfort band stays locked at 22–26 °C / 30–60 %RH for headline claims; ±1 °C sensitivity lives in this phase as analysis only
- **D-04:** Carbon/ToU shifting proven by 24h load-shape comparison (C4 vs C3): kWh moved out of 18:00–22:00 peak into solar-dip/cheap hours, with cost Rs and CO₂ kg deltas from the hourly series
- **D-05:** Shifting metric = peak-window kWh share + cost + CO₂ deltas, not just totals
- **D-06:** Full matrix: controllers {C1, C2, C3, C4-with, C4-as-C3} × scenarios {weekday, weekend, heatwave, exam-day} × PAIRED_SEEDS (0–4), mean±std, paired deltas; exam-day uses the stub timetable
- **D-07:** Ablations: with/without forecasting (C4-with vs C4-as-C3) and with/without carbon awareness (flat-EF vs hourly-EF accounting + a carbon-blind C4 variant if cheap, else accounting-only ablation documented)
- **D-08:** Accounting-only ablation minimum; carbon-blind C4 variant only if it falls out of threshold params
- **D-09:** Pareto: energy vs comfort across controllers × threshold settings; the C4 tuning sweep feeds it points
- **D-10:** All 7 graphs from one command (`python -m eval.report` or similar); dashboard screenshot is a placeholder note (screenshot itself is Phase 6)
- **D-11:** matplotlib (report figures, pinned); plotly stays in Phase 6
- **D-12:** Paired-seed statistics everywhere; headline = savings over C3 with std; no single-seed claims
- **D-13:** Sensitivity: emission factor scale, tariff scale, comfort band ±1 °C — tables, not new claims

### Agent's Discretion
Threshold sweep ranges, figure styling, report module layout, exam-day timetable expansion within the stub, whether tuning promotes a new default C4 config (only with measured win + comfort non-regression).

### Deferred Ideas (OUT OF SCOPE)
None — dashboard + screenshot (Phase 6) untouched; MPC/RL stays out of scope. No new controllers, no forecaster retraining (frozen).

### Project Constraints (from AGENTS.md)
Python 3.12 pin (TF ceiling); paho-mqtt 2.1.0 + VERSION2; NumPy 1R1C model `T_in += dt/C*((T_out-T_in)/R + Q_occ + Q_hvac)`; MQTT everywhere (QoS 1); CSV + pandas, never TSDB in v1.

## Goal

Produce every number the report grades: prove (or honestly bound) load shifting to cheap/clean hours under the hourly EF + ToU series, run the 100-run full matrix with paired statistics, explain the Phase-4 negative ablation (−12.3% weekday, −7.6% weekend, −33.1% heatwave; comfort 0% vs ~3%) with a tuning investigation, and emit the Pareto curve + all 7 graphs from one command. Forecaster, simulator, and C1–C3 are frozen; only C4 constructor params may change.

## Key Questions (answered below)

1. What are the ranked hypotheses for the negative ablation, and what concrete test moves each?
2. What metric proves load shifting given C4 currently has no price signal?
3. How is the 100-run matrix built within a minutes-scale runtime budget?
4. What are the exact ablation arms (forecast × carbon)?
5. How is the Pareto built when comfort is degenerate (0–5% for all controllers)?
6. What is each graph's data source, and what is the one-command report path?

## Findings

### F1. C4 tuning hypotheses, ranked (the intellectual core)

Measured baseline (Phase 4, paired seeds, 1-day): C4-with uses **more** energy than C4-as-C3 in all 3 scenarios; comfort 0% vs ~3%. Forecaster is good (holdout median pred 0.009 when true==0; 24.6 vs 25.7 occupied) — the gap is control physics, not forecast error. [VERIFIED: 04-03-SUMMARY.md:42-55]

Two structural facts bound the whole investigation:

- **(a) The plant is oversized for the room.** `Q_HVAC = {"OFF": 0.0, "REDUCED": -1.2, "ON": -3.5}` [VERIFIED: sim/config.py:43], room `C ≈ 0.12 kWh/K` (±15% per room) [VERIFIED: sim/config.py:28-33]. A 30-min pre-cool at −3.5 kW injects 1.75 kWh into a 0.14 kWh/K room → ~12.5 K plunge, traced live as 26.5 → 13.4 °C straight through the locked 22–26 °C band [VERIFIED: 04-03-SUMMARY.md:53-54]. Pre-cool spends energy and buys no comfort — it *destroys* comfort.
- **(b) The threshold params are currently inert.** `PredictivePolicy.__init__(self, vacancy_min=15, setback_min=60, precool_min=30, earlyoff_min=30, occ_threshold=1)` [VERIFIED: ctrl/predictive.py:113-119], but `_apply_overlay` gates only on `occ30 >= self.occ_threshold` and `occ60 < self.occ_threshold` [VERIFIED: ctrl/predictive.py:146-150] — `precool_min`/`earlyoff_min` are stored and never read. Any "sweep of pre-cool/early-off thresholds" (D-01) must first **wire** these params to behavior (e.g. `precool_min<=30` → gate on `occ_30`, `>30` → gate on `occ_60`; `earlyoff_min` → require both horizons empty for N ticks) or add new constructor params. D-01's "constructor params, never hardcoded" rule is load-bearing here.

| Rank | Hypothesis | Expected effect | Concrete test (all paired-seed, comfort on every row) |
|------|-----------|----------------|------------------------------------------------------|
| H1 | **Pre-cool at full ON overshoots through the band** — the 13 °C plunge is the dominant waste term; every false-positive arrival costs ~1.75 kWh and comfort | Largest mover (could flip weekday gap sign if false positives dominate) | **Pre-cool-to-REDUCED variant**: one-line change in the pre-cool branch (`out[room]["hvac"] = "REDUCED"` instead of `"ON"`) as a constructor param (e.g. `precool_level="REDUCED"`); −1.2 kW × 0.5 h = 0.6 kWh per pre-cool vs 1.75 kWh. Compare ON vs REDUCED pre-cool on weekday × 5 seeds |
| H2 | **Early-off too weak** — fires only when C3-hold says `ON` (`hvac == "ON"`) [VERIFIED: ctrl/predictive.py:149]; REDUCED rooms (the common empty-room state under C3) are skipped, so most easy savings stay with C3 | Small–medium positive (bounded: C3 already captures vacancy savings) | **Early-off-from-REDUCED variant**: extend the early-off branch to `hvac in ("ON","REDUCED")` when both horizons empty, constructor-gated (e.g. `earlyoff_from_reduced=True/False`); ablation vs stock C4 |
| H3 | **`occ_threshold=1` over-fires on regressed-count noise** — any predicted ≥1 person pre-cools; raising the gate cuts false positives at the cost of missed arrivals (comfort risk, watch the comfort column) | Medium; trades energy vs comfort directly → feeds Pareto | Sweep `occ_threshold ∈ {1, 3, 8}` (already a live constructor param — cheapest test in the phase); report energy + comfort per setting |
| H4 | **Heatwave false-positive cascade** — weather-shifted T_in lags shift predictions → more pre-cool firing (−33.1% gap) [VERIFIED: 04-03-SUMMARY.md:51-55] | Explains heatwave outlier specifically | Confidence-gated pre-cool: require `occ_30` AND `occ_60` both ≥ threshold (arrival persistent across horizons) vs stock `occ_30`-only; compare heatwave gap. Forecaster stays frozen — gating only, no retraining |
| H5 | **Plant oversize is structural** — even perfect thresholds push −3.5 kW through a 0.14 kWh/K room | Moves absolutes, gap likely persists qualitatively | **Documented analysis, not a remodel** (D-02): scale `Q_HVAC["ON"] ∈ {−3.5, −2.5, −1.75}` via `sim/config.py` override in a scratch script (never commit a physics change); report gap-vs-capacity table showing the finding is robust to plant size |
| H6 (null) | **Comfort-band interplay** — band unreachable for C1/C2/C3 identically (0–5%), so pre-cool cannot buy comfort any controller achieves | Expected: **no movement** — confirms structural, kills "just retune the band" | ±1 °C band recompute on saved frames (no reruns); gap invariant → report as robustness evidence |

**Promotion rule (D-agents'-discretion):** a new default C4 config only with measured mean win over stock C4 on weekday+heatwave AND comfort non-regression; otherwise the phase reports "gap characterized, stock C4 retained" — an honest negative result outscores a tuned-to-noise win (PITFALLS Pitfall 3).

### F2. Load-shifting metric design (CTL-05, D-04/D-05)

**Critical API fact:** C4's `step(self, obs, forecast=None, signals=None)` accepts `signals` but never reads it — the overlay uses only occupancy forecasts [VERIFIED: ctrl/predictive.py:121-130]. There is **no price/carbon-responsive behavior in C4 today**. Therefore:

- **Primary proof (no new policy logic, D-04-compliant): accounting-level shifting.** The hourly series already exists: EF shape solar-dip 10–16h ×0.80 / evening peak 18–23h ×1.18 / night ×1.02 / morning ×0.95, mean-normalized to the CEA v21.0 anchor 0.710 kgCO₂/kWh [VERIFIED: sim/grid.py:6-14,39,51-57]; ToU adders on Rs 9.0 base: off-peak −1.50 (22–06), morning +0.80 (09–12), evening +1.10 (18–22) [VERIFIED: sim/grid.py:42-46]. `compute_metrics` joins per-minute power against `grid.hourly_rows()` on timestamp.hour — carbon/cost come **only** from the series, no scalar constant anywhere [VERIFIED: ctrl/harness.py:32-54]. Any occupancy-driven schedule difference between C4 and C3 therefore already produces cost/CO₂ deltas. That is the D-04 deliverable.
- **Shifting metric (D-05):** per (controller, scenario) report (i) **peak-window kWh share** = kWh in 18:00–22:00 / total kWh (also 18–23h EF-peak variant — report which window once, keep it), computed from saved telemetry frames; (ii) **cost Rs** and **CO₂ kg** deltas C4−C3 from `compute_metrics`; (iii) 24h load-shape overlay plot (F-graph G1). "kWh moved" = (C3 peak-share − C4 peak-share) × C3 total. No new simulation needed — recompute from frames.
- **Honesty guard:** because C4 has no price gate, do NOT claim "carbon-responsive control" — claim "cost/CO₂ consequences of predictive scheduling under time-varying tariffs," and show the 24h shape. If a price-gated variant falls out of threshold params cheaply (e.g. block pre-cool during 18–22h unless occupied — a constructor param `precool_blackout=(18,22)`), it becomes the D-08 carbon-blind-variant counterpart; otherwise accounting-only ablation is the documented minimum (D-08).

### F3. Full-matrix design + runtime budget (EVAL-01)

- **Matrix:** controllers {C1, C2, C3, C4-with, C4-as-C3} × scenarios {weekday, weekend, heatwave, exam-day} × PAIRED_SEEDS [0,1,2,3,4] [VERIFIED: sim/config.py:74-77] = **100 runs**. Extend `ctrl/compare.py::run_matrix` (crash-resumable: existing CSVs re-read, not re-run [VERIFIED: ctrl/compare.py:70-91]) with `c4-with`/`c4-as-c3` factories (`PredictivePolicy()` + shared frozen forecaster vs `forecast=None`; fresh policy per run per the 04-03 leakage fix). `POLICY_FACTORIES` currently holds only c1/c2/c3 [VERIFIED: ctrl/compare.py:49-53]; exam-day resolves via `SCENARIO_TABLE` to the weekday stub [VERIFIED: sim/config.py:126-131] — label it "exam-day (stub=weekday)" in every table (compare.py already excludes it by default for honest labeling [VERIFIED: ctrl/compare.py:11-12]).
- **Measured runtime (this session):** 2 reactive runs = 0.50 s → **~0.25 s/run** sim-only. C4-with adds HistGB inference each 5-min tick (288 ticks/day × 6 predicts) — unmeasured, budget 1–3 s/run. Forecaster training happens **once per timetable group** (weekday-group + weekend), never in the loop [VERIFIED: ctrl/predictive.py:318-326,394-419]. **Budget: 100 runs ≈ 1–5 min + ~2 min one-time training** — no sampling-down, no parallelization needed; the tuning sweep (H1–H4 × ~3 settings ≈ 9 extra configs × 2 scenarios × 5 seeds = 90 runs) fits the same budget. Total phase compute < 30 min on a student laptop.
- **Aggregation:** `aggregate()` pattern — mean±std with ddof=1, `saved_pct` paired within (scenario, seed) then aggregated [VERIFIED: ctrl/compare.py:94-126]. Phase 5 reframes the headline as **saved-% over C3** (strongest baseline, PITFALLS Pitfall 8), keeping vs-C1 as a secondary column.

### F4. Ablation arms (EVAL-03, D-07/D-08)

| Arm | What varies | Cost | Status |
|-----|------------|------|--------|
| Forecast on/off | `forecast=forecaster` vs `forecast=None` (fresh `PredictivePolicy()` per run) | Free (same 100-run matrix) | Exists (`run_ablation` [VERIFIED: ctrl/predictive.py:394-445]); generalize to 4 scenarios |
| Carbon accounting | Recompute CO₂ on saved frames with **flat EF** (series mean 0.710 every hour) vs hourly series; identical kWh profiles must show zero shifting delta (PITFALLS Pitfall 6 verification gate) | Zero reruns — pure recompute | New, trivial (`hourly_rows(ef_base=...)` + constant-EF variant) |
| Carbon-blind C4 (conditional) | Only if it falls out of threshold params (e.g. `precool_blackout` on/off) | One extra matrix arm | D-08: build iff cheap, else document accounting-only as the ablation |

### F5. Pareto construction (EVAL-04, D-09)

Points = every controller × every tuning setting (C1, C2, C3, stock C4, H1 REDUCED pre-cool, H2 REDUCED early-off, H3 threshold sweep, H4 dual-horizon gate) on weekday mean (energy_kwh, comfort_pct). **Include C4 variants even if none beats C3 on energy** — the tradeoff is visible as a dominated-cluster plot, which is itself the report's honest finding. **Degeneracy warning:** comfort sits at 0–5% for all controllers (pre-existing sim structure), so the Pareto may be a near-vertical cluster, not a sweeping curve — plan for that visually (zoomed axes, annotate the cluster) rather than discovering it at figure time. The ±1 °C band recompute adds vertical spread analytically.

### F6. Seven-graph spec with data source per graph (D-10/D-11)

All matplotlib `Agg` backend (existing pattern [VERIFIED: ctrl/compare.py:23-28]), `results/figures/` (gitignored), one command `python -m eval.report` (new `eval/` package; `sim/`, `ctrl/`, `ml/` frozen except C4 constructor params per CONTEXT integration points):

| # | Graph (idea-doc §Graphs) | Data source (no new sim) | Notes |
|---|--------------------------|--------------------------|-------|
| G1 | 24h energy profile, baseline vs proposed | telemetry.csv hourly-mean total kW, C3 vs C4 + occupancy shade | Generalize `render_figure` [VERIFIED: ctrl/compare.py:129-160] to C4 arms + EF/price twin shade |
| G2 | Savings % by scenario and controller | summary.csv, saved-% **vs C3**, error bars = std | Headline figure; comfort column in caption/table |
| G3 | Energy vs comfort tradeoff (Pareto) | Sweep points (F5) | Highest-value figure per FEATURES research |
| G4 | Cumulative CO₂ avoided | Hourly cumsum of power/60×EF from telemetry frames | Flat-EF counterfactual line proves the series matters |
| G5 | Predicted vs actual occupancy+demand | `holdout_pred_rows` pattern [VERIFIED: ctrl/predictive.py:366-391] (frozen forecaster, committed pred CSV) | Carry from 04-03; regenerate via report cmd (04-VERIFICATION follow-up #4) |
| G6 | Ablation bar chart | Forecast arms + carbon-accounting arms, paired deltas with std | Two panels: forecast-ablation, carbon-ablation |
| G7 | Dashboard screenshot | **Placeholder note only** — screenshot is Phase 6 | D-10: emit a `.txt`/caption stub so the report build doesn't break |

### F7. Paired statistics reporting format (D-12, EVAL-01/02)

Every table row: `mean±std (n=5, paired seeds 0–4)`, std with ddof=1 (summary.py convention). `saved_pct` computed within (scenario, seed) vs C3, then aggregated — never difference-of-means. Significance: paired t-test (or Wilcoxon) across the 5 seeds per (scenario, controller-pair); p>0.05 → "no significant difference" stated in text (PITFALLS Pitfall 3). Every results table carries the comfort column (CTL-06); any run violating the band is marked, not celebrated (Pitfall 5). No bare percentages anywhere; figures carry error bars + scenario labels (UX pitfalls).

### F8. Sensitivity analysis design (D-13, EXT-01)

All three are **recomputes on saved frames — zero reruns**: (i) EF scale ×{0.8, 1.0, 1.2} via `hourly_rows(ef_base=...)` / `write_csv --ef-base` [VERIFIED: sim/grid.py:60-85,88-95]; (ii) tariff scale ditto on price (add `--price-scale` or post-multiply in report code); (iii) comfort band ±1 °C via `comfort_pct` recompute with overridden `COMFORT_T_MIN/MAX` (headline claims stay on the locked band per D-03). Output: tables, not claims. Exam-day stub expansion (if any) stays within the block-table format parsed by occupancy logic — never hardcoded times.

## Risks

| Risk | Likelihood / Impact | Mitigation (cheap) |
|------|--------------------|--------------------|
| Tuning finds nothing — gap robust across H1–H4 | Medium / Medium (phase still delivers matrix+graphs, but headline is negative) | Pre-commit to honest-negative framing: "predictive overlay costs X% under oversized-plant physics" + H5 robustness table; Pareto of dominated points is a valid contribution |
| Pareto degenerate (comfort cluster 0–5%) | High / Low | Zoomed axes + band-sensitivity spread; caption states the structural cause (H6) |
| Claiming carbon-responsiveness C4 doesn't have | Medium / High (examiner credibility) | F2 honesty guard: "consequences under ToU," not "carbon-responsive control," unless blackout-variant built |
| `results/` gitignored vs report reproducibility (04-VERIFICATION follow-up #4) | High / Low | `eval/report.py` regenerates everything (incl. forecaster training + pred CSV) from one command; commit code, never CSVs |
| Exam-day stub = weekday duplicated numbers | Certain / Low | Label "stub=weekday" in every table (established pattern); expansion optional within stub |
| Full-budget bake-off verdict pending at Phase 5 (follow-up #3) | Medium / Low | Run the 6-config × 5-seed verdict once, record `ship:` verdict; forecaster choice frozen regardless |

## Open Questions

1. **Pre-cool blackout variant (price-gated C4)?** — Q: does the planner add `precool_blackout` hours as a constructor param to create a genuine carbon-blind/policy ablation pair? What we know: D-08 allows it iff cheap; it is ~5 lines in `_apply_overlay`. Recommendation: build it — it converts the carbon ablation from accounting-only to behavioral, the highest-credibility upgrade in the phase.
2. **Sweep ranges for H1–H4** — agent's discretion; recommended defaults: `precool_level ∈ {ON, REDUCED}`, `occ_threshold ∈ {1,3,8}`, `earlyoff_from_reduced ∈ {F,F,T}`, dual-horizon gate on/off. ~9 configs, all within budget.
3. **CEA re-check** — grid.py pins v21.0/FY24-25 with a v22.0-due-~Nov-2026 note [VERIFIED: sim/grid.py:6-9]; if v22.0 is out, EF-scale sensitivity already covers the delta — no blocking lookup needed.

## Sources

- Primary (HIGH): `ctrl/predictive.py:113-151` (constructor + overlay law), `sim/config.py:40-77` (plant, band, seeds), `sim/grid.py:6-75` (EF/ToU construction), `ctrl/harness.py:32-71` + `ctrl/compare.py:70-160` (metrics, matrix, figure patterns), `04-03-SUMMARY.md:42-55` (measured gap + traced plunge), `04-VERIFICATION.md:20-31` (pass rationale + 4 follow-ups), PITFALLS.md Pitfalls 3/5/6/8 (paired seeds, comfort gate, hourly-EF, strongest baseline).
- Secondary (MEDIUM): idea-doc Experiments + Graphs sections (matrix shape, 7-graph list); SUMMARY.md Phase-5 paragraph (economics-then-rigor ordering).
- Tertiary (LOW): runtime projection for C4-with inference (1–3 s/run) — unmeasured this session; planner should time one C4 run before finalizing the sweep size.

## Metadata

- Standard stack: HIGH — no new libraries; `eval/` uses matplotlib + numpy + pandas already in repo.
- Architecture: HIGH — extends proven `run_matrix`/`aggregate`/`render_figure` patterns; one new package.
- Pitfalls: HIGH — every credibility trap maps to an existing, tested guard.
- **Valid until:** stable (sim frozen) — 30 days.
