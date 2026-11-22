#!/usr/bin/env python3
"""Reproduce Table IX (ns-3 results with measured device timings) from the archived per-run outputs.
Input: results/tables/all_runs_hwPi_beaconfix.csv (one row per run; 30 seeds per configuration).
Output: means, Student-t 95% CI half-widths (relative to the mean), and the PDR - Sync. gap."""
import sys, os
import numpy as np, pandas as pd
from scipy import stats
here = os.path.dirname(os.path.abspath(__file__))
D = pd.read_csv(os.path.join(here, "tables", "all_runs_hwPi_beaconfix.csv"))
ROWS = [("A", 500, 0, "msm", "A, 500 sensors", "HiBaF-MSM"), ("A", 500, 0, "ind", "", "B1 indiv."), ("A", 500, 0, "base", "", "Base"),
        ("A2", 100, 0, "msm", "A2, 400 rep/s", "HiBaF-MSM"), ("A2", 100, 0, "ind", "", "B1 indiv."), ("A2", 100, 0, "base", "", "Base"),
        ("E", 100, 10, "msm", "E, 10 attackers", "HiBaF-MSM"), ("E", 100, 10, "msmfix", "", "MSM-bisection"),
        ("E", 100, 10, "ind", "", "B1 indiv."), ("E", 100, 10, "base", "", "Base")]
M = [("pdr", "PDR", 3, 1), ("syncSuccess", "Sync.", 3, 1), ("e2eP95", "p95 (s)", 3, 1),
     ("colCpuUtil", "Col. CPU (%)", 1, 100), ("hecmPerVerified", "HECM/rep.", 2, 1), ("energyPerReport_mJ", "Est. sensor mJ/rep.", 1, 1)]
def ci(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    return x.mean(), stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)), len(x)
print("Scenario | Variant | " + " | ".join(h for _, h, _, _ in M) + " | n")
worst = (0, "")
for sc, ns, at, v, lab, name in ROWS:
    g = D[(D.scen == sc) & (D.nSensors == ns) & (D.attackers == at) & (D.variant == v)]
    cells = []
    for col, h, nd, k in M:
        mu, hw, n = ci(g[col]); cells.append(f"{mu*k:.{nd}f}")
        if mu: worst = max(worst, (hw / mu, f"{sc} {name} {h}"))
    print(f"{lab} | {name} | " + " | ".join(cells) + f" | {n}")
print("max relative CI half-width: %.2f%% (%s)" % (100 * worst[0], worst[1]))
print("max per-run PDR - Sync.: %.6f; max p99 delay: %.3f s" % ((D.pdr - D.syncSuccess).max(), D.e2eP99.max()))
