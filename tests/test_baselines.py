"""C1 tracer: 1-day weekday seed-0 run yields kWh > AlwaysOff."""

import numpy as np

from ctrl.baselines import FixedSchedulePolicy, OccupancyRulePolicy
from ctrl.schedules import is_on
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


def test_is_on_classroom_weekday_boundaries():
    assert is_on("classroom_A", 8 * 60, "weekday") is True
    assert is_on("classroom_A", 18 * 60 - 1, "weekday") is True
    assert is_on("classroom_A", 18 * 60, "weekday") is False


def test_is_on_weekend_mostly_off():
    assert is_on("classroom_A", 10 * 60, "weekend") is True
    assert is_on("classroom_A", 14 * 60, "weekend") is False
    for room in ("classroom_B", "office", "lab"):
        assert is_on(room, 12 * 60, "weekend") is False


def test_is_on_lab_evening_and_gap():
    assert is_on("lab", 18 * 60 + 30, "weekday") is True  # evening block
    assert is_on("lab", 14 * 60 + 30, "weekday") is False  # mid gap


def test_is_on_heatwave_matches_weekday():
    for room in ("classroom_A", "classroom_B", "office", "lab"):
        for minute in (0, 8 * 60, 12 * 60, 18 * 60 + 30, 23 * 60):
            assert is_on(room, minute, "heatwave") == is_on(
                room, minute, "weekday"
            )


def test_c1_weekend_energy_below_weekday():
    weekend = run_day(FixedSchedulePolicy(scenario="weekend"), "weekend", 0)
    weekday = run_day(FixedSchedulePolicy(scenario="weekday"), "weekday", 0)
    assert weekend < weekday
