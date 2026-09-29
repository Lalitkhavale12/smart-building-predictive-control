"""4-room building simulator (D-14): `BuildingSim` with reset/step interface.

`step(action)` is the ONLY place sim-time advances. One step = 1 minute.
Phase 3 calls the policy every 5th step (CONTROL_HOOK_STEPS) and holds the
action between calls.

Determinism: a single `numpy.random.Generator` (PCG64) is threaded through as
an argument — never globals, never np.random.seed (NEP 19). RNG is consumed
in a FIXED order: occupancy schedule built once at reset (rooms sorted,
blocks in table order), then per step rooms in sorted order with weather
draws before humidity draws. Same (code, config, seed) -> identical
trajectory. Float formatting is fixed (%.4f) wherever telemetry serializes,
so the byte-for-byte rule holds.

Action: {room_id: {"hvac": "OFF"|"REDUCED"|"ON", "light": 0|1}}
Obs:     {room_id: {"T_in": f, "T_out": f, "RH": f, "occupancy": n,
                    "power_kW": f}}
power_kW = |Q_hvac|/COP + light load (electrical).
"""

import numpy as np

from sim import config as cfg
from sim import occupancy as occ_mod
from sim import thermal as th
from sim import weather as wx

# Paired seeds (D-08): identical seeds reused by every controller in later
# phases for paired comparison. Plan 03 eval helper imports this.
PAIRED_SEEDS = list(cfg.PAIRED_SEEDS)


def seeds_equal(traj_a, traj_b):
    """Exact equality of two run trajectories (DataFrame.equals: exact)."""
    if set(traj_a) != set(traj_b):
        return False
    return all(traj_a[room].equals(traj_b[room]) for room in traj_a)


class BuildingSim:
    def __init__(self, config=cfg, rng=None, scenario="weekday"):
        self.cfg = config
        self.rng = rng if rng is not None else np.random.default_rng()
        self.scenario = wx.validate_scenario(scenario)
        self.minute = 0
        self.t_in = {}
        self.rh = {}
        self.schedule = None
        self.reset()

    def reset(self, seed=None, scenario=None):
        """Fresh state; returns initial obs. Reseeds RNG iff seed given."""
        if scenario is not None:
            self.scenario = wx.validate_scenario(scenario)
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.minute = 0
        # Start rooms at a comfortable 24 C / mid humidity.
        self.t_in = {room: 24.0 for room in self.cfg.ROOMS}
        self.rh = {room: self.cfg.RH_INIT for room in self.cfg.ROOMS}
        # Occupancy timetable built once per run (seeded jitter/absence here).
        self.schedule = occ_mod.get_day_schedule(self.scenario, self.rng)
        return self._obs({room: {"hvac": "OFF", "light": 0} for room in self.cfg.ROOMS})

    def step(self, action):
        """Advance exactly 1 minute of sim-time. Returns obs dict."""
        c = self.cfg
        obs = {}
        for room in sorted(c.ROOMS):  # fixed order: determinism
            # 1. weather draws first (outdoor temp noise for this room-minute)
            t_out = wx.outdoor_temp(self.minute, self.scenario, self.rng)
            # 2. humidity random walk, clipped (uncoupled from T by design)
            self.rh[room] = wx.rh_step(self.rh[room], self.rng)
            # 3. occupancy lookup (draws happened at reset, same fixed order)
            occ = self._occupancy(room, self.minute)
            # 4. physics integration
            hvac = action[room]["hvac"]
            light = action[room]["light"]
            q_hvac = c.Q_HVAC[hvac]
            q_occ = occ * c.Q_OCC_PER_PERSON
            self.t_in[room] = th.thermal_step(
                self.t_in[room], t_out, q_occ, q_hvac, c.R_PER_ROOM[room], c.C_PER_ROOM[room]
            )
            obs[room] = {
                "T_in": self.t_in[room],
                "T_out": t_out,
                "RH": self.rh[room],
                "occupancy": occ,
                "power_kW": th.electrical_power_kw(q_hvac, light),
            }
        self.minute += 1
        return obs

    def _occupancy(self, room, minute):
        """Occupant count from the run schedule (modulo wraps past day end)."""
        return int(self.schedule.at[minute % len(self.schedule), room])

    def _obs(self, action):
        c = self.cfg
        return {
            room: {
                "T_in": self.t_in[room],
                "T_out": c.T_OUT_MEAN,
                "RH": self.rh[room],
                "occupancy": 0,
                "power_kW": th.electrical_power_kw(c.Q_HVAC[action[room]["hvac"]], action[room]["light"]),
            }
            for room in c.ROOMS
        }
