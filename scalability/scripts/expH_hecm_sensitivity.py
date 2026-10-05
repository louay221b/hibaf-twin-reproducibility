"""Experiment H -- platform-independent HECM sensitivity (analytical sensitivity)."""
import csv, math
from common import *

N_LIST = [100, 500, 1000, 2000, 4000]
D_LIST = [5, 10, 30, 60]                      # Delta_w in seconds
T_US   = [250, 500, 1000, 2000, 3000, 4000, 5000, 10000]   # T_HECM in microseconds (0.25..10 ms)

# ---- full grid -------------------------------------------------------------
rows = []
for D in D_LIST:
    for N in N_LIST:
        C = c_dt(N)
        for t in T_US:
            proc_us = C * t
            rows.append({
                "N_site": N, "Delta_w_s": D, "T_HECM_ms": t / 1000,
                "C_DT_HECM": C,
                "T_proc_ms": proc_us / 1000,
                "utilization_U": round(proc_us / window_us(D), 9),
                "feasible": int(proc_us <= window_us(D)),
                "R_required_HECM_per_s": round(C / D, 6),
                "T_HECM_max_ms": round(1000 * D / C, 9),
            })
with open(CSV / "expH_full_grid.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

# ---- T_HECM_max table (long + wide) ---------------------------------------
long_rows = [{"N_site": N, "Delta_w_s": D, "C_DT_HECM": c_dt(N),
              "T_HECM_max_ms": round(1000 * D / c_dt(N), 9)} for N in N_LIST for D in D_LIST]
with open(CSV / "expH_tmax_long.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(long_rows[0])); w.writeheader(); w.writerows(long_rows)
with open(CSV / "expH_tmax_table.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["N_site", "C_DT_HECM"] + [f"Tmax_ms@Delta_w={D}s" for D in D_LIST])
    for N in N_LIST:
        w.writerow([N, c_dt(N)] + [f"{1000 * D / c_dt(N):.4f}" for D in D_LIST])

# ---- maximum feasible N vs T_HECM (dense curve + the 8 sweep points) --------
def n_max(D, t_us):
    cap = window_us(D) // t_us            # max number of HECM that fit in the window
    return (cap - 2) // 2 if cap >= 2 else ""   # 2N+2 <= cap

dense = sorted(set(int(round(10 ** (2 + i * (math.log10(20000) - 2) / 119))) for i in range(120)) | set(T_US))
nrows = []
for D in D_LIST:
    for t in dense:
        nrows.append({"Delta_w_s": D, "T_HECM_ms": t / 1000, "N_max_feasible": n_max(D, t),
                      "in_sweep_set": int(t in T_US)})
with open(CSV / "expH_nmax_curve.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(nrows[0])); w.writeheader(); w.writerows(nrows)
with open(CSV / "expH_nmax_table.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["T_HECM_ms"] + [f"N_max@Delta_w={D}s" for D in D_LIST])
    for t in T_US:
        w.writerow([t / 1000] + [n_max(D, t) for D in D_LIST])
print("H: rows", len(rows), "| nmax rows", len(nrows))
