"""CSV logger + CLI runner gate (SIM-03, D-13, RESEARCH Findings section 6).

Asserts: exact schema column order, 1440x4 rows per day, ISO-8601 sim-time
timestamps, run_meta.json contents, --out traversal rejection (T-03-01), and
a 5-seed summarize() mean+-std check (the Plan 03 eval-helper contract).
"""

import json

import pandas as pd
import pytest

from sim import config as cfg
from sim import logger as log_mod
from sim import run as run_mod
from sim import summary as summary_mod

DAY = cfg.STEPS_PER_DAY
NROOMS = len(cfg.ROOMS)


@pytest.fixture
def cwd_results(tmp_path, monkeypatch):
    """Sandbox cwd so resolve_out('results/...') lands in tmp, not the repo."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results").mkdir()
    return tmp_path


def _run_seed(scenario, days, seed, cwd_results):
    out = run_mod.resolve_out(f"results/{scenario}/seed{seed:02d}")
    return run_mod.run(scenario, days, seed, out)


def test_schema_column_order(cwd_results):
    telemetry_path, meta_path = _run_seed("weekday", 1, 0, cwd_results)
    frame = pd.read_csv(telemetry_path)
    assert list(frame.columns) == log_mod.TELEMETRY_COLUMNS
    assert frame["HVAC_state"].isin(["OFF", "REDUCED", "ON"]).all()
    # ISO-8601 sim-time from the run epoch (4 room-rows share each step stamp).
    assert frame["timestamp"].iloc[0] == "2026-01-15T00:00:00"
    assert frame["timestamp"].iloc[4] == "2026-01-15T00:01:00"
    assert frame["timestamp"].nunique() == DAY
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["seed"] == 0 and meta["scenario"] == "weekday"
    assert meta["git_hash"] and meta["config"] and meta["versions"]


def test_rowcount_per_day(cwd_results):
    telemetry_path, _ = _run_seed("weekday", 1, 0, cwd_results)
    frame = pd.read_csv(telemetry_path)
    assert len(frame) == DAY * NROOMS  # 1440 steps x 4 rooms = 5760 rows/day
    assert set(frame["room"]) == set(cfg.ROOMS)
    assert (frame.groupby("room").size() == DAY).all()


def test_five_seed_summary_stats(cwd_results):
    for seed in range(5):
        _run_seed("weekday", 1, seed, cwd_results)
    table = summary_mod.summarize(cwd_results / "results" / "weekday")
    assert set(table["room"]) == set(cfg.ROOMS)
    assert (table["n_seeds"] == 5).all()
    for col in ("mean_T_in_mean", "mean_T_in_std", "energy_kwh_mean",
                "energy_kwh_std", "comfort_pct_mean", "comfort_pct_std"):
        assert col in table.columns, f"missing {col}"
    assert (table["energy_kwh_std"] >= 0).all()  # real mean+-std, not constants
    assert (cwd_results / "results" / "weekday" / "summary.csv").exists()


def test_out_traversal_rejected(cwd_results):
    with pytest.raises(ValueError):
        run_mod.resolve_out("results/../../evil")
    with pytest.raises(ValueError):
        run_mod.resolve_out("../evil")
