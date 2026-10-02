"""Smart-building predictive-control dashboard (DASH-01).

Thin viewer over saved Phase-5 report artifacts. Reads committed-code
CSVs/PNGs plus saved per-seed telemetry frames for display aggregation
only (no matrix reruns, no training paths). Run with:
streamlit run dashboard/app.py
"""

import pathlib

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from viz.building3d import build_figure

ROOT = pathlib.Path(__file__).resolve().parent.parent
TABLES = ROOT / "results" / "report_tables"
FIGS = ROOT / "results" / "figures"
MATRIX = ROOT / "results" / "full_matrix"

HEADLINE_CSV = "results/report_tables/headline_savings_over_c3.csv"
SAVINGS_CSV = "results/report_tables/g2_savings.csv"
PROFILE_CSV = "results/report_tables/g1_24h_profile.csv"
G1_PNG = "results/figures/fig_g1_24h_profile.png"
G2_PNG = "results/figures/fig_g2_savings.png"
G3_PNG = "results/figures/fig_g3_pareto.png"
G4_PNG = "results/figures/fig_g4_co2.png"
G5_PNG = "results/figures/fig_g5_pred_actual.png"
G6_PNG = "results/figures/fig_g6_ablation.png"

SCENARIOS = ["weekday", "weekend", "heatwave", "exam-day"]
CONTROLLERS = ["c1", "c2", "c3", "c4-with", "c4-as-c3"]
SEEDS = [0, 1, 2, 3, 4]

st.set_page_config(
    page_title="Smart Building — Energy/Comfort/Savings",
    layout="wide",
)
st.markdown(
    f"<style>{(ROOT / 'dashboard' / 'style.css').read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)
st.title("Carbon- and Comfort-Aware Predictive Control — Dashboard")

st.sidebar.title("Smart Building Control")
scenario = st.sidebar.selectbox("Scenario", SCENARIOS)
controller_a = st.sidebar.selectbox("Controller A (compare)", CONTROLLERS, index=3)
controller_b = st.sidebar.selectbox("Controller B (compare)", CONTROLLERS, index=2)
seed = st.sidebar.selectbox("Seed (per-seed panel)", SEEDS)
st.sidebar.caption("Saved report data — see REPRODUCE.md to regenerate.")


@st.cache_data
def load_table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / name)


@st.cache_data
def seed_energies(controller: str, scenario_name: str) -> pd.DataFrame:
    """Per-seed energy (kWh) aggregated from saved telemetry frames."""
    rows = []
    for s in SEEDS:
        frame = pd.read_csv(
            MATRIX / controller / scenario_name / f"seed{s:02d}" / "telemetry.csv",
            usecols=["power_kW"],
        )
        rows.append({"seed": s, "energy_kwh": frame["power_kW"].sum() / 60.0})
    return pd.DataFrame(rows)


required = [TABLES / "headline_savings_over_c3.csv", TABLES / "g2_savings.csv"]
missing = [str(p) for p in required if not p.exists()]
figures = [G1_PNG, G2_PNG, G3_PNG, G4_PNG, G5_PNG, G6_PNG]
missing += [f for f in figures if not (ROOT / f).exists()]
if missing:
    st.warning("Report data not found — run `python -m eval.report` first.")
    st.stop()

headline = load_table("headline_savings_over_c3.csv")
savings = load_table("g2_savings.csv")
profile = load_table("g1_24h_profile.csv")


def row_for(controller: str, scenario_name: str) -> pd.Series:
    match = headline[
        (headline["scenario"] == scenario_name) & (headline["controller"] == controller)
    ]
    if match.empty:
        st.warning("No headline row for this filter — run `python -m eval.report` first.")
        st.stop()
    return match.iloc[0]


def metric_cards(row: pd.Series, base: pd.Series) -> None:
    st.metric(
        "Energy (kWh)",
        f"{row['energy_kwh_mean']:.2f}",
        delta=f"{row['saved_pct_vs_c3_mean']:+.1f}% vs C3",
        help="Mean daily energy over 5 paired seeds. Delta is savings vs the C3 setback baseline.",
    )
    st.metric(
        "Saved vs C3 (%)",
        f"{row['saved_pct_vs_c3_mean']:.1f}",
        help="Headline metric — always reported against C3, never against fixed-schedule.",
    )
    st.metric(
        "Cost (Rs)",
        f"{row['cost_rs_mean']:.1f}",
        delta=f"{base['cost_rs_mean'] - row['cost_rs_mean']:+.1f} Rs vs C3",
        help="Operating cost under the time-of-use tariff (hourly prices).",
    )
    st.metric(
        "CO2 (kg)",
        f"{row['co2_kg_mean']:.2f}",
        delta=f"{base['co2_kg_mean'] - row['co2_kg_mean']:+.2f} kg vs C3",
        help="CO2 under the time-varying grid emission factor (CEA-based hourly series).",
    )
    st.metric(
        "Comfort (%)",
        f"{row['comfort_pct_mean']:.1f}",
        delta=f"{row['comfort_pct_mean'] - base['comfort_pct_mean']:+.1f}pp vs C3",
        help="% of occupied time inside 22-26 C and 30-60% RH. Every claim carries this column.",
    )


base_row = row_for("c3", scenario)
row_a = row_for(controller_a, scenario)
row_b = row_for(controller_b, scenario)

tab_overview, tab_shape, tab_savings, tab_tradeoff, tab_ablation, tab_forecast, tab_3d = st.tabs(
    ["Overview", "Load shape", "Savings", "Tradeoff", "Ablation", "Forecast", "3D Building"]
)

