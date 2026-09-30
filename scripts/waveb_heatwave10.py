"""Wave B Task 4: C3 vs tuned-C4 on heatwave seeds 0-9 (ad-hoc; PAIRED_SEEDS untouched)."""
import sys
sys.path.insert(0, ".")
from ctrl.compare import run_matrix, paired_ttest

seeds = list(range(10))
per_run = run_matrix(["c3", "c4-with"], ["heatwave"], seeds, out_root="results/heatwave10")
t_e, p_e = paired_ttest(per_run, "heatwave", "c4-with", "c3", metric="energy_kwh")
t_c, p_c = paired_ttest(per_run, "heatwave", "c4-with", "c3", metric="comfort_pct")
print(f"energy:  t={t_e:.3f} p={p_e:.6f} -> {'SIGNIFICANT' if p_e < 0.05 else 'not significant'}")
print(f"comfort: t={t_c:.3f} p={p_c:.6f} -> {'SIGNIFICANT' if p_c < 0.05 else 'not significant'}")
import pandas as pd
df = pd.DataFrame(per_run)
for c in ["c3", "c4-with"]:
    sub = df[df.controller == c]
    print(f"{c}: energy {sub.energy_kwh.mean():.3f}+/-{sub.energy_kwh.std(ddof=1):.3f} kWh, "
          f"comfort {sub.comfort_pct.mean():.1f}+/-{sub.comfort_pct.std(ddof=1):.1f}% (n=10)")
