"""Experiment D: DT scalability (analytical, stated Eq. 4)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .costs import MODELS, dt_ops, evaluate, scenario_label

VT = "analytical result"


def run(cfg, psets, skip):
    sc = cfg["scenario"]["uniform_reference_roles"]
    rows = []
    for N in cfg["dt"]["N_site"]:
        ops = dt_ops(N)
        base = dict(experiment="D_dt", N_site=N, value_type=VT, **ops.as_dict())
        rows.append(dict(base, cost_model="counts_only", scenario="platform-independent operation counts",
                         param_set="n/a", delta_w_s=np.nan, dt_projection_ms=np.nan,
                         pct_of_window=np.nan, exceeds_window=None))
        for ps in psets:
            for model in MODELS:
                lat, miss = evaluate(ops, ps, "dt", model, sc)
                if lat is None:
                    skip.add("D_dt", "dt_projection", model, ps.name, miss)
                    continue
                for dw in cfg["delta_w_s"]:
                    rows.append(dict(base, cost_model=model, scenario=scenario_label(ps, model),
                                     param_set=ps.name, delta_w_s=dw, dt_projection_ms=lat,
                                     pct_of_window=100 * lat / (dw * 1000),
                                     exceeds_window=bool(lat > dw * 1000)))
    return dict(d_dt=pd.DataFrame(rows))
