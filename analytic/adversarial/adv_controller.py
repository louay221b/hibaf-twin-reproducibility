#!/usr/bin/env python3
"""Adversarial evaluation of the adaptive MSM controller (Algorithms 2-3) at one collector.
Event-driven: Poisson arrivals, batches formed when |Q| >= b or the 100 ms timer expires, partial batches re-select h
(Algorithm 2), mu_hat = EWMA (lambda = 0.2) of the invalid share of each verified batch. Costs: benchmark c(n) and
GROUPTEST of eval_analytic.py (Table VII); time per HECM = measured Pi 4 cost; Gamma = Delta_ver / T_HECM.
Comparators: same controller fed the true instantaneous rate (oracle), and individual verification (B1)."""
import importlib.util, math, sys, os
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "results" / "generated" / "v33" / "adversarial"
spec = importlib.util.spec_from_file_location("ea", HERE.parent / "eval_analytic.py"); ea = importlib.util.module_from_spec(spec); spec.loader.exec_module(ea)
c, C1 = ea.c_msm, ea.C1
T_HECM = 1.706e-3                 # s, measured Raspberry Pi 4
GAMMA = 1.0 / T_HECM              # Delta_ver = 1 s  ->  ~586 HECM
LAM, T_BATCH, RATE, DUR = 0.2, 0.100, 100.0, 60.0     # EWMA, batch timer, reports/s at the collector, s
SEEDS = range(1, 31)
def W(m, h):
    if m == 1: return C1
    k = math.ceil(m / h); return c(m) + m * C1 + (h * c(k) if h > 1 else 0)
def E(m, h, mu):
    if m == 1: return C1
    if h == 1: return c(m) + ea.p_any(mu, m) * m * C1
    k = math.ceil(m / h); return c(m) + ea.p_any(mu, m) * h * c(k) + h * ea.p_any(mu, k) * k * C1
_ctrl_cache = {}
def controller(mu):                                  # Algorithm 3
    key = round(mu, 4)
    if key in _ctrl_cache: return _ctrl_cache[key]
    best = (1, 1, C1)
    for b in (2, 4, 8, 16, 32, 64, 128, 256):
        for g in (1, 2, 4, 8, 16):
            if g > b or W(b, g) > GAMMA: continue
            e = E(b, g, mu) / b
            if e < best[2]: best = (b, g, e)
    _ctrl_cache[key] = best[:2]; return best[:2]
def reselect(m, mu):                                 # Algorithm 2, partial batch
    cand = [h for h in (1, 2, 4, 8, 16) if h <= m and W(m, h) <= GAMMA]
    return min(cand, key=lambda h: E(m, h, mu))

# ---------------- attack patterns: p(t) = probability that a report arriving at t is invalid
def p_step(t):        return 0.25 if 20 <= t < 40 else 0.0
def p_alt(t):         return (0.50 if (t - 20) % 5.0 < 0.5 else 0.0) if 20 <= t < 40 else 0.0     # 0.5 s on / 4.5 s off
def p_burst(t):       return (1.00 if (t - 20) % 2.0 < 0.2 else 0.0) if 20 <= t < 40 else 0.0     # 0.2 s at 100 % every 2 s
def p_ind(t):         return 0.05
PATTERNS = {"step": p_step, "alternating": p_alt, "burst": p_burst, "independent": p_ind, "clustered": None}
def draw(rng, name):
    n = rng.poisson(RATE * DUR); t = np.sort(rng.uniform(0, DUR, n))
    if name == "clustered":                          # 5 % invalid in runs of 16 consecutive reports
        v = np.zeros(n, np.int8); starts = np.nonzero(rng.random(n) < 0.05 / 16)[0]
        for s in starts: v[s:s+16] = 1
        p_true = np.full(n, 0.05)
    else:
        f = PATTERNS[name]; p_true = np.array([f(x) for x in t]); v = (rng.random(n) < p_true).astype(np.int8)
    return t, v, p_true

def run(t, v, p_true, mode):
    n = len(t); s = 0; cur = 0.0; mu = 0.0; rows = []; delay = np.zeros(n)
    while s < n:
        if mode == "indiv":
            start = max(cur, t[s]); done = start + C1 * T_HECM; delay[s] = done - t[s]
            rows.append((start, 1, 1, 1, C1, C1, 0.0, max(0, np.searchsorted(t, start, "right") - s), v[s])); cur = done; s += 1; continue
        est = p_true[s] if mode == "oracle" else mu
        b, g = controller(est)
        full = t[s + b - 1] if s + b - 1 < n else np.inf
        T = min(full, t[s] + T_BATCH); start = max(cur, T)
        arrived = np.searchsorted(t, start, "right") - s
        m = int(min(b, max(1, arrived)))
        h = g if m == b else reselect(m, est)
        chunk = v[s:s+m]; cost = ea.group_test(chunk, min(h, m)); w = W(m, min(h, m))
        done = start + cost * T_HECM; delay[s:s+m] = done - t[s:s+m]
        rows.append((start, m, b, h, cost, w, mu, arrived, int(chunk.sum())))
        mu = (1 - LAM) * mu + LAM * chunk.sum() / m
        cur = done; s += m
    B = pd.DataFrame(rows, columns=["t", "m", "b", "h", "cost", "W", "mu_hat", "queue", "inv"])
    return B, delay

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    out = []; series = {}
    for name in PATTERNS:
        for seed in SEEDS:
            rng = np.random.default_rng(1000 + seed); t, v, p_true = draw(rng, name)
            att = (t >= 20) & (t < 40) if name not in ("independent", "clustered") else np.ones(len(t), bool)
            for mode in ("ewma", "oracle", "indiv"):
                B, d = run(t, v, p_true, mode)
                inwin = (B.t >= 20) & (B.t < 40) if name not in ("independent", "clustered") else np.ones(len(B), bool)
                out.append(dict(pattern=name, seed=seed, mode=mode, n=len(t), invalid_share=v[att].mean(),
                                cost_per_report=B.cost.sum() / B.m.sum(), cost_win=B.cost[inwin].sum() / B.m[inwin].sum(),
                                max_batch_cost=B.cost.max(), max_W=B.W.max(), gamma=GAMMA,
                                over_indiv_frac=((B.cost > B.m * C1 + 1e-9)).mean(),
                                max_queue=B.queue.max(), p95_delay=np.percentile(d, 95), max_delay=d.max(),
                                cpu_util=(B.cost.sum() * T_HECM) / DUR))
                if seed == 1: series[(name, mode)] = B
    R = pd.DataFrame(out); R.to_csv(OUT / "adv_runs.csv", index=False)
    S = R.groupby(["pattern", "mode"]).agg(cost_per_report=("cost_per_report", "mean"), cost_win=("cost_win", "mean"),
          max_batch_cost=("max_batch_cost", "max"), max_W=("max_W", "max"), over_indiv_frac=("over_indiv_frac", "mean"),
          max_queue=("max_queue", "max"), p95_delay=("p95_delay", "mean"), max_delay=("max_delay", "max"),
          cpu_util=("cpu_util", "mean"), invalid_share=("invalid_share", "mean")).reset_index()
    S["cost_win_vs_indiv"] = S.cost_win / C1; S["gamma"] = GAMMA
    S.to_csv(OUT / "adv_summary.csv", index=False)
    pd.set_option("display.width", 220); print(S.round(4).to_string())
    for (name, mode), B in series.items(): B.to_csv(OUT / f"series_{name}_{mode}.csv", index=False)
