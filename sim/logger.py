"""Telemetry logger (SIM-03, D-13, RESEARCH Findings section 6).

Exact schema (this order — downstream phases parse positionally):
  timestamp,room,T_in_C,T_out_C,RH_pct,occupancy,HVAC_state,power_kW,light_on

Rules: timestamps are ISO-8601 SIM-TIME from RUN_START + step index (never
wall-clock, so same-seed reruns are byte-identical); HVAC_state in
{OFF, REDUCED, ON}; power_kW is electrical (|Q_hvac|/COP + light); floats at
4 decimals via float_format="%.4f". One telemetry.csv per seed (all rooms) +
run_meta.json (seed, git hash, config snapshot, package versions).
"""

import datetime
import json
import pathlib
import platform
import subprocess

import pandas as pd

TELEMETRY_COLUMNS = [
    "timestamp", "room", "T_in_C", "T_out_C", "RH_pct",
    "occupancy", "HVAC_state", "power_kW", "light_on",
]

# Sim epoch: run start, midnight. Multi-day runs add step minutes past day end.
RUN_START = datetime.datetime(2026, 1, 15, 0, 0, 0)


def sim_timestamp(step):
    """ISO-8601 sim-time for a 1-min step index (deterministic, no wall-clock)."""
    return (RUN_START + datetime.timedelta(minutes=int(step))).isoformat()


class TelemetryLogger:
    """Accumulates per-step per-room rows; save_csv writes the experiment record."""

    def __init__(self):
        self._rows = []

    def record(self, step, room, obs_room, action_room):
        self._rows.append({
            "timestamp": sim_timestamp(step),
            "room": room,
            "T_in_C": float(obs_room["T_in"]),
            "T_out_C": float(obs_room["T_out"]),
            "RH_pct": float(obs_room["RH"]),
            "occupancy": int(obs_room["occupancy"]),
            "HVAC_state": action_room["hvac"],
            "power_kW": float(obs_room["power_kW"]),
            "light_on": int(action_room["light"]),
        })

    def to_frame(self):
        return pd.DataFrame(self._rows, columns=TELEMETRY_COLUMNS)

    def save_csv(self, path):
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.to_frame().to_csv(path, index=False, float_format="%.4f")
        return path


def _git_hash():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def write_run_meta(out_dir, seed, scenario, days, config):
    """run_meta.json: seed, git hash, config snapshot, package versions."""
    import numpy
    import pandas

    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "seed": int(seed),
        "scenario": scenario,
        "days": int(days),
        "git_hash": _git_hash(),
        "config": {
            "rooms": list(config.ROOMS),
            "R_per_room": dict(config.R_PER_ROOM),
            "C_per_room": dict(config.C_PER_ROOM),
            "Q_hvac": dict(config.Q_HVAC),
            "Q_occ_per_person": config.Q_OCC_PER_PERSON,
            "COP": config.COP,
            "P_light_kW": config.P_LIGHT_KW,
            "comfort_band_C": [config.COMFORT_T_MIN, config.COMFORT_T_MAX],
            "comfort_band_RH": [config.COMFORT_RH_MIN, config.COMFORT_RH_MAX],
            "dt_s": config.DT_S,
            "control_hook_steps": config.CONTROL_HOOK_STEPS,
        },
        "versions": {
            "python": platform.python_version(),
            "numpy": numpy.__version__,
            "pandas": pandas.__version__,
        },
    }
    with (out_dir / "run_meta.json").open("w") as fh:
        json.dump(meta, fh, indent=2, sort_keys=True)
    return out_dir / "run_meta.json"
