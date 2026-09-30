"""C4 tuning tests (Phase 5, plan 05-01): stock-default regression + new flags.

Stock defaults (precool_min=30, earlyoff_min=30, occ_threshold=1,
precool_level="ON", earlyoff_from_reduced=False, require_both_horizons=False,
precool_blackout=None) MUST reproduce the pre-Phase-5 overlay exactly.
"""

import copy

from ctrl.predictive import Forecast, PredictivePolicy, RoomForecast
from sim import config as cfg


def _obs4(occupancy):
    return {
        room: {"T_in": 24.0, "T_out": 31.0, "RH": 55.0,
               "occupancy": occupancy, "power_kW": 0.0}
        for room in cfg.ROOMS
    }


def _stub(occ_30, occ_60=0.0):
    return Forecast(
        rooms={room: RoomForecast(occ_30, occ_60) for room in cfg.ROOMS})


def _legacy_overlay(c4, obs, base, forecast):
    """Inline copy of the pre-Phase-5 _apply_overlay law (regression oracle)."""
    from ctrl.predictive import _as_number

    out = {room: dict(base[room]) for room in base}
    for room in obs:
        if obs[room]["occupancy"] != 0:
            continue
        try:
            pred = forecast.predictions(room)
            occ30 = _as_number(getattr(pred, "occ_30", None))
            occ60 = _as_number(getattr(pred, "occ_60", None))
        except (KeyError, AttributeError):
            continue
        if occ30 is None or occ60 is None:
            continue
        hvac = out[room]["hvac"]
        if occ30 >= c4.occ_threshold:
            if hvac != "ON":
                out[room]["hvac"] = "ON"
        elif occ60 < c4.occ_threshold and hvac == "ON":
            out[room]["hvac"] = "OFF"
    return out


def test_stock_defaults_reproduce_legacy():
    """Stock config is byte-identical to the pre-Phase-5 overlay law."""
    import random

    from ctrl.baselines import SetbackPolicy

    rng = random.Random(42)
    for trial in range(30):
        stock = PredictivePolicy()  # all stock defaults
        # Random scripted obs/forecast sequence incl. occupied rooms.
        script = []
        for _ in range(rng.randint(1, 12)):
            occ = rng.choice([0, 0, 0, 3, 12])
            o30 = rng.choice([0.0, 0.5, 4.0, 25.0])
            o60 = rng.choice([0.0, 0.5, 4.0, 25.0])
            script.append((_obs4(occ), _stub(o30, o60)))
        ref_c3 = SetbackPolicy()
        for obs, fc in script:
            snapshot = copy.deepcopy(obs)
            action = stock.step(copy.deepcopy(obs), forecast=fc)
            assert obs == snapshot  # obs never mutated
            base = ref_c3.step(copy.deepcopy(obs))  # same vacancy history
            expected = _legacy_overlay(stock, obs, base, fc)
            for room in cfg.ROOMS:
                assert action[room] == expected[room], (trial, room)


def test_precool_min_selects_horizon():
    """precool_min>30 gates pre-cool on occ_60 instead of occ_30."""
    far_only = PredictivePolicy(precool_min=60)
    # Near arrival only (occ_30 high, occ_60 empty): stock pre-cools, far-gate does not.
    assert PredictivePolicy().step(
        _obs4(0), forecast=_stub(25.0, 0.0))["classroom_A"]["hvac"] == "ON"
    action = far_only.step(_obs4(0), forecast=_stub(25.0, 0.0))
    assert action["classroom_A"]["hvac"] == "OFF"  # C3 unseen-default, no pre-cool
    # Far arrival (occ_60 high): far-gate pre-cools.
    action = PredictivePolicy(precool_min=60).step(
        _obs4(0), forecast=_stub(0.0, 25.0))
    assert action["classroom_A"]["hvac"] == "ON"


