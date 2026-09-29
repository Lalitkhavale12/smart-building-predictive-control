"""C1 fixed-schedule tables (D-01/D-02).

Room-type wall-clock tables using the same day-type vocabulary as the sim
(``weekday``/``weekend``/``heatwave``). Heatwave reuses the weekday occupancy
pattern (only weather differs), so its wall-clock schedule is identical to
weekday — C1 under heatwave stress differs by physics response, not by
schedule; report as-is.

Tables (agent's discretion, per RESEARCH F2 — deliberately NO gap-skipping
between class blocks; conditioning empty rooms mid-gap is the honest waste
C2/C3 must beat, and it is what real fixed schedules do):

- Classrooms (A/B): ON 08:00-18:00 weekdays, OFF otherwise.
- Office: ON 09:00-18:00 weekdays, OFF otherwise.
- Lab: ON during its four booked blocks 09:30-11:00 / 12:30-14:00 /
  15:00-17:30 / 18:00-20:00, OFF otherwise. The evening block 18:00-20:00 is
  covered (OQ1): a fixed schedule covers a booked block even though it runs
  past the classroom/office close.
- Weekend: all OFF except classroom_A 10:00-14:00 (mirrors the weekend
  timetable).

``TIMETABLES`` may be imported ONLY from this module (C1's wall-clock).
C2/C3 read current obs occupancy only — no future peeking.
"""

# (start_min, end_min) wall-clock half-open intervals, minutes since midnight.
_WEEKDAY = {
    "classroom_A": [(8 * 60, 18 * 60)],
    "classroom_B": [(8 * 60, 18 * 60)],
    "office": [(9 * 60, 18 * 60)],
    "lab": [
        (9 * 60 + 30, 11 * 60),
        (12 * 60 + 30, 14 * 60),
        (15 * 60, 17 * 60 + 30),
        (18 * 60, 20 * 60),
    ],
}

_WEEKEND = {
    "classroom_A": [(10 * 60, 14 * 60)],
    "classroom_B": [],
    "office": [],
    "lab": [],
}


def is_on(room, minute_of_day, day_type):
    """Wall-clock schedule lookup: True if ``room`` HVAC is ON at ``minute_of_day``.

    ``day_type`` is ``weekday``/``weekend``/``heatwave`` (heatwave answers are
    identical to weekday by design). Unknown rooms are OFF.
    """
    table = _WEEKEND if day_type == "weekend" else _WEEKDAY
    return any(start <= minute_of_day < end for start, end in table.get(room, []))
