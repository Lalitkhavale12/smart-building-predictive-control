"""C4 predictive controller (CTL-04): C3 SetbackPolicy + forecast overlay.

C4 = C3 setback logic with a thin forecast overlay (pre-cool before predicted
arrivals, early-off before predicted departures). Fallback (D-09): when
``forecast`` is None the policy degrades to C3 exactly — this is both the
robustness path and the forecast-off ablation arm.

Forecasts travel as in-process objects, never over MQTT (D-10). Lights always
follow current occupancy, like every baseline.

Frozen forecaster: HistGB occupancy/demand models pre-fit ONCE on C1-schedule
tick telemetry via :mod:`ml.forecast` (train once, reuse — never train inside
the control loop). Live features are built from a 13-tick rolling obs buffer
at the 5-min control hook, matching the training tick grid exactly.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from ctrl.baselines import SetbackPolicy
from ml import forecast as fc
from sim import config as cfg

# --- Tick grid: policy runs every CONTROL_HOOK_STEPS sim-minutes ---------------
TICK = cfg.CONTROL_HOOK_STEPS  # 5 sim-min per control call
TICK_LAGS = (1, 3, 6, 12)  # ticks -> 5/15/30/60 min of history
TICK_HORIZONS = {30: 6, 60: 12}  # forecast horizon min -> ticks ahead
HISTORY_TICKS = max(TICK_LAGS) + 1  # 13 ticks = 60 min + current

OCC_TICK_COLS = ("occupancy", "T_in_C", "T_out_C", "RH_pct")
DEM_TICK_COLS = ("power_total_kW", "T_in_mean_C", "T_out_C", "RH_mean_pct", "occ_total")
CAL_COLS = ("tod_sin", "tod_cos", "is_weekend")

OCC_TICK_FEATURES = (
    [f"{c}_lag{lag}" for lag in TICK_LAGS for c in OCC_TICK_COLS] + list(CAL_COLS)
)
DEM_TICK_FEATURES = (
    [f"{c}_lag{lag}" for lag in TICK_LAGS for c in DEM_TICK_COLS] + list(CAL_COLS)
)


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


def _calendar(minute_of_day, is_weekend):
    mod = int(minute_of_day) % cfg.STEPS_PER_DAY
    return {
        "tod_sin": float(np.sin(2 * np.pi * mod / 1440.0)),
        "tod_cos": float(np.cos(2 * np.pi * mod / 1440.0)),
        "is_weekend": int(is_weekend),
    }


class PredictivePolicy(SetbackPolicy):
    """C4: C3 + forecast overlay (D-08, research F6).

    Constructor thresholds are agent's-discretion params with documented
    defaults: ``precool_min``/``earlyoff_min`` = 30 min (== the +30 forecast
    horizon), ``occ_threshold`` = 1 person.

    Overlay law, applied on top of the C3 base action per empty room:

    - PRE-COOL: forecast occupancy within 30 min >= threshold while C3 says
      REDUCED/OFF -> force ON (comfort-safe direction: only ever turns
      cooling ON).
    - EARLY-OFF: forecast stays below threshold at +30 AND +60 while C3's
      vacancy hold still says ON -> force OFF (fires only on empty rooms,
      so no occupied-room comfort exposure — T-04-05).
    - Otherwise C3 exactly: occupied rooms, REDUCED/OFF with no predicted
      arrival, OFF staying empty.
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
        minute = ((self._calls * TICK) % cfg.STEPS_PER_DAY)
        self._calls += 1
        if forecast is None:
            return super().step(obs, forecast=None, signals=signals)
        if hasattr(forecast, "observe"):
            forecast.observe(obs, minute)
        base = super().step(obs, forecast=None, signals=signals)
        return self._apply_overlay(obs, base, forecast)

    def _apply_overlay(self, obs, base, forecast):
        out = {room: dict(base[room]) for room in base}
        for room in obs:
            if obs[room]["occupancy"] != 0:
                continue  # occupied rooms always stay C3-ON
            try:
                pred = forecast.predictions(room)
                occ30 = _as_number(getattr(pred, "occ_30", None))
                occ60 = _as_number(getattr(pred, "occ_60", None))
            except (KeyError, AttributeError):
                continue  # unknown room / malformed container -> C3 stands
            if occ30 is None or occ60 is None:
                continue  # garbage predictions fall back to C3 (T-04-04)
            hvac = out[room]["hvac"]
            if occ30 >= self.occ_threshold:
                if hvac != "ON":
                    out[room]["hvac"] = "ON"  # PRE-COOL before arrival
            elif occ60 < self.occ_threshold and hvac == "ON":
                out[room]["hvac"] = "OFF"  # EARLY-OFF: skip the C3 hold
        return out


