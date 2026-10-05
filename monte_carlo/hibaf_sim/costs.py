"""Analytical operation counts and None-aware latency evaluation.

Every formula returns an *operation-count vector* (Ops). Latency is obtained only by
combining counts with literature-derived per-operation times via `evaluate`, which
refuses to proceed (returns None + reasons) if a needed parameter is null.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

HECM_ONLY = "hecm_only_lower_bound"
FULL = "full_formula"
MODELS = (HECM_ONLY, FULL)

OPS_TO_PARAM = {
    "hecm": "T_HECM_ms",
    "hadd": "T_HAdd_ms",
    "hash": "T_hash_ms",
    "aead_enc": "T_AEAD_enc_ms",
    "aead_dec": "T_AEAD_dec_ms",
}


@dataclass
class Ops:
    hecm: object = 0
    hadd: object = 0
    hash: object = 0
    aead_enc: object = 0
    aead_dec: object = 0

    def __add__(self, o):
        return Ops(*(getattr(self, k) + getattr(o, k) for k in OPS_TO_PARAM))

    def scale(self, c):
        return Ops(*(getattr(self, k) * c for k in OPS_TO_PARAM))

    def as_dict(self, prefix="n_"):
        return {f"{prefix}{k}": getattr(self, k) for k in OPS_TO_PARAM}


def ind_pond_ops(n=1) -> Ops:
    return Ops(hecm=2 * n, hadd=n, hash=n)


def batch_pond_ops(n) -> Ops:
    return Ops(hecm=2 * n + 1, hadd=2 * n - 1, hash=n)


def station_ops(P) -> Ops:
    return Ops(hecm=2 * P + 1, hash=P + 1)


def dt_ops(N_site) -> Ops:
    return Ops(hecm=2 * N_site + 2, aead_dec=N_site)


def sensor_ops() -> Ops:
    return Ops(hecm=1, hash=1, aead_enc=1)


def scenario_label(ps, model) -> str:
    if model == "counts_only":
        return "platform-independent operation counts"
    if model == HECM_ONLY:
        return f"{ps.display_name} HECM-only lower-bound scenario"
    return f"{ps.display_name} full-formula scenario"


def expected_hecm_strategy_a(n, mu):
    return (2 * n + 1) + (1 - (1 - mu) ** n) * 2 * n


def evaluate(ops: Ops, pset, role: str, model: str, scenario_roles=()):
    keys = ["hecm"] if model == HECM_ONLY else list(OPS_TO_PARAM)
    total, missing = 0.0, []
    for k in keys:
        c = getattr(ops, k)
        if not np.any(np.asarray(c) != 0):
            continue
        v, why = pset.get(OPS_TO_PARAM[k], role, scenario_roles)
        if v is None:
            missing.append(why)
            continue
        total = total + np.asarray(c) * v if isinstance(c, np.ndarray) else total + c * v
    return (None if missing else total), missing


class SkipLog:
    def __init__(self):
        self._rows = {}

    def add(self, experiment, quantity, model, param_set, missing):
        key = (experiment, quantity, model, param_set, "; ".join(sorted(set(missing))))
        self._rows[key] = self._rows.get(key, 0) + 1

    def load_rows(self, df, experiments):
        for r in df.itertuples(index=False):
            if r.experiment in experiments:
                self._rows[(r.experiment, r.quantity, r.cost_model, r.param_set, r.missing_or_blocked)] = int(r.n_configurations_affected)

    def df(self) -> pd.DataFrame:
        rows = [dict(experiment=k[0], quantity=k[1], cost_model=k[2], param_set=k[3],
                     missing_or_blocked=k[4], n_configurations_affected=v)
                for k, v in self._rows.items()]
        return pd.DataFrame(rows, columns=["experiment", "quantity", "cost_model", "param_set",
                                           "missing_or_blocked", "n_configurations_affected"])


def stats(x):
    x = np.asarray(x, dtype=float)
    sd = float(x.std(ddof=1)) if x.size > 1 else 0.0
    sd = 0.0 if sd < 1e-9 * max(1.0, abs(float(x.mean()))) else sd
    return dict(mean=float(x.mean()), median=float(np.median(x)),
                std=sd, p95=float(np.percentile(x, 95)))
