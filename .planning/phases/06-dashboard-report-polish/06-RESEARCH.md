# Phase 06: Dashboard + Report Polish — Research

**Researched:** 2026-09-30
**Domain:** Streamlit CSV/PNG viewer + report polish docs (no new science)
**Confidence:** HIGH (all data bindings read from disk this session; env versions verified via `python -c import`)

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Streamlit app `dashboard/app.py`: live-updating energy/comfort/savings view per scenario/controller from `results/` CSVs + embedded Phase-5 figures (G1–G6); filters for scenario + controller + seed
- **D-02:** Single page with sections (overview, 24h shape, savings, Pareto, ablation); multi-page is polish nobody grades
- **D-03:** Dashboard reads committed-code outputs only: `results/report_tables/*.csv` + `results/figures/*.png` + `results/full_matrix/summary.csv`; never recomputes the matrix, never imports ML training paths
- **D-04:** No live sim behind dashboard; display saved report data; one "run small demo" button allowed only if it calls `sim.run` with fixed seed and finishes in seconds
- **D-05:** Protocol note `docs/protocols.md`: MQTT vs HTTP vs CoAP table (overhead, QoS, suitability) with choice rationale (why MQTT won here) + MQTT security note (anonymous lab broker → commented TLS block in mosquitto.conf → production checklist)
- **D-06:** One page, syllabus-mapped (Unit 4 + Tutorials); the table is the deliverable
- **D-07:** One-command reproduction: `README.md` pinned env (Python 3.14 verified working + 3.12 note) + `requirements.txt` complete (streamlit/plotly pinned) + `python -m eval.report` regenerates all figures; a `REPRODUCE.md` or README section lists the exact command sequence with expected outputs
- **D-08:** Real screenshot: run `streamlit run dashboard/app.py`, capture PNG → `results/figures/fig_g7_dashboard.png` replacing the G7 `.txt` stub; headless capture via script if display absent, else documented manual step with the file committed
- **D-09:** Scripted capture attempt first (playwright/chrome screenshot of localhost); manual fallback documented, file still committed
- Agent's discretion: Streamlit layout/styling (default theme, boring), figure section order, exact reproduce commands. ThingSpeak/Blynk syllabus screenshot: optional manual step, not a gate.

### Deferred Ideas (OUT OF SCOPE)
None — nothing deferred beyond this phase; MPC/RL stays out of scope permanently.

## Goal

Users can watch live energy, comfort, and savings and reproduce every report artifact. This phase builds a thin Streamlit viewer over Phase-5 outputs, a one-page protocol comparison note, reproduce docs, and a real dashboard screenshot that replaces the G7 stub. No new science, no retraining, no controller changes.

## Phase Requirements

| ID | Description (from REQUIREMENTS.md) | Research Support |
|----|-------------------------------------|------------------|
| DASH-01 | View live energy, comfort and savings on dashboard (Streamlit primary + ThingSpeak/Blynk syllabus screenshot) | Findings §1–§4 (app structure, cache, plotly-vs-PNG, screenshot path); ThingSpeak/Blynk is optional manual step per CONTEXT |
| DASH-02 | Compare MQTT vs HTTP vs CoAP briefly with protocol choice rationale and MQTT security note | Findings §5 (protocols.md outline with table content + security note) |

## Key Questions

1. What exact files/columns does the dashboard bind to? → Answered by disk reads below (§0).
2. Single-page Streamlit viewer over CSVs+PʌNGs — what structure? → §1.
3. How to avoid reload jank on every widget interaction? → §2 (`st.cache_data`).
4. Interactive Plotly charts, static PNGs, or both? → §3 (both: Plotly for 24h/savings tables, `st.image` for G1–G6).
5. How to capture the G7 screenshot on this Windows box? → §4 (playwright-first, manual fallback — prescribed concretely).
6. What goes in `docs/protocols.md`? → §5 (table rows + security note content).
7. What makes reproduction one-command? → §6 (checklist + pins).

## Findings

### §0. Grounded data bindings (read from disk 2026-09-30 — planner: use these verbatim)

**`results/report_tables/` (11 CSVs):**

