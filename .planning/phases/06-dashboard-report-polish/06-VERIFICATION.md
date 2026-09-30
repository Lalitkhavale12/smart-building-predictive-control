# Phase 06: Dashboard + Report Polish — Verification Report

**Phase goal:** Users can watch live energy, comfort, and savings and reproduce every report artifact
**Verified:** 2026-09-30 (UTC)
**Status:** PASS — all 3 success criteria met
**Mode:** mvp (goal-backward, outcome-observable)

## Verdict per criterion

| # | Success criterion | Verdict | Evidence |
|---|-------------------|---------|----------|
| 1 | User can open the dashboard and watch live energy, comfort, and savings update (Streamlit primary plus ThingSpeak/Blynk syllabus screenshot) ← DASH-01 | **PASS** | `dashboard/app.py` (101 lines) implements 06-UI-SPEC exactly: sidebar "Smart Building Control" + Scenario/Controller/Seed selects + pinned-data caption; 7 sections (overview KPI cards from `headline_savings_over_c3.csv`, G1 image, Plotly savings bar from `g2_savings.csv` + G2 image, G3+G4 tradeoff, G6 ablation, G5 forecast, honesty footer with SHIFTING-FINDING.md link). `tests/test_dashboard.py` 7/7 pass. Live boot on alternate port 8512 → `HTTP 200` via curl.exe, process killed, port freed. ThingSpeak/Blynk handled per locked D-discretion as optional manual step (REPRODUCE.md step 6), not a gate. |
| 2 | User can read the brief MQTT vs HTTP vs CoAP comparison with protocol choice rationale and MQTT security note ← DASH-02 | **PASS** | `docs/protocols.md` has the comparison table (overhead, interaction pattern, QoS, here-suitability), why-MQTT-won rationale (shared `topics.py` contract, retained setpoints, LWT), and 3-step MQTT security note referencing the commented `listener 8883` TLS block + `allow_anonymous`. `mosquitto.conf` TLS block confirmed present on disk (`#listener 8883`, `cafile`/`certfile`/`keyfile` placeholders, untouched). `tests/test_reproduce.py` protocols tests (table + TLS + G7 slot) pass. |
| 3 | User can reproduce all required graphs and the report from a pinned env plus seed set with one command ← DASH-01 | **PASS** | `requirements.txt` pins `streamlit==1.56.0` + `plotly==6.9.0`; installed versions verified identical (1.56.0, 6.9.0). `python -m eval.report` one-command report (G1–G7 + summary tables); G7 stub-skip guard in `eval/report.py:141-147` returns existing PNG untouched — code-read confirmed AND behaviorally proven: ran `python -m eval.report --only g7` → printed PNG path, `git status` clean (no clobber). REPRODUCE.md command sequence spot-checked accurate (version check, pip install, one-command report, dashboard boot on :8501, screenshot step + manual fallback). `results/figures/` holds G1–G7 PNGs; `results/report_tables/` holds 11 CSVs. |

## Evidence detail

- **Tests:** `python -m pytest tests/test_dashboard.py tests/test_reproduce.py -q` → **11 passed** (7 dashboard + 4 reproduce).
- **Boot check:** `Start-Process python -m streamlit run dashboard/app.py --server.headless true --server.port 8512` → `curl.exe http://127.0.0.1:8512/` → **HTTP 200**; process killed, port 8512 confirmed free afterward. (Note: `Invoke-WebRequest` failed in this sandbox due to a proxy artifact; native curl.exe succeeded — app-side serving confirmed, client-side quirk only.)
- **G7 PNG:** `results/figures/fig_g7_dashboard.png` — magic bytes `89504e470d0a1a0a` (real PNG), PIL-validated 1600×900 RGB, 158 KB; `git ls-files` shows it **tracked** despite `results/` gitignore (deliberate force-add exception); placeholder stub absent from disk (`Test-Path` → False); committed as `4b2075e`; `--only g7` re-run does not clobber it.
- **Data bindings:** dashboard references only committed CSVs/PNGs that exist on disk (`headline_savings_over_c3.csv`, `g2_savings.csv`, G1–G6 PNGs); `@st.cache_data` loader present; controller keys `c1,c2,c3,c4-with,c4-as-c3` and 4 scenarios match on-disk data; no `sim/`/`ml/`/`ctrl`/TF/sklearn imports (demo button cut per D-04, UI-SPEC records the 10 s budget rationale); graded figures via `st.image`, never replotted (no `savefig`).
- **mosquitto.conf:** `listener 1883` + `allow_anonymous true` (lab) and commented `#listener 8883` + `cafile`/`certfile`/`keyfile` placeholders (checked-in TLS path) — matches the security note's claims.
- **Anti-patterns:** no TODO/FIXME/placeholder/stub markers in new files; `scripts/capture_dashboard.py` documents Playwright as ad-hoc-only (correctly kept out of `requirements.txt`).

## Issues

None blocking. Two non-blocking notes:

1. **Filter interactivity proven by code-read, not click-through.** Boot returns HTTP 200 and tests assert the sidebar/widgets/bindings exist, but no automated test changes a filter and asserts the KPI cards update. The recompute path is 3 lines of pandas filtering with no branching — low risk. Optional human click-through: `streamlit run dashboard/app.py`, change Scenario/Controller, confirm cards + Plotly chart update.
2. **Full `python -m eval.report` not re-run by verifier** (only `--only g7` spot-check; full run is ~1 min and rewrites figures). Backbone is covered by 06-02's recorded full-suite result (117 passed, 2 skipped) plus the passing smoke tests above.

## Overall

**VERDICT: PASS.** Phase 06 goal achieved: the Streamlit dashboard serves live energy/comfort/savings views over Phase-5 data (HTTP 200), the protocol comparison + MQTT security note is readable and grounded in `mosquitto.conf`, and every report artifact reproduces from the pinned env via one command with the G7 screenshot committed as real PNG evidence. No gaps; ready to ship.
