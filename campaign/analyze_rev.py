#!/usr/bin/env python3
"""Summaries for the revision campaign (tags Dev, Dz, G, H_*): mean and Student-t 95% CI over 30 runs."""
import glob, os
from pathlib import Path, json, sys
import pandas as pd, numpy as np
from scipy import stats
rows = []
ROOT = Path(__file__).resolve().parents[1]
RUNS = Path(os.environ.get("HIBAF_RUNS_DIR", str(ROOT / "runs")))
TABLES = ROOT / "results" / "tables"
TABLES.mkdir(parents=True, exist_ok=True)
for f in glob.glob(str(RUNS / "*/summary.csv")):
    tag = [p for p in os.path.basename(os.path.dirname(f)).split("_") if p.startswith("tag-")]
    d = os.path.basename(os.path.dirname(f))
    t = d.split("tag-")[1].split("_variant")[0]
    if t in ("Dev", "Dz", "G") or t.startswith("H_"):
        r = pd.read_csv(f); r["tagx"] = t; r["dir"] = d; rows.append(r)
if not rows:
    raise SystemExit(f"No revision campaign summaries found in {RUNS}. Run campaign_rev.py first.")
D = pd.concat(rows, ignore_index=True)
D.to_csv(TABLES / "all_runs_rev.csv", index=False)
def ci(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 2: return (np.nan, np.nan, len(x))
    return (x.mean(), stats.t.ppf(0.975, len(x)-1) * x.std(ddof=1) / np.sqrt(len(x)), len(x))
def summ(df, keys, metrics):
    out = []
    for k, g in df.groupby(keys):
        r = dict(zip(keys, k if isinstance(k, tuple) else (k,)))
        for m in metrics:
            mu, h, n = ci(g[m]); r[m] = mu; r[m + "_ci"] = h; r["n"] = n
        out.append(r)
    return pd.DataFrame(out)
res = {}
dev = D[D.tagx == "Dev"]
res["Dev"] = summ(dev, ["defenses", "attackers", "variant"], ["pdr", "detectToMitigate", "revPropagation", "attackCommitted", "falseRevoked", "macDrop", "colCpuUtil"])
dz = D[D.tagx == "Dz"]
res["Dz"] = summ(dz, ["evidence"], ["pdr", "falseRevoked", "noticesReceived", "noticesRejected", "syncSuccess"])
g = D[D.tagx == "G"]
res["G"] = summ(g, ["reportInterval", "pondSpacing", "beaconStagger"], ["pdr", "syncSuccess", "e2eMean", "e2eP95", "windowMissFrac", "airtimePerPond"])
h = D[D.tagx.str.startswith("H_")].copy(); h["plat"] = h.tagx.str.split("_").str[-1]; h["scen"] = h.tagx.str.split("_").str[1]
res["H"] = summ(h, ["scen", "plat", "nSensors", "reportInterval", "attackers", "variant"],
                ["pdr", "syncSuccess", "e2eMean", "e2eP95", "colCpuUtil", "energyPerReport_mJ", "energyCpu_mJ", "hecmPerVerified"])
for k, v in res.items():
    v.to_csv(TABLES / f"rev_{k}.csv", index=False)
    print("==", k, len(v)); print(v.to_string(max_cols=40, float_format=lambda x: f"{x:.4g}"))