| File | Header (verbatim, first line) |
|------|-------------------------------|
| `g1_24h_profile.csv` | `hour,c3_kw_mean,c3_kw_std,c4_kw_mean,c4_kw_std,occupancy_mean` |
| `g2_savings.csv` | `controller,scenario,scenario_label,n_seeds,energy_kwh_mean,energy_kwh_std,saved_pct_vs_c3_mean,saved_pct_vs_c3_std,saved_pct_vs_c1_mean,saved_pct_vs_c1_std,cost_rs_mean,cost_rs_std,co2_kg_mean,co2_kg_std,comfort_pct_mean,comfort_pct_std` |
| `g3_pareto.csv` | `label,energy,energy_std,comfort,comfort_std,kind` |
| `g4_co2.csv` | `hour,c3_co2_mean,c3_co2_std,c4_co2_mean,c4_co2_std,avoided_mean,avoided_std,c4_flat_mean` |
| `g5_pred_actual_stats.csv` | `target,horizon_min,n,rmse,mae` |
| `g6_forecast_ablation.csv` | `scenario,dE_mean,dE_std,dCO2_mean,dCO2_std,dComf_mean,dComf_std` |
| `g6_carbon_ablation.csv` | `scenario,controller,prem_mean,prem_std` |
| `headline_savings_over_c3.csv` | same 16-col schema as `g2_savings.csv` (controller,scenario,scenario_label,n_seeds,energy_kwh_mean,…,comfort_pct_std) |
| `shifting_peak_share.csv` | `scenario,seed,c3_peak_share_18_22,c4_peak_share_18_22,d_peak_share,d_cost_rs,d_co2_kg,d_energy_kwh` |
| `ablation.csv` | `panel,scenario,seed,controller,ef_mode,energy_kwh,cost_rs,co2_kg,comfort_pct,co2_delta,d_energy_kwh,d_cost_rs,d_co2_kg,d_comfort_pp` |
| `sensitivity.csv` | `analysis,scenario,controller,param,energy_kwh_mean,energy_kwh_std,co2_kg_mean,co2_kg_std,cost_rs_mean,cost_rs_std,comfort_pct_mean,comfort_pct_std` |

**`results/figures/` (7 entries):** `fig_g1_24h_profile.png`, `fig_g2_savings.png`, `fig_g3_pareto.png`, `fig_g4_co2.png`, `fig_g5_pred_actual.png`, `fig_g6_ablation.png`, `fig_g7_dashboard_placeholder.txt` (341 B stub — "screenshot is Phase 6 … build never breaks on the 7th slot").