# --- Frozen-forecaster training data: 5-min ticks --------------------------------

def to_ticks(frame):
    """Subsample 1-min telemetry to the 5-min control-hook tick grid."""
    ts = frame["timestamp"].unique()
    keep = set(ts[::TICK])
    return frame[frame["timestamp"].isin(keep)].copy().reset_index(drop=True)


def build_tick_occupancy_windows(ticks, room, horizon_ticks):
    """Lag features + occupancy(t+H) target for one room, inside one partition.

    Mirrors ``ml.forecast.build_occupancy_windows`` on the tick grid with
    tick lags (1,3,6,12) == 5/15/30/60 min. power_kW is NEVER a feature
    (proxy-for-outcome leakage, same rule as the 1-min builder).
    """
    import pandas as pd

    sub = ticks[ticks["room"] == room].copy()
    if sub.empty:
        raise ValueError(f"build_tick_occupancy_windows: no rows for {room!r}")
    sub["_ts"] = pd.to_datetime(sub["timestamp"])
    sub = sub.sort_values("_ts").reset_index(drop=True)
    feats = pd.DataFrame(index=sub.index)
    cal = _calendar_series(sub["_ts"])
    for key, values in cal.items():
        feats[key] = values
    for lag in TICK_LAGS:
        for col in OCC_TICK_COLS:
            feats[f"{col}_lag{lag}"] = sub[col].shift(lag)
    feats["timestamp"] = sub["_ts"]
    feats[fc.TARGET_COL] = sub["occupancy"].shift(-horizon_ticks).astype(float)
    feats[fc.NOW_COL] = sub["occupancy"].astype(float)
    return feats.dropna().reset_index(drop=True)


def build_tick_demand_windows(ticks, horizon_ticks):
    """Lag features + building-total power_kW(t+H) target, inside one partition."""
    import pandas as pd

    agg = (
        ticks.assign(_ts=pd.to_datetime(ticks["timestamp"]))
        .groupby("_ts", as_index=False)
        .agg(
            power_total_kW=("power_kW", "sum"),
            T_in_mean_C=("T_in_C", "mean"),
            T_out_C=("T_out_C", "first"),
            RH_mean_pct=("RH_pct", "mean"),
            occ_total=("occupancy", "sum"),
        )
        .sort_values("_ts")
        .reset_index(drop=True)
    )
    feats = pd.DataFrame(index=agg.index)
    cal = _calendar_series(agg["_ts"])
    for key, values in cal.items():
        feats[key] = values
    for lag in TICK_LAGS:
        for col in DEM_TICK_COLS:
            feats[f"{col}_lag{lag}"] = agg[col].shift(lag)
    feats["timestamp"] = agg["_ts"]
    feats[fc.TARGET_COL] = agg["power_total_kW"].shift(-horizon_ticks).astype(float)
    feats[fc.NOW_COL] = agg["power_total_kW"].astype(float)
    return feats.dropna().reset_index(drop=True)


def _calendar_series(ts):
    minute_of_day = ts.dt.hour * 60 + ts.dt.minute
    return {
        "tod_sin": np.sin(2 * np.pi * minute_of_day / 1440.0),
        "tod_cos": np.cos(2 * np.pi * minute_of_day / 1440.0),
        "is_weekend": (ts.dt.dayofweek >= 5).astype(int),
    }


def tick_feature_row(history, minute, is_weekend, features):
    """Single live feature row from the last HISTORY_TICKS tick dicts.

    ``history`` is a list of dicts (oldest..newest) with tick-grid keys;
    column order follows ``features`` so training and live rows match.
    """
    row = dict(_calendar(minute, is_weekend))
    for lag in TICK_LAGS:
        hist = history[-(lag + 1)]
        for col in OCC_TICK_COLS + DEM_TICK_COLS:
            key = f"{col}_lag{lag}"
            if key in features:
                row[key] = hist[col]
    return [float(row[col]) for col in features]


