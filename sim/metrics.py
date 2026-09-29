"""Comfort + energy scoring (SIM-04, D-11/D-12, RESEARCH Findings section 7).

Band (locked guide default): occupied frames where 22.0 <= T_in <= 26.0 AND
30.0 <= RH <= 60.0. comfort_pct = 100 * in-comfort occupied steps / total
occupied steps; an empty room (zero occupied steps) returns NaN — never 100%.

NOTE on RH: humidity is an uncoupled random walk (sim/weather.py documents
the simplification), so comfort-RH failures are noise-driven — acceptable in
Phase 1. The band must NEVER be retuned to make results pass; the +-1 C
sensitivity sweep lives in Phase 5.
"""

import math

import numpy as np

from sim import config as cfg


def comfort_flag(t_in, rh, occupied):
    """Elementwise in-comfort mask (scalars, arrays, or Series — all work)."""
    occupied = np.asarray(occupied) > 0
    t_ok = (np.asarray(t_in, dtype=float) >= cfg.COMFORT_T_MIN) & (
        np.asarray(t_in, dtype=float) <= cfg.COMFORT_T_MAX
    )
    rh_ok = (np.asarray(rh, dtype=float) >= cfg.COMFORT_RH_MIN) & (
        np.asarray(rh, dtype=float) <= cfg.COMFORT_RH_MAX
    )
    return occupied & t_ok & rh_ok


def comfort_pct(frame):
    """Comfort % over occupied steps of a telemetry frame; NaN if never occupied."""
    occupied = np.asarray(frame["occupancy"]) > 0
    total = int(occupied.sum())
    if total == 0:
        return math.nan
    flag = comfort_flag(frame["T_in_C"], frame["RH_pct"], frame["occupancy"])
    return 100.0 * float(np.asarray(flag).sum()) / total


def energy_kwh(power_kw):
    """Electrical energy [kWh] from a power_kW series (1-min steps -> 1/60 h)."""
    return float((np.asarray(power_kw, dtype=float) * (1.0 / 60.0)).sum())


def room_stats(frame):
    """Per-room, per-run triple the summary helper aggregates over seeds."""
    return {
        "mean_T_in": float(np.asarray(frame["T_in_C"], dtype=float).mean()),
        "energy_kwh": energy_kwh(frame["power_kW"]),
        "comfort_pct": comfort_pct(frame),
    }
