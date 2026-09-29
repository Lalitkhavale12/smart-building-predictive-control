"""Grid series gate (D-09/D-10, RESEARCH Findings section 8).

Asserts: 24 rows, series mean == CEA v21.0 anchor 0.710 +- 0.001, evening
peak above solar dip, and the no-scalar guard — a numeric EMISSION_FACTOR
assignment anywhere in sim/ fails (flat factors make shifting vacuous).
"""

import csv
import pathlib
import re

import pytest

from sim import grid as grid_mod

REPO = pathlib.Path(__file__).resolve().parent.parent
CSV = REPO / "data" / "grid_hourly.csv"


def _rows():
    with CSV.open() as fh:
        return list(csv.DictReader(fh))


def test_csv_has_24_rows():
    assert CSV.exists(), "data/grid_hourly.csv missing — run: python sim/grid.py"
    rows = _rows()
    assert len(rows) == 24, f"expected 24 rows, got {len(rows)}"
    assert [r for r in rows[0].keys()] == ["hour", "ef_kg_per_kwh", "price_rs_per_kwh"]
    assert [int(r["hour"]) for r in rows] == list(range(24))


def test_mean_is_cea_anchor():
    rows = _rows()
    mean = sum(float(r["ef_kg_per_kwh"]) for r in rows) / len(rows)
    assert mean == pytest.approx(0.710, abs=0.001), f"mean EF {mean:.4f} != 0.710"


def test_evening_peak_above_solar_dip():
    rows = _rows()
    ef = [float(r["ef_kg_per_kwh"]) for r in rows]
    dip = sum(ef[10:17]) / 7      # solar dip 10-16h
    peak = sum(ef[18:24]) / 6     # evening fossil peak 18-23h
    assert peak > dip, f"peak {peak:.4f} must exceed dip {dip:.4f}"


def test_no_scalar_emission_factor():
    """No `EMISSION_FACTOR = <number>` anywhere in sim/ (Pitfall-6 guard)."""
    sim_dir = REPO / "sim"
    banned = re.compile(r"EMISSION_FACTOR\s*=\s*[0-9]")
    offenders = [f"{p.name}:{i}: {ln.strip()}" for p in sorted(sim_dir.glob("*.py"))
                 for i, ln in enumerate(p.read_text().splitlines(), 1)
                 if banned.search(ln)]
    assert not offenders, "scalar EF in sim/:\n" + "\n".join(offenders)


def test_builder_reproduces_csv():
    assert grid_mod.hourly_rows() is not None
    rebuilt = {(h, e, p) for h, e, p in grid_mod.hourly_rows()}
    on_disk = {(int(r["hour"]), float(r["ef_kg_per_kwh"]), float(r["price_rs_per_kwh"]))
               for r in _rows()}
    assert rebuilt == on_disk, "data/grid_hourly.csv is stale — re-run python sim/grid.py"
