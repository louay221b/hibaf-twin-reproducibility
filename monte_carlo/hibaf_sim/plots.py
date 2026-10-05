"""Six figures, each saved as PNG and PDF. Axis labels state the cost model used."""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .costs import HECM_ONLY

NOTE = "Taji-Ghanimi reference-platform HECM-only lower-bound scenario (not a 128-bit HiBaF-Twin latency)"


def _save(fig, outdir, name):
    os.makedirs(outdir, exist_ok=True)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, name + ".png"), dpi=200)
    fig.savefig(os.path.join(outdir, name + ".pdf"))
    plt.close(fig)


def _sets(df):
    d = df[df.cost_model == HECM_ONLY]
    return list(d.param_set.unique()) if not d.empty else []


def fig1_pond_latency(res, outdir, skip):
    df = res["a1_pond"]
    sets = _sets(df)
    if not sets:
        skip.add("plots", "fig1_pond_latency", HECM_ONLY, "all", ["no computable rows"]); return
    fig, ax = plt.subplots(figsize=(6, 4))
    for ps in sets:
        d = df[(df.cost_model == HECM_ONLY) & (df.param_set == ps)]
        d = d.drop_duplicates(subset=["n", "variant"])
        for variant, ls in (("individual", "-o"), ("batch_verification_only_all_valid", "--s")):
            x = d[d.variant == variant].sort_values("n")
            ax.plot(x.n, x.projection_ms, ls, label=f"{variant} ({ps})")
    ax.set_xlabel("Reports per pond n"); ax.set_ylabel("Scenario projection (ms); count = 2n or 2n+1 HECM")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.grid(alpha=.3, which="both")
    ax.set_title("Pond verification: scenario projection vs n\n" + NOTE, fontsize=7); ax.legend(fontsize=7)
    _save(fig, outdir, "fig1_pond_latency_vs_reports")


def fig2_dt_latency(res, cfg, outdir, skip):
    df = res["d_dt"]; sets = _sets(df)
    if not sets:
        skip.add("plots", "fig2_dt_latency", HECM_ONLY, "all", ["no computable rows"]); return
    fig, ax = plt.subplots(figsize=(6, 4))
    for ps in sets:
        d = df[(df.cost_model == HECM_ONLY) & (df.param_set == ps)].drop_duplicates("N_site").sort_values("N_site")
        ax.plot(d.N_site, d.dt_projection_ms / 1000, "-o", label=f"DT, {ps}")
        for r in d.itertuples():
            ax.annotate(f"{int(r.n_hecm):,} HECM", (r.N_site, r.dt_projection_ms / 1000), fontsize=6, xytext=(3, -9), textcoords="offset points")
    for dw in cfg["delta_w_s"]:
        ax.axhline(dw, ls=":", color="gray"); ax.text(df.N_site.min(), dw * 1.05, f"$\\Delta_w$={dw}s", fontsize=7)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("$N_{site}$ (reports per site container)"); ax.set_ylabel("DT scenario projection (s)")
    ax.grid(alpha=.3, which="both"); ax.legend(fontsize=7)
    ax.set_title("DT scenario projection vs $N_{site}$\n" + NOTE, fontsize=7)
    _save(fig, outdir, "fig2_dt_latency_vs_nsite")


def fig3_window_pct(res, cfg, outdir, skip):
    df = res["a2_site"]; sets = _sets(df)
    if not sets:
        skip.add("plots", "fig3_window_pct", HECM_ONLY, "all", ["no computable rows"]); return
    ps = sets[0]
    d = df[(df.cost_model == HECM_ONLY) & (df.param_set == ps)]
    cfgs = d[["P", "n_per_pond"]].drop_duplicates().values.tolist()
    fig, axs = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    dws = cfg["delta_w_s"]; wd = 0.8 / len(dws)
    for ax, col, ttl in ((axs[0], "pct_aggregate_sequential_work", "Aggregate sequential work"),
                         (axs[1], "pct_parallel_critical_path", "Parallel-collector critical-path projection")):
        for i, dw in enumerate(dws):
            vals = [d[(d.P == P) & (d.n_per_pond == n) & (d.delta_w_s == dw)][col].iloc[0] for P, n in cfgs]
            ax.bar(np.arange(len(cfgs)) + i * wd, vals, wd, label=f"$\\Delta_w$={dw}s")
        ax.axhline(100, color="r", ls="--"); ax.set_yscale("log")
        ax.set_xticks(np.arange(len(cfgs)) + 0.4 - wd / 2)
        ax.set_xticklabels([f"{P}x{n}" for P, n in cfgs], fontsize=8)
        ax.set_xlabel("Site configuration (ponds x sensors/pond)"); ax.set_title(ttl, fontsize=9)
    axs[0].set_ylabel("% of reporting window (scenario projection)"); axs[0].legend(fontsize=7)
    fig.suptitle("Window consumption: " + NOTE, fontsize=8)
    _save(fig, outdir, "fig3_window_consumed_pct")


