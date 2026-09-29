"""Single-room 1R1C explicit-Euler thermal step (D-01/D-02).

Source form (lumped capacitance, Kircher DER-buildings-1; InferLab Lec-6 8.7):
    C * dT_in/dt = (T_out - T_in) / R + Q_gains
Discretised at dt = 60 s:
    T_in += dt_h / C * ((T_out - T_in) / R + Q_occ + Q_hvac)

Cooling-negative sign convention: Q_hvac < 0 removes heat, Q_occ > 0 adds it.

Stability: explicit Euler stable iff dt_h < 2*tau. Here dt_h = 1/60 h and
tau ~= 3.6 h, margin ~400x — unconditionally safe, no solver needed.
"""

from sim import config as cfg


def thermal_step(t_in, t_out, q_occ_kw, q_hvac_kw, r, c, dt_h=cfg.DT_H):
    """Advance one room's indoor temp by one sim step. Pure function.

    Args:
        t_in: indoor temp [degC].  t_out: outdoor temp [degC].
        q_occ_kw: occupancy heat gain, >= 0 [kW].
        q_hvac_kw: HVAC thermal power, <= 0 for cooling [kW].
        r: thermal resistance [degC/kW].  c: capacitance [kWh/K].
        dt_h: step in hours (default 1/60).

    Returns:
        New indoor temp [degC].
    """
    return t_in + dt_h / c * ((t_out - t_in) / r + q_occ_kw + q_hvac_kw)


def electrical_power_kw(q_hvac_kw, light_on):
    """Electrical draw [kW] = |Q_hvac|/COP + light load."""
    return abs(q_hvac_kw) / cfg.COP + (cfg.P_LIGHT_KW if light_on else 0.0)
