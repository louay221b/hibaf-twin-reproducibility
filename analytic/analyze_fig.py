#!/usr/bin/env python3
"""Merge ns-3 runs, compute mean / sd / 95% CI (Student t, n = runs), Welch t-tests and
Hedges' g for HiBaF-MSM vs. each baseline, and draw publication figures.
Every number in the figures and tables comes from runs/*/summary.csv."""
import glob, os, sys
import numpy as np, pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/home/claude/sim"
FIG = os.path.join(ROOT, "figures_generic"); os.makedirs(FIG, exist_ok=True)
TAB = os.path.join(ROOT, "tables")
TABOUT = os.path.join(ROOT, "tables_generic"); os.makedirs(TABOUT, exist_ok=True)

D = pd.read_csv(os.path.join(TAB, "all_runs_original_3510.csv"))   # archived campaign (figures only)
print(len(D), "runs merged")

# reference palette, fixed order (slot -> variant), plus marker shapes as secondary encoding
STYLE = {
    "msm":    dict(color="#2a78d6", marker="o", label="HiBaF-MSM (proposed)"),
    "ind":    dict(color="#eb6834", marker="s", label="Individual verification (B1)"),
    "base":   dict(color="#1baf7a", marker="^", label="HiBaF-Base, no MSM (ablation)"),
    "sym":    dict(color="#eda100", marker="D", label="Hop-by-hop symmetric (weaker security)"),
    "msmfix": dict(color="#e87ba4", marker="v", label="MSM + bisection, no controller (ablation)"),
}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6,
                     "axes.edgecolor": "#8a8984", "axes.labelcolor": "#0b0b0b", "xtick.color": "#52514e",
                     "ytick.color": "#52514e", "legend.frameon": False, "savefig.dpi": 300,
                     "lines.linewidth": 2, "lines.markersize": 5, "axes.axisbelow": True})

def ci(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x)
    if n < 2: return (np.nan, np.nan, np.nan, n)
    m, s = x.mean(), x.std(ddof=1); h = stats.t.ppf(0.975, n-1)*s/np.sqrt(n)
    return m, s, h, n

def summarize(df, keys, metrics):
    rows = []
    for k, g in df.groupby(keys):
        r = dict(zip(keys, k if isinstance(k, tuple) else (k,)))
        for mtr in metrics:
            m, s, h, n = ci(g[mtr]); r[mtr+"_mean"] = m; r[mtr+"_sd"] = s; r[mtr+"_ci95"] = h; r["n"] = n
        rows.append(r)
    return pd.DataFrame(rows)

def compare(df, keys, metric, ref="msm"):
    """Welch t-test + Hedges g + % change of each variant vs. ref, per configuration."""
    out = []
    for k, g in df.groupby(keys):
        a = g[g.variant == ref][metric].dropna()
        for v in sorted(set(g.variant) - {ref}):
            b = g[g.variant == v][metric].dropna()
            if len(a) < 2 or len(b) < 2: continue
            t, p = stats.ttest_ind(a, b, equal_var=False)
            sp = np.sqrt(((len(a)-1)*a.var(ddof=1) + (len(b)-1)*b.var(ddof=1)) / (len(a)+len(b)-2))
            gH = (a.mean()-b.mean())/sp*(1-3/(4*(len(a)+len(b))-9)) if sp > 0 else np.nan
            out.append(dict(zip(keys, k if isinstance(k, tuple) else (k,)), metric=metric, vs=v,
                            ref_mean=a.mean(), other_mean=b.mean(),
                            pct_change=100*(a.mean()-b.mean())/b.mean() if b.mean() else np.nan,
                            welch_t=t, p_value=p, hedges_g=gH, n_ref=len(a), n_other=len(b)))
    return pd.DataFrame(out)

