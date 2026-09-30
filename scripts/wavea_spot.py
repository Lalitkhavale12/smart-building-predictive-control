from ctrl.baselines import FixedSchedulePolicy, OccupancyRulePolicy, SetbackPolicy
from ctrl.compare import _predictive_policy, forecaster_for
from ctrl.harness import run_controller

for scen in ("weekday", "heatwave"):
    for name, pol, fc in (("C1", FixedSchedulePolicy(scenario=scen), None),
                          ("C2", OccupancyRulePolicy(), None),
                          ("C3", SetbackPolicy(), None),
                          ("C4tuned", _predictive_policy(), forecaster_for(scen))):
        _, m = run_controller(pol, scen, 0, forecast=fc)
        line = (name + " " + scen + " seed0: energy=" + format(m["energy_kwh"], ".3f")
                + "kWh comfort=" + format(m["comfort_pct"], ".1f")
                + "% cost=Rs" + format(m["cost_rs"], ".1f")
                + " co2=" + format(m["co2_kg"], ".2f") + "kg")
        print(line, flush=True)
