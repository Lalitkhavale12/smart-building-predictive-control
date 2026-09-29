"""Hourly grid carbon + ToU price series (D-09/D-10, RESEARCH Findings section 8).

================================================================================
DOCUMENTED ASSUMPTIONS — READ BEFORE USING THESE NUMBERS IN THE REPORT
================================================================================
1. CEA SOURCE + YEAR: the series mean is the Central Electricity Authority
   CO2 Baseline Database v21.0 (Nov 2025) weighted-average grid factor of
   0.710 tCO2/MWh for FY 2024-25 (0.727 in FY 2023-24; Table S of the
   User_Guide_V_21.0.pdf). Re-check annually — v22.0 (FY25-26) lands ~Nov 2026.
2. DAILY SHAPE IS A TRANSPARENT MODELLED ASSUMPTION, not a measurement: solar
   dip 10-16h x0.80, evening fossil peak 18-23h x1.18, night x1.02, morning
   x0.95. Raw multipliers are mean-normalized to 1.0 so the series mean stays
   EXACTLY the CEA anchor (mean == 0.710 +- 0.001, asserted in tests). To swap
   the shape, edit HOURLY_SHAPE below — the mean guarantee is structural.
3. AVERAGE (NOT MARGINAL) emission factor is used consistently for BOTH
   control decisions AND carbon accounting. Operating margin (0.961) / build
   margin (0.512) are reported in the CEA guide for context; mixing marginal
   decisions with average accounting (or vice versa) is the Pitfall-6 trap.
4. ToU prices are MSEDCL commercial classic 4-slab time-of-day adders on a
   ~Rs 9/kWh base energy charge (approved tariff schedule FY24-25):
   22:00-06:00 -1.50 | 06:00-09:00 & 12:00-18:00 +0.00 | 09:00-12:00 +0.80 |
   18:00-22:00 +1.10 (Rs/kWh). MERC MYT Order (Case 217/2024, Mar 2025)
   redesigns slabs toward a 09:00-17:00 solar-hours rebate / 17:00-24:00 peak
   surcharge for FY25-30 — adopting the MYT table is a DOCUMENTED PHASE-5
   OPTION, not Phase-1 work.
================================================================================

Carbon-shifting math itself lives in Phase 5; this module ONLY builds and
verifies the 24-row hourly series. There is deliberately NO scalar emission
constant anywhere (grep-test enforced): a flat factor would make load-shifting
mathematically vacuous.
"""

import argparse
import csv
import pathlib

# Annual anchor: CEA v21.0 weighted average, FY 2024-25, kgCO2/kWh.
GRID_EF_BASE_KG_PER_KWH = 0.710

# ToU base energy charge with classic 4-slab adders (Rs/kWh, MSEDCL FY24-25).
TOU_BASE_RS_PER_KWH = 9.0
TOU_OFFPEAK_ADDER = -1.50   # 22:00-06:00
TOU_NORMAL_ADDER = 0.00     # 06:00-09:00 and 12:00-18:00
TOU_MORNING_ADDER = 0.80    # 09:00-12:00
TOU_EVENING_ADDER = 1.10    # 18:00-22:00

# Raw daily-shape multipliers (modelled assumption, mean-normalized at build).
# solar dip 10-16h x0.80 | evening fossil peak 18-23h x1.18 | night x1.02 |
# morning x0.95. Night = 00-05, morning = 06-09 + 17 (leftovers by construction).
HOURLY_SHAPE = (
    [1.02] * 6    # hours 00-05: night
    + [0.95] * 4  # hours 06-09: morning ramp
    + [0.80] * 7  # hours 10-16: solar dip
    + [0.95]      # hour  17:    shoulder (morning-class multiplier)
    + [1.18] * 6  # hours 18-23: evening fossil peak
)


def hourly_rows(ef_base=GRID_EF_BASE_KG_PER_KWH):
    """24 (hour, ef, price) rows; EF multipliers mean-normalized so mean == base."""
    mean_shape = sum(HOURLY_SHAPE) / 24.0
    rows = []
    for hour in range(24):
        ef = ef_base * HOURLY_SHAPE[hour] / mean_shape
        if hour in (22, 23, 0, 1, 2, 3, 4, 5):
            price = TOU_BASE_RS_PER_KWH + TOU_OFFPEAK_ADDER
        elif hour in (9, 10, 11):
            price = TOU_BASE_RS_PER_KWH + TOU_MORNING_ADDER
        elif hour in (18, 19, 20, 21):
            price = TOU_BASE_RS_PER_KWH + TOU_EVENING_ADDER
        else:
            price = TOU_BASE_RS_PER_KWH + TOU_NORMAL_ADDER
        rows.append((hour, round(ef, 4), round(price, 2)))
    return rows


def write_csv(path, ef_base=GRID_EF_BASE_KG_PER_KWH):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["hour", "ef_kg_per_kwh", "price_rs_per_kwh"])
        writer.writerows(hourly_rows(ef_base=ef_base))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build data/grid_hourly.csv")
    parser.add_argument("--ef-base", type=float, default=GRID_EF_BASE_KG_PER_KWH)
    parser.add_argument("--shape", default="default", choices=["default"])
    parser.add_argument("--out", default="data/grid_hourly.csv")
    args = parser.parse_args(argv)
    write_csv(args.out, ef_base=args.ef_base)
    print(f"wrote {args.out} (ef_base={args.ef_base}, shape={args.shape})")


if __name__ == "__main__":
    main()
