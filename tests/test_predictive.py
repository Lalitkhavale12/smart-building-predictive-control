"""C4 predictive controller tests (CTL-04): None-to-C3 identity + overlay."""

import copy

import numpy as np

from ctrl.baselines import SetbackPolicy
from ctrl.predictive import (
    Forecast,
    PredictivePolicy,
    RoomForecast,
    build_frozen_forecaster,
    build_tick_occupancy_windows,
    tick_feature_row,
    OCC_TICK_FEATURES,
    TICK_HORIZONS,
)
from ctrl.harness import run_controller
from sim import config as cfg


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


def _stub(occ_30, occ_60=0.0):
    """Forecast stub: every room predicts (occ_30, occ_60)."""
    return Forecast(
        rooms={room: RoomForecast(occ_30, occ_60) for room in cfg.ROOMS})


def test_precool_fires_on_predicted_arrival():
    """Empty room + arrival within 30 min forces ON (C3 would say OFF)."""
    c4 = PredictivePolicy()
    action = c4.step(_obs4(0), forecast=_stub(25.0))
    assert action["classroom_A"]["hvac"] == "ON"  # C3 unseen-default is OFF
    assert action["classroom_A"]["light"] == 0


def test_precool_overrides_reduced_hold():
    """Arrival forecast upgrades a C3-REDUCED room to ON."""
    c4 = PredictivePolicy()
    empty_forecast = _stub(0.0)
    c4.step(_obs4(4), forecast=empty_forecast)  # occupy: reset vacancy timer
    for _ in range(6):  # 30 empty min -> C3 REDUCED, forecast empty -> no overlay
        action = c4.step(_obs4(0), forecast=empty_forecast)
    assert action["office"]["hvac"] == "REDUCED"
    action = c4.step(_obs4(0), forecast=_stub(4.0))
    assert action["office"]["hvac"] == "ON"


def test_earlyoff_fires_when_c3_holds_on_but_forecast_empty():
    """After a departure C3 holds ON; empty forecast skips the hold -> OFF."""
    c3, c4 = SetbackPolicy(), PredictivePolicy()
    c3.step(_obs4(3))
    c4.step(_obs4(3), forecast=_stub(0.0))
    assert c3.step(_obs4(0))["lab"]["hvac"] == "ON"  # C3 5-min hold
    assert c4.step(_obs4(0), forecast=_stub(0.0))["lab"]["hvac"] == "OFF"


def test_earlyoff_blocked_by_predicted_arrival():
    """Same departure, but arrival forecast keeps the C3 hold ON."""
    c4 = PredictivePolicy()
    c4.step(_obs4(3), forecast=_stub(0.0))
    assert c4.step(_obs4(0), forecast=_stub(6.0))["lab"]["hvac"] == "ON"


def test_occupied_untouched():
    """Occupied rooms always stay C3-ON whatever the forecast says."""
    for occ_30 in (0.0, 30.0):
        c4 = PredictivePolicy()
        action = c4.step(_obs4(12), forecast=_stub(occ_30))
        assert action["classroom_A"]["hvac"] == "ON"
        assert action["classroom_A"]["light"] == 1


def test_garbage_forecast_falls_back_to_c3():
    """NaN / missing-room / raiser forecasts degrade to C3 exactly (T-04-04)."""

    class Raiser:
        def predictions(self, room):
            raise KeyError(room)

    c3 = SetbackPolicy()
    for bad in (_stub(float("nan")), Raiser()):
        c4, ref = PredictivePolicy(), SetbackPolicy()
        c3.step(_obs4(2))
        ref.step(_obs4(2))
        c4.step(_obs4(2), forecast=bad)
        for _ in range(4):
            assert c4.step(_obs4(0), forecast=bad) == ref.step(_obs4(0))


def test_tick_features_match_vectorized():
    """Live single-row builder == training shift-based row on the same ticks."""
    import pandas as pd

    from ctrl.baselines import FixedSchedulePolicy
    from ctrl.predictive import to_ticks

    frame, _ = run_controller(
        FixedSchedulePolicy(scenario="weekday"), "weekday", 0, days=1)
    ticks = to_ticks(frame)
    room, horizon = "classroom_A", TICK_HORIZONS[30]
    vec = build_tick_occupancy_windows(ticks, room, horizon)
    sub = ticks[ticks["room"] == room].reset_index(drop=True)
    i = vec.index[0] + 0  # first surviving row; back out its source position
    # The vectorized row timestamp tells us which tick it describes.
    ts = pd.to_datetime(vec.loc[0, "timestamp"])
    pos = sub.index[pd.to_datetime(sub["timestamp"]) == ts][0]
    hist = sub.iloc[pos - 12:pos + 1]
    assert len(hist) == 13
    buf = [{
        "occupancy": float(r["occupancy"]), "T_in_C": float(r["T_in_C"]),
        "T_out_C": float(r["T_out_C"]), "RH_pct": float(r["RH_pct"]),
    } for _, r in hist.iterrows()]
    minute = int(ts.hour * 60 + ts.minute)
    live = tick_feature_row(buf, minute, 0, OCC_TICK_FEATURES)
    train = [float(vec.loc[0, col]) for col in OCC_TICK_FEATURES]
    assert np.allclose(live, train, atol=1e-9)


TINY_C4_SEARCH = {
    "histgb": [{"reg__max_iter": [10], "reg__max_depth": [3],
                "reg__learning_rate": [0.1]}],
}


def test_frozen_forecaster_end_to_end_tiny():
    """Tiny-budget forecaster predicts finite values and drives a full run."""
    forecaster, _ = build_frozen_forecaster(
        "weekday", days=1, seed=0, search=TINY_C4_SEARCH)
    policy = PredictivePolicy()
    obs = {room: {"T_in": 24.0, "T_out": 31.0, "RH": 55.0,
                  "occupancy": 0, "power_kW": 0.5} for room in cfg.ROOMS}
    for minute in range(0, 70, 5):
        forecaster.observe(obs, minute)
    pred = forecaster.predictions("classroom_A")
    assert np.isfinite(pred.occ_30) and np.isfinite(pred.occ_60)
    assert np.isfinite(forecaster.demand_30)
    frame, metrics = run_controller(
        PredictivePolicy(), "weekday", 1, days=1, forecast=forecaster)
    assert len(frame) == cfg.STEPS_PER_DAY * len(cfg.ROOMS)
    for key in ("energy_kwh", "cost_rs", "co2_kg", "comfort_pct"):
        assert key in metrics
    # Deterministic rerun with the shared object (minute-wrap buffer reset).
    frame2, _ = run_controller(
        PredictivePolicy(), "weekday", 1, days=1, forecast=forecaster)
    assert frame2.equals(frame)
