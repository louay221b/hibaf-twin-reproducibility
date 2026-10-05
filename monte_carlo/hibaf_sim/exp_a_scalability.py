"""Experiment A: scalability (STATED formulas Eqs. 1-5). A1 one collector; A2 site; A3 sensor.

Site wording: "aggregate sequential work" = P*pond + station + DT (sum of all work);
"parallel-collector critical-path projection" = one collector + station + DT (collectors are
independent and run concurrently; identical collectors assumed)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .costs import (MODELS, batch_pond_ops, dt_ops, evaluate, ind_pond_ops, scenario_label,
                    sensor_ops, station_ops)

VT = "analytical result"
CNT = "platform-independent operation counts"


def run(cfg, psets, skip):
    sc = cfg["scenario"]["uniform_reference_roles"]
    dws = cfg["delta_w_s"]
    pond_rows, site_rows, sensor_rows = [], [], []

    for n in cfg["per_pond"]["n"]:
        for variant, ops in (("individual", ind_pond_ops(n)), ("batch_verification_only_all_valid", batch_pond_ops(n))):
            base = dict(experiment="A1_per_pond", n=n, variant=variant, value_type=VT, **ops.as_dict())
            pond_rows.append(dict(base, cost_model="counts_only", scenario=CNT, param_set="n/a",
                                  delta_w_s=np.nan, projection_ms=np.nan, pct_of_window=np.nan))
            for ps in psets:
                for model in MODELS:
                    lat, miss = evaluate(ops, ps, "pond", model, sc)
                    if lat is None:
                        skip.add("A1_per_pond", f"pond_{variant}_projection", model, ps.name, miss)
                        continue
                    for dw in dws:
                        pond_rows.append(dict(base, cost_model=model, scenario=scenario_label(ps, model),
                                              param_set=ps.name, delta_w_s=dw, projection_ms=lat,
                                              pct_of_window=100 * lat / (dw * 1000)))

    for P in cfg["site"]["P"]:
        for n in cfg["site"]["n_per_pond"]:
            N = P * n
            pond, st, dt = batch_pond_ops(n), station_ops(P), dt_ops(N)
            seq_h = P * pond.hecm + st.hecm + dt.hecm
            pipe_h = pond.hecm + st.hecm + dt.hecm
            base = dict(experiment="A2_site", P=P, n_per_pond=N // P, N_site=N, value_type=VT,
                        hecm_pond_batch_verification_only=pond.hecm, hecm_station=st.hecm, hecm_dt=dt.hecm,
                        hecm_aggregate_sequential_work=seq_h,
                        hecm_parallel_collector_critical_path=pipe_h)
            site_rows.append(dict(base, cost_model="counts_only", scenario=CNT, param_set="n/a",
                                  delta_w_s=np.nan))
            for ps in psets:
                for model in MODELS:
                    lp, mp = evaluate(pond, ps, "pond", model, sc)
                    ls, ms_ = evaluate(st, ps, "station", model, sc)
                    ld, md_ = evaluate(dt, ps, "dt", model, sc)
                    miss = mp + ms_ + md_
                    if miss:
                        skip.add("A2_site", "site_projection", model, ps.name, miss)
                        continue
                    seq, pipe = P * lp + ls + ld, lp + ls + ld
                    for dw in dws:
                        site_rows.append(dict(
                            base, cost_model=model, scenario=scenario_label(ps, model),
                            param_set=ps.name, delta_w_s=dw,
                            pond_projection_ms=lp, station_projection_ms=ls, dt_projection_ms=ld,
                            aggregate_sequential_work_projection_ms=seq,
                            parallel_collector_critical_path_projection_ms=pipe,
                            pct_aggregate_sequential_work=100 * seq / (dw * 1000),
                            pct_parallel_critical_path=100 * pipe / (dw * 1000),
                            exceeds_window_aggregate_sequential_work=bool(seq > dw * 1000),
                            exceeds_window_parallel_critical_path=bool(pipe > dw * 1000)))

    ops = sensor_ops()
    sensor_rows.append(dict(experiment="A3_sensor", cost_model="counts_only", scenario=CNT,
                            param_set="n/a", projection_ms=np.nan, value_type=VT, **ops.as_dict()))
    for ps in psets:
        for model in MODELS:
            lat, miss = evaluate(ops, ps, "sensor", model, sc)
            if lat is None:
                skip.add("A3_sensor", "sensor_report_projection", model, ps.name, miss)
            else:
                sensor_rows.append(dict(experiment="A3_sensor", cost_model=model, scenario=scenario_label(ps, model),
                                        param_set=ps.name, projection_ms=lat, value_type=VT, **ops.as_dict()))
    return dict(a1_pond=pd.DataFrame(pond_rows), a2_site=pd.DataFrame(site_rows),
                a3_sensor=pd.DataFrame(sensor_rows))
