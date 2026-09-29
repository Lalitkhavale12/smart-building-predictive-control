# Pitfalls Research

**Domain:** Carbon- and comfort-aware predictive control for smart buildings (IoT simulation + ML forecasting + academic evaluation)
**Researched:** 2026-09-29
**Confidence:** HIGH (claims cross-checked across occupancy-ML literature, building-simulation calibration studies, MPC field trials, carbon-aware computing research, and forecasting-evaluation methodology)

## Critical Pitfalls

### Pitfall 1: Temporal data leakage in occupancy/demand forecasting

**What goes wrong:**
The forecaster reports excellent accuracy (often 95%+ or high R²) on a random train-test split, but the model collapses on genuinely unseen future data. Environmental time-series data (temperature, CO₂, humidity) is strongly autocorrelated, so a random split places temporally adjacent — nearly identical — samples on both sides of the split. The model memorizes neighbours instead of learning to forecast. One cross-scenario study found models scoring 0.95+ accuracy under random splits dropped to 0.61–0.88 under walk-forward evaluation, with the gap entirely attributable to protocol, not model quality.

**Why it happens:**
Standard ML tutorials teach `train_test_split(shuffle=True)` as the default. Team members coming from non-time-series ML backgrounds apply it unthinkingly to sensor streams. Related variants: scaling/imputation fitted on the whole dataset before splitting; feature selection on full data; overlapping sliding windows leaking across the split boundary; using same-day future context (e.g., CO₂ decay after departure) as a "feature" for predicting that departure.

**How to avoid:**
- Chronological split only: train on the first 70–80% of the timeline, test on the final 20–30%. Never shuffle.
- Use walk-forward / expanding-window validation (e.g., 4 folds, each test block strictly after all its training data) for model selection.
- Fit every preprocessing step (scaler, imputer, feature selector) on the training partition only, then apply to test.
- When windowing the series (e.g., window of 5 steps → next-step label), split by time first, then window within each partition so no window straddles the boundary.
- Fill out a leakage checklist per model: (a) is any test timestamp earlier than a training timestamp? (b) was any preprocessing statistic computed with test data? (c) is every feature available at prediction time in deployment?

**Warning signs:**
- Test accuracy suspiciously close to train accuracy on noisy sensor data; R² > 0.95 on occupancy from environmental sensors alone.
- LSTM dramatically beats baselines only under random splits; gap vanishes under chronological split.
- Features include same-timestep CO₂/temperature readings that are *consequences* of occupancy rather than predictors (proxy-for-outcome leakage).
- Anyone on the team says "we shuffled to make it robust."

**Phase to address:**
ML forecasting phase (model training + evaluation design). Must be fixed before the controller phase consumes forecasts — a leaky forecaster makes the controller look good in simulation for entirely fake reasons.

---

### Pitfall 2: Synthetic-only validation — the simulator-to-reality gap

**What goes wrong:**
All results come from the team's own simulator, whose occupancy timetables, weather noise, and sensor characteristics were invented by the same people who built the controller. The proposed controller wins because it implicitly exploits simulator regularities (e.g., occupancy always starts exactly at 9:00, noise is Gaussian and mild). The report claims generality that evaporates on any real building trace. Examiners specifically discount "tested on our own synthetic data only" as evidence.

**Why it happens:**
Building the simulator first creates a closed loop: data generation and control evaluation share assumptions. Public datasets (UCI Appliances, ASHRAE) require schema wrangling, missing-value handling, and timetable mapping, so teams postpone "validation on real data" until the end — then run out of time and ship synthetic-only.

**How to avoid:**
- Schedule public-dataset validation as a first-class deliverable of the ML phase, not a stretch item: at minimum, the forecaster (RF/GB + LSTM) must be trained/evaluated on UCI Appliances Energy Prediction or an ASHRAE subset with MAE/RMSE/R² reported.
- Keep the simulator honest: inject sensor noise, packet-drop gaps, irregular occupancy deviations (late arrivals, exam-day surges), and heatwave weather the controller never saw during tuning.
- Report both numbers side by side: synthetic-simulator accuracy AND public-dataset accuracy. A gap is expected and honest; hiding it is the pitfall.
- Use transfer thinking: if a model trained on synthetic data is tested on real traces (even zero-shot), report that number — it is the strongest credibility signal available without hardware.

