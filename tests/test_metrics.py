"""Comfort metric gate (SIM-04, D-11/D-12, RESEARCH Findings section 7).

Band: 22.0 <= T_in <= 26.0 AND 30.0 <= RH <= 60.0 over occupied steps only;
comfort_pct = 100 * in-comfort occupied / total occupied; empty room -> NaN.
"""

import math

import pandas as pd
import pytest

from sim import metrics as met


def _frame(rows):
    """rows: (T_in, RH, occupied) -> telemetry-shaped frame."""
    return pd.DataFrame(
        [{"T_in_C": t, "RH_pct": rh, "occupancy": o, "power_kW": 0.0}
         for t, rh, o in rows]
    )


def test_fully_comfortable():
    frame = _frame([(24.0, 45.0, 2)] * 60)
    assert met.comfort_pct(frame) == 100.0


def test_partially_comfortable():
    frame = _frame([(24.0, 45.0, 2)] * 30 + [(30.0, 45.0, 2)] * 30)
    assert met.comfort_pct(frame) == 50.0


def test_temp_only_fail():
    """T outside band, RH fine -> zero comfort (temp alone gates)."""
    frame = _frame([(30.0, 45.0, 3)] * 20)
    assert not met.comfort_flag(30.0, 45.0, 3)
    assert met.comfort_pct(frame) == 0.0


def test_rh_only_fail():
    """RH outside band, T fine -> zero comfort (RH alone gates)."""
    frame = _frame([(24.0, 75.0, 3)] * 20)
    assert met.comfort_pct(frame) == 0.0


def test_unoccupied_frames_excluded():
    """Empty steps (even with terrible T/RH) leave the denominator alone."""
    frame = _frame([(24.0, 45.0, 2)] * 10 + [(40.0, 90.0, 0)] * 100)
    assert met.comfort_pct(frame) == 100.0


def test_empty_room_nan():
    """Zero occupied steps -> NaN, never 100% (the no-comfort-blind rule)."""
    frame = _frame([(24.0, 45.0, 0)] * 60)
    assert math.isnan(met.comfort_pct(frame))


def test_energy_kwh_sums_power_over_sixtieth():
    power = pd.Series([1.2] * 60)  # 1.2 kW for one hour -> 1.2 kWh
    assert met.energy_kwh(power) == pytest.approx(1.2)
