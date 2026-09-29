"""Outdoor weather (SIM-02 / D-06, RESEARCH Findings section 4).

T_out(t) = T_mean + A*sin(2*pi*(t_hours - 9)/24) + heatwave_offset + noise.
All constants live in sim/config.py. Noise and the RH walk draw ONLY from the
passed-in rng (the sim Generator) — never globals.

Simplification (documented, not hidden): RH is a bounded random walk with NO
physics coupling to temperature. Real psychrometrics are deferred — never
needed in v1 (RESEARCH section 4). Since RH is uncoupled, comfort-RH failures
are noise-driven; acceptable in Phase 1.
"""

import math

import pandas as pd

from sim import config as cfg


def validate_scenario(scenario):
    """Scenario gate: author-controlled strings only (threat-model boundary)."""
    if scenario not in cfg.SCENARIOS:
        raise ValueError(f"scenario must be one of {cfg.SCENARIOS}, got {scenario!r}")
    return scenario


def heatwave_offset(scenario):
    """+4 C in the heatwave scenario, 0 otherwise (incl. exam-day stub)."""
    return cfg.HEATWAVE_OFFSET if validate_scenario(scenario) == "heatwave" else 0.0


def base_temp(minute):
    """Noise-free sinusoid: mean 31 C, max 35 C at 15:00, min 27 C at 03:00."""
    t_hours = minute / 60.0
    return cfg.T_OUT_MEAN + cfg.T_OUT_AMPLITUDE * math.sin(2 * math.pi * (t_hours - 9) / 24.0)


def outdoor_temp(minute, scenario, rng):
    """Single-step outdoor temp with scenario offset + seeded gaussian noise."""
    return base_temp(minute) + heatwave_offset(scenario) + float(rng.normal(0.0, cfg.T_OUT_NOISE_STD))


def rh_step(prev_rh, rng):
    """One bounded-random-walk step from prev RH (uncoupled from T by design)."""
    return float(min(cfg.RH_MAX, max(cfg.RH_MIN, prev_rh + float(rng.normal(0.0, cfg.RH_STEP_STD)))))


def daily_profile(scenario, rng, n_minutes=cfg.STEPS_PER_DAY):
    """Full-day weather series: DataFrame with T_out / RH columns.

    Draw order: the whole T_out noise series first, then the RH walk, so
    the temperature trace is an independent sub-stream — retuning an RH
    parameter never reshapes T_out (ablation hygiene).
    """
    validate_scenario(scenario)
    t_out = [outdoor_temp(minute, scenario, rng) for minute in range(n_minutes)]
    rh, prev = [], cfg.RH_INIT
    for _ in range(n_minutes):
        prev = rh_step(prev, rng)
        rh.append(prev)
    return pd.DataFrame({"T_out": t_out, "RH": rh})