M = ["pdr", "syncSuccess", "deadlineMiss", "e2eMean", "e2eP95", "e2eP99", "jitter", "authMean", "authP95",
     "throughputRps", "goodputBps", "sensorFramesPerReport", "sensorBytesPerReport", "airtimePerPond",
     "lanBytesPerRep", "wanBytesPerRep", "energyPerReport_mJ", "energyTx_mJ", "energyRx_mJ", "energyCpu_mJ",
     "colCpuUtil", "colCpuUtilMax", "meanBatch", "hecmPerVerified", "stHecmPerRep", "beHecmPerRep",
     "sigDrop", "macDrop", "quotaDrop", "negDrop", "revokedDrop", "attackCommitted", "revPropagation",
     "detectToMitigate", "windowMissFrac", "macTxDrop"]

def line(ax, s, x, y, variants, xlog=False, ylog=False):
    for v in variants:
        d = s[s.variant == v].sort_values(x)
        if d.empty: continue
        st = STYLE[v]
        ax.errorbar(d[x], d[y+"_mean"], yerr=d[y+"_ci95"], color=st["color"], marker=st["marker"],
                    label=st["label"], capsize=2, elinewidth=1)
    if xlog: ax.set_xscale("log")
    if ylog: ax.set_yscale("log")

def save(fig, name):
    fig.tight_layout(); fig.savefig(os.path.join(FIG, name+".png")); fig.savefig(os.path.join(FIG, name+".pdf")); plt.close(fig)

TAG = D.tag.astype(str)
allcmp = []

# ---------------- A: scalability
A = D[TAG == "A"]
if len(A):
    sA = summarize(A, ["variant", "nSensors"], M); sA.to_csv(f"{TABOUT}/A_scalability.csv", index=False)
    allcmp.append(compare(A, ["nSensors"], "e2eMean")); allcmp.append(compare(A, ["nSensors"], "energyPerReport_mJ"))
    allcmp.append(compare(A, ["nSensors"], "hecmPerVerified"))
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
    V = ["msm", "ind", "base", "sym"]
    line(ax[0], sA, "nSensors", "e2eMean", V); ax[0].set_xlabel("IoT sensors"); ax[0].set_ylabel("Mean sensor-to-DT delay (s)")
    line(ax[1], sA, "nSensors", "pdr", V); ax[1].set_xlabel("IoT sensors"); ax[1].set_ylabel("Packet delivery ratio")
    line(ax[2], sA, "nSensors", "energyPerReport_mJ", V); ax[2].set_xlabel("IoT sensors"); ax[2].set_ylabel("Sensor energy per report (mJ)")
    ax[0].legend(fontsize=7, loc="upper left"); save(fig, "fig06_scalability")

# ---------------- A2: load
A2 = D[TAG == "A2"]
if len(A2):
    A2 = A2.assign(offered=A2.nSensors / A2.reportInterval)
    s = summarize(A2, ["variant", "offered"], M); s.to_csv(f"{TABOUT}/A2_load.csv", index=False)
    for mtr in ["pdr", "e2eP95", "throughputRps", "colCpuUtil"]:
        allcmp.append(compare(A2, ["offered"], mtr))
    V = ["msm", "ind", "base", "sym"]
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 3.1))
    line(ax[0], s, "offered", "pdr", V, xlog=True); ax[0].set_xlabel("Offered load (reports/s, 100 sensors)"); ax[0].set_ylabel("Packet delivery ratio")
    line(ax[1], s, "offered", "e2eP95", V, xlog=True); ax[1].set_xlabel("Offered load (reports/s)"); ax[1].set_ylabel("95th-pct. sensor-to-DT delay (s)")
    ax[0].legend(fontsize=7, loc="lower left"); save(fig, "fig07_pdr_load")
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
    line(ax[0], s, "offered", "throughputRps", V, xlog=True, ylog=True); ax[0].set_xlabel("Offered load (reports/s)"); ax[0].set_ylabel("Throughput at DT (reports/s)")
    line(ax[1], s, "offered", "goodputBps", V, xlog=True, ylog=True); ax[1].set_xlabel("Offered load (reports/s)"); ax[1].set_ylabel("Goodput (measurement bytes/s)")
    line(ax[2], s, "offered", "airtimePerPond", V, xlog=True); ax[2].set_xlabel("Offered load (reports/s)"); ax[2].set_ylabel("802.15.4 airtime per collector area (sensor TX)")
    ax[0].legend(fontsize=7, loc="upper left"); save(fig, "fig08_throughput_load")

