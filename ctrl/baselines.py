"""C1 fixed-schedule + C2 occupancy-rule baselines (CTL-01/CTL-02)."""

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
