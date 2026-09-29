"""Policy interface stub (D-14).

Phase 1 ships only the ABC + an all-OFF smoke stub. Real controllers (C1-C4)
arrive in Phase 3 and keep this exact interface: `step(obs, forecast=None,
signals=None)` — forecast/signals default None so ablations are flag flips.
Policies must treat obs as read-only and must NEVER reach into sim internals;
tests/test_boundaries.py enforces the split.
"""

from abc import ABC, abstractmethod


class BasePolicy(ABC):
    @abstractmethod
    def step(self, obs, forecast=None, signals=None):
        """Map obs -> action.

        obs: {room_id: {"T_in", "T_out", "RH", "occupancy", "power_kW"}}
        Returns: {room_id: {"hvac": "OFF"|"REDUCED"|"ON", "light": 0|1}}
        """
        raise NotImplementedError


class AlwaysOffPolicy(BasePolicy):
    """Smoke-test stub: everything OFF, lights off."""

    def step(self, obs, forecast=None, signals=None):
        return {room: {"hvac": "OFF", "light": 0} for room in obs}
