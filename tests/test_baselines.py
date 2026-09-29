"""C1 tracer: 1-day weekday seed-0 run yields kWh > AlwaysOff."""

import numpy as np

from ctrl.baselines import FixedSchedulePolicy
from sim import config as cfg
from sim import metrics
from sim.policy import AlwaysOffPolicy
from sim.simulator import BuildingSim


def run_day(policy, scenario, seed):
    """run.py loop pattern: re-query every CONTROL_HOOK_STEPS, hold between."""
    sim = BuildingSim(rng=np.random.default_rng(seed), scenario=scenario)
    obs = sim.reset(seed=seed)
    action = policy.step(obs)
    powers = {room: [] for room in cfg.ROOMS}
    for step in range(cfg.STEPS_PER_DAY):
        if step % cfg.CONTROL_HOOK_STEPS == 0:
            action = policy.step(obs)
        obs = sim.step(action)
        for room in cfg.ROOMS:
            powers[room].append(obs[room]["power_kW"])
    return sum(metrics.energy_kwh(powers[r]) for r in cfg.ROOMS)


def test_c1_weekday_seed0_positive_kwh_above_always_off():
    c1_kwh = run_day(FixedSchedulePolicy(scenario="weekday"), "weekday", 0)
    off_kwh = run_day(AlwaysOffPolicy(), "weekday", 0)
    assert c1_kwh > 0
    assert c1_kwh > off_kwh
