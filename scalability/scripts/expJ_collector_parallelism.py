"""Experiment J -- limited pond-collector parallelism (platform-independent workload projection, HECM counts only).
Model: collectors processed in waves of k concurrent collectors; station then DT run strictly after
(no pipelining) -- a conservative critical-path model."""
import csv
from common import *

P_LIST = [10, 50, 100, 200]
n_LIST = [10, 20, 50]
K_BASE = [1, 2, 4, 8, 16]

rows = []
for P in P_LIST:
    ks = sorted(set([k for k in K_BASE if k <= P] + [P]))      # drop k>P, de-duplicate, always include k=P
    for n in n_LIST:
        N = P * n
        Cc, Cs, Cd = c_collector(n), c_station(P), c_dt(N)
        agg = P * Cc + Cs + Cd
        crit_full = 1 * Cc + Cs + Cd                           # k = P : single wave
        for k in ks:
            waves = ceil_div(P, k)
            crit = waves * Cc + Cs + Cd
            rows.append({
                "P": P, "n_per_pond": n, "N_site": N, "k_collectors": k, "collector_waves": waves,
                "C_collector": Cc, "C_station": Cs, "C_DT": Cd,
                "C_aggregate_sequential": agg,
                "C_critical_path": crit,
                "reduction_vs_sequential_pct": round(100 * (1 - crit / agg), 4),
                "excess_over_full_parallel_HECM": crit - crit_full,
                "excess_over_full_parallel_pct": round(100 * (crit - crit_full) / crit_full, 4),
                "DT_share_of_critical_path_pct": round(100 * Cd / crit, 4),
            })
with open(CSV / "expJ_collector_parallelism.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

# diminishing returns: marginal gain of each step in k within a configuration
drows = []
for P in P_LIST:
    for n in n_LIST:
        sub = [r for r in rows if r["P"] == P and r["n_per_pond"] == n]
        sub.sort(key=lambda r: r["k_collectors"])
        prev = None
        for r in sub:
            if prev is None:
                mg, mgp = 0, 0.0
            else:
                mg = prev["C_critical_path"] - r["C_critical_path"]
                mgp = round(100 * mg / r["C_aggregate_sequential"], 4)
            drows.append({"P": P, "n_per_pond": n, "N_site": r["N_site"], "k_collectors": r["k_collectors"],
                          "C_critical_path": r["C_critical_path"],
                          "marginal_HECM_saved_vs_previous_k": mg,
                          "marginal_saved_pct_of_aggregate": mgp,
                          "cumulative_reduction_vs_sequential_pct": r["reduction_vs_sequential_pct"],
                          "remaining_gap_to_full_parallel_pct": r["excess_over_full_parallel_pct"]})
            prev = r
with open(CSV / "expJ_diminishing_returns.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(drows[0])); w.writeheader(); w.writerows(drows)
print("J: rows", len(rows), "| diminishing-returns rows", len(drows))
