"""sim — reproducible multi-room RC-thermal building simulator (Phase 1).

Physics + evaluation foundation only. No MQTT, no ML, no controllers.
Later phases plug in via `sim.simulator.BuildingSim` and `sim.policy.BasePolicy`.
"""

import sys
import warnings

# Project pins Python 3.12 (TensorFlow CPU-wheel ceiling for Phase 4).
# Warn — never hard-fail — so physics work stays runnable on other interpreters.
if sys.version_info[:2] != (3, 12):
    warnings.warn(
        f"sim tested on Python 3.12, running on "
        f"{sys.version_info.major}.{sys.version_info.minor}; "
        f"proceeding anyway (3.13+ breaks TF wheels in Phase 4 only).",
        RuntimeWarning,
        stacklevel=2,
    )

__all__ = []
