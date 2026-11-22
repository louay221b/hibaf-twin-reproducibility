#!/usr/bin/env python3
"""Regenerate the 0.61-ms scalability, Monte Carlo and analytical figures.

Portable adaptation of make_figures_0p61.py from last script.zip, November 2026.
The original had absolute paths and an outdated 'vs B4' label.
The 0.61-ms run dataset is required and is not included with the supplied scripts.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument("--runs", type=Path, default=ROOT / "results/tables/all_runs_hwall_0p61.csv")
p.add_argument("--output", type=Path, default=ROOT / "results/figures/backend_0p61ms")
args = p.parse_args()
if not args.runs.is_file():
    p.error(f"Missing original 0.61-ms run CSV: {args.runs}")
args.output.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6,
    "axes.edgecolor": "#8a8984", "axes.labelcolor": "#0b0b0b",
    "xtick.color": "#52514e", "ytick.color": "#52514e",
    "legend.frameon": False, "savefig.dpi": 300
})
def save(fig, name):
    fig.tight_layout()
    fig.savefig(args.output / (name + ".pdf"))
    fig.savefig(args.output / (name + ".png"), dpi=150)
    plt.close(fig)

D = pd.read_csv(args.runs)
A = D[D.tag == "HW_A"]
def ci(x):
    x = np.asarray(x, float)
    n = len(x)
    return stats.t.ppf(.975, n-1) * x.std(ddof=1) / np.sqrt(n)
ST = {
 "msm": dict(color="#2a78d6", marker="o", label="HiBaF-Twin (proposed)"),
 "ind": dict(color="#eb6834", marker="s", label="Individual verification (B1)"),
 "base": dict(color="#1baf7a", marker="^", label="HiBaF-Base"),
 "sym": dict(color="#eda100", marker="D", label="Hop-by-hop symmetric")
}
fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
for i, (y, lab) in enumerate([
 ("e2eMean", "Mean sensor-to-DT delay (s)"),
 ("pdr", "Packet delivery ratio"),
 ("energyPerReport_mJ", "Sensor energy per report (mJ)")
]):
    for v in ["msm", "ind", "base", "sym"]:
        g = A[A.variant == v].groupby("nSensors")[y]
        m = g.mean()
        h = g.apply(ci)
        ax[i].errorbar(m.index, m.values, yerr=h.values,
                       capsize=2, elinewidth=1, lw=2, ms=5, **ST[v])
    ax[i].set_xlabel("IoT sensors")
    ax[i].set_ylabel(lab)
ax[0].legend(fontsize=7, loc="best")
save(fig, "fig06_scalability")

with (ROOT / "crypto_level1" / "bench_g2_127_calibration.json").open() as fh:
    cal = json.load(fh)
C1 = cal["rows"][0]["rho_indiv_total_over_hecm"]
pts = sorted((r["n"], r["rho_best_over_hecm"]) for r in cal["rows"])
_ln = np.log([a for a,b in pts]); _lc = np.log([b for a,b in pts])
def c0(k):
    if k <= 0: return 0.
    if k == 1: return C1
    return float(np.exp(np.interp(np.log(k), _ln, _lc)))
def c_msm(k):
    return c0(k) if k <= 500 else c0(500)*k/500

ST2 = {
 "hibaf": dict(color="#2a78d6", marker="o", label="HiBaF-Twin (controller)"),
 "indiv": dict(color="#eb6834", marker="s", label="Individual (B1)"),
 "base": dict(color="#1baf7a", marker="^", label="HiBaF-Base, bisection"),
 "msm_bisect": dict(color="#e87ba4", marker="v", label="MSM, bisection (no controller)")
}
mixed = pd.read_csv(ROOT / "analytic" / "mc_mixed.csv")
replay = pd.read_csv(ROOT / "analytic" / "mc_replay.csv")
fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
for i, n in enumerate([100, 500]):
    d = mixed[mixed.n == n]
    for k in ["base", "msm_bisect", "hibaf"]:
        ax[i].plot(d.mu_pct, d[k+"_mean"]/d.indiv, **ST2[k], ms=4, lw=1.6)
    ax[i].axhline(1., color=ST2["indiv"]["color"], lw=1.4, ls="--",
                  label=ST2["indiv"]["label"])
    ax[i].set_yscale("log")
    ax[i].set_xlabel("invalid-report probability (%)")
    ax[i].set_ylabel("cost / individual verification")
    ax[i].set_title(f"({'ab'[i]}) mixed validity, n = {n}", fontsize=9)
ax[1].legend(fontsize=7, loc="center right", bbox_to_anchor=(1.0, 0.62))
for n, ls in [(100, "-"), (500, ":")]:
    d = replay[replay.n == n]
    ax[2].plot(d.replay_pct, d.base_saving_pct, ls=ls,
               **{k:v for k,v in ST2["base"].items() if k!="label"},
               ms=4, lw=1.6, label=f"HiBaF-Base, n={n}")
    ax[2].plot(d.replay_pct, d.hibaf_saving_pct, ls=ls,
               **{k:v for k,v in ST2["hibaf"].items() if k!="label"},
               ms=4, lw=1.6, label=f"HiBaF-Twin, n={n}")
ax[2].set_xlabel("replay-related share (%)")
ax[2].set_ylabel("workload saving vs. B2 (%)")
ax[2].set_title("(c) replay pre-filtering", fontsize=9)
ax[2].legend(fontsize=7)
save(fig, "fig_mc")

N = 4000
TH = np.linspace(.01, 1., 100)
be_base = lambda th: 2 + 2*th*N
be_msm = lambda th: C1 + np.array([c_msm(max(1, round(t*N))) for t in np.atleast_1d(th)])
fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
for dw, col in [(5,"#2a78d6"),(30,"#1baf7a")]:
    ax[0].plot(TH, 1000*dw/be_msm(TH), color=col, lw=1.6,
               label=fr"HiBaF-Twin, $\Delta_w$={dw} s")
    ax[0].plot(TH, 1000*dw/be_base(TH), color=col, lw=1.4, ls="--",
               label=fr"HiBaF-Base, $\Delta_w$={dw} s")
ax[0].set_yscale("log"); ax[0].set_xlabel(r"audit rate $\theta$")
ax[0].set_ylabel(r"max. admissible $T_{\rm HECM}$ (ms)")
ax[0].set_title(r"(a) back end, $N_{\rm site}$=4000", fontsize=9)
ax[0].legend(fontsize=7)
K=[1,2,4,8,16]
for th,col in [(.25,"#2a78d6"),(1.,"#eb6834")]:
    ax[1].plot(K,[2+2*math.ceil(th*N/k) for k in K], color=col,
               ls="--",marker="^",ms=4,lw=1.4,label=fr"HiBaF-Base, $\theta$={th}")
    ax[1].plot(K,[C1+c_msm(math.ceil(th*N/k)) for k in K], color=col,
               marker="o",ms=4,lw=1.6,label=fr"HiBaF-Twin, $\theta$={th}")
ax[1].set_yscale("log");ax[1].set_xticks(K)
ax[1].set_xlabel(r"back-end workers $k_{\rm BE}$")
ax[1].set_ylabel("critical path (HECM)")
ax[1].set_title("(b) back-end parallel verification", fontsize=9)
ax[1].legend(fontsize=7)
P,n=200,20;KC=[1,2,5,10,20,50,100,200]
for th,col in [(.25,"#2a78d6"),(1.,"#eb6834")]:
    ax[2].plot(KC,[math.ceil(P/k)*(2*n+2)+(2*P+1)+(2+2*th*P*n)
                   for k in KC],color=col,ls="--",marker="^",ms=4,lw=1.4,
               label=fr"HiBaF-Base, $\theta$={th}")
    ax[2].plot(KC,[math.ceil(P/k)*(c_msm(n)+1)+(c_msm(P)+1)
                   +(C1+c_msm(round(th*P*n))) for k in KC],
               color=col,marker="o",ms=4,lw=1.6,
               label=fr"HiBaF-Twin, $\theta$={th}")
ax[2].set_xscale("log");ax[2].set_yscale("log")
ax[2].set_xlabel(r"concurrent collectors $k_C$")
ax[2].set_ylabel("site critical path (HECM)")
ax[2].set_title(r"(c) site, $P$=200, $n$=20", fontsize=9)
ax[2].set_ylim(60,3e4)
ax[2].legend(fontsize=6.5,loc="lower left",ncol=2)
save(fig,"fig_scal")
print(C1, be_msm(.25)[0], 1000*30/be_msm(.25)[0])