def fig4_mixed(res, outdir, skip):
    s = res["b_summary"]; s = s[s.cost_model == "counts_only"]
    ns = sorted(s.n.unique()); fig, axs = plt.subplots(1, len(ns), figsize=(3.2 * len(ns), 3.8), sharey=False)
    for ax, n in zip(np.atleast_1d(axs), ns):
        for strat, st in (("A_full_individual_fallback", "-o"), ("B_recursive_divide_conquer", "--s")):
            d = s[(s.n == n) & (s.strategy == strat)].sort_values("mu_pct")
            ax.plot(d.mu_pct, d.overhead_pct_vs_individual, st, label=strat.split("_")[0] + " (" + ("current" if strat[0] == "A" else "enhanced variant") + ")")
        ax.axhline(0, color="gray", lw=.8); ax.set_title(f"n={n}", fontsize=9)
        ax.set_xlabel("Invalid reports $\\mu$ (%)"); ax.grid(alpha=.3)
    np.atleast_1d(axs)[0].set_ylabel("Overhead vs individual (% of HEC scalar mults)")
    np.atleast_1d(axs)[0].legend(fontsize=7)
    fig.suptitle("Mixed-validity overhead (Monte Carlo result)", fontsize=9)
    _save(fig, outdir, "fig4_mixed_validity_overhead")


def fig5_replay(res, outdir, skip):
    s = res["c_summary"]; c = s[s.cost_model == "counts_only"]
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    for n in sorted(c.n.unique()):
        d = c[c.n == n].sort_values("replay_pct")
        axs[0].plot(d.replay_pct, d.hecm_avoided_pct_of_baseline, "-o", label=f"n={n}")
    axs[0].set_xlabel("Replay share of submitted reports (%)"); axs[0].set_ylabel("HEC scalar mults avoided (% of no-filter baseline)")
    axs[0].legend(fontsize=7); axs[0].grid(alpha=.3); axs[0].set_title("HEC operations avoided", fontsize=9)
    sets = _sets(s); nref = 100 if 100 in c.n.values else int(c.n.max())
    if sets:
        for ps in sets:
            d = s[(s.param_set == ps) & (s.cost_model == HECM_ONLY) & (s.n == nref)].sort_values("replay_pct")
            axs[1].plot(d.replay_pct, d.baseline_projection_mean_ms, "--s", label=f"no filtering ({ps})")
            axs[1].plot(d.replay_pct, d.filtered_projection_mean_ms, "-o", label=f"early filtering ({ps})")
        axs[1].set_xlabel("Replay share (%)"); axs[1].set_ylabel(f"Mean scenario projection (ms), n={nref}")
        axs[1].legend(fontsize=7); axs[1].grid(alpha=.3); axs[1].set_title("Verification delay projection\n" + NOTE, fontsize=6)
    fig.suptitle("Replay early-rejection savings (Monte Carlo result)", fontsize=9)
    _save(fig, outdir, "fig5_replay_savings")


def fig6_sensitivity(res, cfg, psets, outdir, skip):
    thr = res["e_thresholds"]; comp = res["e_comparison"]
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    for ax, q, xl in ((axs[0], "dt", "$N_{site}$"), (axs[1], "pond_batch", "n (reports per pond)")):
        for dw in cfg["delta_w_s"]:
            d = thr[(thr.quantity == q) & (thr.delta_w_s == dw)].sort_values("size_num")
            ax.plot(d.size_num, d.max_T_HECM_ms, "-o", ms=3, label=f"$\\Delta_w$={dw}s")
        for ps in psets:
            v = ps.timings.get("T_HECM_ms")
            if v is not None:
                ax.axhline(v, ls="--", color="k", lw=1)
        ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel(xl)
        ax.set_ylabel("Max tolerable $T_{HECM}$ (ms) for sequential fit"); ax.grid(alpha=.3, which="both")
    axs[0].legend(fontsize=7); axs[0].set_title("DT (HECM-only lower bound)", fontsize=9); axs[1].set_title("Pond batch (HECM-only lower bound)", fontsize=9)
    fig.suptitle("Sensitivity: analytical tolerance thresholds vs available literature parameter sets", fontsize=9)
    _save(fig, outdir, "fig6_sensitivity_parameter_sets")


def make_all(res, cfg, psets, outdir, skip):
    fig1_pond_latency(res, outdir, skip)
    fig2_dt_latency(res, cfg, outdir, skip)
    fig3_window_pct(res, cfg, outdir, skip)
    fig4_mixed(res, outdir, skip)
    fig5_replay(res, outdir, skip)
    fig6_sensitivity(res, cfg, psets, outdir, skip)
