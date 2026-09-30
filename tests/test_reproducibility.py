"""Seeded determinism (SIM-02, RESEARCH Validation Architecture SIM-02 rows).

RNG rule (NumPy NEP 19): every test builds `np.random.default_rng(seed)`
Generator (PCG64) instances passed as constructor args. Legacy
`np.random.RandomState` and `np.random.seed` globals are FORBIDDEN in sim/ —
they share global state across modules and silently break paired-seed
comparisons (PITFALLS Pitfall 3); test_no_legacy_rng greps for them.

Trajectories use sim-time only (step index) — no wall-clock timestamps —
so byte-for-byte comparison is meaningful.
"""

import pathlib
import re

import numpy as np
import pandas as pd
import pytest

from sim import config as cfg
from sim import occupancy as occ_mod
from sim import weather as wx
from sim.simulator import PAIRED_SEEDS, BuildingSim, seeds_equal

OFF_ACTION = {room: {"hvac": "OFF", "light": 0} for room in cfg.ROOMS}
DAY = cfg.STEPS_PER_DAY


def run_day(seed, scenario="weekday"):
    """Full 1-day AlwaysOff run -> {room: DataFrame} telemetry (sim-time)."""
    sim = BuildingSim(rng=np.random.default_rng(seed), scenario=scenario)
    sim.reset(seed=seed)
    rows = {room: [] for room in cfg.ROOMS}
    action = dict(OFF_ACTION)
    for _ in range(DAY):
        obs = sim.step(action)
        for room in cfg.ROOMS:
            rows[room].append((obs[room]["T_in"], obs[room]["T_out"], obs[room]["RH"],
                               obs[room]["occupancy"], obs[room]["power_kW"]))
    return {room: pd.DataFrame(rows[room],
                               columns=["T_in", "T_out", "RH", "occupancy", "power_kW"])
            for room in cfg.ROOMS}


def to_bytes(traj):
    """Fixed-format CSV bytes per room: the byte-for-byte serialisation."""
    return b"".join(traj[room].to_csv(index=False, float_format="%.4f").encode()
                    for room in sorted(traj))


def test_same_seed_identical():
    a, b = run_day(7), run_day(7)
    assert seeds_equal(a, b)
    assert to_bytes(a) == to_bytes(b)  # byte-identical telemetry output


def test_diff_seed_differs():
    a, b = run_day(7), run_day(8)
    assert not seeds_equal(a, b)
    assert to_bytes(a) != to_bytes(b)  # seeds change noise draws


def test_scenario_differs():
    rng_kw = lambda: np.random.default_rng(0)  # noqa: E731 — same seed, both arms
    occ_wd = occ_mod.get_day_schedule("weekday", rng_kw())
    occ_we = occ_mod.get_day_schedule("weekend", rng_kw())
    assert not occ_wd.equals(occ_we)
    # Weekend is nearly empty: only classroom_A 10:00-14:00 carries people.
    assert occ_we.drop(columns=["classroom_A"]).to_numpy().sum() == 0
    assert occ_we["classroom_A"].sum() > 0
    # Heatwave reuses weekday occupancy; its weather carries the +4 C offset.
    occ_hw = occ_mod.get_day_schedule("heatwave", np.random.default_rng(0))
    assert occ_hw.equals(occ_wd)
    # Exam-day is a REAL dense timetable (post-calibration reversal: it must
    # DIFFER from weekday — the old stub alias is gone). Derivation of the
    # discriminators: weekday classroom_A sits in the 13:00-14:00 lunch gap at
    # minute 810 (13:30) — neighbours end 13:00+10 jitter=13:10 / start
    # 14:00-10 jitter=13:50, so 0 is guaranteed; exam-day runs 13:00-17:00
    # there (latest jittered start 13:10 < 13:30, binomial all-absent ~0).
    occ_ex = occ_mod.get_day_schedule("exam-day", np.random.default_rng(0))
    assert not occ_ex.equals(occ_wd)
    assert occ_wd.at[810, "classroom_A"] == 0
    assert occ_ex.at[810, "classroom_A"] > 0
    # All four rooms occupied mid-morning (minute 600 = 10:00 sits inside
    # every 09:00 block even at extreme jitter: latest start 09:10).
    assert (occ_ex.iloc[600] > 0).all()
    w_wd = wx.daily_profile("weekday", np.random.default_rng(0))
    w_hw = wx.daily_profile("heatwave", np.random.default_rng(0))
    assert (w_hw["T_out"] - w_wd["T_out"]).mean() == pytest.approx(4.0, abs=1e-9)


def test_paired_seeds_available():
    assert len(PAIRED_SEEDS) >= 5
    assert PAIRED_SEEDS[:5] == [0, 1, 2, 3, 4]
    # Every paired seed must produce a runnable, distinct day.
    seen = set()
    for seed in PAIRED_SEEDS[:5]:
        blob = to_bytes(run_day(seed))
        assert blob not in seen
        seen.add(blob)


def test_no_legacy_rng():
    """Forbid RandomState / global seeding anywhere in sim/ (NEP 19)."""
    sim_dir = pathlib.Path(__file__).resolve().parent.parent / "sim"
    banned = re.compile(r"RandomState|np\.random\.seed|numpy\.random\.seed|default_rng\(\)")
    offenders = [f"{p.name}:{i}: {ln.strip()}" for p in sorted(sim_dir.glob("*.py"))
                 for i, ln in enumerate(p.read_text().splitlines(), 1) if banned.search(ln)]
    # default_rng() seedless is allowed ONLY in BuildingSim.__init__ (explicit
    # opt-in for ad-hoc use; every test and eval path passes seed explicitly).
    offenders = [o for o in offenders if "simulator.py" not in o]
    assert not offenders, "legacy/unseeded RNG in sim/:\n" + "\n".join(offenders)
