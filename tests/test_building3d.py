"""Smoke tests for the 3D building twin (viz/building3d.py).

Guards: locked floor map (F1 = 2 classrooms, F2 = office + lab, F3 terrace
visual-only), figure builds from real saved telemetry, colors in range,
viewer rules (saved frames only — no sim/ml/ctrl imports).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

APP = pathlib.Path(__file__).resolve().parent.parent / "viz" / "building3d.py"

SIM_ROOMS = {"classroom_A", "classroom_B", "office", "lab"}


def _read() -> str:
    return APP.read_text(encoding="utf-8")


def test_module_parses():
    ast.parse(_read())


def test_floor_map_locked():
    from viz.building3d import ROOMS

    by_floor = {}
    for room, floor, *_rest, simulated in ROOMS:
        by_floor.setdefault(floor, []).append((room, simulated))
    assert {r for r, _ in by_floor[1]} == {"classroom_A", "classroom_B"}
    assert {r for r, _ in by_floor[2]} == {"office", "lab"}
    assert all(sim for _, sim in by_floor[1] + by_floor[2])
    assert by_floor[3] == [("terrace", False)]


def test_no_training_path_imports():
    code = "\n".join(
        ln for ln in _read().splitlines() if ln.strip() and not ln.strip().startswith("#")
    )
    for bad in ("from sim", "import sim", "from ml", "import ml",
                "from ctrl", "import ctrl", "tensorflow", "sklearn"):
        assert bad not in code, f"training-path import leaked: {bad}"


def test_figure_from_real_telemetry():
    from viz.building3d import ROOMS, T_MAX, T_MIN, build_figure

    fig = build_figure("c4-with", "weekday", 0, 12)
    assert len(fig.data) == len(ROOMS)  # 4 rooms + terrace
    for trace, (room, *_rest, simulated) in zip(fig.data, ROOMS):
        if not simulated:
            continue
        vals = list(trace["intensity"])
        assert vals and all(T_MIN - 15 <= v <= T_MAX + 15 for v in vals)


def test_all_hours_build():
    from viz.building3d import build_figure

    for hour in (0, 8, 12, 18, 23):
        fig = build_figure("c3", "heatwave", 2, hour)
        assert len(fig.data) == 5


def test_missing_frame_raises():
    from viz.building3d import build_figure

    with pytest.raises(FileNotFoundError):
        build_figure("c1", "weekday", 99, 12)
