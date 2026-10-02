"""Style guards for the dashboard card system (ui-ux-pro-max).

The designer contract: metric/chart/image/table surfaces render as bordered
cards with shadows; theme carries the design-system palette; no emoji icons.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "dashboard" / "app.py"
CSS = ROOT / "dashboard" / "style.css"
TOML = ROOT / ".streamlit" / "config.toml"


def test_style_css_exists_and_loads():
    assert CSS.exists(), "dashboard/style.css missing"
    src = APP.read_text(encoding="utf-8")
    assert "style.css" in src, "app.py does not load style.css"
    css = CSS.read_text(encoding="utf-8")
    for surface in ("stMetric", "stPlotlyChart", "stImage", "stDataFrame"):
        assert surface in css, f"card style missing for {surface}"


def test_cards_have_border_shadow_radius():
    css = CSS.read_text(encoding="utf-8")
    assert re.search(r"border:\s*1px solid #E2E8F0", css), "card border missing"
    assert "border-radius: 12px" in css, "card radius missing"
    assert "box-shadow" in css, "card shadow missing"
    assert "prefers-reduced-motion" in css, "reduced-motion guard missing"


def test_theme_palette():
    toml = TOML.read_text(encoding="utf-8")
    for hexcode in ("#1E40AF", "#F8FAFC", "#0F172A"):
        assert hexcode in toml, f"palette color {hexcode} missing from theme"


def test_no_emoji_page_icon():
    src = APP.read_text(encoding="utf-8")
    assert 'page_icon=":' not in src, "emoji page icon violates icon rules"