# ---------------- B + C: degradation and DT synchronisation
B1 = D[TAG == "B1"]; B2 = D[TAG == "B2"]; Cc = D[TAG == "C"]
if len(B1) and len(B2) and len(Cc):
    s1 = summarize(B1, ["variant", "radius"], M); s1.to_csv(f"{TABOUT}/B1_radius.csv", index=False)
    s2 = summarize(B2, ["variant", "wanLoss"], M); s2.to_csv(f"{TABOUT}/B2_wanloss.csv", index=False)
    sc = summarize(Cc, ["variant", "wanDelayMs", "wanRate"], M); sc.to_csv(f"{TABOUT}/C_dtsync.csv", index=False)
    allcmp.append(compare(Cc, ["wanDelayMs", "wanRate"], "e2eMean")); allcmp.append(compare(B1, ["radius"], "pdr"))
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
    line(ax[0], s1, "radius", "pdr", ["msm", "ind"]); ax[0].set_xlabel("Collector-area radius (m), natural PHY loss"); ax[0].set_ylabel("Packet delivery ratio")
    line(ax[1], s2, "wanLoss", "e2eP95", ["msm", "ind"]); ax[1].set_xlabel("WAN packet error rate"); ax[1].set_ylabel("95th-pct. sensor-to-DT delay (s)")
    for rate, ls in [("10Mbps", "-"), ("128kbps", "--")]:
        d = sc[(sc.wanRate == rate)]
        for v in ["msm", "ind"]:
            dd = d[d.variant == v].sort_values("wanDelayMs"); st = STYLE[v]
            ax[2].errorbar(dd.wanDelayMs, dd.e2eMean_mean, yerr=dd.e2eMean_ci95, color=st["color"], marker=st["marker"],
                           linestyle=ls, capsize=2, label=f"{st['label'].split(' (')[0]}, WAN {rate}")
    ax[2].set_xlabel("WAN one-way delay (ms)"); ax[2].set_ylabel("Mean sensor-to-DT delay (s)")
    ax[0].legend(fontsize=7, loc="lower left"); ax[2].legend(fontsize=6, loc="upper left"); save(fig, "fig09_degradation_dtsync")

# ---------------- D: security events
Dd = D[TAG == "D"]
if len(Dd):
    sd = summarize(Dd, ["variant", "attackers", "defenses"], M); sd.to_csv(f"{TABOUT}/D_security.csv", index=False)
    allcmp.append(compare(Dd, ["attackers", "defenses"], "colCpuUtil"))

# ---------------- E: MSM ablation under invalid-report stress
E = D[TAG == "E"]
if len(E):
    se = summarize(E, ["variant", "attackers"], M); se.to_csv(f"{TABOUT}/E_msm_ablation.csv", index=False)
    for mtr in ["hecmPerVerified", "colCpuUtil", "e2eP95", "syncSuccess", "energyPerReport_mJ"]:
        allcmp.append(compare(E, ["attackers"], mtr))
    V = ["msm", "msmfix", "base", "ind"]
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
    line(ax[0], se, "attackers", "hecmPerVerified", V); ax[0].set_xlabel("Compromised sensors (of 100), 2 invalid reports/s each"); ax[0].set_ylabel("Collector verification cost\n(HECM-equiv. per accepted report)")
    line(ax[1], se, "attackers", "colCpuUtil", V); ax[1].set_xlabel("Compromised sensors"); ax[1].set_ylabel("Collector CPU utilisation")
    line(ax[2], se, "attackers", "e2eP95", V, ylog=True); ax[2].set_xlabel("Compromised sensors"); ax[2].set_ylabel("95th-pct. sensor-to-DT delay (s)")
    ax[0].legend(fontsize=7, loc="upper left"); save(fig, "fig11_msm_ablation")