class FrozenForecaster:
    """Pre-fit HistGB models + rolling obs buffer; predict-only in the loop.

    ``observe(obs, minute)`` is called by the policy every control tick;
    ``predictions(room)`` returns a RoomForecast. Before the 60-min buffer
    fills, predictions fall back to persistence (current occupancy), which
    keeps the overlay C3-identical through the midnight cold start. A minute
    wrap (new run reusing this object) resets the buffers, keeping reruns
    deterministic.
    """

    def __init__(self, occ_models, dem_models, is_weekend=0):
        self._occ = dict(occ_models)
        self._dem = dict(dem_models)
        self.is_weekend = is_weekend
        self.demand_30 = 0.0
        self.demand_60 = 0.0
        self._last_minute = None
        self._reset()

    def _reset(self):
        self._room_hist = {room: deque(maxlen=HISTORY_TICKS) for room in cfg.ROOMS}
        self._bld_hist = deque(maxlen=HISTORY_TICKS)

    def observe(self, obs, minute):
        """Feed one control-tick obs into the rolling buffer."""
        if self._last_minute is not None and minute <= self._last_minute:
            # New run reusing this object (or midnight wrap): restart the
            # buffer. The 00:00-01:00 cold start uses persistence, which is
            # C3-identical while the building is empty anyway.
            self._reset()
        self._last_minute = minute
        bld = {"power_total_kW": 0.0, "T_in_mean_C": 0.0,
               "T_out_C": 0.0, "RH_mean_pct": 0.0, "occ_total": 0}
        for room in cfg.ROOMS:
            o = obs[room]
            self._room_hist[room].append({
                "occupancy": float(o["occupancy"]),
                "T_in_C": float(o["T_in"]),
                "T_out_C": float(o["T_out"]),
                "RH_pct": float(o["RH"]),
            })
            bld["power_total_kW"] += float(o.get("power_kW", 0.0))
            bld["T_in_mean_C"] += float(o["T_in"])
            bld["T_out_C"] = float(o["T_out"])
            bld["RH_mean_pct"] += float(o["RH"])
            bld["occ_total"] += float(o["occupancy"])
        n = len(cfg.ROOMS)
        bld["T_in_mean_C"] /= n
        bld["RH_mean_pct"] /= n
        self._bld_hist.append(bld)
        if len(self._bld_hist) == HISTORY_TICKS:
            row = tick_feature_row(
                list(self._bld_hist), minute, self.is_weekend, DEM_TICK_FEATURES)
            self.demand_30 = float(self._dem[30].predict([row])[0])
            self.demand_60 = float(self._dem[60].predict([row])[0])
        else:
            self.demand_30 = bld["power_total_kW"]
            self.demand_60 = bld["power_total_kW"]

    def predictions(self, room):
        """RoomForecast for one room (KeyError if unknown room)."""
        hist = list(self._room_hist[room])
        if len(hist) < HISTORY_TICKS:
            now = float(hist[-1]["occupancy"]) if hist else 0.0
            return RoomForecast(occ_30=now, occ_60=now)
        minute = self._last_minute if self._last_minute is not None else 0
        row = tick_feature_row(hist, minute, self.is_weekend, OCC_TICK_FEATURES)
        occ30 = max(0.0, float(self._occ[(room, 30)].predict([row])[0]))
        occ60 = max(0.0, float(self._occ[(room, 60)].predict([row])[0]))
        return RoomForecast(occ_30=occ30, occ_60=occ60)


def build_frozen_forecaster(scenario, days=3, seed=0, search=None, model="histgb"):
    """Fit HistGB occupancy+demand models ONCE on C1 tick telemetry.

    Heatwave/exam-day reuse the weekday timetable (SCENARIO_TABLE), so they
    share the weekday forecaster; weekend gets its own. Returns
    ``(forecaster, test_ticks)`` — the holdout ticks feed the
    predicted-vs-actual evidence. Demand models train on C1 data only
    (control-feedback coupling note from research Q3).
    """
    from ctrl.baselines import FixedSchedulePolicy
    from ctrl.harness import run_controller

    train_scenario = cfg.SCENARIO_TABLE.get(scenario, "weekday")
    if train_scenario not in ("weekday", "weekend"):
        train_scenario = "weekday"
    frame, _ = run_controller(
        FixedSchedulePolicy(scenario=train_scenario), train_scenario, seed, days=days
    )
    ticks = to_ticks(frame)
    train_ticks, test_ticks = fc.chronological_split(ticks)
    occ_models, dem_models = {}, {}
    for room in cfg.ROOMS:
        for horizon_min, horizon_ticks in TICK_HORIZONS.items():
            windows = build_tick_occupancy_windows(train_ticks, room, horizon_ticks)
            space = None if search is None else search.get(model)
            fitted = fc.train_model(
                windows[OCC_TICK_FEATURES].to_numpy(),
                windows[fc.TARGET_COL].to_numpy(),
                model=model, horizon=horizon_ticks, search=space,
                random_state=fc.DEFAULT_SEED,
            )
            occ_models[(room, horizon_min)] = fitted
    for horizon_min, horizon_ticks in TICK_HORIZONS.items():
        windows = build_tick_demand_windows(train_ticks, horizon_ticks)
        space = None if search is None else search.get(model)
        dem_models[horizon_min] = fc.train_model(
            windows[DEM_TICK_FEATURES].to_numpy(),
            windows[fc.TARGET_COL].to_numpy(),
            model=model, horizon=horizon_ticks, search=space,
            random_state=fc.DEFAULT_SEED,
        )
    forecaster = FrozenForecaster(
        occ_models, dem_models,
        is_weekend=1 if train_scenario == "weekend" else 0,
    )
    return forecaster, test_ticks


