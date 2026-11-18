"""Guard: a partial matrix summary must never be treated as a complete input.

The README's single-run command (`eval.matrix --controllers c3 --seeds 1`)
leaves a one-row summary.csv behind. `eval.report` used to accept any existing
summary as complete, then fig_g2 crashed with IndexError on the missing
controller rows. Completeness is now checked before reuse.
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import eval.report as report  # noqa: E402

CONTROLLERS = ["c1", "c2", "c3", "c4-with", "c4-as-c3"]
SCENARIOS = ["weekday", "weekend", "heatwave", "exam-day"]


def _write_summary(root: pathlib.Path, rows):
    path = root / "results" / "full_matrix" / "summary.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["controller", "scenario"]).to_csv(path, index=False)
    return path


def test_missing_summary_is_incomplete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert report._summary_complete() is False


def test_single_controller_summary_is_incomplete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_summary(tmp_path, [{"controller": "c3", "scenario": "weekday"}])
    assert report._summary_complete() is False


def test_full_matrix_summary_is_complete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rows = [{"controller": c, "scenario": s}
            for c in CONTROLLERS for s in SCENARIOS]
    _write_summary(tmp_path, rows)
    assert report._summary_complete() is True


def test_summary_without_expected_columns_is_incomplete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "results" / "full_matrix" / "summary.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"foo": range(20)}).to_csv(path, index=False)
    assert report._summary_complete() is False
