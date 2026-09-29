"""Boundary guard (D-14 / Pitfall E): sim/ must not import future ctrl/ml/iot.

Controller reaching into physics internals invalidates every Phase 3
comparison, so the split is enforced by test, not convention. Fails on:
- any `import ctrl|ml|iot` / `from ctrl|ml|iot ...` in sim/*.py
- sim modules actually resolving such imports at runtime
"""

import pathlib
import re

SIM_DIR = pathlib.Path(__file__).resolve().parent.parent / "sim"
FORBIDDEN = re.compile(r"(?:^|\s)(?:import|from)\s+(ctrl|ml|iot)\b")


def test_no_future_package_imports():
    offenders = []
    for path in sorted(SIM_DIR.glob("*.py")):
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if FORBIDDEN.search(line):
                offenders.append(f"{path.name}:{i}: {line.strip()}")
    assert not offenders, "sim/ reaches into future packages:\n" + "\n".join(offenders)


def test_sim_modules_import_cleanly():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # py-version notice, not this test's concern
        import sim.config
        import sim.policy
        import sim.simulator
        import sim.thermal
    assert hasattr(sim.simulator, "BuildingSim")
    assert hasattr(sim.policy, "BasePolicy")
