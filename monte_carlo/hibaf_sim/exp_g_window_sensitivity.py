"""Experiment G: reporting-window sensitivity, Delta_w in cfg['delta_w_s'] (analytical result).

Uses ONLY platform-independent operation counts and, where applicable, the labelled
"Taji-Ghanimi reference-platform HECM-only lower-bound scenario".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .costs import HECM_ONLY, dt_ops, evaluate, scenario_label, station_ops

VT = "analytical result"
DAGGER_EXTRA_HECM = 2
NOTE = ("Delta_w is a protocol/configuration parameter, not an empirically optimal aquaculture value; "
        "HECM-only lower bound omits hashes, KDF, AEAD, group additions, communication, scheduling and queueing")


def _targets(cfg):
    for N in cfg["dt"]["N_site"]:
        yield "Digital Twin", "N_site", N, "2N+2", dt_ops(N), "dt"
    for P in cfg["site"]["P"]:
        yield "Site station", "P", P, "2P+1", station_ops(P), "station"


def run(cfg, psets, skip):
    sc = cfg["scenario"]["uniform_reference_roles"]
    dws = cfg["delta_w_s"]
    rows = []
    for ps in psets:
        ok = True
        for tier, var, size, form, ops, role in _targets(cfg):
            lat, miss = evaluate(ops, ps, role, HECM_ONLY, sc)
            if lat is None:
                skip.add("G_window_sensitivity", f"{role}_window_projection", HECM_ONLY, ps.name, miss)
                ok = False
        if not ok:
            continue
        for tier, var, size, form, ops, role in _targets(cfg):
            lat, _ = evaluate(ops, ps, role, HECM_ONLY, sc)
            latd, _ = evaluate(type(ops)(hecm=ops.hecm + DAGGER_EXTRA_HECM), ps, role, HECM_ONLY, sc)
            for dw in dws:
                rows.append(dict(
                    experiment="G_window_sensitivity", tier=tier, size_var=var, size=size,
                    delta_w_s=dw, hecm_formula=form, hecm_count=ops.hecm,
                    required_hecm_per_s=ops.hecm / dw,
                    max_T_HECM_ms_to_fit_window=dw * 1000 / ops.hecm,
                    param_set=ps.name, scenario=scenario_label(ps, HECM_ONLY),
                    projection_ms=lat, pct_of_window=100 * lat / (dw * 1000),
                    lower_bound_exceeds_window=bool(lat > dw * 1000),
                    hecm_count_dagger=ops.hecm + DAGGER_EXTRA_HECM,
                    projection_ms_dagger=latd, pct_of_window_dagger=100 * latd / (dw * 1000),
                    lower_bound_exceeds_window_dagger=bool(latd > dw * 1000),
                    value_type=VT, note=NOTE))
    if not rows:
        for tier, var, size, form, ops, role in _targets(cfg):
            for dw in dws:
                rows.append(dict(experiment="G_window_sensitivity", tier=tier, size_var=var, size=size,
                                 delta_w_s=dw, hecm_formula=form, hecm_count=ops.hecm,
                                 required_hecm_per_s=ops.hecm / dw,
                                 max_T_HECM_ms_to_fit_window=dw * 1000 / ops.hecm,
                                 param_set="n/a", scenario="platform-independent operation counts",
                                 projection_ms=np.nan, pct_of_window=np.nan, lower_bound_exceeds_window=None,
                                 hecm_count_dagger=ops.hecm + DAGGER_EXTRA_HECM, projection_ms_dagger=np.nan,
                                 pct_of_window_dagger=np.nan, lower_bound_exceeds_window_dagger=None,
                                 value_type=VT, note=NOTE))
    return dict(g_window=pd.DataFrame(rows))


def texts(res, cfg, psets):
    """The manuscript-specific LaTeX prose is not required to regenerate the numerical results."""
    return {}
