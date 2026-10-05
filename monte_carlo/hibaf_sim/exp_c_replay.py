"""Experiment C: replay simulation (Monte Carlo) with the corrected duplicate-handling mechanism.

Mechanism (modified Algorithm 2):
  N_w^Bp : persistent per-window set of cryptographically ACCEPTED (ID, nonce) pairs.
  D_p,w  : temporary set of FINGERPRINTS (H3) of complete reports seen in the current batch; it only
           collapses byte-identical copies.  Two different reports sharing (ID, nonce) in one batch are
           NOT rejected by arrival order; cryptographic verification resolves them (no pre-emption).

Report classes per submitted report:
  valid | a cross-window replay | b replay of a previously ACCEPTED same-window report
  | c exact duplicate inside the current batch | d same (ID,nonce), modified payload | e invalid, unseen nonce
Early rejection / deduplication applies only to a, b, c.  d and e reach cryptographic verification.
Class d reports carry a modified payload (invalid signature); their legitimate companion is a valid report
in the same batch (copies cannot exceed available originals; orphans are reclassified: orphan c -> valid,
orphan d -> e).  Class b assumes the accepted original was processed in an earlier batch of the same window.

Cost accounting.  Filtered system: one H3 fingerprint per report that passes the window and N_w checks
(valid, c, d, e); batch verification on valid+d+e; strategy-A fallback if d+e > 0.  Cache lookups are not
charged.  Baseline (no early filtering, no caches, no fingerprints): all n reports reach batch verification;
a, d, e fail the check, b and c verify successfully.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .costs import MODELS, Ops, evaluate, scenario_label, stats

VT = "Monte Carlo result"
CNT = "platform-independent operation counts"
WKEYS = ("a_cross_window_replay", "b_accepted_same_window_replay",
         "c_exact_duplicate_in_batch", "d_same_id_nonce_modified_payload")


def _ops(m, fp, n_inv):
    m = np.asarray(m, dtype=np.int64)
    f = (np.asarray(n_inv) > 0).astype(np.int64)
    has = m > 0
    return Ops(hecm=np.where(has, 2 * m + 1, 0) + f * 2 * m,
               hadd=np.where(has, 2 * m - 1, 0) + f * m,
               hash=np.asarray(fp, dtype=np.int64) + m + f * m)


def run(cfg, psets, skip, n_windows=None):
    W = int(n_windows or cfg["n_windows"])
    sc = cfg["scenario"]["uniform_reference_roles"]
    rc = cfg["replay"]
    w = np.array([rc["class_weights"][k] for k in WKEYS], dtype=float)
    if abs(w.sum() - 1) > 1e-9:
        raise ValueError("replay.class_weights must sum to 1")
    mu_new = float(rc["invalid_new_nonce_pct_of_non_replay"]) / 100
    raw_parts, srows = [], []

    for n in rc["n"]:
        for rp in rc["replay_pct"]:
            rng = np.random.default_rng(np.random.SeedSequence([int(cfg["seed"]), 3, int(n), int(rp)]))
            r = rp / 100.0
            pv = np.concatenate([[(1 - r) * (1 - mu_new)], r * w, [(1 - r) * mu_new]])
            d = rng.multinomial(n, pv / pv.sum(), size=W)
            nv, na, nb, nc, nd, ne = (d[:, i].astype(np.int64) for i in range(6))
            nc_eff = np.minimum(nc, nv); orph_c = nc - nc_eff; nv = nv + orph_c; nc = nc_eff
            nd_eff = np.minimum(nd, nv); orph_d = nd - nd_eff; ne = ne + orph_d; nd = nd_eff
            reclass = orph_c + orph_d
            m = nv + nd + ne
            fp = nv + nc + nd + ne
            filt = _ops(m, fp, nd + ne)
            base = _ops(np.full(W, n), np.zeros(W), na + nd + ne)
            base.hash = n + (na + nd + ne > 0).astype(np.int64) * n
            avoided = base.hecm - filt.hecm
            raw_parts.append(pd.DataFrame(dict(
                experiment="C_replay", n=n, replay_pct=rp, window=np.arange(W),
                n_valid=nv, n_a_cross_window=na, n_b_accepted_same_window=nb,
                n_c_exact_duplicate_in_batch=nc, n_d_modified_payload_same_id_nonce=nd,
                n_e_invalid_unseen_nonce=ne, n_reclassified_orphans=reclass,
                n_early_rejected_a_b=na + nb, n_collapsed_c=nc, n_reaching_crypto=m,
                n_fingerprint_hashes=fp,
                hecm_filtered=filt.hecm, hadd_filtered=filt.hadd, hash_filtered=filt.hash,
                hecm_baseline=base.hecm, hadd_baseline=base.hadd, hash_baseline=base.hash,
                hecm_avoided=avoided, value_type=VT)))
            hb, hf = stats(base.hecm), stats(filt.hecm)
            common = dict(
                experiment="C_replay", n=n, replay_pct=rp, n_windows=W, value_type=VT,
                scenario_class_weights=str(dict(zip(WKEYS, w.tolist()))),
                scenario_invalid_new_nonce_pct=mu_new * 100,
                early_rejected_a_b_pct=float(100 * (na + nb).mean() / n),
                collapsed_c_pct=float(100 * nc.mean() / n),
                early_or_collapsed_a_b_c_pct=float(100 * (na + nb + nc).mean() / n),
                d_reaching_crypto_pct=float(100 * nd.mean() / n),
                e_reaching_crypto_pct=float(100 * ne.mean() / n),
                reaching_crypto_mean=float(m.mean()),
                hecm_filtered_mean=hf["mean"], hecm_baseline_mean=hb["mean"],
                hecm_avoided_mean=float(avoided.mean()),
                hecm_avoided_pct_of_baseline=float(100 * avoided.mean() / hb["mean"]))
            nan = np.nan
            srows.append(dict(common, cost_model="counts_only", scenario=CNT, param_set="n/a",
                              filtered_projection_mean_ms=nan, filtered_projection_median_ms=nan,
                              filtered_projection_std_ms=nan, filtered_projection_p95_ms=nan,
                              baseline_projection_mean_ms=nan, baseline_projection_median_ms=nan,
                              baseline_projection_std_ms=nan, baseline_projection_p95_ms=nan,
                              projection_saved_mean_ms=nan, projection_saved_pct=nan))
            for ps in psets:
                for model in MODELS:
                    lf, m1 = evaluate(filt, ps, "pond", model, sc)
                    lb, m2 = evaluate(base, ps, "pond", model, sc)
                    if lf is None or lb is None:
                        skip.add("C_replay", "verification_delay_projection", model, ps.name, m1 + m2)
                        continue
                    sf, sb = stats(lf), stats(lb)
                    srows.append(dict(
                        common, cost_model=model, scenario=scenario_label(ps, model), param_set=ps.name,
                        filtered_projection_mean_ms=sf["mean"], filtered_projection_median_ms=sf["median"],
                        filtered_projection_std_ms=sf["std"], filtered_projection_p95_ms=sf["p95"],
                        baseline_projection_mean_ms=sb["mean"], baseline_projection_median_ms=sb["median"],
                        baseline_projection_std_ms=sb["std"], baseline_projection_p95_ms=sb["p95"],
                        projection_saved_mean_ms=sb["mean"] - sf["mean"],
                        projection_saved_pct=100 * (sb["mean"] - sf["mean"]) / sb["mean"]))
    return dict(c_raw=pd.concat(raw_parts, ignore_index=True), c_summary=pd.DataFrame(srows))