**Warning signs:**
- All graphs use perfectly smooth 24h profiles with sharp timetable edges and no missing data.
- The word "ASHRAE" or "UCI" appears in the proposal but no dataset file exists in the repo by mid-project.
- Simulator occupancy is a deterministic function of hour-of-day (a lookup table), making forecasting trivially easy.

**Phase to address:**
ML forecasting phase (dataset acquisition in week 1 of that phase) + controller evaluation phase (robustness scenarios). Roadmap must order "download and baseline public dataset" before "tune controller."

---

### Pitfall 3: Single-seed results presented as conclusions

**What goes wrong:**
The team runs each scenario once, the proposed controller beats fixed-schedule by 12%, and the report declares victory. But neural-network weight initialization, simulator noise draws, and stochastic occupancy deviations all inject variance — published studies show seed-to-seed swings of 2%+ even for well-tuned models, enough to flip "proposed beats baseline" when the true effect is small. A single run cannot distinguish a real improvement from a lucky draw, and cherry-picked seeds can manufacture significance out of nothing.

**Why it happens:**
Single runs are fast; multi-seed runs feel like "extra credit." LSTM training is slow, so teams train once and move on. Nobody runs a statistical test because the syllabus never required one.

**How to avoid:**
- Fix a predefined seed set (e.g., seeds 0–4, minimum 5; 10 if compute allows) and run *every* controller × scenario combination on all of them. Same seeds for all controllers — paired comparison.
- Report mean ± std everywhere (tables and bar charts with error bars). Never report a bare percentage.
- Apply a basic significance check (paired t-test or Wilcoxon across seeds) before claiming "X beats Y." If p > 0.05, say "no significant difference" — that honesty scores higher than a fragile win.
- Set all seeds explicitly (Python `random`, NumPy, TensorFlow/PyTorch, simulator RNG) and log them; "random" runs that can't be reproduced are worthless as evidence.

**Warning signs:**
- Results tables show integers or one-decimal percentages with no ± values.
- The savings margin (e.g., 3–5%) is smaller than the unreported run-to-run variance.
- Code has no `seed` argument anywhere; rerunning gives different numbers.

**Phase to address:**
Controller evaluation phase — bake "seed loop + stats" into the experiment harness before the first comparison runs, not as a post-hoc rerun.

---

### Pitfall 4: Reaching for full MPC/RL when a predictive rule-based controller suffices

**What goes wrong:**
The team spends half the project building a Model Predictive Control optimizer or RL agent: formulating the optimization, fighting solver convergence, tuning reward shaping — and ends with an unstable controller, no baselines, and no graphs. Field evidence is unambiguous: simplified/rule-extracted predictive controllers achieve 90–95% of full MPC's energy savings at a fraction of the complexity, and MPC's edge depends on an accurate building model the team doesn't have. Commercial buildings still run on rules/PID for exactly this reason (expertise and robustness gap).

**Why it happens:**
MPC/RL sounds more impressive in a report title. Tutorials make `cvxpy`/`stable-baselines3` look plug-and-play, hiding the modelling-accuracy prerequisite: MPC with a poor building model performs *worse* than simple rules (documented 2–6× comfort degradation with under-modelled controllers). RL additionally needs reward design, long training, and stability analysis nobody has time for.

**How to avoid:**
- Follow the project scope: controllers 1–4 (fixed, occupancy-rule, setback, predictive rule-based) are the deliverable; MPC/RL is explicitly a stretch goal to cut under time pressure.
- Build the predictive contribution as pre-cool-before-arrival + early-off-before-departure driven by the forecaster — that *is* predictive control, and it is defensible, explainable, and syllabus-mappable.
- If MPC curiosity persists, cap it: one room, one scenario, reported as "exploratory comparison," never on the critical path.
- Kill criterion: if the optimizer doesn't beat the predictive rule-based controller on the weekday scenario by mid-project, delete it and reinvest the time in ablations and graphs.

**Warning signs:**
- Week 3+ and no baseline controller runs yet because "the MPC isn't converging."
- Controller code imports an optimization/RL library but has no fallback if the solver fails at runtime.
- Team can't explain in one sentence what the controller does without equations.

