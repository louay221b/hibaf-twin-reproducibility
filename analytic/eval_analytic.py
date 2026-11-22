#!/usr/bin/env python3
"""Analytical and Monte Carlo evaluation (draft Sections VI-B..VI-F, updated to the current protocol).
 - Mixed-validity batches: individual (B1), Base + recursive bisection (draft model), MSM + bisection,
   HiBaF-MSM with the adaptive controller (Dorfman group testing, Algorithm 3).
 - Replay filtering vs. B4 (no pre-filtering) for Base and HiBaF-MSM.
 - Scalability (back-end admissible HECM time, parallel workers, site critical path) with and without MSM.
 - Computational energy per report / per window with the platform cost sets.
Costs are in HECM units from the measured ratio curve (audit/bench_g2_127_calibration.json).
Seed 20260603 and 10 000 windows per configuration, as in the draft."""
import json, math, os
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analytic"
OUT.mkdir(parents=True, exist_ok=True)
SEED, NW = 20260603, 10_000
BATCH = [10, 50, 100, 500]; MU = [0.0, 0.01, 0.05, 0.10, 0.25]; REPLAY = [0.0, 0.10, 0.25, 0.50]
with (ROOT / "crypto_level1" / "bench_g2_127_calibration.json").open(encoding="utf-8") as fh:
    cal = json.load(fh)
C1 = cal["rows"][0]["rho_indiv_total_over_hecm"]            # 2-term Straus individual verification (1.152)
pts = sorted((r["n"], r["rho_best_over_hecm"]) for r in cal["rows"])
_ln = np.log([p[0] for p in pts]); _lc = np.log([p[1] for p in pts])
def c_msm(k):
    """cost (HECM) of one MSM batch test over k reports (2k+1 terms); k=1 -> individual"""
    if k <= 0: return 0.0
    if k == 1: return C1
    return float(np.exp(np.interp(np.log(k), _ln, _lc)))      # log-log interpolation of measured points
def c_base(k): return 2*k + 1 if k > 1 else 2.0              # draft Base model: 2k+1 HECM per test, 2 per singleton

# ---------------- isolation strategies (exact cost of one window given the validity vector)
def bisect(inv, cost):
    n = len(inv); pre = np.concatenate([[0], np.cumsum(inv)])
    def rec(l, r):
        m = r - l
        if m == 1: return cost(1)
        c = cost(m)
        if pre[r] - pre[l] == 0: return c
        mid = l + m // 2
        return c + rec(l, mid) + rec(mid, r)
    return rec(0, n) if n else 0.0
GAMMA = 1000.0 / 4.20                                         # budget: 1 s at 4.2 ms/HECM (as in ns-3)
def p_any(mu, k): return 1 - (1 - mu)**k
def exp_cost(b, g, mu):
    if g == 1: return c_msm(b) + p_any(mu, b) * b * C1
    k = b / g
    return c_msm(b) + p_any(mu, b) * g * c_msm(k) + g * p_any(mu, k) * k * C1
def worst(b, g): return c_msm(b) + (g * c_msm(b / g) if g > 1 else 0) + b * C1
def controller(mu):
    best = (1, 1, C1)
    for b in (2, 4, 8, 16, 32, 64, 128, 256):          # as Algorithm 3 and the ns-3 controller (40 candidates)
        for g in (1, 2, 4, 8, 16):
            if g > b or worst(b, g) > GAMMA: continue
            e = exp_cost(b, g, mu) / b
            if e < best[2]: best = (b, g, e)
    return best[:2]
def group_test(inv, g):
    n = len(inv)
    if n == 1: return C1
    c = c_msm(n)
    if inv.sum() == 0: return c
    if g == 1: return c + n * C1
    for j in range(g):
        grp = inv[j::g]
        if len(grp) == 0: continue
        c += c_msm(len(grp))
        if grp.sum(): c += len(grp) * C1
    return c
def hibaf_window(inv, b, g):
    tot = 0.0
    for s in range(0, len(inv), b):
        chunk = inv[s:s+b]; tot += group_test(chunk, min(g, len(chunk)))
    return tot

CTRL = {mu: controller(mu) for mu in MU + [0.0125, 0.025, 0.05/0.95*0.05]}
def run_mixed():
    rng = np.random.default_rng(SEED); rows = []
    for n in BATCH:
        for mu in MU:
            b, g = CTRL[mu]
            acc = {"base": [], "msm_bisect": [], "hibaf": []}
            for _ in range(NW):
                inv = (rng.random(n) < mu).astype(np.int8)
                acc["base"].append(bisect(inv, c_base)); acc["msm_bisect"].append(bisect(inv, c_msm)); acc["hibaf"].append(hibaf_window(inv, b, g))
            rows.append(dict(n=n, mu_pct=100*mu, ctrl_b=b, ctrl_g=g, indiv=n*C1, indiv_base=2*n,
                             **{k + "_mean": float(np.mean(v)) for k, v in acc.items()},
                             **{k + "_p95": float(np.percentile(v, 95)) for k, v in acc.items()}))
    return pd.DataFrame(rows)

def run_replay():
    """classes: 0 valid, 1 cross-window replay, 2 accepted same-window replay, 3 exact duplicate,
       4 modified report reusing (ID,nu), 5 invalid unseen nonce (as in the draft)."""
    rng = np.random.default_rng(SEED); rows = []
    for n in BATCH:
        for rs in REPLAY:
            p = [(1-rs)*0.95, rs/4, rs/4, rs/4, rs/4, (1-rs)*0.05]
            r = {k: [] for k in ["base_f", "base_b4", "hib_f", "hib_b4"]}
            # controller input: converged invalid-rate estimate (expected share of failing reports)
            mu_f = (p[4] + p[5]) / (p[0] + p[4] + p[5]); mu_b = p[1] + p[4] + p[5]
            (bf, gf), (bb, gb) = controller(mu_f), controller(mu_b)
            for _ in range(NW):
                cl = rng.choice(6, size=n, p=p)
                keep = np.isin(cl, [0, 4, 5]); fi = np.isin(cl[keep], [4, 5]).astype(np.int8)
                bi = np.isin(cl, [1, 4, 5]).astype(np.int8)                         # B4: replays verified; class 1 fails, 2/3 valid
                r["base_f"].append(bisect(fi, c_base)); r["base_b4"].append(bisect(bi, c_base))
                r["hib_f"].append(hibaf_window(fi, bf, gf)); r["hib_b4"].append(hibaf_window(bi, bb, gb))
            m = {k: float(np.mean(v)) for k, v in r.items()}
            rows.append(dict(n=n, replay_pct=100*rs, ctrl_f=f"{bf}/{gf}", ctrl_b4=f"{bb}/{gb}", **m, base_saving_pct=100*(1-m["base_f"]/m["base_b4"]),
                             hibaf_saving_pct=100*(1-m["hib_f"]/m["hib_b4"])))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    mixed = run_mixed(); mixed.to_csv(f"{OUT}/mc_mixed.csv", index=False)
    print(mixed.round(2).to_string())
    from functools import lru_cache
    controller = lru_cache(None)(controller)
    replay = run_replay(); replay.to_csv(f"{OUT}/mc_replay.csv", index=False)
    print(replay.round(2).to_string())
