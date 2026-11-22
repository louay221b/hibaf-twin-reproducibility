import importlib.util, numpy as np, pandas as pd
from pathlib import Path
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "results" / "generated" / "v33" / "adversarial"
spec=importlib.util.spec_from_file_location('a', HERE / 'adv_controller.py'); a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#e6e5e0", "grid.linewidth": 0.6, "axes.edgecolor": "#8a8984", "axes.labelcolor": "#0b0b0b",
                     "xtick.color": "#52514e", "ytick.color": "#52514e", "legend.frameon": False, "savefig.dpi": 300})
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#52514e"
mus = np.linspace(0, 0.4, 4001); thr = next(m for m in mus if a.controller(m) == (1, 1))
E = pd.read_csv(OUT / "series_step_ewma.csv"); O = pd.read_csv(OUT / "series_step_oracle.csv")
fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
# (a) estimate vs true rate
t = np.linspace(15, 45, 3001); ax[0].plot(t, [a.p_step(x) for x in t], color=GREY, lw=1.4, label="true invalid rate")
w = E[(E.t >= 15) & (E.t <= 45)]; ax[0].plot(w.t, w.mu_hat, color=BLUE, lw=0.9, label=r"EWMA estimate $\hat\mu$")
ax[0].axhline(thr, color=ORANGE, lw=1.2, ls="--", label=f"switch to individual ({thr:.2f})")
ax[0].set_xlabel("time (s)"); ax[0].set_ylabel("invalid-report rate"); ax[0].set_title("(a) step attack: rate estimate", fontsize=9)
ax[0].legend(fontsize=7, loc="upper left"); ax[0].set_ylim(-0.02, 0.9)
# (b) cost per report over time (0.5 s bins)
bins = np.arange(15, 45.01, 0.5)
def binned(B):
    B = B[(B.t >= 15) & (B.t < 45)]; idx = np.digitize(B.t, bins) - 1
    return np.array([B.cost[idx == i].sum() / max(1, B.m[idx == i].sum()) for i in range(len(bins) - 1)])
ctr = bins[:-1] + 0.25
ax[1].plot(ctr, binned(E), color=BLUE, lw=1.6, marker="o", ms=3, label="controller, EWMA")
ax[1].plot(ctr, binned(O), color=GREY, lw=1.2, ls=":", label="controller, true rate")
ax[1].axhline(a.C1, color=ORANGE, lw=1.4, ls="--", label="individual (B1)")
ax[1].set_xlabel("time (s)"); ax[1].set_ylabel("verification cost per report (HECM)"); ax[1].set_title("(b) step attack: cost", fontsize=9)
ax[1].legend(fontsize=7, loc="lower center"); ax[1].set_ylim(0, 2.0)
# (c) attack-window cost relative to individual
S = pd.read_csv(OUT / "adv_summary.csv"); pats = ["step", "alternating", "burst", "clustered"]
x = np.arange(len(pats)); wbar = 0.36
ew = [S[(S.pattern == p) & (S["mode"] == "ewma")].cost_win_vs_indiv.item() for p in pats]
orc = [S[(S.pattern == p) & (S["mode"] == "oracle")].cost_win_vs_indiv.item() for p in pats]
ax[2].bar(x - wbar/2, ew, wbar, color=BLUE, label="controller, EWMA"); ax[2].bar(x + wbar/2, orc, wbar, color="#a9a8a3", label="controller, true rate")
ax[2].axhline(1.0, color=ORANGE, lw=1.4, ls="--", label="individual (B1)")
ax[2].set_xticks(x); ax[2].set_xticklabels(pats, fontsize=8); ax[2].set_ylabel("cost / individual verification")
ax[2].set_title("(c) cost during the attack", fontsize=9); ax[2].legend(fontsize=7, loc="upper right"); ax[2].set_ylim(0, 1.6)
fig.tight_layout(); fig.savefig(OUT / "fig_adv.pdf"); fig.savefig(OUT / "fig_adv.png", dpi=150)
print("threshold", thr)
