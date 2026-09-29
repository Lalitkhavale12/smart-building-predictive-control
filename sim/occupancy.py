"""Seeded occupancy timetables (SIM-02 / D-04, RESEARCH Findings section 3).

Block tables live in sim/config.py (TIMETABLES) — this module only parses them.
Per-run stochastic deviations use ONLY the passed-in rng (a
numpy.random.Generator from BuildingSim): +-10 min jitter on block edges,
5 % per-person absence, Poisson fill for office blocks. Sharp deterministic
edges are forbidden: they make forecasting trivially easy (PITFALLS Pitfall 2).

No ML hooks, no MQTT here (phase boundary).
"""

import numpy as np
import pandas as pd

from sim import config as cfg


def _to_min(hhmm):
    """'HH:MM' -> minutes since midnight."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def get_day_schedule(scenario, rng, n_minutes=cfg.STEPS_PER_DAY):
    """Per-minute occupancy counts: DataFrame indexed by minute, one col/room.

    Args:
        scenario: one of cfg.SCENARIOS. 'heatwave' reuses the weekday
            occupancy pattern (only weather differs); 'exam-day' is a STUB
            that returns weekday blocks until a real exam timetable lands.
        rng: numpy.random.Generator — the sim RNG, never a global.
        n_minutes: day length (default 1440).

    Determinism: rooms in sorted order, blocks in table order — same
    (code, config, seed) -> identical frame.
    """
    if scenario not in cfg.SCENARIOS:
        raise ValueError(f"scenario must be one of {cfg.SCENARIOS}, got {scenario!r}")
    table = cfg.TIMETABLES[cfg.SCENARIO_TABLE[scenario]]
    jitter, absence_p = cfg.OCC_EDGE_JITTER_MIN, cfg.OCC_ABSENCE_P
    frame = {}
    for room in sorted(cfg.ROOMS):  # fixed order: determinism
        occ = np.zeros(n_minutes, dtype=int)
        for start, end, fill in table[room]:
            s = min(n_minutes, max(0, _to_min(start) + int(rng.integers(-jitter, jitter + 1))))
            e = min(n_minutes, max(0, _to_min(end) + int(rng.integers(-jitter, jitter + 1))))
            if e <= s:
                continue  # jitter inversion guard (dead on hour-long blocks)
            n = e - s
            if isinstance(fill, str) and fill.startswith("poisson:"):
                lam = float(fill.split(":")[1])
                occ[s:e] = np.clip(rng.poisson(lam, size=n), 0, cfg.OFFICE_MAX)
            else:
                # 5 % random absence: each head present w.p. 1-p, per minute.
                occ[s:e] = rng.binomial(int(fill), 1.0 - absence_p, size=n)
        frame[room] = occ
    return pd.DataFrame(frame, index=range(n_minutes))
