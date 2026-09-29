"""C1 fixed-schedule + C2 occupancy-rule + C3 setback baselines (CTL-01/02/03)."""

from sim import config as cfg
from sim.policy import BasePolicy

from ctrl.schedules import is_on


class FixedSchedulePolicy(BasePolicy):
    """C1: wall-clock schedule per room type (D-01).

    Minute-of-day derives from a step counter incremented once per ``step()``
    call: the driver calls the policy every ``CONTROL_HOOK_STEPS`` sim-minutes,
    so ``minute_of_day = call_count * CONTROL_HOOK_STEPS mod 1440``.
    HVAC from :func:`ctrl.schedules.is_on`; lights from current occupancy.
    ``forecast``/``signals`` accepted and ignored. ``obs`` treated read-only.
    """

    def __init__(self, scenario="weekday"):
        self.scenario = scenario
        self._calls = 0

    def step(self, obs, forecast=None, signals=None):
        minute = (self._calls * cfg.CONTROL_HOOK_STEPS) % cfg.STEPS_PER_DAY
        self._calls += 1
        day_type = "weekend" if self.scenario == "weekend" else "weekday"
        return {
            room: {
                "hvac": "ON" if is_on(room, minute, day_type) else "OFF",
                "light": 1 if obs[room]["occupancy"] > 0 else 0,
            }
            for room in obs
        }


class OccupancyRulePolicy(BasePolicy):
    """C2: OFF after ``vacancy_min`` continuous empty sim-minutes (D-03/D-04).

    Per-room empty timer inside the policy, reset on ``occupancy > 0``. The
    counter accumulates ``CONTROL_HOOK_STEPS`` sim-minutes per ``step()``
    call (never call counts — counting calls would stretch the delay 5x).
    Reads only current ``obs`` occupancy; no timetable peeking (that is C4's
    job). Lights follow current occupancy.
    """

    def __init__(self, vacancy_min=15):
        self.vacancy_min = vacancy_min
        self._empty_min = {}

    def step(self, obs, forecast=None, signals=None):
        action = {}
        for room in obs:
            if obs[room]["occupancy"] > 0:
                self._empty_min[room] = 0
                hvac = "ON"
            else:
                # Unseen rooms default to long-vacant (midnight start = vacant
                # for hours): first empty observation yields OFF, not a 15-min
                # hold-ON transient that would penalize low-energy scenarios.
                self._empty_min[room] = (
                    self._empty_min.get(room, self.vacancy_min)
                    + cfg.CONTROL_HOOK_STEPS
                )
                hvac = "OFF" if self._empty_min[room] >= self.vacancy_min else "ON"
            action[room] = {
                "hvac": hvac,
                "light": 1 if obs[room]["occupancy"] > 0 else 0,
            }
        return action


class SetbackPolicy(BasePolicy):
    """C3: setback — REDUCED for the first ``setback_min`` empty minutes, OFF after (D-05/D-06).

    Identical vacancy tracking to C2 (sim-minute counter, ``vacancy_min=15``
    default): empty < vacancy_min → ON (hold); vacancy_min ≤ empty <
    setback_min → REDUCED; empty ≥ setback_min → OFF; occupied → ON.

    The 60-min setback is grounded in room tau ~3.6 h (BASE_TAU_HOURS): one
    hour of REDUCED (-1.2 kW vs ON -3.5 kW, ~1/3 capacity) holds the room
    within fast-recovery reach of the comfort band, while OFF lets it drift.
    Reads only current ``obs`` occupancy; lights follow current occupancy.
    """

    def __init__(self, vacancy_min=15, setback_min=60):
        self.vacancy_min = vacancy_min
        self.setback_min = setback_min
        self._empty_min = {}

    def step(self, obs, forecast=None, signals=None):
        action = {}
        for room in obs:
            if obs[room]["occupancy"] > 0:
                self._empty_min[room] = 0
                hvac = "ON"
            else:
                # Unseen rooms default to long-vacant (midnight start = vacant
                # for hours): first empty observation yields OFF, same as C2.
                self._empty_min[room] = (
                    self._empty_min.get(room, self.setback_min)
                    + cfg.CONTROL_HOOK_STEPS
                )
                empty = self._empty_min[room]
                if empty >= self.setback_min:
                    hvac = "OFF"
                elif empty >= self.vacancy_min:
                    hvac = "REDUCED"
                else:
                    hvac = "ON"
            action[room] = {
                "hvac": hvac,
                "light": 1 if obs[room]["occupancy"] > 0 else 0,
            }
        return action
