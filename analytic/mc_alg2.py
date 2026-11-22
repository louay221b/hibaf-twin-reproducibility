"""Monte Carlo check: partial batches handled exactly as Algorithm 2 (re-select h for the actual size m,
subject to W(m,h) <= Gamma, groups of ceil(m/h)), versus the archived model (keeps g*, capped at m).
Same seed, windows and validity sequences as eval_analytic.run_mixed()."""
import importlib.util, math, numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "results" / "generated" / "v33"
OUT.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location("ea", HERE / "eval_analytic.py"); ea = importlib.util.module_from_spec(spec); spec.loader.exec_module(ea)
c, C1, G = ea.c_msm, ea.C1, ea.GAMMA
def W_m(m, h):  # Eq. (5) with groups of ceil(m/h)
    if m == 1: return C1
    k = math.ceil(m / h); return c(m) + m * C1 + (h * c(k) if h > 1 else 0)
def E_m(m, h, mu):  # Eq. (4) at the actual size, groups of ceil(m/h)
    if m == 1: return C1
    if h == 1: return c(m) + ea.p_any(mu, m) * m * C1
    k = math.ceil(m / h); return c(m) + ea.p_any(mu, m) * h * c(k) + h * ea.p_any(mu, k) * k * C1
def reselect(m, mu):
    cand = [h for h in (1, 2, 4, 8, 16) if h <= m and W_m(m, h) <= G]
    return min(cand, key=lambda h: E_m(m, h, mu))
def window_alg2(inv, b, g, mu, stats):
    tot = 0.0
    for s in range(0, len(inv), b):
        ch = inv[s:s+b]; m = len(ch)
        if m < b:
            h = reselect(m, mu); stats["Wmax"] = max(stats["Wmax"], W_m(m, h))
            cost = ea.group_test(ch, h); stats["partial_max"] = max(stats["partial_max"], cost)
        else:
            cost = ea.group_test(ch, g)
        tot += cost
    return tot
ref = pd.read_csv(HERE / "mc_mixed.csv")
rng = np.random.default_rng(ea.SEED); rows = []
for n in ea.BATCH:
    for mu in ea.MU:
        b, g = ea.CTRL[mu]; old, new = [], []; st = {"Wmax": 0.0, "partial_max": 0.0}
        for _ in range(ea.NW):
            inv = (rng.random(n) < mu).astype(np.int8)
            old.append(ea.hibaf_window(inv, b, g)); new.append(window_alg2(inv, b, g, mu, st))
        r = ref[(ref.n == n) & (ref.mu_pct == 100*mu)].iloc[0]
        rows.append(dict(n=n, mu=100*mu, b=b, g=g, archived=r.hibaf_mean, old_recomputed=np.mean(old), alg2=np.mean(new),
                         indiv=n*C1, old_ratio=np.mean(old)/(n*C1), alg2_ratio=np.mean(new)/(n*C1),
                         diff_pct=100*(np.mean(new)/np.mean(old)-1), Wmax_partial=st["Wmax"], Gamma=G, partial_cost_max=st["partial_max"]))
D = pd.DataFrame(rows); D.to_csv(OUT / "mc_alg2.csv", index=False)
print(D.round(4).to_string())
print("max |diff| %:", D.diff_pct.abs().max().round(3), "| archived reproduced:", np.allclose(D.archived, D.old_recomputed),
      "| all partial W <= Gamma:", (D.Wmax_partial <= D.Gamma).all(), "| alg2 <= individual everywhere:", (D.alg2_ratio <= 1 + 1e-9).all())
