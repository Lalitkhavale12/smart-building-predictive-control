---
phase: 06-dashboard-report-polish
plan: 02
subsystem: report-polish
tags: [docs, reproduce, mqtt, g7-screenshot, streamlit]
requires: [06-01]
provides: [protocols-note, reproduce-docs, g7-png-pipeline]
affects: [06-03]
tech-stack:
  added: [playwright-1.63.0-ad-hoc-only]
  patterns: [stub-skip-guard, force-add-gitignored-evidence]
key-files:
  created:
    - docs/protocols.md
    - tests/test_reproduce.py
    - REPRODUCE.md
    - scripts/capture_dashboard.py
    - results/figures/fig_g7_dashboard.png
  modified:
    - eval/report.py
decisions:
  - Playwright kept OUT of requirements.txt (screenshot tooling, not runtime dep)
  - PNG force-added despite results/ gitignore (deliberate evidence exception)
metrics:
  duration: ~25 min
  completed: 2026-09-30
status: complete
actuals:
  tokens: 3500
  tasks: 3
  commits: 3
plan_head_before: 5d378d4565a94fc9e66a71f61dfe046fc79e42ab
---

# Phase 06 Plan 02: Report-Polish Slice Summary

One-liner: MQTT-vs-HTTP-vs-CoAP note with TLS cross-check, fresh-clone REPRODUCE.md, G7 stub-skip guard, and a real 1600x900 dashboard PNG captured via scripted Playwright and force-committed.

## What was built

- `docs/protocols.md` (new): one-page Unit-4/Tutorials note — MQTT/HTTP/CoAP table (overhead, interaction, QoS, here-suitability), why-MQTT-won rationale (shared topics contract, retained setpoints, LWT), 3-step MQTT security note referencing the commented `listener 8883` TLS block verified present in `mosquitto.conf` (disk-read confirmed, file untouched).
- `tests/test_reproduce.py` (new, 4 tests): `test_pins_streamlit_plotly` (== pins, comment-filtered grep), `test_protocols_table` / `test_protocols_tls_note` (table markers + 8883/mosquitto.conf/allow_anonymous), `test_protocols_g7_slot` (exactly one of PNG/stub). All names match the `-k 'protocols or pins'` filter.
- `REPRODUCE.md` (new): fresh-clone sequence — version check (3.14.6 + 3.12 note), pip install, one-command report (7 figs + 11 tables), dashboard boot on :8501, screenshot step + manual fallback, optional ThingSpeak/Blynk one-liner (not a gate).
- `eval/report.py` (edit, g7 branch only): returns existing `fig_g7_dashboard.png` untouched; writes the stub only when no PNG exists. Proven both directions (sentinel-PNG preservation test + stub-write test).
- `scripts/capture_dashboard.py` (new, ~20 lines): sync Playwright, 1600x900 viewport, 5 s settle, screenshots to the G7 path. Playwright installed ad-hoc (1.63.0), NOT added to requirements.txt.
- `results/figures/fig_g7_dashboard.png` (force-added, 158 KB, valid PNG 1600x900 RGB per PIL): real capture of the 06-01 dashboard; `.txt` stub deleted from disk (was never tracked).

## Test results

- Task 1: `pytest tests/test_reproduce.py -q -k 'protocols or pins'` → 4 passed.
- Task 2: `python -m eval.report --only g7` writes stub when absent / preserves PNG when present; reproduce suite 4 passed.
- Task 3: `py_compile` clean; post-capture `--only g7` re-run prints the PNG path, no stub recreated; reproduce suite 4 passed.
- Phase gate: full `pytest -q` → **117 passed, 2 skipped**; `git ls-files` confirms the PNG is tracked despite the `results/` gitignore.

## Commits

- 2039490 `docs(06-02): protocols comparison note + reproduce smoke test`
- e8a642b `docs(06-02): REPRODUCE.md + G7 stub-skip guard`
- 4b2075e `feat(06-02): scripted G7 dashboard capture + PNG evidence`

## Deviations

None — plan executed exactly as written. Scripted capture succeeded on the first real attempt (Chromium headless-shell downloaded ~115 MB; `Start-Process python -m streamlit` in a single shell since each tool call is a fresh shell). Manual fallback was not needed but stays documented in REPRODUCE.md. Commits landed on `main` per this repo's established practice (06-01 did the same; no worktree/agent branch in play).

## Screenshot disposition

Real PNG committed (not a stub, not a fake): scripted capture → PIL-validated 1600x900 → stub deleted → force-added → survival re-proven. Threat T-06-04 accepted per plan (regenerable build output).

## Self-Check: PASSED

- Files exist: docs/protocols.md, tests/test_reproduce.py, REPRODUCE.md, scripts/capture_dashboard.py, results/figures/fig_g7_dashboard.png — all FOUND.
- Commits 2039490, e8a642b, 4b2075e — all FOUND in `git log`.
- Stub absent from disk; PNG tracked (`git ls-files`).