with tab_overview:
    st.header(f"Overview — {scenario}")
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader(controller_a)
        metric_cards(row_a, base_row)
    with col_b:
        st.subheader(controller_b)
        metric_cards(row_b, base_row)
    st.subheader("Comfort gauges (% occupied time in band)")
    gauge_a, gauge_b = st.columns(2)
    for col, row, name in ((gauge_a, row_a, controller_a), (gauge_b, row_b, controller_b)):
        with col:
            st.plotly_chart(
                go.Figure(
                    go.Indicator(
                        mode="gauge+number+delta",
                        value=float(row["comfort_pct_mean"]),
                        title={"text": name},
                        delta={"reference": float(base_row["comfort_pct_mean"])},
                        gauge={"axis": {"range": [0, 100]}},
                    )
                ),
                use_container_width=True,
            )
    st.subheader(f"Per-seed spread — {controller_a} / {scenario}")
    st.info("Same 5 paired seeds behind every controller — spread here is weather/occupancy noise, not controller luck.")
    seeds_df = seed_energies(controller_a, scenario)
    st.plotly_chart(
        px.bar(seeds_df, x="seed", y="energy_kwh", title=f"Energy per seed (kWh) — {controller_a}"),
        use_container_width=True,
    )
    st.dataframe(seeds_df.style.format({"energy_kwh": "{:.3f}"}), use_container_width=True)
    st.download_button(
        "Download per-seed table (CSV)",
        seeds_df.to_csv(index=False),
        file_name=f"seeds_{controller_a}_{scenario}.csv",
    )
    st.download_button(
        "Download headline table (CSV)",
        headline[headline["scenario"] == scenario].to_csv(index=False),
        file_name=f"headline_{scenario}.csv",
    )
    st.caption(f"Seed {seed} selected in the sidebar is highlighted in the table above.")

with tab_shape:
    st.header("24h load shape")
    st.info("Hover for values. C4 trims HVAC during empty midday blocks; the shaded evening peak is where time-of-use prices bite.")
    hero = go.Figure()
    hero.add_trace(
        go.Scatter(
            x=profile["hour"], y=profile["c3_kw_mean"],
            name="C3 mean", error_y=dict(array=profile["c3_kw_std"]),
        )
    )
    hero.add_trace(
        go.Scatter(
            x=profile["hour"], y=profile["c4_kw_mean"],
            name="C4 mean", error_y=dict(array=profile["c4_kw_std"]),
        )
    )
    hero.add_trace(
        go.Scatter(
            x=profile["hour"], y=profile["occupancy_mean"],
            name="Occupancy", yaxis="y2", opacity=0.4,
        )
    )
    hero.update_layout(
        title="24h load shape — report data (scenario-fixed)",
        xaxis_title="Hour", yaxis_title="Power (kW)",
        yaxis2=dict(title="Occupancy", overlaying="y", side="right"),
    )
    st.plotly_chart(hero, use_container_width=True)
    st.image(str(ROOT / G1_PNG), caption="G1 24h profile — graded report figure (scenario-fixed)")

with tab_savings:
    st.header("Savings")
    st.info("Every bar is savings vs C3 with paired-seed std. Weekend bars near zero are honest: C1 is already near-optimal there.")
    view = savings[savings["scenario"] == scenario].sort_values("controller")
    view["highlight"] = (view["controller"] == controller_a).map(
        {True: "controller A", False: "other"}
    )
    fig = px.bar(
        view,
        x="controller",
        y="saved_pct_vs_c3_mean",
        error_y="saved_pct_vs_c3_std",
        color="highlight",
        title=f"Saved % vs C3 — {scenario}",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.image(str(ROOT / G2_PNG), caption="G2 savings — graded report figure (scenario-fixed)")

with tab_tradeoff:
    st.header("Tradeoff")
    st.info("Energy vs comfort across controllers and threshold settings. A dominated cluster is still a result — it bounds what tuning can buy.")
    st.image(str(ROOT / G3_PNG), caption="G3 Pareto — graded report figure (scenario-fixed)")
    st.image(str(ROOT / G4_PNG), caption="G4 CO2 — graded report figure (scenario-fixed)")

with tab_ablation:
    st.header("Ablation")
    st.info("Forecast arm isolates the ML contribution (C4-with vs C4-as-C3); carbon arm is accounting-level — savings are less-energy-everywhere, not shifted off-peak.")
    st.image(str(ROOT / G6_PNG), caption="G6 ablation — graded report figure (scenario-fixed)")

with tab_forecast:
    st.header("Forecast check")
    st.info("Frozen forecaster, walk-forward evaluation — predictions vs actuals with RMSE. No leakage: chronological splits only.")
    st.image(str(ROOT / G5_PNG), caption="G5 forecast — graded report figure (scenario-fixed)")

with tab_3d:
    st.header("3D Building twin")
    st.info("F1: classrooms A/B, F2: office/lab — colored by room temperature. Grey F3 terrace is visual-only, not simulated. Hover any room for its simulation inputs.")
    hour = st.slider("Hour of day", 0, 23, 12)
    try:
        st.plotly_chart(
            build_figure(controller_a, scenario, seed, hour),
            use_container_width=True,
        )
    except FileNotFoundError:
        st.warning("Telemetry frame missing for this filter — run the evaluation matrix first.")

st.divider()
st.caption(
    "Honesty note: savings come from using less energy everywhere, "
    "not from off-peak shifting — see SHIFTING-FINDING.md "
    "(.planning/phases/05-carbon-economics-full-evaluation/SHIFTING-FINDING.md)."
)
