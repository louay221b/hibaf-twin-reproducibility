"""Experiment I -- DT multi-worker processing capacity (idealized parallel-processing simulation).

Protocol ordering at the DT (Algorithm 3): the station-container signature sigma_ST is verified FIRST,
serially (2 HECM). The N per-report sensor-signature verifications are then independent and are
distributed over k idealized workers (2 HECM each, split as evenly as possible):

    C_DT_parallel(N,k) = 2 + 2*ceil(N/k)          (k = 1 gives the exact sequential count 2N+2)

Idealized: no scheduling / synchronization / memory / communication overhead. HECM counts only;
the generic T_HECM scenarios are NOT tied to any hardware."""
import csv
from common import *

N_LIST = [500, 1000, 2000, 4000]
D_LIST = [5, 10, 30, 60]
K_LIST = [1, 2, 4, 8]
T_US   = [500, 1000, 2000, 4000]               # generic T_HECM scenarios (ms: 0.5, 1, 2, 4)
SERIAL = 2                                     # station-signature verification (serial, before the report loop)

def c_dt_parallel(N, k):
    return SERIAL + 2 * ceil_div(N, k)

def k_min_new(N, win_us, t_us):
    """smallest k with (2 + 2*ceil(N/k)) * t <= window  <=>  ceil(N/k) <= m,  m = (cap-2)//2"""
    cap = win_us // t_us
    m = (cap - SERIAL) // 2
    return ceil_div(N, m) if m >= 1 else ""

def k_min_old(N, win_us, t_us):                # previous (superseded) model ceil((2N+2)/k), kept only for the change check
    cap = win_us // t_us
    return ceil_div(2 * N + 2, cap) if cap >= 1 else ""

rows = []
for N in N_LIST:
    for D in D_LIST:
        win = window_us(D)
        for t in T_US:
            kmin = k_min_new(N, win, t)
            t1 = c_dt_parallel(N, 1) * t
            for k in K_LIST:
                npw = ceil_div(N, k)
                C = c_dt_parallel(N, k)
                comp_us = C * t
                rows.append({
                    "N_site": N, "Delta_w_s": D, "T_HECM_ms": t / 1000, "workers_k": k,
                    "serial_HECM": SERIAL, "reports_per_worker": npw,
                    "C_DT_parallel_HECM": C,
                    "completion_time_ms": comp_us / 1000,
                    "utilization": round(comp_us / win, 9),
                    "deadline_met": int(comp_us <= win),
                    "min_workers_required": kmin,
                    "min_workers_within_k_grid": (kmin if (kmin != "" and kmin <= 8) else ">8"),
                    "model_speedup_vs_k1": round(t1 / comp_us, 6),   # idealized-model quantity, NOT measured
                })
with open(CSV / "expI_all_configs.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

mrows, crows = [], []
for N in N_LIST:
    for D in D_LIST:
        for t in T_US:
            kn, ko = k_min_new(N, window_us(D), t), k_min_old(N, window_us(D), t)
            mrows.append({"N_site": N, "Delta_w_s": D, "T_HECM_ms": t / 1000, "C_DT_HECM_sequential": c_dt(N),
                          "min_workers_required": kn})
            crows.append({"N_site": N, "Delta_w_s": D, "T_HECM_ms": t / 1000,
                          "k_min_new_2plus2ceil(N/k)": kn, "k_min_old_ceil((2N+2)/k)": ko, "changed": int(kn != ko)})
with open(CSV / "expI_min_workers.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(mrows[0])); w.writeheader(); w.writerows(mrows)
with open(CSV / "expI_min_workers_change_check.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(crows[0])); w.writeheader(); w.writerows(crows)
print("I: rows", len(rows), "| min-worker rows", len(mrows), "| min-worker values changed vs old model:", sum(c["changed"] for c in crows))
