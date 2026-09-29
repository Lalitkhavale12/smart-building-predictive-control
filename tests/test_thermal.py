"""Thermal sanity numbers (SIM-01, RESEARCH Findings section 2 table).

DEVIATION (Rule 1 — spec arithmetic fix, see 01-01-SUMMARY.md): two of the
four bands in the plan draft were hand-computed inconsistently with the very
R/C/Q the plan pins, and no in-band retune exists — the four literal bands
are mathematically irreconcilable for ANY single (R, C, Q):
  - pull-down 30->24 ON: plan said 20-35 min; model gives ~13 min.
    dT/dt ~= Q_ON/C = -3.5/0.12 ~= -29 C/h -> 6 K in ~13 min (envelope term
    is second-order). 20-35 min would need C ~= 0.2-0.34, which breaks decay.
  - occupancy kick, 30 people OFF: plan said +0.5-1.5 C/30 min; model gives
    ~+12 C. 30*0.10 = 3.0 kW into C = 0.12 kWh/K is ~0.42 C/min — a sealed
    classroom genuinely overheats fast (that is WHY rooms need AC). +1 C
    corresponds to ~3 occupants (office scale), suggesting the draft band was
    computed for 3 people but written as 30.
Config values are kept EXACTLY as specified (they match the cited anchors and
satisfy decay/tau/heatwave); the two erroneous bands are corrected below with
derivations. Sign-error detection (the tests' purpose) is fully preserved:
flipped/dropped Q terms fail the corrected bands.
"""

import warnings

import pytest

from sim import config as cfg
from sim.thermal import thermal_step

warnings.simplefilter("ignore")  # py-version notice; irrelevant to physics

R, C = 30.0, 0.12  # base-room values under test


def test_pulldown_time():
    """Empty room 30 -> 24 C at ON reaches setpoint in 8-20 min (~13)."""
    t_in, steps = 30.0, 0
    while t_in > 24.0 and steps < 5000:
        t_in = thermal_step(t_in, 31.0, 0.0, cfg.Q_HVAC["ON"], R, C)
        steps += 1
    assert 8 <= steps <= 20, f"pull-down took {steps} min, expected 8-20"


def test_decay_rate():
    """OFF with T_out - T_in = 4 K drifts 1.0-1.2 C/h; tau ~= 3.6 h."""
    t0 = 27.0
    drift_per_h = (thermal_step(t0, 31.0, 0.0, 0.0, R, C) - t0) * 60
    assert 1.0 <= drift_per_h <= 1.2, f"decay {drift_per_h:.3f} C/h outside 1.0-1.2"
    assert cfg.BASE_TAU_HOURS == pytest.approx(3.6, abs=0.05)


def test_heatwave_hold():
    """Continuous ON vs 38 C outdoor holds 24 C with duty < 100% (~13%)."""
    t_ss = 38.0 + R * cfg.Q_HVAC["ON"]  # steady state under full cooling
    assert t_ss < 24.0, f"ON cannot hold setpoint: steady state {t_ss:.1f} C"
    duty = abs((24.0 - 38.0) / R / cfg.Q_HVAC["ON"])
    assert duty < 1.0, f"duty {duty:.2f} >= 100%"


def test_occupancy_kick():
    """30 occupants, HVAC OFF: room gains +8-14 C over 30 min (~12).

    3.0 kW into C = 0.12 kWh/K ~= 0.42 C/min initial rate. A flipped Q_occ
    sign would COOL the room; a dropped term would show only ~+0.5 C from
    envelope leak — both fail this band.
    """
    t_in = 27.0
    for _ in range(30):
        t_in = thermal_step(t_in, 31.0, 30 * cfg.Q_OCC_PER_PERSON, 0.0, R, C)
    rise = t_in - 27.0
    assert 8.0 <= rise <= 14.0, f"occupancy rise {rise:.2f} C outside 8-14"
