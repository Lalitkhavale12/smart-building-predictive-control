"""MQTT topic contract (Phase 2, D-01) — single source of truth.

Bridge, node shim, and firmware-contract test all import these helpers;
nothing hardcodes a topic literal elsewhere. Room identity comes from
``sim.config.ROOMS``; rooms contain underscores, never slashes, so no
wildcard-escape hazard. Stdlib + sim.config only — no paho import here.
"""

from sim.config import Q_HVAC

VALID_DEVICES = ("hvac", "light")

# Mirror of sim/config.py Q_HVAC keys (OFF/REDUCED/ON) and the (0, 1) light pair (D-03).
VALID_HVAC = frozenset(Q_HVAC)
VALID_LIGHT = (0, 1)

# Bridge-side subscriptions.
WILDCARD_TELEMETRY = "building/+/telemetry"
WILDCARD_STATUS = "building/+/status"


def telemetry_topic(room):
    """Node -> bridge sensor feed."""
    return f"building/{room}/telemetry"


def command_topic(room, device):
    """Bridge -> node setpoint. Device is hvac or light; commands are never retained."""
    assert device in VALID_DEVICES, f"device must be one of {VALID_DEVICES}, got {device!r}"
    return f"building/{room}/command/{device}"


def status_topic(room):
    """Retained online/offline presence (LWT target)."""
    return f"building/{room}/status"


def command_filter(room):
    """Per-node subscription covering both command devices."""
    return f"building/{room}/command/#"
