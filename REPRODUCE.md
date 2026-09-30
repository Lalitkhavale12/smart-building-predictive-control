# Reproduce Every Result (fresh clone → full report + dashboard)

Verified on Python 3.14.6. Machines that train the LSTM strictly (TF-strict)
should use Python 3.12 per `requirements.txt`; inference/regen needs no GPU.

## 1. Python version

```bash
python --version
```

Expected: `Python 3.14.6` (or 3.12.x for training-strict machines).

## 2. Install

```bash
pip install -r requirements.txt
```

## 3. One-command report

```bash
python -m eval.report
```

Expected: 7 figures in `results/figures/` (`fig_g1_24h_profile.png` …
`fig_g6_ablation.png` + the G7 slot) and 11 tables in
`results/report_tables/`, in under ~1 min once forecaster/matrix inputs exist
(longer on a truly fresh clone while the frozen forecaster + matrix regenerate
from committed code — no manual steps, just wall time).

Subset runs: `python -m eval.report --only g7` touches only the G7 slot and
never overwrites an existing `fig_g7_dashboard.png`.

## 4. Dashboard

```bash
streamlit run dashboard/app.py
```

Expected: opens `http://localhost:8501` with energy/comfort/savings sections.
If `results/` is empty (gitignored on fresh clone), the app warns and tells
you to run step 3 first. Keep the default localhost bind — never
`--server.address 0.0.0.0` on a shared network.

## 5. G7 screenshot

```bash
python scripts/capture_dashboard.py
```

Expected: `results/figures/fig_g7_dashboard.png` (1600×900), committed with
`git add -f` (the `results/` gitignore exception). The script boots the
dashboard headless on port 8501 and needs `playwright` + Chromium (ad-hoc
install, intentionally NOT in `requirements.txt`):

```bash
pip install playwright
playwright install chromium
```

**Manual fallback** (scripted capture blocked — e.g. no browser/display on
this machine): `streamlit run dashboard/app.py`, screenshot the browser window
(Snipping Tool / Shift+Win+S), save as
`results/figures/fig_g7_dashboard.png`, delete
`fig_g7_dashboard_placeholder.txt`, `git add -f` the PNG. Either path lands
the same file; `python -m eval.report` never clobbers it (G7 stub is written
only when no PNG exists).

## 6. ThingSpeak/Blynk (optional, manual, not a gate)

Syllabus IoT-cloud screenshot: forward one building metric to a
ThingSpeak/Blynk free-tier channel from a successful run and screenshot the
cloud dashboard. Needs a cloud account; never blocks steps 1–5.
