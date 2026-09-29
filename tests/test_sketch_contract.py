"""Sketch-contract tests (Phase 2 plan 02, D-08/D-09, T-02-06).

Pins iot/esp32_node.ino to iot/topics.py: any topic drift fails the suite.
Also enforces D-10 (commands never retained, repo-wide) and D-12 (no
forecast traffic on the bus).
"""

import json
import pathlib
import re

from iot import topics

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKETCH = ROOT / "iot" / "esp32_node.ino"

SAMPLE_ROOM = "classroom_A"


def sketch_text():
    return SKETCH.read_text(encoding="utf-8")


def test_topic_literals_match_topics_helpers():
    text = sketch_text()
    room = re.search(r'#define\s+ROOM_ID\s+"([^"]+)"', text).group(1)
    literals = set(re.findall(r'"(building/[A-Za-z0-9_/#]+)"', text))
    assert topics.telemetry_topic(room) in literals
    assert topics.status_topic(room) in literals
    assert topics.command_filter(room) in literals
    # Sample-room spot check against helper output (drift-proof, not hardcoded).
    assert topics.telemetry_topic(SAMPLE_ROOM) == f"building/{SAMPLE_ROOM}/telemetry"
    assert topics.command_filter(SAMPLE_ROOM) in literals or room != SAMPLE_ROOM


def test_buffer_512_and_payload_fits():
    text = sketch_text()
    assert re.search(r"setBufferSize\s*\(\s*512\s*\)", text), "PubSubClient buffer must be 512 B"
    sample = {
        "timestamp": "2026-01-15T00:07:00", "room": SAMPLE_ROOM, "T_in_C": 24.1234,
        "T_out_C": 31.5678, "RH_pct": 55.1234, "occupancy": 28,
        "HVAC_state": "REDUCED", "power_kW": 1.3667, "light_on": 1,
    }
    assert len(json.dumps(sample).encode()) < 512


def test_commands_never_retained_repo_wide():
    # .py: no retain=True on a command-topic line (status is the only retained topic).
    offenders = [
        f"{p.relative_to(ROOT)}:{i}: {line.strip()}"
        for p in ROOT.rglob("*.py")
        if ".venv" not in p.parts and "site-packages" not in p.parts
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if re.search(r"retain\s*=\s*True", line) and "command" in line.lower()
        and not line.strip().startswith("#")
    ]
    assert offenders == [], f"retained command publish: {offenders}"
    # .ino: the sketch never publishes to a command topic at all.
    cmd_pubs = [
        line.strip()
        for line in sketch_text().splitlines()
        if "publish" in line and "command" in line.lower()
    ]
    assert cmd_pubs == [], f"sketch publishes to command topic: {cmd_pubs}"


def test_no_forecast_topics_under_iot():
    hits = [
        str(p.relative_to(ROOT))
        for p in (ROOT / "iot").rglob("*")
        if p.is_file() and "forecast" in p.read_text(encoding="utf-8", errors="replace").lower()
    ]
    assert hits == [], f"forecast traffic on the bus: {hits}"
