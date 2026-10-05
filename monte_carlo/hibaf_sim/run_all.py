"""python -m hibaf_sim.run_all --config config/simulation_config.yaml --out results"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import matplotlib
import numpy as np
import pandas as pd
import yaml

from . import exp_a_scalability, exp_b_mixed_validity, exp_c_replay, exp_d_dt_scalability
from . import exp_e_sensitivity, exp_f_full_hierarchy, exp_g_window_sensitivity, plots, report
from .costs import SkipLog
from .params import load_config, load_param_sets


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/simulation_config.yaml")
    ap.add_argument("--out", default="results")
    ap.add_argument("--reuse-mc", action="store_true",
                    help="do not recompute Monte Carlo experiments B and C; reload their existing summary CSVs from --out/summary")
    ap.add_argument("--n-windows", type=int, default=None, help="override Monte Carlo windows (quick test only)")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if args.n_windows:
        cfg["n_windows"] = args.n_windows
    psets = load_param_sets(cfg)
    skip = SkipLog()
    raw, summ, fig = (os.path.join(args.out, d) for d in ("raw", "summary", "figures"))
    for d in (raw, summ, fig):
        os.makedirs(d, exist_ok=True)

    res = {}
    res.update(exp_a_scalability.run(cfg, psets, skip))
    if args.reuse_mc:
        res["b_summary"] = pd.read_csv(os.path.join(summ, "exp_b_mixed_validity_summary.csv"))
        res["c_summary"] = pd.read_csv(os.path.join(summ, "exp_c_replay_summary.csv"))
        old = os.path.join(args.out, "skipped_analyses.csv")
        if os.path.exists(old):
            skip.load_rows(pd.read_csv(old), {"B_mixed_validity", "C_replay"})
    else:
        res.update(exp_b_mixed_validity.run(cfg, psets, skip))
        res.update(exp_c_replay.run(cfg, psets, skip))
    res.update(exp_d_dt_scalability.run(cfg, psets, skip))
    res.update(exp_e_sensitivity.run(cfg, psets, skip))
    res.update(exp_f_full_hierarchy.run(cfg, psets, skip))
    res.update(exp_g_window_sensitivity.run(cfg, psets, skip))

    if not args.reuse_mc:
        res["b_raw"].to_csv(os.path.join(raw, "exp_b_mixed_validity_windows.csv"), index=False)
        res["c_raw"].to_csv(os.path.join(raw, "exp_c_replay_windows.csv"), index=False)
    names = {"a1_pond": "exp_a1_pond_scalability", "a2_site": "exp_a2_site_scalability",
             "a3_sensor": "exp_a3_sensor", "b_summary": "exp_b_mixed_validity_summary",
             "c_summary": "exp_c_replay_summary", "d_dt": "exp_d_dt_scalability",
             "e_audit": "exp_e_completeness_audit", "e_comparison": "exp_e_set_comparison",
             "e_thresholds": "exp_e_thresholds",
             "f_components": "exp_f_hierarchy_components", "f_symbolic": "exp_f_hierarchy_symbolic",
             "f_numeric": "exp_f_hierarchy_numeric", "f_reconciliation": "exp_f_hierarchy_reconciliation",
             "g_window": "exp_g_window_sensitivity"}
    for k, v in names.items():
        if args.reuse_mc and k in ("b_summary", "c_summary"):
            continue
        res[k].to_csv(os.path.join(summ, v + ".csv"), index=False)

    tex = exp_f_full_hierarchy.latex_tables(res, cfg)
    os.makedirs(os.path.join(args.out, "tables"), exist_ok=True)
    for k, v in tex.items():
        with open(os.path.join(args.out, "tables", k + ".tex"), "w", encoding="utf-8") as fh:
            fh.write(v)
    gtext = exp_g_window_sensitivity.texts(res, cfg, psets)
    os.makedirs(os.path.join(args.out, "text"), exist_ok=True)
    for k, v in gtext.items():
        sub = "tables" if k.endswith("table.tex") else "text"
        with open(os.path.join(args.out, sub, k), "w", encoding="utf-8") as fh:
            fh.write(v)
    plots.make_all(res, cfg, psets, fig, skip)
    skip_df = skip.df()
    skip_df.to_csv(os.path.join(args.out, "skipped_analyses.csv"), index=False)
    report.build(res, cfg, psets, skip_df, os.path.join(args.out, "REPORT.md"), tex, gtext)

    with open(args.config, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    manifest = dict(seed=cfg["seed"], n_windows=cfg["n_windows"], monte_carlo_recomputed=not args.reuse_mc, config_sha256=digest,
                    python=sys.version.split()[0], numpy=np.__version__, pandas=pd.__version__,
                    matplotlib=matplotlib.__version__, pyyaml=yaml.__version__,
                    note="analytical / Monte Carlo simulation from literature-derived inputs; no physical-device runs")
    with open(os.path.join(args.out, "run_manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"done: {args.out}  (skipped analyses logged: {len(skip_df)} rows)")


if __name__ == "__main__":
    main()
