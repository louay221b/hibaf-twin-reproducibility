"""Experiment E: sensitivity across literature parameter sets.

E1 completeness audit: which quantities can be computed per parameter set (and what is missing).
E2 set comparison: DT latency at the largest N_site for every set with the needed parameters.
E3 tolerance thresholds (parameter-free): the largest T_HECM (ms) for which a sequential workload
   still fits in Delta_w under the HECM-only model, from count * T_HECM <= Delta_w.
"""
from __future__ import annotations

import pandas as pd

from .costs import HECM_ONLY, MODELS, batch_pond_ops, dt_ops, evaluate, scenario_label,
from .costs import sensor_ops, station_ops

VT = "analytical result"


def run(cfg, psets, skip):
    sc = cfg["scenario"]["uniform_reference_roles"]
    dws = cfg["delta_w_s"]

    audit = []
    quantities = [("sensor", "sensor report (Eq.5)", sensor_ops()),
                  ("pond", "pond batch, n=100 (Eq.2)", batch_pond_ops(100)),
                  ("station", "station, P=10 (Eq.3)", station_ops(10)),
                  ("dt", "DT, N_site=100 (Eq.4)", dt_ops(100))]
    for ps in psets:
        for role, label, ops in quantities:
            for model in MODELS:
                lat, miss = evaluate(ops, ps, role, model, sc)
                audit.append(dict(param_set=ps.name, provenance_status=ps.provenance_status,
                                  role=role, role_coverage=ps.role_status(role, sc),
                                  quantity=label, cost_model=model, computable=lat is not None,
                                  missing_or_blocked="; ".join(miss)))
    audit = pd.DataFrame(audit)

    Nmax = max(cfg["dt"]["N_site"])
    comp = []
    for ps in psets:
        lat, miss = evaluate(dt_ops(Nmax), ps, "dt", HECM_ONLY, sc)
        if lat is None:
            skip.add("E_sensitivity", f"set_comparison_dt_N{Nmax}", HECM_ONLY, ps.name, miss)
            continue
        for dw in dws:
            comp.append(dict(experiment="E2_set_comparison", param_set=ps.name,
                             T_HECM_ms=ps.timings["T_HECM_ms"], N_site=Nmax, delta_w_s=dw,
                             cost_model=HECM_ONLY, scenario=scenario_label(ps, HECM_ONLY),
                             n_hecm=dt_ops(Nmax).hecm, dt_projection_ms=lat,
                             pct_of_window=100 * lat / (dw * 1000), value_type=VT))
    comp = pd.DataFrame(comp)
    if comp["param_set"].nunique() < 2 if not comp.empty else True:
        skip.add("E_sensitivity", "set_comparison_plot", "n/a", "all",
                 ["fewer than two parameter sets with a non-null T_HECM covering the DT role"])

    thr = []
    for dw in dws:
        for N in cfg["dt"]["N_site"]:
            thr.append(dict(quantity="dt", size=str(N), size_num=N, delta_w_s=dw,
                            hecm_count=2 * N + 2, max_T_HECM_ms=dw * 1000 / (2 * N + 2)))
        for n in cfg["per_pond"]["n"]:
            thr.append(dict(quantity="pond_batch", size=str(n), size_num=n, delta_w_s=dw,
                            hecm_count=2 * n + 1, max_T_HECM_ms=dw * 1000 / (2 * n + 1)))
        for P in cfg["site"]["P"]:
            for n in cfg["site"]["n_per_pond"]:
                agg = P * (2 * n + 1) + (2 * P + 1) + (2 * P * n + 2)
                crit = (2 * n + 1) + (2 * P + 1) + (2 * P * n + 2)
                thr.append(dict(quantity="site_aggregate_sequential_work", size=f"{P}x{n}", size_num=P * n,
                                delta_w_s=dw, hecm_count=agg, max_T_HECM_ms=dw * 1000 / agg))
                thr.append(dict(quantity="site_parallel_collector_critical_path", size=f"{P}x{n}", size_num=P * n,
                                delta_w_s=dw, hecm_count=crit, max_T_HECM_ms=dw * 1000 / crit))
    thr = pd.DataFrame(thr)
    thr["value_type"] = VT
    return dict(e_audit=audit, e_comparison=comp, e_thresholds=thr)
