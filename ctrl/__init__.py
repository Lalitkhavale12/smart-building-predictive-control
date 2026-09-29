"""Baseline + predictive controllers (Phase 3+).

Lights rule (all baselines, documented once here): lights follow occupancy —
``light = 1`` iff the room is currently occupied, ``0`` otherwise. Lighting
has no thermal inertia, so instant-off on vacancy is free savings with zero
comfort cost; no vacancy delay is applied to lights (unlike HVAC).
"""
