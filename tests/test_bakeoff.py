"""Bake-off + LSTM tests (Phase 4, FOR-03, D-03/D-04).

Fast by design: 1-day frames, 1-config searches, tiny LSTM (units=4,
epochs=2). Full-budget runs live in ml/bakeoff.py:main, not here.
"""

import pathlib
import re

import numpy as np
import pytest

from ctrl.baselines import FixedSchedulePolicy
from ctrl.harness import run_controller
from ml import bakeoff as bo
from ml import forecast as fc
from ml import lstm as lstm_mod

TINY_SEARCH = {
    "rf": [{"reg__n_estimators": [10], "reg__max_depth": [4], "reg__min_samples_leaf": [2]}],
    "histgb": [{"reg__max_iter": [10], "reg__max_depth": [3], "reg__learning_rate": [0.1]}],
}
TINY_LSTM = {"units": 4, "layers": 1, "epochs": 2, "patience": 1, "batch_size": 64}


def _frame(days=1, seed=0):
    frame, _ = run_controller(
        FixedSchedulePolicy(scenario="weekday"), "weekday", seed, days=days
    )
    return frame


def test_lstm_caps():
    """Units/epochs/layers beyond the locked caps raise (D-04)."""
    with pytest.raises(ValueError):
        lstm_mod.check_caps(units=65)
    with pytest.raises(ValueError):
        lstm_mod.check_caps(layers=3)
    with pytest.raises(ValueError):
        lstm_mod.check_caps(epochs=51)
    lstm_mod.check_caps()  # defaults are within caps


def test_tf_isolated_from_package_top_level():
    """No indent-0 TF import in ml/ top-level modules (T-04-SC)."""
    pat = re.compile(r"^(import tensorflow|from tensorflow)", re.M)
    for name in ("ml/lstm.py", "ml/bakeoff.py", "ml/__init__.py", "ml/forecast.py"):
        src = pathlib.Path(name).read_text()
        assert not pat.search(src), f"TF at top level of {name}"


def test_lstm_finite_both_horizons_and_roundtrip(tmp_path):
    """Tiny LSTM: finite +30/+60 predictions; save→load→predict identical."""
    frame = _frame()
    train_df, test_df = fc.chronological_split(frame)
    tr30 = fc.build_occupancy_windows(train_df, "classroom_A", 30)
    Xtr, ytr = lstm_mod.dataset_from_windows(tr30, fc.OCC_FEATURES)
    art = lstm_mod.train_lstm(Xtr[:400], ytr[:400], **TINY_LSTM)
    assert art["epochs_used"] <= TINY_LSTM["epochs"]
    assert art["seeds"] == {"tf_seed": 0, "sklearn_seed": 0, "data_seed": 0}
    for horizon in (30, 60):
        te = fc.build_occupancy_windows(test_df, "classroom_A", horizon)
        Xte, _ = lstm_mod.dataset_from_windows(te, fc.OCC_FEATURES)
        preds = lstm_mod.predict_lstm(art, Xte[:50])
        assert np.all(np.isfinite(preds)), f"NaN/inf at H={horizon}"
    model_path, _ = lstm_mod.save_artifact(art, str(tmp_path / "lstm.keras"))
    reloaded = lstm_mod.load_artifact(model_path)
    te30 = fc.build_occupancy_windows(test_df, "classroom_A", 30)
    Xte, _ = lstm_mod.dataset_from_windows(te30, fc.OCC_FEATURES)
    before = lstm_mod.predict_lstm(art, Xte[:50])
    after = lstm_mod.predict_lstm(reloaded, Xte[:50])
    assert np.allclose(before, after)


def test_bakeoff_table(monkeypatch):
    """Per-horizon tables carry all four rows + an explicit tie verdict."""
    monkeypatch.setattr(bo, "PAIRED_SEEDS", [0, 1])
    frames = {s: _frame(seed=s) for s in (0, 1)}
    for horizon in fc.HORIZONS:
        table = bo.evaluate_models(frames[0], "classroom_A", horizon,
                                   search=TINY_SEARCH, lstm_kwargs=TINY_LSTM)
        assert set(table) == {"persistence", "rf", "histgb", "lstm"}
        for row in table.values():
            assert set(row) >= {"mae", "rmse", "r2"}
    tables = bo.run_bakeoff(frames, "classroom_A",
                            search=TINY_SEARCH, lstm_kwargs=TINY_LSTM)
    assert set(tables) == {30, 60}  # per-horizon separation, never averaged
    for horizon in (30, 60):
        assert set(tables[horizon]["rows"]) == {"persistence", "rf", "histgb", "lstm"}
        assert tables[horizon]["verdict"].startswith("ship: ")
        assert tables[horizon]["reason"]
    text = bo.format_bakeoff(tables)
    assert "verdict" in text


def test_tie_rule():
    """<3% LSTM gain with overlapping std → ship HistGB (locked D-03)."""
    verdict, _ = bo.tie_break(9.8, 0.5, 10.0, 0.5)
    assert verdict == "ship: histgb"
    verdict, _ = bo.tie_break(9.0, 0.1, 10.0, 0.1)
    assert verdict == "ship: lstm"
    verdict, _ = bo.tie_break(float("nan"), float("nan"), 10.0, 0.5)
    assert verdict == "ship: histgb"
    verdict, _ = bo.tie_break(10.5, 0.5, 10.0, 0.5)
    assert verdict == "ship: histgb"
