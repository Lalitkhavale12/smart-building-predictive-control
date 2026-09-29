"""Harness + C3 tracer tests (Phase 3 plan 02, D-05/D-06/D-07/D-08/D-13)."""

import pathlib

import numpy as np
import pandas as pd
import pytest

from ctrl.baselines import (
    FixedSchedulePolicy,
    OccupancyRulePolicy,
    SetbackPolicy,
)
from ctrl.harness import run_controller
from sim import config as cfg
from sim.logger import TELEMETRY_COLUMNS


def _obs(occupancy):
    return {"lab": {"occupancy": occupancy}}


def test_c3_one_day_run_schema_and_metrics():
    frame, metrics = run_controller(SetbackPolicy(), "weekday", 0)
    assert len(frame) == cfg.STEPS_PER_DAY * len(cfg.ROOMS)  # 1440 * 4
    assert list(frame.columns) == TELEMETRY_COLUMNS
    assert metrics["energy_kwh"] > 0
    for key in ("energy_kwh", "cost_rs", "co2_kg", "comfort_pct"):
        assert key in metrics
    comfort = metrics["comfort_pct"]
    assert pd.isna(comfort) or 0.0 <= comfort <= 100.0


def test_c3_reduced_while_c2_off_at_30min_vacancy():
    c2, c3 = OccupancyRulePolicy(), SetbackPolicy()
    assert c2.step(_obs(2))["lab"]["hvac"] == "ON"
    assert c3.step(_obs(2))["lab"]["hvac"] == "ON"
    for _ in range(6):  # 6 empty calls x 5 sim-min = 30 empty minutes
        c2_hvac = c2.step(_obs(0))["lab"]["hvac"]
        c3_hvac = c3.step(_obs(0))["lab"]["hvac"]
    assert c2_hvac == "OFF"
    assert c3_hvac == "REDUCED"


def test_c3_off_after_60min_vacancy_and_on_when_occupied():
    policy = SetbackPolicy()
    policy.step(_obs(1))
    for _ in range(12):  # 12 x 5 = 60 empty minutes
        hvac = policy.step(_obs(0))["lab"]["hvac"]
    assert hvac == "OFF"
    assert policy.step(_obs(3))["lab"]["hvac"] == "ON"  # reoccupancy resets


@pytest.mark.parametrize("factory", [
    lambda scenario: FixedSchedulePolicy(scenario=scenario),
    lambda scenario: OccupancyRulePolicy(),
    lambda scenario: SetbackPolicy(),
], ids=["c1", "c2", "c3"])
def test_rerun_byte_identical(factory):
    """Same seed + controller → DataFrame.equals AND byte-identical CSV text."""
    frame_a, _ = run_controller(factory("weekday"), "weekday", 2)
    frame_b, _ = run_controller(factory("weekday"), "weekday", 2)
    assert frame_a.equals(frame_b)
    csv_a = frame_a.to_csv(index=False, float_format="%.4f")
    csv_b = frame_b.to_csv(index=False, float_format="%.4f")
    assert csv_a.encode() == csv_b.encode()


def test_no_scalar_carbon_constant_in_ctrl():
    """Carbon/cost come only from grid.hourly_rows() — never a scalar in ctrl/."""
    import re

    pattern = re.compile(r"EMISSION_FACTOR|EF_KG|0\.710")
    hits = [
        (path.name, lineno, line.strip())
        for path in sorted(pathlib.Path("ctrl").glob("*.py"))
        for lineno, line in enumerate(path.read_text().splitlines(), 1)
        if pattern.search(line)
    ]
    assert hits == [], f"scalar emission constant in ctrl/: {hits}"
