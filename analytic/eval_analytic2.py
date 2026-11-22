#!/usr/bin/env python3
"""Figures/tables for the analytical evaluation: Monte Carlo (from eval_analytic.py CSVs), scalability, energy."""
import json, math, os
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import importlib.util
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ea", ROOT / "analytic" / "eval_analytic.py")
ea = importlib.util.module_from_spec(spec); spec.loader.exec_module(ea)
OUT = ea.OUT; C1 = ea.C1
def c_msm(k):
    """MSM batch cost (HECM) over k reports; beyond the largest measured batch (500) extrapolated linearly
       per report (conservative: Pippenger's per-report cost keeps falling)."""
    if k <= 500: return ea.c_msm(k)
    return ea.c_msm(500) * k / 500
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#e6e5e0", "grid.linewidth": 0.6, "axes.edgecolor": "#8a8984", "axes.labelcolor": "#0b0b0b",
                     "xtick.color": "#52514e", "ytick.color": "#52514e", "legend.frameon": False, "savefig.dpi": 300})
ST = {"hibaf": dict(color="#2a78d6", marker="o", label="HiBaF-MSM (controller)"),
      "indiv": dict(color="#eb6834", marker="s", label="Individual (B1)"),
      "base": dict(color="#1baf7a", marker="^", label="Base, bisection (no MSM)"),
      "msm_bisect": dict(color="#e87ba4", marker="v", label="MSM, bisection (no controller)")}
mixed = pd.read_csv(f"{OUT}/mc_mixed.csv"); replay = pd.read_csv(f"{OUT}/mc_replay.csv")

# ---------- Fig: Monte Carlo
fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
for i, n in enumerate([100, 500]):
    d = mixed[mixed.n == n]
    for k in ["base", "msm_bisect", "hibaf"]:
        ax[i].plot(d.mu_pct, d[k + "_mean"] / d.indiv, **{kk: v for kk, v in ST[k].items()}, ms=4, lw=1.6)
    ax[i].axhline(1.0, color=ST["indiv"]["color"], lw=1.4, ls="--", label=ST["indiv"]["label"])
    ax[i].set_yscale("log"); ax[i].set_xlabel("invalid-report probability (%)"); ax[i].set_ylabel("cost / individual verification")
    ax[i].set_title(f"({'ab'[i]}) mixed validity, n = {n}", fontsize=9)
ax[1].legend(fontsize=7, loc="center right", bbox_to_anchor=(1.0, 0.62))
for n, ls in [(100, "-"), (500, ":")]:
    d = replay[replay.n == n]
    ax[2].plot(d.replay_pct, d.base_saving_pct, ls=ls, **{kk: v for kk, v in ST["base"].items() if kk != "label"}, ms=4, lw=1.6, label=f"Base, n={n}")
    ax[2].plot(d.replay_pct, d.hibaf_saving_pct, ls=ls, **{kk: v for kk, v in ST["hibaf"].items() if kk != "label"}, ms=4, lw=1.6, label=f"HiBaF-MSM, n={n}")
ax[2].set_xlabel("replay-related share (%)"); ax[2].set_ylabel("workload saving vs. B4 (%)"); ax[2].set_title("(c) replay pre-filtering", fontsize=9)
ax[2].legend(fontsize=7)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_mc.pdf"); fig.savefig(f"{OUT}/fig_mc.png"); plt.close(fig)

# ---------- Scalability (draft Eqs. 22-33, with the MSM realization)
N = 4000; THETA = np.linspace(0.01, 1.0, 100)
def be_base(th): return 2 + 2 * th * N
def be_msm(th): return C1 + np.array([c_msm(max(1, round(t * N))) for t in np.atleast_1d(th)])
fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
for dw, col in [(5, "#2a78d6"), (30, "#1baf7a")]:
    ax[0].plot(THETA, 1000 * dw / be_msm(THETA), color=col, lw=1.6, label=fr"MSM, $\Delta_w$={dw} s")
    ax[0].plot(THETA, 1000 * dw / be_base(THETA), color=col, lw=1.4, ls="--", label=fr"Base, $\Delta_w$={dw} s")
ax[0].set_yscale("log"); ax[0].set_xlabel(r"audit rate $\theta$"); ax[0].set_ylabel(r"max. admissible $T_{\rm HECM}$ (ms)")
ax[0].set_title(r"(a) back end, $N_{\rm site}$=4000", fontsize=9); ax[0].legend(fontsize=7)
K = [1, 2, 4, 8, 16]
for th, col in [(0.25, "#2a78d6"), (1.0, "#eb6834")]:
    ax[1].plot(K, [2 + 2 * math.ceil(th * N / k) for k in K], color=col, ls="--", marker="^", ms=4, lw=1.4, label=fr"Base, $\theta$={th}")
    ax[1].plot(K, [C1 + c_msm(math.ceil(th * N / k)) for k in K], color=col, marker="o", ms=4, lw=1.6, label=fr"MSM, $\theta$={th}")
