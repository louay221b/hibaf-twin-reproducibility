#!/usr/bin/env python3
"""Recalibration with the measured ESP32 cost (tags H_*_hwLow / H_*_hwHigh): mean and 95% CI over 30 runs,
and the LaTeX rows of the recalibration table."""
import glob, os
import pandas as pd, numpy as np
from scipy import stats
rows = []
for f in glob.glob("/home/claude/sim/runs/*hwPi*/summary.csv"):
    d = os.path.basename(os.path.dirname(f)); t = d.split("tag-")[1].split("_variant")[0]
    r = pd.read_csv(f); r["tagx"] = t; rows.append(r)
D = pd.concat(rows, ignore_index=True); D["plat"] = D.tagx.str.split("_").str[-1]; D["scen"] = D.tagx.str.split("_").str[1]
D.to_csv("tables/all_runs_hwPi.csv", index=False)
M = ["pdr", "syncSuccess", "e2eMean", "e2eP95", "colCpuUtil", "energyPerReport_mJ", "energyCpu_mJ", "hecmPerVerified"]
def ci(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    return x.mean(), stats.t.ppf(0.975, len(x)-1) * x.std(ddof=1) / np.sqrt(len(x)), len(x)
out = []
for k, g in D.groupby(["scen", "plat", "nSensors", "reportInterval", "attackers", "variant"]):
    r = dict(zip(["scen", "plat", "nSensors", "reportInterval", "attackers", "variant"], k))
    for m in M:
        mu, h, n = ci(g[m]); r[m] = mu; r[m + "_ci"] = h; r["n"] = n
    out.append(r)
S = pd.DataFrame(out); S.to_csv("tables/rev_H_pi.csv", index=False)
print(S[["scen","plat","nSensors","reportInterval","attackers","variant","n"]+M].to_string(float_format=lambda x: f"{x:.4g}"))
mx = max((S[m+"_ci"]/S[m]).max() for m in ["pdr","syncSuccess","e2eP95","energyPerReport_mJ","hecmPerVerified"])
print("max relative CI half-width (selected metrics): %.2f%%" % (100*mx))
