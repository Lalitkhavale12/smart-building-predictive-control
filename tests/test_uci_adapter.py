"""UCI adapter tests (Phase 4, FOR-04, D-12/D-13).

Never touches the network: fetch is monkeypatched. Never touches sim/ or
ctrl/: enforced by the import-surface test below.
"""

import io
import pathlib
import re
import urllib.error
import zipfile

import pandas as pd

from ml import uci


def _fake_zip(n_rows=8):
    cols = sorted(uci.REQUIRED_COLS)
    data = {c: [1.0] * n_rows for c in cols}
    data["date"] = pd.date_range("2016-01-11 17:00", periods=n_rows, freq="10min").astype(str)
    data["Appliances"] = [100.0] * n_rows
    data["T1"] = [21.0] * n_rows
    data["RH_1"] = [40.0] * n_rows
    data["T_out"] = [7.0] * n_rows
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("EnergyData.csv", pd.DataFrame(data).to_csv(index=False))
    return buf.getvalue()


def test_skip_on_network_failure(monkeypatch):
    """Blocked network → (None, documented reason), fast, never raises."""

    def boom(url, timeout=30):
        raise urllib.error.URLError("blocked in test")

    frame, reason = uci.load_or_skip(fetcher=boom)
    assert frame is None
    assert "synthetic-only" in reason


def test_main_exit_zero_on_failure(monkeypatch, capsys):
    """CLI prints the reason and exits 0 on fetch failure (locked D-13)."""
    monkeypatch.setattr(uci, "fetch_zip",
                        lambda url, timeout=30: (_ for _ in ()).throw(
                            urllib.error.URLError("blocked in test")))
    assert uci.main() == 0
    assert "synthetic-only" in capsys.readouterr().out


def test_aligned_frame_schema(monkeypatch):
    """Mocked fetch → frame aligned to the 04-01 room schema (demand-only)."""
    blob = _fake_zip()
    monkeypatch.setattr(uci, "EXPECTED_ROWS", 8)
    monkeypatch.setattr(uci, "fetch_zip", lambda url, timeout=30: blob)
    frame, reason = uci.load_or_skip()
    assert reason == ""
    assert list(frame.columns) == list(uci.FRAME_COLS)
    assert (frame["room"] == "uci_appliances").all()
    assert (frame["occupancy"] == 0.0).all()  # placeholder, never scored
    assert (frame["power_kW"] == 100.0 * 0.006).all()  # Wh/10min → kW
    assert frame["timestamp"].is_monotonic_increasing


def test_row_count_verified(monkeypatch):
    """Wrong row count fails loudly, never silently (T-04-02)."""
    import pytest

    blob = _fake_zip(n_rows=8)
    with pytest.raises(ValueError, match="row count"):
        uci.load_appliances(blob)


def test_stdlib_only_and_no_sim_ctrl():
    """Adapter imports stdlib+pandas only; touches nothing in sim/ or ctrl/."""
    src = pathlib.Path("ml/uci.py").read_text()
    assert "demand-only" in src.lower() or "demand only" in src.lower()
    assert "no occupancy ground truth" in src.lower()
    assert re.search(r"H\s*=\s*3.*H\s*=\s*6|H=3/H=6", src), "horizon-step map missing"
    for mod in ("sim", "ctrl", "sklearn", "tensorflow"):
        assert not re.search(rf"^\s*(import|from)\s+{mod}\b", src, re.M), \
            f"ml/uci.py must not import {mod}"
    assert uci.FETCH_TIMEOUT_S <= 60, "fetch must stay time-boxed"
