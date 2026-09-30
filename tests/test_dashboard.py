"""Smoke test for the Phase-6 Streamlit dashboard viewer (DASH-01).

Binding guard: dashboard/app.py is a thin viewer over Phase-5 outputs.
It must parse, reference only committed CSVs/PNGs that exist on disk,
use a @st.cache_data loader, expose sidebar filters for the four
scenarios + five controller keys, import no sim/ml/ctrl training paths,
never use the bare c4 key, and show graded figures via st.image
(never replotted).
"""

from __future__ import annotations

import ast
import pathlib
import re

APP = pathlib.Path(__file__).resolve().parent.parent / "dashboard" / "app.py"
ROOT = pathlib.Path(__file__).resolve().parent.parent
TABLES = ROOT / "results" / "report_tables"
FIGS = ROOT / "results" / "figures"

SCENARIOS = ["weekday", "weekend", "heatwave", "exam-day"]
CONTROLLERS = ["c1", "c2", "c3", "c4-with", "c4-as-c3"]
REQUIRED_FIGURES = [
    "fig_g1_24h_profile.png",
    "fig_g2_savings.png",
    "fig_g3_pareto.png",
    "fig_g4_co2.png",
    "fig_g5_pred_actual.png",
    "fig_g6_ablation.png",
]

FORBIDDEN_IMPORTS = [
    "from sim", "import sim",
    "from ml", "import ml",
    "from ctrl", "import ctrl",
    "tensorflow", "sklearn", "torch",
]


def _read_app() -> str:
    return APP.read_text(encoding="utf-8")


def _code_lines(src: str) -> list[str]:
    """Non-comment, non-blank lines so header prose can't self-invalidate gates."""
    return [ln for ln in src.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def test_app_parses():
    ast.parse(_read_app())


def test_referenced_csvs_exist():
    src = _read_app()
    refs = set(re.findall(r"results/report_tables/([A-Za-z0-9_.-]+\.csv)", src))
    assert refs, "app references no report_tables CSVs"
    for name in sorted(refs):
        assert (TABLES / name).exists(), f"referenced CSV missing: {name}"
    assert (TABLES / "headline_savings_over_c3.csv").exists()
    assert (TABLES / "g2_savings.csv").exists()


def test_referenced_figures_exist():
    src = _read_app()
    refs = set(re.findall(r"results/figures/([A-Za-z0-9_.-]+\.png)", src))
    assert refs, "app references no figure PNGs"
    for name in sorted(refs):
        assert (FIGS / name).exists(), f"referenced figure missing: {name}"
    for name in REQUIRED_FIGURES:
        assert name in refs, f"graded figure not embedded: {name}"
        assert (FIGS / name).exists(), f"graded figure missing on disk: {name}"


def test_cache_loader_and_sidebar_filters():
    code = "\n".join(_code_lines(_read_app()))
    assert "cache_data" in code, "missing @st.cache_data loader"
    assert "selectbox" in code or "select_box" in code, "missing sidebar selects"
    for scenario in SCENARIOS:
        assert scenario in code, f"scenario option missing: {scenario}"
    for ctrl in CONTROLLERS:
        assert ctrl in code, f"controller key missing: {ctrl}"


def test_no_training_path_imports():
    code = "\n".join(_code_lines(_read_app()))
    for bad in FORBIDDEN_IMPORTS:
        assert bad not in code, f"training-path import leaked into viewer: {bad}"


def test_no_bare_c4_key():
    code = "\n".join(_code_lines(_read_app()))
    # Exact quoted key only — hyphenated c4-with / c4-as-c3 must pass.
    assert not re.search(r"""["']c4["']""", code), "bare c4 controller key used"


def test_graded_figures_shown_as_images_not_replots():
    code = "\n".join(_code_lines(_read_app()))
    assert "st.image" in code, "graded figures must be shown via st.image"
    assert "savefig" not in code, "viewer must never replot graded figures"
