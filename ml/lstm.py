"""Small capped LSTM forecaster (Phase 4, FOR-03, D-04).

One small Keras LSTM: 1-2 layers, at most 64 units, at most 50 epochs with
early stopping, one config per target (no architecture search). Consumes the
60-min sliding-window tensors built post-split inside each partition by the
04-01 windowing functions in :mod:`ml.forecast` (reused, never reimplemented).

All TensorFlow imports live inside functions in this module, so a broken TF
env never blocks the HistGB path (``ml.forecast`` / ``ml.bakeoff`` catch the
ImportError and report LSTM as reference-skipped).

UCI horizon mapping is documented in :mod:`ml.uci`, not here.
"""

from __future__ import annotations

import logging
import os
import random

import joblib
import numpy as np

from sim import config as cfg

logger = logging.getLogger(__name__)

# Locked caps (D-04 / F9): exceeding any of these is a test failure.
MAX_UNITS = 64
MAX_EPOCHS = 50
MAX_LAYERS = 2
WINDOW_LEN = 60  # 60-min sliding windows on 1-min sim telemetry
DEFAULT_UNITS = 32
DEFAULT_LAYERS = 1
DEFAULT_PATIENCE = 5

# One config per target — no architecture search (D-04). Committed literal so
# the bake-off comparison stays auditable (D-03).
LSTM_CONFIG = {
    "units": DEFAULT_UNITS,
    "layers": DEFAULT_LAYERS,
    "epochs": MAX_EPOCHS,
    "patience": DEFAULT_PATIENCE,
    "window": WINDOW_LEN,
    "batch_size": 64,
}

DEFAULT_SEED = cfg.PAIRED_SEEDS[0]


def check_caps(units=DEFAULT_UNITS, layers=DEFAULT_LAYERS, epochs=MAX_EPOCHS):
    """Raise when a config exceeds the locked LSTM caps."""
    if units > MAX_UNITS:
        raise ValueError(f"units {units} exceeds cap {MAX_UNITS}")
    if layers > MAX_LAYERS:
        raise ValueError(f"layers {layers} exceeds cap {MAX_LAYERS}")
    if epochs > MAX_EPOCHS:
        raise ValueError(f"epochs {epochs} exceeds cap {MAX_EPOCHS}")


def seed_all(seed=DEFAULT_SEED):
    """Seed TF + sklearn-adjacent + data RNGs; return + log the seed chain."""
    seeds = {"tf_seed": seed, "sklearn_seed": seed, "data_seed": seed}
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    # ponytail: TF seed set inside build/train (TF import is function-local).
    logger.info("lstm seeds tf=%s sklearn=%s data=%s", seed, seed, seed)
    return seeds


