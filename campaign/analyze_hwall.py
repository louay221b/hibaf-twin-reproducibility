#!/usr/bin/env python3
"""Summaries of the hardware-calibrated campaign (runs_hwall/, tags HW_*), and scalability figure."""
import glob, os, json
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
RUNS = Path(os.environ.get("HIBAF_RUNS_DIR", str(ROOT / "runs_hwall")))
OUT = ROOT / "results" / "generated" / "v33"
OUT.mkdir(parents=True, exist_ok=True)
rows = []
for f in glob.glob(str(RUNS / "*/summary.csv")):
    d = os.path.basename(os.path.dirname(f)); tag = d.split("tag-")[1].split("_variant")[0]
    r = pd.read_csv(f); r["tagx"] = tag; rows.append(r)
D = pd.concat(rows, ignore_index=True); D.to_csv(OUT / "all_runs_hwall.csv", index=False)
def ci(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x)
    if n < 2: return np.nan, np.nan, n
    return x.mean(), stats.t.ppf(0.975, n-1) * x.std(ddof=1) / np.sqrt(n), n
def S(tag, keys, metrics):
    g = D[D.tagx == tag]; out = []
    for k, gg in g.groupby(keys):
        r = dict(zip(keys, k if isinstance(k, tuple) else (k,)))
        for m in metrics: mu, h, n = ci(gg[m]); r[m] = mu; r[m + "_ci"] = h; r["n"] = n
        out.append(r)
    return pd.DataFrame(out)
pd.set_option("display.width", 250); fmt = lambda x: f"{x:.4g}"
res = {}
def show(name, df):
    res[name] = df; print(f"\n== {name}"); print(df.to_string(float_format=fmt, index=False))
if (D.tagx == "HW_A").any():
    show("A", S("HW_A", ["variant", "nSensors"], ["pdr", "syncSuccess", "e2eMean", "e2eP95", "colCpuUtil", "energyPerReport_mJ", "hecmPerVerified"]))
if (D.tagx == "HW_B1").any(): show("B1", S("HW_B1", ["variant", "radius"], ["pdr"]))
if (D.tagx == "HW_B2").any(): show("B2", S("HW_B2", ["variant", "wanLoss"], ["syncSuccess", "e2eP95", "e2eP99", "pdr"]))
for t in ["HW_F_burst", "HW_F_burst_aq", "HW_F_outage"]:
    if (D.tagx == t).any(): show(t, S(t, ["variant"], ["pdr", "syncSuccess", "e2eP99", "quotaDrop"]))
if (D.tagx == "HW_Dev").any(): show("Dev", S("HW_Dev", ["variant", "attackers", "defenses"], ["pdr", "macDrop", "detectToMitigate", "revPropagation", "attackCommitted", "falseRevoked"]))
if (D.tagx == "HW_Dz").any(): show("Dz", S("HW_Dz", ["evidence"], ["pdr", "falseRevoked", "noticesReceived", "noticesRejected"]))
if (D.tagx == "HW_R").any():
    g = D[D.tagx == "HW_R"].copy(); g["rpVerified_frac"] = g.rpVerified / g.rpSent.replace(0, np.nan)
    D.loc[g.index, "rpVerified_frac"] = g.rpVerified_frac
    show("R", S("HW_R", ["variant", "replayRate"], ["pdr", "attackCommitted", "rpBeDup", "rpVerified_frac"]))
if (D.tagx == "HW_G").any(): show("G", S("HW_G", ["reportInterval", "pondSpacing", "beaconStagger"], ["pdr"]))
if (D.tagx == "HW_BEsens").any():
    be = S("HW_BEsens", ["variant"], ["pdr", "e2eMean"]); a5 = S("HW_A", ["variant", "nSensors"], ["pdr", "e2eMean"]); a5 = a5[a5.nSensors == 500]
    m = be.merge(a5, on="variant", suffixes=("_be119", "_be010")); m["delay_rise_ms"] = 1000 * (m.e2eMean_be119 - m.e2eMean_be010); show("BEsens", m)
for k, v in res.items(): v.to_csv(OUT / f"hwall_{k}.csv", index=False)
if "A" in res:
    STYLE = {"msm": dict(color="#2a78d6", marker="o", label="HiBaF-MSM (proposed)"), "ind": dict(color="#eb6834", marker="s", label="Individual verification (B1)"),
             "base": dict(color="#1baf7a", marker="^", label="HiBaF-Base, no MSM (ablation)"), "sym": dict(color="#eda100", marker="D", label="Hop-by-hop symmetric (weaker security)")}
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6,
                         "axes.edgecolor": "#8a8984", "axes.labelcolor": "#0b0b0b", "xtick.color": "#52514e", "ytick.color": "#52514e", "legend.frameon": False,
                         "savefig.dpi": 300, "lines.linewidth": 2, "lines.markersize": 5, "axes.axisbelow": True})
    sA = res["A"]; fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
    for i, (y, lab) in enumerate([("e2eMean", "Mean sensor-to-DT delay (s)"), ("pdr", "Packet delivery ratio"), ("energyPerReport_mJ", "Sensor energy per report (mJ)")]):
        for v in ["msm", "ind", "base", "sym"]:
            d = sA[sA.variant == v].sort_values("nSensors")
            if len(d): ax[i].errorbar(d.nSensors, d[y], yerr=d[y + "_ci"], capsize=2, elinewidth=1, **STYLE[v])
        ax[i].set_xlabel("IoT sensors"); ax[i].set_ylabel(lab)
    ax[0].legend(fontsize=7, loc="best"); fig.tight_layout(); fig.savefig(OUT / "fig06_scalability_hw.pdf"); fig.savefig(OUT / "fig06_scalability_hw.png", dpi=150)
print("\nruns:", len(D), D.tagx.value_counts().to_dict())
