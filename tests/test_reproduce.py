"""Reproduce smoke test (Phase 6, plan 06-02, DASH-02 / D-07).

Pins requirements.txt streamlit/plotly == pins, the protocols.md comparison
table + TLS note, and the G7 slot (exactly one of PNG or placeholder stub).
Run: pytest tests/test_reproduce.py -q -k 'protocols or pins'
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _non_comment_lines(path):
    return [ln for ln in pathlib.Path(path).read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def test_pins_streamlit_plotly():
    lines = _non_comment_lines(ROOT / "requirements.txt")
    text = "\n".join(lines)
    assert re.search(r"^streamlit==\S+", text, re.M), "streamlit == pin missing"
    assert re.search(r"^plotly==\S+", text, re.M), "plotly == pin missing"


def test_protocols_table():
    text = (ROOT / "docs" / "protocols.md").read_text()
    assert "MQTT" in text and "HTTP" in text and "CoAP" in text
    assert "Overhead" in text
    assert "QoS" in text
    assert "Suitability here" in text


def test_protocols_tls_note():
    text = (ROOT / "docs" / "protocols.md").read_text()
    assert "8883" in text
    assert "mosquitto.conf" in text
    assert "allow_anonymous" in text


def test_protocols_g7_slot():
    figs = ROOT / "results" / "figures"
    png = figs / "fig_g7_dashboard.png"
    stub = figs / "fig_g7_dashboard_placeholder.txt"
    assert png.exists() or stub.exists(), "G7 slot holds neither PNG nor stub"
    assert not (png.exists() and stub.exists()), "G7 slot holds both PNG and stub"
