"""Experiment F: full_hierarchy_counts_only.

Operation counts DERIVED from Algorithms 1-3 and the window protocol; no timing value is used.
Counts are symbolic in n (reports per pond), P (ponds), N = P*n and are evaluated for the configured grid.
"""
from __future__ import annotations

import pandas as pd

FIELDS = ["hecm", "hadd", "h3", "h2", "kdf", "aead_enc", "aead_dec", "sig_ttp_gen", "sig_ttp_ver"]
DATA_FIELDS = FIELDS[:7]
HDR = {"hecm": "HECM", "hadd": "HAdd", "h3": "$H_3$", "h2": "$H_2$", "kdf": "KDF",
       "aead_enc": "AEAD-enc", "aead_dec": "AEAD-dec",
       "sig_ttp_gen": r"Sig$_{\mathrm{TTP}}$.Gen", "sig_ttp_ver": r"Sig$_{\mathrm{TTP}}$.Ver"}
VARS = ("N", "P", "n", "1")
EXPLICIT = "explicit"
CONDITIONAL = "conditional_ttp_same_genus2_schnorr"


def E(c=0, n=0, P=0, N=0):
    return {"1": c, "n": n, "P": P, "N": N}


def eadd(a, b):
    return {k: a[k] + b[k] for k in a}


def eval_e(a, v):
    return a["1"] + a["n"] * v["n"] + a["P"] * v["P"] + a["N"] * v["N"]


def estr(a):
    out = ""
    for k in VARS:
        c = a[k]
        if c == 0:
            continue
        sign = "-" if c < 0 else ("+" if out else "")
        mag = abs(c)
        body = str(mag) if k == "1" else (k if mag == 1 else f"{mag}{k}")
        out += f"{sign}{body}"
    return out or "0"


def C(**kw):
    return {f: kw.get(f, E()) for f in FIELDS}


def cadd(a, b):
    return {f: eadd(a[f], b[f]) for f in FIELDS}


def cvar(var, a):
    return {f: (E(**{var: a[f]["1"]}) if var != "1" else a[f]) for f in FIELDS}


def is_zero(c):
    return all(estr(c[f]) == "0" for f in FIELDS)


SIG_GEN_D = C(hecm=E(1), h3=E(1), h2=E(1))
SIG_VER_D = C(hecm=E(2), hadd=E(1), h3=E(1), h2=E(1))
REP_GEN = C(hecm=E(1), h2=E(1))
REP_VER = C(hecm=E(2), hadd=E(1), h2=E(1))
TTP_VER = C(sig_ttp_ver=E(1))
TTP_GEN = C(sig_ttp_gen=E(1))


def conditional(c):
    out = dict(c)
    for f in FIELDS:
        add = c["sig_ttp_ver"]["1"] * SIG_VER_D[f]["1"] + c["sig_ttp_gen"]["1"] * SIG_GEN_D[f]["1"]
        out[f] = eadd(c[f], E(c=add))
    out["sig_ttp_gen"] = E()
    out["sig_ttp_ver"] = E()
    return out


def components(cp):
    rows = []
    add = lambda *a: rows.append(a)
    RL = "verify TTP-signed RL_w (Sig_TTP.Ver, generic primitive)"
    add("sensor", "data", "per report", "N", "report signature generation", REP_GEN)
    add("sensor", "data", "per report", "N", "per-window key derivation KDF", C(kdf=E(1)))
    add("sensor", "data", "per report", "N", "AEAD encryption", C(aead_enc=E(1)))
    add("sensor", "control", "per sensor per window", "N", "verify station beacon signature", SIG_VER_D)
    if cp["sensor_verifies_rl_signature"]:
        add("sensor", "control", "per sensor per window", "N", RL, TTP_VER)
    add("pond", "data", "per window", "P", "report fingerprints d_i=H3(report)", C(h3=E(n=1)))
    add("pond", "data", "per window", "P", "challenge e_i recomputation", C(h2=E(n=1)))
    add("pond", "data", "per window", "P", "batch-verification-only cost C_batch", C(hecm=E(1, n=2), hadd=E(-1, n=2)))
    add("pond", "data", "per window", "P", "collector container signature generation", SIG_GEN_D)
    add("pond", "control", "per pond per window", "P", "verify station beacon signature", SIG_VER_D)
    if cp["pond_verifies_rl_signature"]:
        add("pond", "control", "per pond per window", "P", RL, TTP_VER)
    add("station", "data", "per window", "1", "verify each collector signature", cvar("P", SIG_VER_D))
    add("station", "data", "per window", "1", "site-container signature generation", SIG_GEN_D)
    add("station", "control", "per window", "1", "beacon signature generation", SIG_GEN_D)
    if cp["station_verifies_rl_signature"]:
        add("station", "control", "per window", "1", RL, TTP_VER)
    add("dt", "data", "per window", "1", "verify station signature", SIG_VER_D)
    add("dt", "data", "per window", "1", "independent sensor-signature verification", cvar("N", REP_VER))
    add("dt", "data", "per window", "1", "per-window key derivation KDF", cvar("N", C(kdf=E(1))))
    add("dt", "data", "per window", "1", "AEAD decryption", cvar("N", C(aead_dec=E(1))))
    if cp["dt_verifies_rl_signature"]:
        add("dt", "control", "per window", "1", RL, TTP_VER)
    add("ttp", "control", "per window", "1", "RL_w signature generation", TTP_GEN)
    return rows