def holdout_pred_rows(forecaster, test_ticks, scenario):
    """Predicted-vs-actual rows on the holdout, per room/target/horizon."""
    rows = []
    for room in cfg.ROOMS:
        for horizon_min, horizon_ticks in TICK_HORIZONS.items():
            windows = build_tick_occupancy_windows(test_ticks, room, horizon_ticks)
            preds = forecaster._occ[(room, horizon_min)].predict(
                windows[OCC_TICK_FEATURES].to_numpy())
            for ts, true, pred in zip(
                    windows["timestamp"], windows[fc.TARGET_COL], preds):
                rows.append({
                    "scenario": scenario, "room": room, "target": "occupancy",
                    "horizon_min": horizon_min, "timestamp": str(ts),
                    "y_true": float(true), "y_pred": float(pred),
                })
    for horizon_min, horizon_ticks in TICK_HORIZONS.items():
        windows = build_tick_demand_windows(test_ticks, horizon_ticks)
        preds = forecaster._dem[horizon_min].predict(
            windows[DEM_TICK_FEATURES].to_numpy())
        for ts, true, pred in zip(windows["timestamp"], windows[fc.TARGET_COL], preds):
            rows.append({
                "scenario": scenario, "room": "BUILDING", "target": "demand",
                "horizon_min": horizon_min, "timestamp": str(ts),
                "y_true": float(true), "y_pred": float(pred),
            })
    return rows


def run_ablation(scenarios=("weekday", "weekend", "heatwave"), seeds=None,
                 days=1, out_csv="results/ablation_c4.csv",
                 pred_csv="results/pred_vs_actual_c4.csv"):
    """D-11 ablation: C4-with-forecast vs C4-as-C3 on paired seeds.

    Fresh policy instances per run (same class + params — the flag flip is
    ``forecast=forecaster`` vs ``forecast=None``); forecasters are built once
    per timetable group and reused (never trained inside the loop).
    """
    import pandas as pd

    from ctrl.harness import compute_metrics, run_controller

    seeds = list(cfg.PAIRED_SEEDS) if seeds is None else list(seeds)
    forecasters, test_ticks_by_group, pred_rows = {}, {}, []
    for scenario in scenarios:
        group = cfg.SCENARIO_TABLE.get(scenario, "weekday")
        if group not in forecasters:
            forecaster, test_ticks = build_frozen_forecaster(group)
            forecasters[group] = forecaster
            test_ticks_by_group[group] = test_ticks
            pred_rows.extend(holdout_pred_rows(forecaster, test_ticks, group))
    rows = []
    for scenario in scenarios:
        forecaster = forecasters[cfg.SCENARIO_TABLE.get(scenario, "weekday")]
        for seed in seeds:
            frame_on, metrics_on = run_controller(
                PredictivePolicy(), scenario, seed, days=days, forecast=forecaster)
            rows.append({"scenario": scenario, "seed": seed,
                         "arm": "forecast_on", **metrics_on})
            frame_off, metrics_off = run_controller(
                PredictivePolicy(), scenario, seed, days=days, forecast=None)
            rows.append({"scenario": scenario, "seed": seed,
                         "arm": "forecast_off", **metrics_off})
    import pathlib

    pd.DataFrame(rows).to_csv(pathlib.Path(out_csv), index=False)
    pd.DataFrame(pred_rows).to_csv(pathlib.Path(pred_csv), index=False)
    table = pd.DataFrame(rows)
    for scenario in scenarios:
        sub = table[table["scenario"] == scenario]
        on = sub[sub["arm"] == "forecast_on"]["energy_kwh"].mean()
        off = sub[sub["arm"] == "forecast_off"]["energy_kwh"].mean()
        comfort = sub[sub["arm"] == "forecast_on"]["comfort_pct"].mean()
        print(f"{scenario}: on={on:.3f} off={off:.3f} "
              f"gap={(off - on):+.3f} kWh ({100 * (off - on) / off:+.1f}%) "
              f"comfort_on={comfort:.1f}%")
    return table


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="C4 forecast on/off ablation")
    parser.add_argument("--ablate", action="store_true")
    args = parser.parse_args()
    if args.ablate:
        run_ablation()
