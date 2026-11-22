#!/usr/bin/env python3
"""Historical scenario R (replay injection): per (replayRate, variant) means and 95% CIs over 30 runs."""
import glob, os
from pathlib import Path
import pandas as pd, numpy as np
from scipy import stats
ROOT = Path(__file__).resolve().parents[1]
RUNS = Path(os.environ.get("HIBAF_RUNS_DIR", str(ROOT / "runs")))
OUT = ROOT / "results" / "generated" / "v33"
OUT.mkdir(parents=True, exist_ok=True)
rows = []
for f in glob.glob(str(RUNS / "*tag-R_*" / "summary.csv")):
    rows.append(pd.read_csv(f))
D = pd.concat(rows, ignore_index=True)
D["honestQuotaDrop"] = D.quotaDrop - D.rpDropQuota
D["rpRecv"] = D.rpDropMacWin + D.rpDropCache + D.rpDropPending + D.rpDropQuota + D.rpVerified
for k in ["rpDropMacWin", "rpDropCache", "rpDropPending", "rpDropQuota", "rpVerified", "rpDupVerify", "rpBenign", "rpBeDup"]:
    D[k + "_frac"] = np.where(D.rpRecv > 0, D[k] / D.rpRecv.clip(lower=1), np.nan)
D.to_csv(OUT / "all_runs_R.csv", index=False)
M = ["pdr", "syncSuccess", "e2eMean", "e2eP95", "colCpuUtil", "hecmPerVerified", "airtimePerPond", "rpSent", "rpRecv",
     "rpDropMacWin_frac", "rpDropCache_frac", "rpDropPending_frac", "rpDropQuota_frac", "rpVerified_frac", "rpDupVerify", "rpBenign", "rpBeDup",
     "attackCommitted", "honestQuotaDrop", "windowDrop", "macTxDrop", "dupPendingHonest"]
def ci(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 2: return (np.nan, np.nan)
    return x.mean(), stats.t.ppf(0.975, len(x)-1) * x.std(ddof=1) / np.sqrt(len(x))
out = []
for (rr, v), g in D.groupby(["replayRate", "variant"]):
    r = dict(replayRate=rr, variant=v, n=len(g))
    for m in M:
        r[m], r[m + "_ci"] = ci(g[m])
    out.append(r)
S = pd.DataFrame(out); S.to_csv(OUT / "rev_R.csv", index=False)
pd.set_option("display.width", 250)
print(S[["replayRate", "variant", "n"] + M].to_string(float_format=lambda x: f"{x:.4g}"))