**`results/full_matrix/summary.csv` header (verbatim):** `controller,scenario,scenario_label,n_seeds,energy_kwh_mean,energy_kwh_std,saved_pct_vs_c3_mean,saved_pct_vs_c3_std,saved_pct_vs_c1_mean,saved_pct_vs_c1_std,cost_rs_mean,cost_rs_std,co2_kg_mean,co2_kg_std,comfort_pct_mean,comfort_pct_std` — same 16-col schema as g2/headline. Controller keys are `c1,c2,c3,c4-with,c4-as-c3` (note: NOT bare `c4` — 05-03 deviation #1). Scenario values include `weekday,weekend,heatwave,exam-day (stub=weekday)`.

**Other ground facts:** `dashboard/` does not exist yet (greenfield file). `results/` is gitignored (`results/` line in `.gitignore`) — the G7 PNG is the deliberate exception and must be force-added (`git add -f`). `eval/report.py` docstring confirms the G7 slot is a `.txt` stub by design (T-05-09). Env verified: streamlit 1.56.0 + plotly 6.9.0 on Python 3.14.6 [VERIFIED: `python -c "import streamlit, plotly"` this session]. Playwright is NOT installed and no chrome/chromium/msedge on PATH [VERIFIED: `pip show playwright` + `Get-Command` this session].

### §1. Streamlit app structure — single page, sections, filters

Use one `dashboard/app.py` (~100–150 lines), default theme, no custom CSS. Structure [ASSUMED — standard Streamlit idiom, matches STACK.md "dashboard in ~100 lines"]:

```python
import pathlib
import pandas as pd
import streamlit as st
import plotly.express as px

ROOT = pathlib.Path(__file__).resolve().parent.parent
TABLES = ROOT / "results" / "report_tables"
FIGS = ROOT / "results" / "figures"

st.set_page_config(page_title="Smart Building — Energy/Comfort/Savings", layout="wide")
st.title("Carbon- and Comfort-Aware Predictive Control — Dashboard")

# Sidebar filters drive every section
scenario = st.sidebar.selectbox("Scenario", ["weekday", "weekend", "heatwave", "exam-day"])
controllers = st.sidebar.multiselect("Controllers", ["c1", "c2", "c3", "c4-with"], default=["c3", "c4-with"])
seed = st.sidebar.selectbox("Seed (seed-level tables only)", ["mean", 0, 1, 2, 3, 4])
```

Sections in order: (1) Overview KPI row (`st.metric`: energy kWh, saved % vs C3, CO₂ kg, comfort % — filtered row from `headline_savings_over_c3.csv`); (2) 24h shape (Plotly line from `g1_24h_profile.csv`); (3) Savings bars (Plotly bar from `g2_savings.csv` filtered by scenario); (4) Pareto (`st.image` of `fig_g3_pareto.png` — never replot, the 21-point annotation is the deliverable); (5) Ablation (`st.image` G6 + forecast-delta table); (6) Report figures expander with `st.image` G1,G2,G4,G5. Seed filter applies only to seed-level tables (`ablation.csv`, `shifting_peak_share.csv`); mean tables ignore it — label this in the UI so it isn't a bug report later.

Optional demo button (D-04 allows, does not require): if included, call `sim.run` with a fixed seed and tiny horizon, show the resulting KPI row only. Gate: must finish in <10 s or cut it. Never import `ml/` training paths.

### §2. `st.cache_data` usage — cache every CSV load

Every widget interaction reruns the whole script; without caching, 11 CSV reads per keystroke. Prescription: wrap each loader [ASSUMED — canonical Streamlit pattern, stable since 1.18]:

```python
@st.cache_data
def load_table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / name)
```

One function covers all tables. PNGs via `st.image(path)` need no caching (Streamlit handles media hashing). Do NOT use `st.cache_resource` (that's for models/connections). Missing-file handling: `if not path.exists(): st.warning("Run `python -m eval.report` first")` — dashboard must degrade gracefully on a fresh clone where `results/` is absent (gitignored).

### §3. Plotly vs static PNG — decision: BOTH, split by role

| Content | Render as | Why |
|---------|-----------|-----|
| 24h profile, savings bars, KPI-filtered views | Plotly (`px.line`, `px.bar` with error bars from `*_std` cols) via `st.plotly_chart(..., use_container_width=True)` | Filters need interactivity; data is already aggregated so Plotly code is ~5 lines per chart |
| G1–G6 report figures | `st.image("results/figures/fig_gXX_*.png")` | These ARE the graded artifacts; replotting risks divergence from the report. Never replot a G-figure in Plotly |
| Pareto (G3) | `st.image` only | The 21-point dominated-cluster annotation is hand-tuned in matplotlib; do not attempt a Plotly replica |

Plotly 6.9.0 note: `px.bar(error_y=...)` and `use_container_width=True` are stable APIs — no version risk [ASSUMED, LOW risk — these APIs are unchanged for years; verify at runtime if a traceback appears].

### §4. Screenshot capture path — PRESCRIPTIVE (try in this order)

Target file: `results/figures/fig_g7_dashboard.png` (replaces the `.txt` stub; force-add since `results/` is gitignored).

**Step 1 (try first): Playwright scripted capture.** Install + capture in one go:

```bash
pip install playwright
playwright install chromium
streamlit run dashboard/app.py --server.headless true --server.port 8501 &
python scripts/capture_dashboard.py   # playwright: goto localhost:8501, wait 5 s, screenshot to results/figures/fig_g7_dashboard.png
```

`scripts/capture_dashboard.py` is ~20 lines (`sync_playwright`, `page.goto`, `page.wait_for_timeout(5000)`, `page.screenshot`). Keep the script in repo — it's the reproduce evidence for D-09.

**Step 2 (fallback, fully acceptable): manual capture.** If Step 1 fails (no network for browser download, sandbox blocks Chromium): run `streamlit run dashboard/app.py`, screenshot the browser window (Snipping Tool / Shift+Win+S), save as `results/figures/fig_g7_dashboard.png`, commit with `git add -f`. Document the manual step in REPRODUCE.md — CONTEXT D-08/D-09 explicitly bless this fallback ("manual fallback documented, file still committed").

**Do NOT:** use matplotlib to fake a dashboard screenshot; use headless Chrome `--screenshot` without playwright (flag is flaky on Windows without a display); leave the `.txt` stub alongside (delete it when the PNG lands, and update `eval/report.py` G7 handling so `python -m eval.report` doesn't recreate the stub over the PNG — planner: include a small report.py edit task).

### §5. `docs/protocols.md` outline (DASH-02, one page, syllabus-mapped)

Target: one page, table is the deliverable, mapped to Unit 4 + Tutorials [per CONTEXT D-06]. Content prescription [ASSUMED — standard IoT-protocol comparison, planner should sanity-check numbers against course slides, not the internet]:

```markdown
# Telemetry Protocol Comparison (Unit 4)
## Comparison table
| Criterion | MQTT (chosen) | HTTP | CoAP |
| Overhead per message | ~2 B fixed header + topic | ~200+ B headers per request | ~4 B fixed header |
| Interaction | pub/sub via broker | request/response (polling) | request/response (+ observe) |
| QoS / reliability | QoS 0/1/2 + retained + LWT | TCP retry only, app must dedupe | confirmable msgs, no broker persistence |
| Suitability here | many-to-many rooms↔controller, push on change | polling wastes ESP32 loop, no LWT | built for constrained nodes but no local broker maturity on student laptops |
## Why MQTT won here
- one `topics.py` contract shared by sim/bridge/firmware; retained setpoints + LWT give the IOT-04 fault-tolerance story for free
## MQTT security note
- Lab: anonymous localhost broker (`mosquitto.conf` listener 1883, no auth) — convenience only
- Checked-in path: commented TLS block in `mosquitto.conf` (port 8883, CA/cert placeholders)
- Production checklist: enable auth (password_file/ACL per room), TLS everywhere, no anonymous on LAN, rotate creds per deployment
```

Planner note: verify `mosquitto.conf` actually has the commented TLS block; if missing, add a task to append it (D-05 requires it).

### §6. Reproduce-docs checklist + requirements pins

**Checklist (REPRODUCE.md or README section):** exact command sequence with expected outputs —
1. `python --version` → 3.14.6 (verified working; 3.12 note per STACK.md for TF-strict machines)
2. `pip install -r requirements.txt`
3. `python -m eval.report` → expect 7 figures + 11 tables (<1 min after forecaster regen)
4. `streamlit run dashboard/app.py` → opens localhost:8501
5. Screenshot step → `results/figures/fig_g7_dashboard.png`

**requirements.txt pins needed** (current file has numpy/pandas/matplotlib/pytest/paho-mqtt/sklearn/tensorflow; streamlit/plotly missing — planner: one task to append):

```
streamlit==1.56.0
plotly==6.9.0
```

Versions are the VERIFIED installed ones (import-checked this session), so pin `==` exactly — no registry lookup needed. Playwright stays OUT of requirements.txt (screenshot tooling only, not a runtime dep; install ad-hoc in §4 Step 1).

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Fresh clone has empty `results/` → dashboard shows nothing | HIGH (gitignored by convention) | `st.warning` + "run `python -m eval.report` first" guard; REPRODUCE.md order |
| `python -m eval.report` recreates G7 `.txt` stub after PNG lands | MEDIUM | Task: edit `eval/report.py` to skip stub when PNG exists |
| G7 PNG forgotten from commit (gitignored) | MEDIUM | Commit with `git add -f results/figures/fig_g7_dashboard.png`; verification step checks it |
| Playwright/Chromium install blocked on some laptop | MEDIUM | Manual fallback is pre-blessed (D-09); script kept in repo for machines where it works |
| Controller key `c4` vs `c4-with` confusion in filters | LOW (documented in 05-03) | Hardcode filter options to `c1,c2,c3,c4-with` (+`c4-as-c3` where relevant); never bare `c4` |
| Plotly 6.x API drift breaks a chart call | LOW | Charts are 5-line `px` calls; runtime traceback → fix forward, no research needed |

## Open Questions

1. **mosquitto.conf TLS block** — does the checked-in `mosquitto.conf` actually contain the commented TLS block D-05 references? *Recommendation:* planner adds a verify-then-append task; 5-minute fix, no research needed.
2. **Demo button (D-04)** — include or cut? *Recommendation:* cut unless `sim.run` fixed-seed tiny-horizon completes in <10 s; dashboard grades on display, not the button.
3. **ThingSpeak/Blynk screenshot** — CONTEXT says optional manual step, not a gate. *Recommendation:* one REPRODUCE.md line documenting it as optional; no task beyond that.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `@st.cache_data` CSV-loader pattern + `st.image`/`st.plotly_chart` APIs as sketched | §1–§3 | LOW — canonical stable Streamlit APIs; runtime traceback fixes in minutes |
| A2 | Protocol table values (header sizes, QoS semantics) | §5 | LOW — planner cross-checks against course slides; table is illustrative, not load-bearing |
| A3 | `playwright install chromium` works on student Windows laptops | §4 | LOW — manual fallback pre-blessed; no plan risk |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ | 3.14.6 | — |
| streamlit | dashboard | ✓ | 1.56.0 | — |
| plotly | dashboard charts | ✓ | 6.9.0 | `st.line_chart`/`st.bar_chart` (built-in, no dep) |
| pandas | CSV loading | ✓ (implied by report runs) | — | — |
| playwright/chromium | scripted screenshot | ✗ | — | manual capture (blessed) |
| Chrome/Edge on PATH | alt scripted capture | ✗ (not on PATH) | — | playwright install, else manual |

## Validation Architecture

> nyquist_validation is enabled (config: `workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (existing suite: 106 passed, 2 skipped per 05-03) |
| Config file | existing (repo convention) |
| Quick run command | `pytest -x -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | dashboard loads CSVs, filters render | smoke (import + file-exists) | `python -c "import ast; ast.parse(open('dashboard/app.py').read())" + pytest tests/ -q` | ❌ Wave 0 (new `dashboard/` + screenshot-exists check) |
| DASH-02 | protocols.md exists with table + security note | smoke (file/content grep) | `pytest tests/test_reproduce.py -q` (new) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest -x -q`
- **Per wave merge:** `pytest -q`
- **Phase gate:** Full suite green + `fig_g7_dashboard.png` committed + `streamlit run` smoke before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_dashboard.py` — app.py parses, all referenced CSV/PNG paths exist, no `sim`/`ml` imports (D-03 guard)
- [ ] `tests/test_reproduce.py` — requirements.txt contains streamlit+plotly pins; protocols.md has table + TLS note; G7 PNG-or-stub present
- [ ] `dashboard/app.py` + `scripts/capture_dashboard.py` — created in Wave 1, not Wave 0

## Security Domain

> security_enforcement enabled (config: `security_block_on: high`, ASVS L1).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | local-only dashboard, no login |
| V4 Access Control | no | localhost viewer |
| V5 Input Validation | partial | sidebar selects from fixed option lists only (no free-text → no injection surface); CSVs are local build outputs |
| V6 Cryptography | note only | no crypto in dashboard; TLS covered as documentation in protocols.md (D-05) |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious CSV content rendered in dashboard | Tampering | CSVs are local build outputs from committed code, never user uploads — no mitigation needed |
| Streamlit binding to LAN exposing dashboard | Info disclosure | Default `streamlit run` binds localhost; document NOT to use `--server.address 0.0.0.0` on shared networks |

## Sources

### Primary (HIGH confidence)
- Disk reads this session: `results/report_tables/` listing + 9 CSV headers, `results/figures/` listing, G7 stub text, `requirements.txt`, `.gitignore`, `eval/report.py` docstring, `streamlit`/`plotly` import versions, `pip show playwright` + `Get-Command` probe
- `.planning/phases/05-carbon-economics-full-evaluation/05-03-SUMMARY.md` — figure/table inventory, `c4-with` key, G7 stub design

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md` — Streamlit ≥1.50 + Plotly as primary dashboard (prior research, consistent with installed 1.56.0/6.9.0)

### Tertiary (LOW confidence)
- Streamlit `st.cache_data` / `st.metric` / `st.image` idioms and protocol-table values — standard knowledge, flagged [ASSUMED] where load-bearing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — streamlit 1.56.0 + plotly 6.9.0 import-verified; pins are exact installed versions
- Architecture: HIGH — all data bindings quoted from disk; viewer structure follows locked CONTEXT decisions
- Pitfalls: MEDIUM — gitignored-results and G7-stub-overwrite risks are grounded in repo convention; screenshot-tooling risk verified by probe

**Research date:** 2026-09-30
**Valid until:** 30 days (stable domain — viewer over frozen artifacts)
