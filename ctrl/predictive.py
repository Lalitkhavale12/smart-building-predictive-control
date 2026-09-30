"""C4 predictive controller (CTL-04): C3 SetbackPolicy + forecast overlay.

C4 = C3 setback logic with a thin forecast overlay (pre-cool before predicted
arrivals, early-off before predicted departures). Fallback (D-09): when
``forecast`` is None the policy degrades to C3 exactly — this is both the
robustness path and the forecast-off ablation arm.

Forecasts travel as in-process objects, never over MQTT (D-10). Lights always
follow current occupancy, like every baseline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ctrl.baselines import SetbackPolicy


@dataclass
class RoomForecast:
    """Per-room occupancy prediction at the +30/+60 min horizons (D-01)."""

    occ_30: float = 0.0
    occ_60: float = 0.0

    @property
    def occ_next_30min(self):
        """Arrival-window series: max(...) >= occ_threshold means arrival."""
        return [self.occ_30]


@dataclass
class Forecast:
    """In-process forecast container (D-01/D-10): per-room occupancy at
    +30/+60 plus building demand (kW) at +30/+60. Queried per room via
    ``predictions(room)``; never serialized to MQTT."""

    rooms: dict = field(default_factory=dict)
    demand_30: float = 0.0
    demand_60: float = 0.0

    def predictions(self, room):
        """Return the RoomForecast for one room (KeyError if unknown)."""
        return self.rooms[room]


def _as_number(value):
    """Coerce a prediction to float; garbage (None/str/NaN) -> None (T-04-04)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


class PredictivePolicy(SetbackPolicy):
    """C4: C3 + forecast overlay (D-08, research F6).

    Constructor thresholds are agent's-discretion params with documented
    defaults: ``precool_min``/``earlyoff_min`` = 30 min (== the +30 forecast
    horizon), ``occ_threshold`` = 1 person.
    """

    def __init__(self, vacancy_min=15, setback_min=60,
                 precool_min=30, earlyoff_min=30, occ_threshold=1):
        super().__init__(vacancy_min=vacancy_min, setback_min=setback_min)
        self.precool_min = precool_min
        self.earlyoff_min = earlyoff_min
        self.occ_threshold = occ_threshold
        self._calls = 0

    def step(self, obs, forecast=None, signals=None):
        """Map obs -> action; ``obs`` treated read-only, never mutated."""
        self._calls += 1
        if forecast is None:
            return super().step(obs, forecast=None, signals=signals)
        base = super().step(obs, forecast=None, signals=signals)
        return self._apply_overlay(obs, base, forecast)

    def _apply_overlay(self, obs, base, forecast):
        """Forecast overlay on top of a C3 base action (task 2 fills this in)."""
        return base