ax[1].set_yscale("log"); ax[1].set_xticks(K); ax[1].set_xlabel(r"back-end workers $k_{\rm BE}$"); ax[1].set_ylabel("critical path (HECM)")
ax[1].set_title("(b) back-end parallel verification", fontsize=9); ax[1].legend(fontsize=7)
P, n = 200, 20; KC = [1, 2, 5, 10, 20, 50, 100, 200]
for th, col in [(0.25, "#2a78d6"), (1.0, "#eb6834")]:
    ax[2].plot(KC, [math.ceil(P / k) * (2 * n + 2) + (2 * P + 1) + (2 + 2 * th * P * n) for k in KC], color=col, ls="--", marker="^", ms=4, lw=1.4, label=fr"Base, $\theta$={th}")
    ax[2].plot(KC, [math.ceil(P / k) * (c_msm(n) + 1) + (c_msm(P) + 1) + (C1 + c_msm(round(th * P * n))) for k in KC], color=col, marker="o", ms=4, lw=1.6, label=fr"MSM, $\theta$={th}")
ax[2].set_xscale("log"); ax[2].set_yscale("log"); ax[2].set_xlabel(r"concurrent collectors $k_C$"); ax[2].set_ylabel("site critical path (HECM)")
ax[2].set_title(r"(c) site, $P$=200, $n$=20", fontsize=9); ax[2].set_ylim(60, 3e4); ax[2].legend(fontsize=6.5, loc="lower left", ncol=2)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_scal.pdf"); fig.savefig(f"{OUT}/fig_scal.png"); plt.close(fig)
scal = dict(N=N, theta025_dw30_base=1000*30/be_base(0.25), theta025_dw30_msm=float(1000*30/be_msm(0.25)[0]),
            theta1_dw30_base=1000*30/be_base(1.0), theta1_dw30_msm=float(1000*30/be_msm(1.0)[0]),
            theta1_dw5_base=1000*5/be_base(1.0), theta1_dw5_msm=float(1000*5/be_msm(1.0)[0]),
            be_theta1_k1_base=2+2*N, be_theta1_k1_msm=C1+c_msm(N), be_theta1_k16_base=2+2*math.ceil(N/16), be_theta1_k16_msm=C1+c_msm(math.ceil(N/16)))
json.dump(scal, open(f"{OUT}/scalability.json", "w"), indent=1); print(json.dumps(scal, indent=1))

# ---------- Energy (draft Section VI-F: E = P_active * T)
with (ROOT / "platform" / "platform_estimates.json").open(encoding="utf-8") as fh:
    plat = json.load(fh)["rows"]
P_ESP, P_PI = 0.264, 3.4                       # W (draft: 3.3 V x 80 mA; Raspberry Pi 4 active)
T_BLAKE, T_AES = 0.0174, 0.075                  # ms (draft ESP32 values)
esp_ratio_indiv = plat["indiv"]["esp32_insns"] / plat["hecm"]["esp32_insns"]
COST = {"earlier": dict(esp=28.62, pi=4.20), "emu_low": dict(esp=plat["hecm"]["esp32_ms_240MHz_cpi1"], pi=plat["hecm"]["a72_ms_1500MHz_low"]),
        "emu_high": dict(esp=plat["hecm"]["esp32_ms_240MHz_cpi15"], pi=plat["hecm"]["a72_ms_1500MHz_high"])}
rows = []
for k, v in COST.items():
    t_rep = v["esp"] + 2 * T_BLAKE + T_AES
    e_rep = P_ESP * t_rep                        # mJ
    e_win = P_ESP * (2 * esp_ratio_indiv * v["esp"] + T_BLAKE)   # beacon + RL (two 2-term MSMs) + ratchet hash, per window
    r = dict(cost=k, T_esp_ms=v["esp"], T_pi_ms=v["pi"], E_report_mJ=e_rep, E_window_sensor_mJ=e_win)
    for nn in [10, 50, 100, 500]:
        r[f"E_ind_{nn}_J"] = P_PI * nn * C1 * v["pi"] / 1000
        r[f"E_base_{nn}_J"] = P_PI * ((2 * nn + 1) + (2 * nn - 1) * 0.0043) * v["pi"] / 1000
        r[f"E_msm_{nn}_J"] = P_PI * c_msm(nn) * v["pi"] / 1000
    d = replay[replay.n == 100]
    for rs in [0, 50]:
        dd = d[d.replay_pct == rs].iloc[0]
        r[f"E_replay{rs}_base_b4_J"] = P_PI * dd.base_b4 * v["pi"] / 1000; r[f"E_replay{rs}_base_f_J"] = P_PI * dd.base_f * v["pi"] / 1000
        r[f"E_replay{rs}_hib_b4_J"] = P_PI * dd.hib_b4 * v["pi"] / 1000; r[f"E_replay{rs}_hib_f_J"] = P_PI * dd.hib_f * v["pi"] / 1000
    rows.append(r)
energy = pd.DataFrame(rows); energy.to_csv(f"{OUT}/energy.csv", index=False)
pd.set_option("display.width", 250); print(energy.T.round(4).to_string())
