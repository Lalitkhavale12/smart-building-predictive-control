"""Smart-building predictive-control dashboard (DASH-01).

Thin viewer over saved Phase-5 report artifacts. Reads committed-code
CSVs/PNGs, recomputes nothing, imports no training paths. Run with:
streamlit run dashboard/app.py
"""

import pathlib

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
TABLES = ROOT / "results" / "report_tables"
FIGS = ROOT / "results" / "figures"

HEADLINE_CSV = "results/report_tables/headline_savings_over_c3.csv"
SAVINGS_CSV = "results/report_tables/g2_savings.csv"
G1_PNG = "results/figures/fig_g1_24h_profile.png"
G2_PNG = "results/figures/fig_g2_savings.png"
G3_PNG = "results/figures/fig_g3_pareto.png"
G4_PNG = "results/figures/fig_g4_co2.png"
G5_PNG = "results/figures/fig_g5_pred_actual.png"
G6_PNG = "results/figures/fig_g6_ablation.png"

SCENARIOS = ["weekday", "weekend", "heatwave", "exam-day"]
CONTROLLERS = ["c1", "c2", "c3", "c4-with", "c4-as-c3"]
SEEDS = [0, 1, 2, 3, 4]

st.set_page_config(page_title="Smart Building — Energy/Comfort/Savings", layout="wide")
st.title("Carbon- and Comfort-Aware Predictive Control — Dashboard")

st.sidebar.title("Smart Building Control")
scenario = st.sidebar.selectbox("Scenario", SCENARIOS)
controller = st.sidebar.selectbox("Controller", CONTROLLERS)
seed = st.sidebar.selectbox("Seed (seed-level tables only)", SEEDS)
st.sidebar.caption("Saved report data — see REPRODUCE.md to regenerate.")
st.caption("Seed applies to seed-level tables only; headline means ignore it.")


@st.cache_data
def load_table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / name)


required = [TABLES / "headline_savings_over_c3.csv", TABLES / "g2_savings.csv"]
missing = [str(p) for p in required if not p.exists()]
figures = [G1_PNG, G2_PNG, G3_PNG, G4_PNG, G5_PNG, G6_PNG]
missing += [f for f in figures if not (ROOT / f).exists()]
if missing:
    st.warning("Report data not found — run `python -m eval.report` first.")
    st.stop()

headline = load_table("headline_savings_over_c3.csv")
savings = load_table("g2_savings.csv")

st.header("Overview")
row = headline[(headline["scenario"] == scenario) & (headline["controller"] == controller)]
if row.empty:
    st.warning("No headline row for this filter — run `python -m eval.report` first.")
    st.stop()
row = row.iloc[0]
cards = st.columns(5)
cards[0].metric("Energy (kWh)", f"{row['energy_kwh_mean']:.2f}")
cards[1].metric("Saved vs C3 (%)", f"{row['saved_pct_vs_c3_mean']:.1f}")
cards[2].metric("Cost (Rs)", f"{row['cost_rs_mean']:.1f}")
cards[3].metric("CO2 (kg)", f"{row['co2_kg_mean']:.2f}")
cards[4].metric("Comfort (%)", f"{row['comfort_pct_mean']:.1f}")

st.header("24h load shape")
st.image(str(ROOT / G1_PNG), caption="G1 24h profile — report figure (scenario-fixed)")

st.header("Savings")
view = savings[savings["scenario"] == scenario].sort_values("controller")
fig = px.bar(
    view,
    x="controller",
    y="saved_pct_vs_c3_mean",
    error_y="saved_pct_vs_c3_std",
    title=f"Saved % vs C3 — {scenario}",
)
st.plotly_chart(fig, use_container_width=True)
st.image(str(ROOT / G2_PNG), caption="G2 savings — report figure (scenario-fixed)")

st.header("Tradeoff")
st.image(str(ROOT / G3_PNG), caption="G3 Pareto — report figure (scenario-fixed)")
st.image(str(ROOT / G4_PNG), caption="G4 CO2 — report figure (scenario-fixed)")

st.header("Ablation")
st.image(str(ROOT / G6_PNG), caption="G6 ablation — report figure (scenario-fixed)")

st.header("Forecast check")
st.image(str(ROOT / G5_PNG), caption="G5 forecast — report figure (scenario-fixed)")

st.divider()
st.caption(
    "Honesty note: savings come from using less energy everywhere, "
    "not from off-peak shifting — see SHIFTING-FINDING.md "
    "(.planning/phases/05-carbon-economics-full-evaluation/SHIFTING-FINDING.md)."
)
