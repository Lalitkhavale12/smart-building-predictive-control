"""C4 predictive controller tests (CTL-04): None-to-C3 identity + container."""

import copy

from ctrl.baselines import SetbackPolicy
from ctrl.predictive import Forecast, PredictivePolicy, RoomForecast


def _obs4(occupancy):
    """Four-room obs with uniform occupancy (keys mirror sim obs)."""
    return {
        room: {"T_in": 24.0, "T_out": 31.0, "RH": 55.0,
               "occupancy": occupancy, "power_kW": 0.0}
        for room in ("classroom_A", "classroom_B", "office", "lab")
    }


def test_none_is_c3():
    """forecast=None behaves exactly like C3 over occupied/brief/long-empty."""
    c3 = SetbackPolicy()
    c4 = PredictivePolicy()
    script = [_obs4(5), _obs4(5)] + [_obs4(0)] * 14  # occupied, briefly, long empty
    for obs in script:
        snapshot = copy.deepcopy(obs)
        c4_action = c4.step(obs, forecast=None)
        c3_action = c3.step(copy.deepcopy(obs))
        assert c4_action == c3_action
        assert obs == snapshot  # obs never mutated


def test_none_is_c3_custom_thresholds_match_c3():
    """Vacancy/setback params still forward to the C3 core with None forecast."""
    c3 = SetbackPolicy(vacancy_min=5, setback_min=30)
    c4 = PredictivePolicy(vacancy_min=5, setback_min=30)
    for _ in range(8):
        assert c4.step(_obs4(0), forecast=None) == c3.step(_obs4(0))


def test_forecast_container_shape():
    """Container carries per-room occupancy +30/+60 and demand +30/+60 (D-01)."""
    fc = Forecast(
        rooms={"classroom_A": RoomForecast(occ_30=28.0, occ_60=0.0)},
        demand_30=4.2,
        demand_60=1.1,
    )
    pred = fc.predictions("classroom_A")
    assert pred.occ_30 == 28.0 and pred.occ_60 == 0.0
    assert max(pred.occ_next_30min) == 28.0
    assert fc.demand_30 == 4.2 and fc.demand_60 == 1.1
