"""Generate Fig. 7 of the Monte Carlo evaluation with corrected 'vs. B2' axis label.
Portable adaptation of make_fig7_mc.py from last script.zip (2026-11-20).
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analytic"
OUTPUT = ROOT / "results" / "figures"
OUTPUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size":9, "axes.spines.top":False, "axes.spines.right":False,
 "axes.grid":True, "grid.color":"#e6e5e0", "grid.linewidth":0.6,
 "axes.edgecolor":"#8a8984", "axes.labelcolor":"#0b0b0b",
 "xtick.color":"#52514e", "ytick.color":"#52514e", "legend.frameon":False,
 "savefig.dpi":300})
ST2={"hibaf":dict(color="#2a78d6",marker="o",label="HiBaF-Twin (controller)"),
 "indiv":dict(color="#eb6834",marker="s",label="Individual verification (B1)"),
 "base":dict(color="#1baf7a",marker="^",label="HiBaF-Base, bisection (no MSM)"),
 "msm_bisect":dict(color="#e87ba4",marker="v",label="MSM-bisection (no controller)")}
mixed=pd.read_csv(DATA / "mc_mixed.csv")
replay=pd.read_csv(DATA / "mc_replay.csv")
fig,ax=plt.subplots(1,3,figsize=(10,3.1))
for i,n in enumerate([100,500]):
    d=mixed[mixed.n==n]
    for k in ["base","msm_bisect","hibaf"]:
        ax[i].plot(d.mu_pct,d[k+"_mean"]/d.indiv,**ST2[k],ms=4,lw=1.6)
    ax[i].axhline(1.0,color=ST2["indiv"]["color"],lw=1.4,ls="--",label=ST2["indiv"]["label"])
    ax[i].set_yscale("log"); ax[i].set_xlabel("invalid-report probability (%)")
    ax[i].set_ylabel("cost / individual verification")
    ax[i].set_title(f"({'ab'[i]}) mixed validity, n = {n}",fontsize=9)
ax[1].legend(fontsize=7,loc="center right",bbox_to_anchor=(1.0,0.62))
for n,ls in [(100,"-"),(500,":")]:
    d=replay[replay.n==n]
    ax[2].plot(d.replay_pct,d.base_saving_pct,ls=ls,**{k:v for k,v in ST2["base"].items() if k!="label"},ms=4,lw=1.6,label=f"HiBaF-Base, n={n}")
    ax[2].plot(d.replay_pct,d.hibaf_saving_pct,ls=ls,**{k:v for k,v in ST2["hibaf"].items() if k!="label"},ms=4,lw=1.6,label=f"HiBaF-Twin, n={n}")
ax[2].set_xlabel("replay-related share (%)")
ax[2].set_ylabel("workload saving vs. B2 (%)")
ax[2].set_title("(c) replay pre-filtering",fontsize=9)
ax[2].legend(fontsize=7)
fig.tight_layout()
fig.savefig(OUTPUT / "fig_mc.pdf")
fig.savefig(OUTPUT / "fig_mc.png",dpi=150)
plt.close(fig)
