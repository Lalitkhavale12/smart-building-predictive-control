"""Harness + C3 tracer tests (Phase 3 plan 02, D-05/D-06/D-07/D-13)."""

import numpy as np
import pandas as pd
import pytest

from ctrl.baselines import OccupancyRulePolicy, SetbackPolicy
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
