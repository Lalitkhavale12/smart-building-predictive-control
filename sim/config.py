"""All magic numbers live here. Nothing under sim/ hardcodes physics constants.

Conventions: T [degC], R [degC/kW] (UA = 1/R in kW/K), C [kWh/K],
Q [kW, +heating/-cooling], dt in seconds (converted to hours at use).
"""

# --- Timestep (D-04 / D-05: 1-min sim, 5-min control hook) ---
DT_S = 60
DT_H = DT_S / 3600.0  # 1/60 h
CONTROL_HOOK_STEPS = 5  # policy called every 5th step; action held between
STEPS_PER_DAY = 1440

# --- Rooms (D-04: 4 rooms, class/office pattern) ---
ROOMS = ("classroom_A", "classroom_B", "office", "lab")

# --- 1R1C envelope (agent's discretion, RESEARCH Findings section 2) ---
# Base values: R = 30 degC/kW (one exterior wall + window + infiltration,
# ~50 sqm room, UA ~= 33 W/K); C = 0.12 kWh/K (air + furnishings/shallow
# mass, ~100-150 m3 room). Anchors: house C ~= 2.2-3.2 kWh/K at R ~= 2.5
# (Kircher DER-buildings-1); room air-only C ~= 52 kJ/K (InferLab Lec-6 8.7).
# Per-room +-15% (corner vs interior) so rooms are not suspiciously identical.
R_PER_ROOM = {
    "classroom_A": 30.0 * 1.15,  # corner, leakier
    "classroom_B": 30.0 * 0.95,
    "office": 30.0 * 0.85,  # interior
    "lab": 30.0 * 1.05,
}
C_PER_ROOM = {
    "classroom_A": 0.12 * 1.15,  # more mass
    "classroom_B": 0.12 * 0.95,
    "office": 0.12 * 0.85,
    "lab": 0.12 * 1.05,
}

# tau = R*C per room; base room: 30 * 0.12 = 3.6 h — inside the
# lightweight-building 2-5 h band (InferLab Lec-6 8.7.3). Sanity tests assert this.
TAU_HOURS = {room: R_PER_ROOM[room] * C_PER_ROOM[room] for room in ROOMS}
BASE_TAU_HOURS = 30.0 * 0.12  # 3.6 h, the headline number for the report

# --- HVAC discrete levels (D-03) ---
# Fixed thermal Q per level. ON ~= 1-ton split sensible capacity (1 ton =
# 3.517 kW). Negative = cooling (heat removed from room).
Q_HVAC = {"OFF": 0.0, "REDUCED": -1.2, "ON": -3.5}
HVAC_LEVELS = tuple(Q_HVAC)

# --- Internal gains ---
# Q_OCC_PER_PERSON = 0.10 kW sensible heat (~100 W/person, ASHRAE
# Fundamentals Ch.18 textbook value). 30 students = 3.0 kW, i.e. nearly a
# full AC's worth of heat — which is exactly why classrooms need control.
Q_OCC_PER_PERSON = 0.10

# --- Electrical conversion ---
# power_kW = |Q_hvac| / COP + light load. COP 3.0 typical split AC;
# 1.5-ton unit ~= 1.5 kW electrical at full load.
COP = 3.0
P_LIGHT_KW = 0.20  # per room when lights on (classroom LED/fluorescent load)

# --- Comfort band (D-11/D-12, locked guide default — never retune to pass) ---
COMFORT_T_MIN, COMFORT_T_MAX = 22.0, 26.0  # degC
COMFORT_RH_MIN, COMFORT_RH_MAX = 30.0, 60.0  # % RH

# --- Weather (D-06: sinusoid + heatwave offset + seeded noise) ---
# Pune warm-day shape: min ~27 degC ~05:00, max ~35 degC ~15:00.
T_OUT_MEAN = 31.0
T_OUT_AMPLITUDE = 4.0
T_OUT_PEAK_HOUR = 15.0  # hour of daily max
T_OUT_NOISE_STD = 0.3  # degC, seeded gaussian per step
HEATWAVE_OFFSET = 4.0  # degC added in heatwave scenario
RH_INIT = 55.0
RH_STEP_STD = 0.4  # % RH random-walk step
RH_MIN, RH_MAX = 30.0, 70.0  # hard clip (D-06)

# --- Scenarios (SIM-02: CLI/config string, never code edits) ---
SCENARIOS = ("weekday", "weekend", "heatwave", "exam-day")

# --- Paired seeds (D-08: identical seeds reused by every controller later) ---
PAIRED_SEEDS = [0, 1, 2, 3, 4]

# --- Occupancy timetables (SIM-02 / D-04, RESEARCH Findings section 3) ---
# Day-type block tables. Logic in sim/occupancy.py only parses these — it never
# hardcodes a time or a headcount. Block = (start "HH:MM", end "HH:MM", fill)
# where fill is an int headcount or "poisson:<lam>" stochastic fill (office).
# Gaps between blocks are empty (0). Times are wall schedule; occupancy.py
# applies +-10 min seeded jitter on edges at run build time.
TIMETABLES = {
    "weekday": {
        # 2 classrooms, 0-32 teaching blocks with gaps (no class = empty).
        "classroom_A": [
            ("08:00", "09:30", 28),
            ("09:45", "11:15", 32),
            ("11:30", "13:00", 25),
            ("14:00", "15:30", 30),
            ("15:45", "17:15", 20),
        ],
        "classroom_B": [
            ("08:30", "10:00", 22),
            ("10:15", "11:45", 30),
            ("13:00", "14:30", 27),
            ("14:45", "16:15", 18),
        ],
        # Office 0-6, 09:00-18:00; lunch dip via low-lambda middle block.
        "office": [
            ("09:00", "13:00", "poisson:4"),
            ("13:00", "14:00", "poisson:1"),  # lunch dip
            ("14:00", "18:00", "poisson:4"),
        ],
        # Lab/seminar 0-15, irregular blocks incl. an evening session.
        "lab": [
            ("09:30", "11:00", 12),
            ("12:30", "14:00", 8),
            ("15:00", "17:30", 15),
            ("18:00", "20:00", 6),
        ],
    },
    # Weekend: single room 10:00-14:00 with 5 people, rest empty.
    "weekend": {
        "classroom_A": [("10:00", "14:00", 5)],
        "classroom_B": [],
        "office": [],
        "lab": [],
    },
}
# Scenario -> timetable key. Heatwave reuses the weekday occupancy pattern
# (only weather differs, via HEATWAVE_OFFSET); exam-day is a STUB returning
# weekday blocks until a real exam timetable is specified (later phase).
SCENARIO_TABLE = {
    "weekday": "weekday",
    "weekend": "weekend",
    "heatwave": "weekday",
    "exam-day": "weekday",
}

# --- Occupancy stochastic deviations (seeded, via passed-in rng only) ---
OCC_EDGE_JITTER_MIN = 10  # +- minutes on block edges (sharp edges forbidden:
# deterministic tables make forecasting trivially easy, PITFALLS Pitfall 2)
OCC_ABSENCE_P = 0.05  # per-person random absence probability
OFFICE_MAX = 6  # poisson fill clipped to 0-6