# ---------------- F: constrained
F = D[TAG.str.startswith("F_")]
if len(F):
    sf = summarize(F, ["tag", "variant"], M); sf.to_csv(f"{TABOUT}/F_constrained.csv", index=False)
    allcmp.append(compare(F, ["tag"], "syncSuccess"))

# ---------------- fig10: overhead comparison (scenario A, N=100)
if len(A):
    d = summarize(A[A.nSensors == 100], ["variant"], M)
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.1))
    order = ["msm", "ind", "base", "sym"]; d = d.set_index("variant").loc[[v for v in order if v in set(d.variant)]]
    for i, (mtr, lab) in enumerate([("sensorBytesPerReport", "802.15.4 bytes per report (incl. PHY/MAC, frags)"),
                                    ("hecmPerVerified", "Collector HECM-equiv. per report"),
                                    ("energyPerReport_mJ", "Sensor energy per report (mJ)")]):
        ax[i].bar(range(len(d)), d[mtr+"_mean"], yerr=d[mtr+"_ci95"], color=[STYLE[v]["color"] for v in d.index],
                  width=0.6, edgecolor="white", linewidth=2, capsize=2)
        ax[i].set_xticks(range(len(d))); ax[i].set_xticklabels(["MSM", "B1 ind.", "Base", "Sym."], fontsize=8)
        ax[i].set_ylabel(lab, fontsize=8); ax[i].grid(axis="x", visible=False)
        for j, val in enumerate(d[mtr+"_mean"]): ax[i].text(j, val, f"{val:.2f}", ha="center", va="bottom", fontsize=7, color="#52514e")
    save(fig, "fig10_overhead")

# ---------------- fig12: security-performance trade-off (scenario E + D)
if len(E) and len(Dd):
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 3.1))
    se2 = summarize(E, ["variant", "attackers"], M)
    for v in ["msm", "msmfix", "base", "ind"]:
        dd = se2[se2.variant == v].sort_values("attackers"); st = STYLE[v]
        ax[0].plot(dd.colCpuUtil_mean, dd.syncSuccess_mean, color=st["color"], marker=st["marker"], label=st["label"])
    ax[0].set_xlabel("Collector CPU utilisation (stress, 0-10 attackers)"); ax[0].set_ylabel("DT sync success (<= 2 s)")
    ax[0].legend(fontsize=6, loc="lower left")
    sdd = summarize(Dd[Dd.variant == "msm"], ["attackers", "defenses"], M)
    w = 0.38
    for j, (dfn, lab, col) in enumerate([(1, "defenses on", "#2a78d6"), (0, "defenses off", "#eb6834")]):
        x = sdd[sdd.defenses == dfn].sort_values("attackers")
        ax[1].bar(np.arange(len(x)) + (j-0.5)*w, x.sigDrop_mean, yerr=x.sigDrop_ci95, width=w, color=col, label=lab,
                  edgecolor="white", linewidth=2, capsize=2)
    for j, dfn in enumerate([1, 0]):
        x = sdd[sdd.defenses == dfn].sort_values("attackers")
        for k, val in enumerate(x.sigDrop_mean):
            ax[1].text(k + (j-0.5)*w, val*1.15, f"{val:.0f}", ha="center", va="bottom", fontsize=7, color="#52514e")
    ax[1].set_yscale("log"); ax[1].set_ylim(0.5, 5000)
    ax[1].set_xticks(range(3)); ax[1].set_xticklabels(["1", "4", "10"]); ax[1].set_xlabel("Insider attackers (0.5 invalid rep/s each)")
    ax[1].set_ylabel("Invalid reports reaching signature check\n(per run, log scale)"); ax[1].legend(fontsize=7)
    save(fig, "fig12_tradeoff")

C_all = pd.concat([c for c in allcmp if len(c)], ignore_index=True) if allcmp else pd.DataFrame()
C_all.to_csv(f"{TABOUT}/significance.csv", index=False)
print("figures:", sorted(os.listdir(FIG)))