def windows_to_sequences(X, y, window=WINDOW_LEN):
    """Stack flat lag-feature rows into (n, window, n_feat) sequence tensors."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(X) <= window:
        raise ValueError(f"need more than {window} rows, got {len(X)}")
    n_feat = X.shape[1]
    idx = np.arange(window)[None, :] + np.arange(len(X) - window)[:, None]
    return X[idx].reshape(-1, window, n_feat), y[window:]


def dataset_from_windows(frame, features, window=WINDOW_LEN):
    """Build sequence tensors from one 04-01 window partition (post-split)."""
    from ml import forecast as fc  # local: never pulls TF into ml/ top level

    X = frame[list(features)].to_numpy(dtype=float)
    y = frame[fc.TARGET_COL].to_numpy(dtype=float)
    return windows_to_sequences(X, y, window=window)


def build_model(n_features, units=DEFAULT_UNITS, layers=DEFAULT_LAYERS, seed=DEFAULT_SEED):
    """Build the single small LSTM; TF import stays inside this function."""
    import tensorflow as tf  # noqa: PLC0415 — isolated so TF churn can't block HistGB

    check_caps(units=units, layers=layers)
    tf.keras.utils.set_random_seed(seed)
    model = tf.keras.Sequential()
    for i in range(layers):
        last = i == layers - 1
        kwargs = {"units": units, "return_sequences": not last}
        if i == 0:
            kwargs["input_shape"] = (WINDOW_LEN, n_features)
        model.add(tf.keras.layers.LSTM(seed=seed, **kwargs))
    model.add(tf.keras.layers.Dense(1))
    model.compile(optimizer="adam", loss="mse")
    return model


def train_lstm(X_train, y_train, units=DEFAULT_UNITS, layers=DEFAULT_LAYERS,
               epochs=MAX_EPOCHS, patience=DEFAULT_PATIENCE,
               batch_size=64, seed=DEFAULT_SEED, verbose=0):
    """Scale (fit on train only) + train with early stopping. Returns artifact."""
    import tensorflow as tf  # noqa: PLC0415 — see build_model

    from sklearn.preprocessing import StandardScaler

    check_caps(units=units, layers=layers, epochs=epochs)
    seeds = seed_all(seed)
    tf.keras.utils.set_random_seed(seed)
    scaler = StandardScaler()
    n, window, n_feat = X_train.shape
    flat = scaler.fit_transform(X_train.reshape(-1, n_feat)).reshape(n, window, n_feat)
    model = build_model(n_feat, units=units, layers=layers, seed=seed)
    stop = tf.keras.callbacks.EarlyStopping(
        monitor="loss", patience=patience, restore_best_weights=True
    )
    history = model.fit(
        flat, y_train, epochs=epochs, batch_size=batch_size,
        callbacks=[stop], verbose=verbose,
    )
    stopped_epoch = len(history.history["loss"])
    logger.info("lstm trained units=%s layers=%s epochs_used=%s/%s",
                units, layers, stopped_epoch, epochs)
    return {"model": model, "scaler": scaler, "history": history,
            "seeds": seeds, "epochs_used": stopped_epoch}


def predict_lstm(artifact, X):
    """Predict with a trained artifact; raises on NaN/inf output."""
    X = np.asarray(X, dtype=float)
    n, window, n_feat = X.shape
    flat = artifact["scaler"].transform(X.reshape(-1, n_feat)).reshape(n, window, n_feat)
    preds = artifact["model"].predict(flat, verbose=0).reshape(-1)
    if not np.all(np.isfinite(preds)):
        raise ValueError("lstm predictions contain NaN/inf")
    return preds


def save_artifact(artifact, model_path):
    """Persist model (.keras) + scaler sidecar for reuse (never retrain per seed)."""
    model_path = str(model_path)
    artifact["model"].save(model_path)
    scaler_path = model_path + ".scaler.joblib"
    joblib.dump(artifact["scaler"], scaler_path)
    return model_path, scaler_path


def load_artifact(model_path):
    """Reload a persisted artifact; predict-after-load is byte-identical."""
    import tensorflow as tf  # noqa: PLC0415 — isolated, see build_model

    model_path = str(model_path)
    model = tf.keras.models.load_model(model_path)
    scaler = joblib.load(model_path + ".scaler.joblib")
    return {"model": model, "scaler": scaler}


def train_on_frame(df, room, horizon, target="occupancy", seed=DEFAULT_SEED, **kwargs):
    """Split-then-window (04-01 fns) → sequences → one capped LSTM fit."""
    from ml import forecast as fc  # noqa: PLC0415 — reuse, don't reimplement

    params = {**LSTM_CONFIG, **kwargs}
    train_df, _ = fc.chronological_split(df)
    if target == "occupancy":
        tr = fc.build_occupancy_windows(train_df, room, horizon)
        features = fc.OCC_FEATURES
    elif target == "demand":
        tr = fc.build_demand_windows(train_df, horizon)
        features = fc.DEM_FEATURES
    else:  # pragma: no cover
        raise ValueError(f"unknown target {target!r}")
    X_seq, y_seq = dataset_from_windows(tr, features, window=params["window"])
    return train_lstm(X_seq, y_seq, units=params["units"], layers=params["layers"],
                      epochs=params["epochs"], patience=params["patience"],
                      batch_size=params["batch_size"], seed=seed)
