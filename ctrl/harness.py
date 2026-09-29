"""Comparison harness (Phase 3, D-07/D-09): run any BasePolicy over the sim directly.

``run_controller(policy, scenario, seed, days=1, forecast=None, signals=None)``
drives ``BuildingSim`` DIRECTLY (never the MQTT bridge — bridge compat is
asserted by one wiring test only), reusing the run.py loop pattern
(reset(seed) → policy every CONTROL_HOOK_STEPS, hold between → sim.step →
TelemetryLogger.record with sorted ROOMS, so CSVs are schema-identical to
Phase-1 output: TELEMETRY_COLUMNS order, %.4f, sim-time stamps from RUN_START).

C4-ready: ``forecast``/``signals`` are forwarded into every policy.step call
(C1–C3 accept and ignore them), so the predictive controller plugs in with
zero harness edits (Phase-5 embryo).

Per-run metrics: energy_kwh summed over 4 rooms via metrics.energy_kwh;
cost_rs / co2_kg by joining per-minute power/60 against grid.hourly_rows() on
timestamp.hour (day-agnostic by construction); comfort_pct as the
occupied-step-weighted mean across rooms (weights = occupied step counts; NaN
rooms contribute zero weight — never a naive mean of per-room pct). No scalar
emission constant anywhere: carbon/cost come only from the hourly grid series.
"""

import numpy as np
import pandas as pd

from sim import config as cfg
from sim import grid as grid_mod
from sim import logger as log_mod
from sim import metrics as met
from sim.simulator import BuildingSim


def compute_metrics(frame):
    """Per-run (energy_kwh, cost_rs, co2_kg, comfort_pct) from a telemetry frame."""
    hours = pd.to_datetime(frame["timestamp"]).dt.hour
    ef_by_hour = {h: ef for h, ef, _ in grid_mod.hourly_rows()}
    price_by_hour = {h: price for h, _, price in grid_mod.hourly_rows()}
    energy = sum(met.energy_kwh(g["power_kW"]) for _, g in frame.groupby("room"))
    power_per_min = frame["power_kW"] / 60.0
    cost = float((power_per_min * hours.map(price_by_hour)).sum())
    co2 = float((power_per_min * hours.map(ef_by_hour)).sum())
    weighted, weight_total = 0.0, 0
    for _, group in frame.groupby("room"):
        weight = int((group["occupancy"] > 0).sum())
        room_comfort = met.comfort_pct(group)
        if weight > 0 and not pd.isna(room_comfort):
            weight_total += weight
            weighted += room_comfort * weight
    comfort = weighted / weight_total if weight_total else float("nan")
    return {
        "energy_kwh": energy,
        "cost_rs": cost,
        "co2_kg": co2,
        "comfort_pct": comfort,
    }


def run_controller(policy, scenario, seed, days=1, forecast=None, signals=None):
    """One controller × scenario × seed run → (telemetry_df, per_run_metrics)."""
    sim = BuildingSim(rng=np.random.default_rng(seed), scenario=scenario)
    obs = sim.reset(seed=seed)
    logger = log_mod.TelemetryLogger()
    action = policy.step(obs, forecast=forecast, signals=signals)
    total = int(days) * cfg.STEPS_PER_DAY
    for step in range(total):
        if step % cfg.CONTROL_HOOK_STEPS == 0:
            action = policy.step(obs, forecast=forecast, signals=signals)
        obs = sim.step(action)
        for room in sorted(cfg.ROOMS):
            logger.record(step, room, obs[room], action[room])
    frame = logger.to_frame()
    return frame, compute_metrics(frame)
