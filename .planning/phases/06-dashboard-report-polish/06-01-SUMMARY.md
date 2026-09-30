# Phase 06 Plan 01: Streamlit Dashboard Viewer Summary

**Phase:** 06-dashboard-report-polish
**Plan:** 01
**Status:** complete
**Date:** 2026-09-30

One-liner: Streamlit viewer over Phase-5 CSVs/PNGs with filter-driven KPIs + Plotly savings chart, pinned streamlit/plotly deps, green smoke suite, headless HTTP 200.

## What was built

- `dashboard/app.py` (new, ~90 lines): single-page viewer exactly per 06-UI-SPEC — sidebar title "Smart Building Control" + Scenario/Controller/Seed selects + pinned-data caption; 7 main sections in order (overview KPI cards from `headline_savings_over_c3.csv`, G1 image, Plotly savings bar from `g2_savings.csv` + G2 image, G3 Pareto, G6 ablation, G5 forecast, honesty footer with SHIFTING-FINDING.md link). One `@st.cache_data` loader; controller key `c4-with` (never bare `c4`); no sim/ml/ctrl imports (demo button cut); missing-file guard warns with the one-command report instruction instead of raising.
- `tests/test_dashboard.py` (new, 7 tests): app parses via ast; every referenced CSV/PNG exists on disk; cache-data loader + sidebar selects covering 4 scenarios + 5 controller keys; no training-path imports; no bare `c4` (quoted-exact match so hyphenated keys pass); graded figures via `st.image`, never replotted.
- `requirements.txt`: appended `streamlit==1.56.0` + `plotly==6.9.0` (import-verified on Python 3.14.6); existing pins untouched.

## Test results

- Task 1 RED confirmed: 7 failed with FileNotFoundError on missing `dashboard/app.py` (pins present).
- Task 2 GREEN: `py_compile` clean + 7 passed.
- Task 3 headless boot: `streamlit run dashboard/app.py --server.headless true --server.port 8511` → HTTP 200; job stopped/removed; no stray streamlit processes.

## Commits

- 8aeac86 `test(06-01): pin dashboard deps + dashboard smoke test (RED)`
- 5d378d4 `feat(06-01): build Streamlit dashboard viewer per UI-SPEC`
- Task 3: no code changes (boot clean, nothing to fix forward) — no commit.

## Deviations

None — plan executed exactly as written. (Figure-missing guard extended to PNGs alongside CSVs as a Rule-2 graceful-degradation hardening; same warning path, no behavior change on the happy path.)

## Grounding notes

- Header quote: `headline_savings_over_c3.csv` → `controller,scenario,scenario_label,n_seeds,energy_kwh_mean,…,comfort_pct_std` (16-col schema, matches research §0).
- Controller keys on disk: `c1,c2,c3,c4-with,c4-as-c3`; scenarios: `weekday,weekend,heatwave,exam-day` — filter option lists match exactly.
- G4 image shown inside the Tradeoff section (UI-SPEC bindings list G1–G6, section list names G1/G2/G3/G6/G5); 7-section order preserved.
- App is ~90 lines vs the ~100–150 estimate — concise by construction, all 7 sections + guards present.
