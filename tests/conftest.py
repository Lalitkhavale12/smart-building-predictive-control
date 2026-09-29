"""Shared pytest setup: silence the intentional py-version notice and print the
report-record sanity numbers (pull-down minutes, tau) at session start."""

import warnings

warnings.filterwarnings(
    "ignore", message="sim tested on Python 3.12.*", category=RuntimeWarning
)


def pytest_sessionstart(session):
    warnings.simplefilter("ignore")
    from sim import config as cfg
    from sim.thermal import thermal_step

    t_in, steps = 30.0, 0
    while t_in > 24.0 and steps < 5000:
        t_in = thermal_step(t_in, 31.0, 0.0, cfg.Q_HVAC["ON"], 30.0, 0.12)
        steps += 1
    print(f"\n[report-record] pull-down 30->24 C at ON: {steps} min; tau: {cfg.BASE_TAU_HOURS:.1f} h")
