"""C1 tracer: 1-day weekday seed-0 run yields kWh > AlwaysOff."""

import numpy as np

from ctrl.baselines import FixedSchedulePolicy, OccupancyRulePolicy
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


def _obs(occupancy):
    return {"lab": {"occupancy": occupancy}}


def test_c2_flips_off_exactly_after_15_empty_sim_minutes():
    policy = OccupancyRulePolicy()
    assert policy.step(_obs(3))["lab"]["hvac"] == "ON"
    assert policy.step(_obs(0))["lab"]["hvac"] == "ON"  # 5 min
    assert policy.step(_obs(0))["lab"]["hvac"] == "ON"  # 10 min
    assert policy.step(_obs(0))["lab"]["hvac"] == "OFF"  # 15 min


def test_c2_vacancy_min_5_flips_after_one_empty_call():
    policy = OccupancyRulePolicy(vacancy_min=5)
    assert policy.step(_obs(2))["lab"]["hvac"] == "ON"
    assert policy.step(_obs(0))["lab"]["hvac"] == "OFF"


def test_c2_reoccupancy_resets_timer():
    policy = OccupancyRulePolicy()
    policy.step(_obs(1))
    policy.step(_obs(0))  # 5 min
    policy.step(_obs(0))  # 10 min
    assert policy.step(_obs(4))["lab"]["hvac"] == "ON"  # reset
    assert policy.step(_obs(0))["lab"]["hvac"] == "ON"  # 5 min again
    assert policy.step(_obs(0))["lab"]["hvac"] == "ON"  # 10 min again
    assert policy.step(_obs(0))["lab"]["hvac"] == "OFF"  # 15 min again


def test_c2_lights_follow_current_occupancy():
    policy = OccupancyRulePolicy()
    assert policy.step(_obs(2))["lab"]["light"] == 1
    assert policy.step(_obs(0))["lab"]["light"] == 0


def test_c2_reads_no_timetable():
    import pathlib

    src = pathlib.Path("ctrl/baselines.py").read_text()
    assert "TIMETABLES" not in src
