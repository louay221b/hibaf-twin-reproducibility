"""Experiment B: mixed-validity batches (Monte Carlo).

Strategy A (current Algorithm 2): batch; if it fails, individually verify ALL reports.
Strategy B (EVALUATED ENHANCED VARIANT, not in the current Algorithm 2): batch; if it fails,
recursively halve the failing set, batch-testing each half (singleton = individual check),
until invalid reports are isolated.  Both strategies see the SAME random invalid-report draws.

Costs follow the user's rule: failing case cost = batch cost + fallback cost.
The batch equation is assumed to detect any invalid report (Prop. 4: error <= 1/(q-1), neglected).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .costs import (MODELS, Ops, evaluate, expected_hecm_strategy_a, ind_pond_ops, scenario_label, stats)

VT = "Monte Carlo result"
STRAT_A = "A_full_individual_fallback"
STRAT_B = "B_recursive_divide_conquer"
STRAT_NOTE = {STRAT_A: "current HiBaF-Twin Algorithm 2",
              STRAT_B: "evaluated enhanced fallback variant (not part of current Algorithm 2)"}


def dc_isolate(cs, n, infer_sibling=False):
    """Divide-and-conquer fallback. cs = prefix sums (len n+1) of the invalid indicator.

    Returns (hecm, hadd, hash, found_indices, batch_failed). Counts include the initial batch.
    """
    hecm, hadd, hsh = 2 * n + 1, 2 * n - 1, n
    if cs[n] == 0:
        return hecm, hadd, hsh, [], False
    found, stack = [], [(0, n)]
    while stack:
        a, b = stack.pop()
        if b - a == 1:
            found.append(a)
            continue
        mid = (a + b) // 2
        left_failed = False
        for x, y, is_right in ((a, mid, False), (mid, b, True)):
            if is_right and infer_sibling and not left_failed:
                stack.append((x, y))
                continue
            size = y - x
            if size == 1:
                hecm += 2; hadd += 1; hsh += 1
            else:
                hecm += 2 * size + 1; hadd += 2 * size - 1; hsh += size
            fails = (cs[y] - cs[x]) > 0
            if not is_right:
                left_failed = fails
            if fails:
                stack.append((x, y))
    return hecm, hadd, hsh, sorted(found), True


def run(cfg, psets, skip, n_windows=None):
    W = int(n_windows or cfg["n_windows"])
    sc = cfg["scenario"]["uniform_reference_roles"]
    mv = cfg["mixed_validity"]
    infer = bool(mv.get("infer_sibling", False))
    raw_parts, srows = [], []

    for n in mv["n"]:
        for mu_pct in mv["mu_pct"]:
            ss = np.random.SeedSequence([int(cfg["seed"]), 2, int(n), int(round(mu_pct * 100))])
            rng = np.random.default_rng(ss)
            inv = rng.random((W, n)) < mu_pct / 100.0
            k = inv.sum(axis=1)
            fail = k > 0
            f = fail.astype(np.int64)

            res = {STRAT_A: (2 * n + 1 + f * 2 * n, 2 * n - 1 + f * n, n + f * n)}
            cs = np.zeros((W, n + 1), dtype=np.int32)
            cs[:, 1:] = np.cumsum(inv, axis=1)
            bh, ba, bs = (np.empty(W, dtype=np.int64) for _ in range(3))
            for w in range(W):
                if k[w] == 0:
                    bh[w], ba[w], bs[w] = 2 * n + 1, 2 * n - 1, n
                else:
                    h, a_, s_, found, _ = dc_isolate(cs[w].tolist(), n, infer)
                    bh[w], ba[w], bs[w] = h, a_, s_
            res[STRAT_B] = (bh, ba, bs)

            for strat, (h, a_, s_) in res.items():
                raw_parts.append(pd.DataFrame(dict(
                    experiment="B_mixed_validity", n=n, mu_pct=mu_pct, strategy=strat,
                    window=np.arange(W), k_invalid=k, batch_failed=fail,
                    n_hecm=h, n_hadd=a_, n_hash=s_, value_type=VT)))
                ops = Ops(hecm=h, hadd=a_, hash=s_)
                ind_ops = ind_pond_ops(n)
                hs = stats(h)
                base = dict(experiment="B_mixed_validity", n=n, mu_pct=mu_pct, strategy=strat,
                            strategy_note=STRAT_NOTE[strat], n_windows=W, value_type=VT,
                            empirical_batch_fail_rate=float(fail.mean()),
                            analytical_batch_fail_rate=1 - (1 - mu_pct / 100) ** n,
                            hecm_mean=hs["mean"], hecm_median=hs["median"],
                            hecm_std=hs["std"], hecm_p95=hs["p95"],
                            analytical_mean_hecm=(expected_hecm_strategy_a(n, mu_pct / 100)
                                                  if strat == STRAT_A else np.nan),
                            individual_hecm=2 * n)
                srows.append(dict(base, cost_model="counts_only", scenario="platform-independent operation counts", param_set="n/a",
                                  projection_mean_ms=np.nan, projection_median_ms=np.nan, projection_std_ms=np.nan,
                                  projection_p95_ms=np.nan, individual_projection_ms=np.nan,
                                  overhead_pct_vs_individual=100 * (hs["mean"] / (2 * n) - 1)))
                for ps in psets:
                    for model in MODELS:
                        lat, miss = evaluate(ops, ps, "pond", model, sc)
                        ind, miss2 = evaluate(ind_ops, ps, "pond", model, sc)
                        if lat is None or ind is None:
                            skip.add("B_mixed_validity", "latency_stats", model, ps.name, miss + miss2)
                            continue
                        ls = stats(lat)
                        srows.append(dict(base, cost_model=model, scenario=scenario_label(ps, model), param_set=ps.name,
                                          projection_mean_ms=ls["mean"], projection_median_ms=ls["median"],
                                          projection_std_ms=ls["std"], projection_p95_ms=ls["p95"],
                                          individual_projection_ms=ind,
                                          overhead_pct_vs_individual=100 * (ls["mean"] / ind - 1)))
    return dict(b_raw=pd.concat(raw_parts, ignore_index=True), b_summary=pd.DataFrame(srows))
