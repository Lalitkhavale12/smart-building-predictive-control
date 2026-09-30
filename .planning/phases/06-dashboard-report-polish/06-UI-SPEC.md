# Phase 06 UI Design Contract (UI-SPEC)

**Phase:** 06-dashboard-report-polish
**Scope:** Single-page Streamlit viewer over saved report artifacts. No new visual language — default Streamlit theme, boring and shippable.

## Layout

Single page, sidebar + main column:

- **Sidebar:** title "Smart Building Control"; three selectboxes — Scenario (weekday, weekend, heatwave, exam-day), Controller (c1, c2, c3, c4-with, c4-as-c3), Seed (0–4); caption with pinned-data note ("Saved report data — see REPRODUCE.md to regenerate").
- **Main sections (top to bottom):**
  1. Overview — headline metric cards (energy kWh, saved % vs C3, cost Rs, CO₂ kg, comfort %) for current filter selection, read from headline/summary table.
  2. 24h load shape — `st.image` of G1 PNG (never replot graded figures).
  3. Savings — Plotly bar chart from the savings table (filter-driven), plus `st.image` G2.
  4. Tradeoff — `st.image` G3 Pareto.
  5. Ablation — `st.image` G6.
  6. Forecast check — `st.image` G5.
  7. Footer — honesty footnote (less-energy-everywhere, not off-peak shifting) + link to SHIFTING-FINDING.md.

## Data bindings (grounded)

- Tables: `results/report_tables/*.csv` via `@st.cache_data` loader (16-col headline schema; controller key `c4-with`, never bare `c4`).
- Figures: `results/figures/fig_g1_24h_profile.png` … G6, `st.image`, fixed order above.
- No imports from `sim/`, `ml/`, `ctrl/` (demo button cut — sim.run exceeds the 10 s budget with full matrix data needs; saved-data-only per D-04).

## Interactions

- Changing any sidebar filter recomputes only the overview cards + Plotly savings chart from cached frames; static PNGs are scenario-fixed (caption states which scenario each figure shows).
- No forms, no sessions state beyond widget defaults, no auth.

## Acceptance

- `streamlit run dashboard/app.py` renders with zero errors on Python 3.14 + streamlit 1.56.0; every section shows data (no empty states on the default filter); screenshot captured at 1600×900 for G7.

## Out of scope

- Multi-page nav, theming, live simulation, ThingSpeak/Blynk embedding (one optional-step line in REPRODUCE.md).
