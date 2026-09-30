# Phase 6: Dashboard + Report Polish - Context

**Gathered:** 2026-09-30
**Status:** Ready for planning

## Phase Boundary

Live Streamlit dashboard (energy/comfort/savings, reads the same CSVs + figures Phase 5 produced), protocol comparison note (MQTT vs HTTP vs CoAP + MQTT security note), one-command reproduction of every report artifact, and a real dashboard screenshot replacing the G7 stub. Final phase — after this, the project ships. No new science, no retraining, no controller changes.

## Implementation Decisions

[--auto] Selected all gray areas: Dashboard scope, Data source, Comparison note, Reproduction, Screenshot.

### Dashboard scope
- **D-01:** Streamlit app `dashboard/app.py`: live-updating energy/comfort/savings view per scenario/controller from `results/` CSVs + embedded Phase-5 figures (G1–G6); filters for scenario + controller + seed
- **D-02:** [auto] Pages — Q: "Single page or multi?" → Selected: "Single page with sections (overview, 24h shape, savings, Pareto, ablation); multi-page is polish nobody grades" (recommended default)

### Data source
- **D-03:** Dashboard reads committed-code outputs only: `results/report_tables/*.csv` + `results/figures/*.png` + `results/full_matrix/summary.csv`; never recomputes the matrix, never imports ML training paths
- **D-04:** [auto] Live sim? — Q: "Run sim live behind dashboard?" → Selected: "No — display saved report data; one 'run small demo' button allowed only if it calls sim.run with fixed seed and finishes in seconds" (recommended default)

### Comparison note & security
- **D-05:** Protocol note `docs/protocols.md`: MQTT vs HTTP vs CoAP table (overhead, QoS, suitability) with choice rationale (why MQTT won here) + MQTT security note (anonymous lab broker → commented TLS block in mosquitto.conf → production checklist)
- **D-06:** [auto] Length — Q: "How long?" → Selected: "One page, syllabus-mapped (Unit 4 + Tutorials); the table is the deliverable" (recommended default)

### Reproduction & screenshot
- **D-07:** One-command reproduction: `README.md` pinned env (Python 3.14 verified working + 3.12 note) + `requirements.txt` complete (streamlit/plotly pinned) + `python -m eval.report` regenerates all figures; a `REPRODUCE.md` or README section lists the exact command sequence with expected outputs
- **D-08:** Real screenshot: run `streamlit run dashboard/app.py`, capture PNG → `results/figures/fig_g7_dashboard.png` replacing the G7 `.txt` stub; headless capture via script if display absent, else documented manual step with the file committed
- **D-09:** [auto] Screenshot method — Q: "Automated or manual?" → Selected: "Scripted capture attempt first (playwright/chrome screenshot of localhost); manual fallback documented, file still committed" (recommended default)

### the agent's Discretion
- Streamlit layout/styling (keep default theme, boring), figure section order, exact reproduce commands
- ThingSpeak/Blynk syllabus screenshot: document as optional manual step (cloud account needed), not a gate

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope
- `.planning/PROJECT.md` — core value, all prior validated work
- `.planning/REQUIREMENTS.md` — DASH-01, DASH-02 definitions
- `.planning/ROADMAP.md` Phase 6 — goal + 3 success criteria, UI hint: yes
- `smart_building_project_idea.md` — application layer, graphs-to-include (dashboard screenshot)
- `.planning/phases/05-carbon-economics-full-evaluation/05-03-SUMMARY.md` — report outputs this dashboard displays

### Research
- `.planning/research/STACK.md` — Streamlit ≥1.50 + Plotly as primary dashboard, ThingSpeak/Blynk for the syllabus screenshot
- `.planning/research/ARCHITECTURE.md` — dashboard consumes the contract, never defines it

### Existing code (read actual APIs)
- `results/report_tables/` (11 CSVs), `results/figures/` (G1–G6 + G7 stub), `results/full_matrix/summary.csv`
- `eval/report.py` — one-command report this phase extends with reproduce docs

## Existing Code Insights

### Reusable Assets
- All display data already exists as CSVs/PNGs — dashboard is a thin viewer, near-zero logic
- `eval/report.py` regen path is the reproduction backbone

### Established Patterns
- Pinned requirements, CSV-only data flow, gitignored results/ (screenshot PNG is the exception — committed as report evidence)

### Integration Points
- `dashboard/app.py` imports nothing from `sim/`, `ml/`, `ctrl/` except optionally `sim.run` for the tiny demo button

## Specific Ideas

No specific requirements — standard Streamlit viewer. Boring and shippable.

## Deferred Ideas

None — nothing deferred beyond this phase; MPC/RL stays out of scope permanently.

---

*Phase: 6-Dashboard + Report Polish*
*Context gathered: 2026-09-30*