**Phase to address:**
Roadmap scoping (phase 0 decision: MPC is stretch, locked) + controller phase (implement baselines 1–3 *before* controller 4, so a cut MPC still leaves a complete project).

---

### Pitfall 5: Comfort as an afterthought — optimizing energy alone

**What goes wrong:**
The controller saves 30% energy by letting occupied rooms drift to 29 °C / 75% RH, and the report celebrates the savings while comfort is a footnote — or comfort is "measured" only as unoccupied-setback compliance. Any examiner (or occupant) immediately rejects the result: an air conditioner that is off during a lecture saves 100% energy and provides 0% service. Energy-vs-comfort is the central tradeoff of this project; reporting one side is reporting nothing.

**Why it happens:**
Energy (kWh) is a single scalar that goes down satisfyingly; comfort is a constraint that makes the optimization harder and the savings smaller. Teams tune thresholds to maximize the headline savings number, then backfill a comfort claim.

**How to avoid:**
- Define the comfort metric first (e.g., % of occupied time within 22–26 °C and 30–60% RH) and gate every result on it: any controller run violating the comfort floor is marked failed, not celebrated.
- Make the Pareto energy-vs-comfort curve a required graph — it turns the tradeoff from an embarrassment into the project's main analytical contribution.
- Run a comfort-band sensitivity analysis (e.g., ±1 °C bands) to show the tradeoff is characterized, not accidental.
- Include at least one "adversarial" scenario for comfort (heatwave) where naive aggressive saving visibly breaks comfort and the proposed controller holds it.

**Warning signs:**
- Savings % is reported without any comfort number in the same table row.
- Comfort band chosen after seeing results ("22–28 °C makes our numbers pass").
- Heatwave scenario missing or showing 100% comfort because the scenario is too mild.

**Phase to address:**
Simulator phase (comfort metric + band implemented as a first-class output of the thermal model) and enforced in the evaluation phase (every comparison table has both columns).

---

### Pitfall 6: Constant CO₂ factor and naive carbon accounting

**What goes wrong:**
CO₂ avoided is computed as kWh × one constant (e.g., a single CEA annual-average figure), which makes "carbon-aware" load shifting mathematically meaningless — shifting a kWh from 7 PM to 2 PM saves exactly zero under a constant factor, so the ablation "with vs without carbon awareness" shows nothing (or the team fakes differentiation). Deeper trap: mixing average vs marginal emission signals without understanding them — research across 65 grids shows the two signals are often *negatively* correlated, so optimizing on the wrong one can increase the footprint you claim to reduce.

**Why it happens:**
The CEA publishes a single annual grid-average factor that is easy to cite; constructing an hourly time-varying profile takes work. Tutorials present "CO₂ = energy × factor" as one line, hiding that the *time variation* is the entire point of carbon-aware scheduling.

**How to avoid:**
- Build an hourly emission-factor profile from day one (e.g., CEA annual figure modulated by a realistic daily shape: higher during evening fossil peak, lower during solar hours; document the construction transparently as a modelled approximation).
- Keep accounting and signaling consistent and state the choice: use the *same* time-varying average-factor series for both the controller's shifting decisions and the reported CO₂ math. Don't claim marginal-emissions rigor you can't source for the Indian grid.
- Make the carbon ablation real: identical controller with flat factor vs time-varying factor, showing the shifting behaviour difference in a 24h load profile plot.
- Cite the exact CEA figure (value, year, publication) — examiners check this.