STATED = {
    "sensor": C(hecm=E(1), h3=E(1), aead_enc=E(1)),
    "pond": C(hecm=E(1, n=2), hadd=E(-1, n=2), h3=E(n=1)),
    "station": C(hecm=E(1, P=2), h3=E(1, P=1)),
    "dt": C(hecm=E(2, N=2), aead_dec=E(N=1)),
}


def _tier_sum(rows, tier, plane):
    tot = C()
    for r in rows:
        if r[0] == tier and r[1] == plane:
            tot = cadd(tot, r[5])
    return tot


def run(cfg, psets=None, skip=None):
    cp = cfg["hierarchy"]["control_plane"]
    rows = components(cp)
    comp_rows = [dict(experiment="F_full_hierarchy_counts_only", tier=r[0], plane=r[1], unit=r[2],
                      instances_var=r[3], component=r[4], **{f: estr(r[5][f]) for f in FIELDS}) for r in rows]
    tiers = ["sensor", "pond", "station", "dt", "ttp"]
    meta = {}
    for r in rows:
        meta.setdefault((r[0], r[1]), (r[2], r[3]))

    def variants(tier, plane):
        ex = _tier_sum(rows, tier, plane)
        if is_zero(ex):
            return []
        out = [(EXPLICIT, ex)]
        cond = conditional(ex)
        if plane == "control" and any(estr(ex[f]) != "0" for f in ("sig_ttp_gen", "sig_ttp_ver")):
            out.append((CONDITIONAL, cond))
        return out

    sym = []
    for tier in tiers:
        for plane in ("data", "control"):
            for var, tot in variants(tier, plane):
                unit, inst = meta[(tier, plane)]
                sym.append(dict(experiment="F_full_hierarchy_counts_only", variant=var, tier=tier, plane=plane,
                                unit=unit, instances_var=inst, **{f: estr(tot[f]) for f in FIELDS}))
    num = []
    inst_val = lambda var, P, n: {"N": P * n, "P": P, "1": 1}[var]
    for P in cfg["hierarchy"]["P"]:
        for n in cfg["hierarchy"]["n_per_pond"]:
            v = dict(n=n, P=P, N=P * n)
            for tier in tiers:
                for plane in ("data", "control"):
                    for var, tot in variants(tier, plane):
                        unit, ivar = meta[(tier, plane)]
                        k = inst_val(ivar, P, n)
                        per = {f: eval_e(tot[f], v) for f in FIELDS}
                        num.append(dict(experiment="F_full_hierarchy_counts_only", variant=var, P=P, n_per_pond=n,
                                        N_site=P * n, tier=tier, plane=plane, instances=k,
                                        **{f"per_instance_{f}": per[f] for f in FIELDS},
                                        **{f"aggregate_{f}": per[f] * k for f in FIELDS}))
    num = pd.DataFrame(num)

    v = dict(n=100, P=50, N=5000)
    rec = []
    for tier in ("sensor", "pond", "station", "dt"):
        der = _tier_sum(rows, tier, "data")
        st = STATED[tier]
        items = [("hecm", st["hecm"], der["hecm"]), ("hadd", st["hadd"], der["hadd"]),
                 ("hash_class (H3+H2+KDF; stated formulas have one generic hash)",
                  st["h3"], eadd(eadd(der["h3"], der["h2"]), der["kdf"])),
                 ("aead_enc", st["aead_enc"], der["aead_enc"]), ("aead_dec", st["aead_dec"], der["aead_dec"])]
        for name, s_, d_ in items:
            a_, b_ = eval_e(s_, v), eval_e(d_, v)
            rec.append(dict(tier=tier, field=name, stated_expression=estr(s_), derived_expression=estr(d_),
                            stated_at_sample=a_, derived_at_sample=b_,
                            difference_derived_minus_stated=b_ - a_, sample_point="n=100, P=50, N=5000"))
    rec = pd.DataFrame(rec)
    rec = rec[(rec.stated_expression != "0") | (rec.derived_expression != "0")]
    return dict(f_components=pd.DataFrame(comp_rows), f_symbolic=pd.DataFrame(sym), f_numeric=num,
                f_reconciliation=rec)


def latex_tables(res, cfg):
    """The manuscript-specific LaTeX tables are generated in the full package.
    This public helper returns an empty mapping when only numerical CSVs are needed."""
    return {}