def test_earlyoff_min_requires_sustained_departure():
    """earlyoff_min>30 additionally requires occ_30 empty (no new state)."""
    # occ_30 high but occ_60 empty, C3 holding ON after a departure.
    for earlyoff_min, expected in ((30, "OFF"), (60, "ON")):
        c4 = PredictivePolicy(precool_min=60, earlyoff_min=earlyoff_min)
        c4.step(_obs4(3), forecast=_stub(0.0, 0.0))  # occupy: reset timer
        c4.step(_obs4(0), forecast=_stub(0.0, 0.0))  # C3 hold ON
        action = c4.step(_obs4(0), forecast=_stub(6.0, 0.0))
        assert action["lab"]["hvac"] == expected, (earlyoff_min, action)


def test_precool_level_reduced():
    """H1: precool_level='REDUCED' pre-cools to REDUCED instead of ON."""
    c4 = PredictivePolicy(precool_level="REDUCED")
    action = c4.step(_obs4(0), forecast=_stub(25.0))
    assert action["classroom_A"]["hvac"] == "REDUCED"
    assert action["classroom_A"]["light"] == 0


def test_earlyoff_from_reduced():
    """H2: early-off fires from C3-REDUCED rooms only when the flag is set."""
    # Flag off: REDUCED rooms are skipped by early-off.
    c4 = PredictivePolicy(earlyoff_from_reduced=False)
    empty = _stub(0.0)
    c4.step(_obs4(4), forecast=empty)
    for _ in range(6):  # 30 empty min -> C3 REDUCED
        action = c4.step(_obs4(0), forecast=empty)
    assert action["office"]["hvac"] == "REDUCED"
    assert c4.step(_obs4(0), forecast=empty)["office"]["hvac"] == "REDUCED"
    # Flag on: early-off fires from a C3-REDUCED room. The hold forecast
    # (occ30 empty, occ60 occupied) lets C3 evolve to REDUCED undisturbed.
    c4 = PredictivePolicy(earlyoff_from_reduced=True)
    hold = _stub(0.0, 5.0)
    c4.step(_obs4(4), forecast=hold)
    for _ in range(6):
        action = c4.step(_obs4(0), forecast=hold)
    assert action["office"]["hvac"] == "REDUCED"  # pure C3, overlay silent
    assert c4.step(_obs4(0), forecast=empty)["office"]["hvac"] == "OFF"


def test_require_both_horizons():
    """H4: pre-cool needs occ_30 AND occ_60 above threshold."""
    c4 = PredictivePolicy(require_both_horizons=True)
    # Single-horizon arrival: stock would pre-cool, gated version does not.
    action = c4.step(_obs4(0), forecast=_stub(25.0, 0.0))
    assert action["classroom_A"]["hvac"] == "OFF"
    # Persistent arrival across horizons: pre-cools.
    action = PredictivePolicy(require_both_horizons=True).step(
        _obs4(0), forecast=_stub(25.0, 30.0))
    assert action["classroom_A"]["hvac"] == "ON"


def test_precool_blackout():
    """D-08: precool_blackout=(18,22) blocks pre-cool in-window only."""
    c4 = PredictivePolicy(precool_blackout=(18, 22))
    c4._calls = 216  # minute 1080 == 18:00, inside the window
    action = c4.step(_obs4(0), forecast=_stub(25.0))
    assert action["classroom_A"]["hvac"] == "OFF"  # pre-cool suppressed
    # Occupied rooms still get C3-ON inside the window (no comfort exposure).
    c4b = PredictivePolicy(precool_blackout=(18, 22))
    c4b._calls = 216
    assert c4b.step(_obs4(5), forecast=_stub(0.0))["lab"]["hvac"] == "ON"
    # Outside the window the same forecast pre-cools normally.
    c4c = PredictivePolicy(precool_blackout=(18, 22))  # minute 0, off-peak
    assert c4c.step(_obs4(0), forecast=_stub(25.0))["classroom_A"]["hvac"] == "ON"