**Warning signs:**
- `EMISSION_FACTOR = 0.82` (or similar) as a single constant anywhere in the controller or metrics code.
- Ablation "with/without carbon awareness" shows identical kWh profiles (shifting can't exist under a flat factor).
- Report mixes "marginal" and "average" terminology without defining which is used.

**Phase to address:**
Simulator/metrics phase (hourly factor series + ToU tariff built alongside the thermal model) and verified in the evaluation phase (ablation plot must show shifted load).

---

### Pitfall 7: MQTT pipeline that works in demo and dies in evaluation

**What goes wrong:**
The IoT pipeline (ESP32 → MQTT → Python controller → dashboard) works flawlessly in a 5-minute supervised demo, then drops messages, duplicates actuation commands, or silently disconnects during the 24h scenario runs that actually generate results. Root causes are classic and all documented: QoS 0 (fire-and-forget) as default with ~2% packet loss and no redelivery; no Last-Will / retained messages so dashboard shows stale "comfortable" readings from a dead node; no reconnection logic so one broker hiccup ends the run; blocking controller code that can't keep up when all rooms publish simultaneously.

**Why it happens:**
Tutorials show the happy path: connect, publish in a loop, subscribe, done. QoS levels, retained flags, keep-alive tuning, and reconnect loops are "advanced" sections nobody reads. Wokwi simulation hides real network failure modes, so the fragility is invisible until long runs.

**How to avoid:**
- Use QoS 1 (at-least-once) for sensor publishes and actuation commands — measured sweet spot (~99% delivery at ~150 ms latency); design the controller to be idempotent so duplicates are harmless. Never ship QoS 0 for actuation.
- Set Last-Will-and-Testament per room node + retained "online/offline" status topics so failures are visible on the dashboard instead of silent.
- Implement reconnect with backoff in both publisher and subscriber; log every disconnect/reconnect with timestamps as evidence for the robustness experiment.
- Decouple ingestion from control: MQTT subscriber writes to a buffer/store; the controller reads the latest values on its tick. A slow controller must never block message intake.
- Fault-injection test early: kill one room node mid-run and drop 5–10% of packets; the robustness scenario in the report must be a test you actually ran, with numbers.

**Warning signs:**
- Code has no `on_disconnect` handler, no reconnect loop, no QoS argument (defaults to 0).
- Dashboard has no "last updated" timestamp per room — stale data is indistinguishable from live data.
- Longest continuous run so far is under an hour; 24h scenario runs untested.

**Phase to address:**
IoT pipeline phase (QoS/reconnect/LWT as acceptance criteria, not polish) + evaluation phase (sensor-failure and packet-loss experiments with measured degradation numbers).

---

### Pitfall 8: Strawman baselines that flatter the proposed controller

**What goes wrong:**
The proposed controller is compared only against a fixed schedule (HVAC blasting empty rooms all night), guaranteeing a headline-grabbing 30–40% saving that any competent engineer would beat with a ₹200 timer switch. The report's contribution evaporates the moment someone asks "but did you try turning it off when empty?" — a simple 15-minute vacancy rule captures most of the easy savings, and the *marginal* gain of prediction over that rule is the real measure of the ML's value.

**Why it happens:**
Fixed schedule is the easiest baseline to implement and produces the biggest savings delta. Each additional baseline is more code, so teams stop at one.

**How to avoid:**
- Implement all three non-ML baselines from the idea doc (fixed schedule, occupancy-rule "off if empty 15 min", setpoint setback) *before* the proposed controller — they are the yardstick, not optional extras.
- Frame the headline result as savings-over-strongest-baseline, not savings-over-fixed. "8% over occupancy-rule + comfort held" is a stronger, more credible claim than "35% over fixed."
- The ablation with/without forecasting directly quantifies what prediction adds on top of reactive rules — this is the project's core ML justification; protect it.

**Warning signs:**
- Only one baseline exists by evaluation time; "occupancy rule" is described in the proposal but absent from results.
- Savings % looks too good (>30%) without a tradeoff curve to contextualize it.
- Ablation table missing the "reactive rule vs predictive" row.

**Phase to address:**
Controller phase ordering (baselines 1–3 gated before controller 4) + evaluation phase (ablation + strongest-baseline framing in every graph).

---

### Pitfall 9: Uncalibrated, over-detailed thermal model (equifinality trap)

**What goes wrong:**
The team builds an elaborate multi-parameter RC model (separate R/C per wall, window, air mass, furniture…) with values copied fromvikan arbitrary datasheet or guessed, never sanity-checked. Calibration literature shows the trap precisely: many different parameter sets fit one calibration period equally well (equifinality) yet diverge up to 10× in RMSE outside it; occupant behaviour and internal gains dominate over envelope precision in insulated buildings. An uncalibrated fancy model is *less* trustworthy than a simple sanity-checked one — and controller results built on it inherit the fiction.

**Why it happens:**
Physics equations feel rigorous, so "more detail = more accurate" goes unquestioned. Sanity-checking (does the room cool at a plausible rate with AC off? does pre-cooling take ~30 min, not 3?) feels like non-progress versus adding features.

**How to avoid:**
- Start with the simplest RC model that shows correct qualitative behaviour (exponential approach to setpoint, occupancy heat gain, outdoor coupling), and validate behaviour before adding detail: free-floating overnight decay rate, pull-down time from 30→24 °C, steady-state offset — all plausible?
- Fix parameters to documented values with sources (cite them), and run a ±20% sensitivity sweep on the 2–3 most influential ones (wall R, air capacitance, HVAC power) showing results don't hinge on exact guesses.
- Prefer modelling effort on occupancy/internal-gain realism over envelope detail — calibration studies consistently find user behaviour dominates in well-insulated buildings.
- Validate the model outside its "comfort zone": a weekday-tuned model must still behave sanely in the heatwave scenario; if it doesn't, the model — not the controller — is wrong.

**Warning signs:**
- Room reaches setpoint in 2 minutes or 6 hours (either is unphysical for a classroom with a split AC).
- No one can state the model's thermal time constant; parameters have no cited source.
- Adding model detail changed results dramatically — sign of an unidentified, over-flexible model.

**Phase to address:**
Simulator phase (behavioural sanity checks + sensitivity sweep as exit criteria before any ML/controller work consumes simulator output).

---

### Pitfall 10: Unfair ML bake-off — LSTM beats RF by experimental design, not merit

**What goes wrong:**
The report shows LSTM crushing Random Forest, but the comparison was rigged accidentally: RF trained on raw flattened windows while LSTM got engineered sequences; only LSTM got hyperparameter tuning; RF evaluated with default depth; or the naive persistence baseline ("predict current occupancy for +30 min") is missing entirely — and persistence is brutally strong for slow-changing occupancy, sometimes unbeatable at short horizons. Time-series literature repeatedly finds fancy architectures' "wins" vanish under standardized evaluation with proper baselines and multiple seeds.

**Why it happens:**
LSTM is the presumed-sophisticated method, so effort flows to it; RF is treated as a checkbox baseline. Nobody implements persistence because it feels too dumb to include — which is exactly why its absence is suspicious to evaluators.

**How to avoid:**
- Mandatory baseline set for the forecaster: persistence/naive + RF/GB with a real hyperparameter search + LSTM. Same chronological splits, same horizons (30 and 60 min), same metrics (MAE/RMSE/R²) for all.
- Tune all models with comparable effort (grid/random search with a fixed budget each); report the search space briefly so the comparison is auditable.
- Report per-horizon results separately — prediction degrades with horizon, and a model winning at 30 min but losing at 60 min is normal, informative, and honest.
- If LSTM wins by <2–3% with overlapping std across seeds, say so and prefer the simpler model (deployment cost, inference latency, explainability all favour RF/GB on ESP32-adjacent hardware).

**Warning signs:**
- RF hyperparameters are all defaults (`RandomForestRegressor()` with no arguments) while LSTM has a tuned architecture table.
- No persistence/naive row in the results table.
- Only one horizon reported, or metrics averaged across horizons hiding degradation.

**Phase to address:**
ML forecasting phase (evaluation harness with all baselines + fixed tuning budget defined before training runs).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoded timetables/weather in simulator code | Simulator runs day one | Can't add scenarios; tuning constants to flatter results | Never — config files/Day-type tables from the start |
| Single comfort band, no sensitivity run | One less experiment | "Band chosen to pass" suspicion; tradeoff uncharacterized | Never — sensitivity is a required graph |
| Dashboard reads simulator state directly, bypassing MQTT | Pretty screenshot fast | IoT pipeline unproven; demo and results diverge | Temporary during pipeline bring-up only; dashboard must consume MQTT by evaluation phase |
| Jupyter-only ML code, no scripts | Fast experimentation | Controller can't reuse forecaster; results unreproducible | Acceptable for exploration; refactor to `train.py`/`predict.py` before controller integration |
| Wokwi ESP32 firmware hand-tweaked per demo | Demo works | Firmware/simulator drift; 24h runs use different code than demoed | Never — one firmware version, version-controlled, used for all runs |
| Flat annual CO₂ factor "temporarily" | Metrics code runs | Carbon ablation meaningless (see Pitfall 6) | Never — hourly series from day one, even if approximate |
| Skipping requirements.txt/environment pinning | No env friction today | Teammate's laptop + examiner's machine can't reproduce; "works on my machine" | Never — pin env in week 1 (4 members = 4 machines minimum) |
| Saving only the best-seed results | Clean-looking tables | Fabricated significance; collapses under questioning | Never |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Wokwi ESP32 → Mosquitto | Assuming virtual serial/WiFi never drops; no reconnect in firmware loop | Reconnect logic + publish retry in firmware; treat virtual link as fallible, log disconnects |
| Mosquitto broker config | Default anonymous, no persistence, default keep-alive; broker state loss on restart kills long runs | Explicit mosquitto.conf (persistence, keep-alive, max inflight); document QoS choice per topic |
| MQTT → Python controller | Blocking `loop_forever` with control logic inside the message callback; one slow tick stalls intake | Async/threaded intake into a timestamped buffer; controller ticks on schedule reading latest values |
| Python forecaster → controller | Loading a `.pkl`/`.h5` trained on differently-scaled features; silent shape/scale mismatch | Save scaler + model together; assert feature schema at load; integration test with known input→output |
| Controller → ThingSpeak/Blynk | Pushing every tick; hitting free-tier rate limits (ThingSpeak ~15 s min interval) mid-demo | Downsample dashboard pushes (e.g., 1/min aggregates); buffer locally, dashboard is a view not the store |
| Simulator ↔ MQTT topics | Topic naming invented per room ad hoc (`room1/temp` vs `building/room-01/temperature`) | Single topic-namespace doc (`building/{room}/{metric}`) agreed in pipeline phase; all publishers/subscribers conform |
| UCI/ASHRAE dataset → forecaster | Treating public data as drop-in (different granularity, missing occupancy ground truth) | Explicit adapter: resampling, occupancy-proxy definition, documented assumptions; report them |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| LSTM retrained from scratch per experiment | Overnight runs; teammates blocked waiting for weights | Train once per config, version the artifact, reuse across controller experiments | Breaks immediately with 4 members sharing one GPU-less workflow |
| 1-second MQTT publish from every room × full logging | Broker/ThingSpeak throttling; multi-GB CSV logs | 30–60 s publish cadence (thermal dynamics are slow; 1 s buys nothing); log aggregates | Breaks at 24h multi-room runs and dashboard rate limits |
| Monolithic 24h simulation in one process tick loop | One crash loses the whole run; no partial results | Checkpoint metrics per simulated hour; resume support; per-scenario output files | Breaks on first overnight heatwave run that dies at hour 20 |
| Hyperparameter grid explosion (models × horizons × scenarios) | Experiment matrix never finishes; results cherry-picked from partial runs | Fixed small search budget; train forecaster once, evaluate controller across scenarios | Breaks in ML phase week 2 when 100+ combos are queued |
| ThingSpeak/Blynk as primary data store | Gaps when rate-limited; can't recompute metrics | Local CSV/SQLite is the source of truth; dashboard is a display layer only | Breaks the moment metrics need recomputation for the report |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Anonymous Mosquitto broker, no ACLs/TLS (even on LAN/demo network) | Anyone on network can publish fake sensor data or actuation commands; syllabus Unit 3 explicitly covers MQTT security | Enable username/password + ACLs per topic from setup; document TLS as production step; write the security note the syllabus requires |
| Hardcoded broker credentials / API keys (ThingSpeak/Blynk) in committed code | Keys leak via repo sharing with guide/examiners; Blynk quota abuse | Env vars / `.env` (gitignored) from day one; rotate any key that was ever committed |
| No input validation on MQTT payloads (trusting temperature = −999 or 500 °C) | Poisoned metrics, controller acting on garbage (full cooling on a corrupt reading) | Range-check + clamp + flag; corrupt readings logged and excluded, with fallback to last-good value |
| Dashboard publicly writable (Blynk/ThingSpeak channel keys shared) | Strangers can inject data during the demo | Read-only public view; write keys never in screenshots/report; separate demo credentials |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Dashboard as screenshot-afterthought (built the night before submission) | Examiners see raw MQTT logs instead of live energy/comfort/savings; weakest demo component | Dashboard running from pipeline phase; screenshot is a capture of a living system, not a construction project |
| Dashboard shows only instantaneous values, no baselines or savings | Viewer can't tell if the system is doing anything useful | Always-on comparison widgets: baseline vs proposed kWh, cumulative CO₂ avoided, comfort % — the report's graphs, live |
| No per-room "last updated" / online status | Dead sensor looks identical to comfortable room (see Pitfall 7) | Status indicator per room with staleness warning; ties directly to the robustness story |
| Graphs in report without error bars or scenario labels | Reader can't judge significance or generality | Every comparative plot: mean ± std, scenario-named, strongest-baseline framing |

## "Looks Done But Isn't" Checklist

- [ ] **Forecaster:** High R² reported — verify chronological split + walk-forward protocol, not shuffled (Pitfall 1)
- [ ] **Forecaster:** LSTM beats RF — verify equal tuning budgets + persistence baseline present (Pitfall 10)
- [ ] **Controller:** Big savings % — verify comfort column in the same table is within band (Pitfall 5)
- [ ] **Carbon:** CO₂ numbers present — verify hourly time-varying factor, not a constant, and ablation shows shifted load (Pitfall 6)
- [ ] **Baselines:** Comparison table — verify occupancy-rule and setback baselines exist, not just fixed schedule (Pitfall 8)
- [ ] **Statistics:** Results tables — verify mean ± std over ≥5 seeds with significance noted (Pitfall 3)
- [ ] **Public data:** "Validated on UCI/ASHRAE" claimed — verify dataset files + results in repo, not just proposal text (Pitfall 2)
- [ ] **IoT robustness:** "Fault tolerant" claimed — verify kill-a-node / packet-loss test was actually run with numbers (Pitfall 7)
- [ ] **Thermal model:** Simulator runs — verify pull-down/decay sanity numbers documented, not just code that executes (Pitfall 9)
- [ ] **MPC/RL:** Bonus controller present — verify it didn't starve baselines 1–4 of time; core deliverable complete without it (Pitfall 4)
- [ ] **Dashboard:** Screenshot in report — verify it consumes live MQTT data with timestamps, not simulator state (Tech debt #3)
- [ ] **Reproducibility:** Repo shared — verify pinned env + seeds + one-command run reproduces headline numbers

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Temporal leakage discovered late | MEDIUM | Re-split chronologically, refit scalers in-fold, rerun forecaster + all downstream controller numbers; report corrected (lower) metrics honestly — corrected-honest beats inflated-fake |
| Synthetic-only at report time | MEDIUM | Minimum viable rescue: run forecaster on UCI Appliances as-is, report one honest table + limitation paragraph; even partial real-data validation restores credibility |
| Single-seed results challenged | LOW | Rerun the frozen experiment harness on seeds 0–4 (no code changes needed if harness is seeded); add ± std + significance lines to tables |
| MPC rabbit hole consumed weeks | HIGH | Hard cut: freeze MPC branch, ship predictive rule-based controller; reinvest remaining time in baselines + ablations which score more reliably |
| Comfort violations in saved runs | MEDIUM | Tighten controller thresholds, rerun affected scenarios; add Pareto curve showing the tradeoff was explored, not stumbled into |
| Constant-factor carbon math | LOW | Swap in hourly factor series, recompute CO₂ column + ablation plot; half a day's work if metrics code is centralized |
| Fragile MQTT failing long runs | MEDIUM | Add QoS 1 + reconnect + buffering (1–2 days); rerun 24h scenarios; convert the failure into the robustness experiment narrative |
| Strawman-only baselines | LOW–MEDIUM | Implement occupancy-rule + setback (days, not weeks); reframe headline as vs-strongest-baseline |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 — Temporal leakage | ML forecasting phase (evaluation protocol first) | Review: test timestamps all after train; scalers fit train-only; walk-forward code present |
| 2 — Synthetic-only validation | ML forecasting phase (dataset acquisition week 1) | Review: public dataset files + results table in repo before controller tuning starts |
| 3 — Single-seed results | Controller evaluation phase (seeded harness) | Review: every results table shows mean ± std, n≥5 seeds logged |
| 4 — MPC/RL overreach | Scoping/roadmap (stretch-gate) + controller phase order | Review: baselines 1–3 running before any MPC code; kill-criterion date on calendar |
| 5 — Comfort afterthought | Simulator phase (metric implementation) + evaluation | Review: all comparison tables have comfort column; Pareto graph exists |
| 6 — Constant CO₂ factor | Simulator/metrics phase (hourly series) | Review: no scalar EMISSION_FACTOR in code; ablation shows load shift |
| 7 — MQTT fragility | IoT pipeline phase (QoS/reconnect acceptance) | Review: kill-a-node + packet-loss test run with logged numbers |
| 8 — Strawman baselines | Controller phase (baselines-before-contribution gate) | Review: baselines 1–3 merged before controller 4 work begins |
| 9 — Uncalibrated thermal model | Simulator phase (sanity-check exit criteria) | Review: documented pull-down/decay numbers + ±20% sensitivity sweep |
| 10 — Unfair ML bake-off | ML forecasting phase (harness with all baselines) | Review: persistence row present; tuning budgets documented per model |

## Sources

- Kapoor & Narayanan — "Leakage and the reproducibility crisis in ML-based science" (Patterns/Cell 2023): taxonomy of 8 leakage types across 294 papers; model-info-sheet remedy. [HIGH]
- Weng et al. (2026) — cross-scenario occupancy detection across 5 building types: walk-forward protocol, random-split inflation (0.95+ → 0.61–0.88), CO₂/illuminance as top predictors, scenario-dependence. [HIGH]
- Tekler — deep-learning occupancy prediction across space types: chronological 80/20 split to avoid leakage, window/horizon design tradeoffs. [MEDIUM]
- Stjelja, Jokisalo & Kosonen — transfer learning for occupancy prediction: ground-truth collection cost, model robustness across rooms/conditions, accuracy-vs-practicality gap. [MEDIUM]
- Straub et al. collective calibration exercise (Energies 2023): equifinality, RMSE inflating up to 10.8× outside calibration period, occupant behaviour dominating envelope precision, validation-period criticality. [HIGH]
- ORNL/Goldwasser — EnergyPlus time-series calibration best practices: timestamp alignment, anomaly exclusion, warm-up initialization, component-level validation. [MEDIUM]
- Bursill (Carleton thesis) + related sMPC studies: simplified/rule-extracted predictive control achieving 94–95% of full MPC savings; MPC adoption barriers (expertise, modelling cost, PLC limits). [HIGH]
- Picard et al. via KU Leuven review: MPC controller-model order requirements (30+ states), mismatch degrading comfort 2–6×, grey-box MPC underperforming white-box by ~50%. [MEDIUM]
- Sukprasert et al. (2024) + Electricity Maps analysis: average vs marginal carbon signals negatively correlated in 55.4% of 65 regions; optimizing on one can increase the other's footprint. [HIGH]
- Bergmeir (2023) "Forecast evaluation for data scientists": MAPE misuse, naive-benchmark necessity, leakage via preprocessing, single-origin anecdotes, loss/metric alignment. [HIGH]
- Shchur et al. / ACM study on seed variance: 2%+ swings from initialization alone, cherry-picking significance, ≥10–25 seeds for small effects, predefined seed sets + non-parametric tests. [HIGH]
- "No champions in long-term time-series forecasting" (2025, 3,500+ networks): no architecture dominates under standardized evaluation; small setup changes flip rankings. [MEDIUM]
- Gruener et al. (MAYHEM resilience testing): MQTT QoS 0 robust only to minor loss; clustered-broker HA ≠ no-loss; QoS/latency tradeoffs measured. [MEDIUM]
- Palmese et al. (2022) adaptive MQTT-SN QoS: QoS 2 latencies 2 orders of magnitude above QoS 0 under loss; QoS 1 as the practical balance. [MEDIUM]
- MDPI Sensors (2025) MQTT livestock-housing study: measured QoS 0/1/2 comparison (QoS 1: 99.2% delivery, ~150 ms); scalability cliff at ~15–20 nodes. [MEDIUM]

---
*Pitfalls research for: Carbon- and Comfort-Aware Predictive Control for Smart Buildings*
*Researched: 2026-09-29*
