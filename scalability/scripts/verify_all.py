"""Independent checks for Experiments H, I and J."""
import csv
import math
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "csv"


def rows(name):
    with open(CSV / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


# H
for r in rows("expH_full_grid.csv"):
    N = int(r["N_site"])
    D = float(r["Delta_w_s"])
    T = float(r["T_HECM_ms"])
    C = 2 * N + 2
    check(int(r["C_DT_HECM"]) == C, "H: C_DT mismatch")
    check(abs(float(r["T_proc_ms"]) - C * T) < 1e-9, "H: processing time mismatch")
    check(int(r["feasible"]) == int(C * T <= D * 1000), "H: feasibility mismatch")

# I
for r in rows("expI_all_configs.csv"):
    N = int(r["N_site"])
    k = int(r["workers_k"])
    D = float(r["Delta_w_s"])
    T = float(r["T_HECM_ms"])
    C = 2 + 2 * math.ceil(N / k)
    check(int(r["C_DT_parallel_HECM"]) == C, "I: critical-path HECM mismatch")
    check(int(r["deadline_met"]) == int(C * T <= D * 1000), "I: deadline mismatch")

# J
for r in rows("expJ_collector_parallelism.csv"):
    P = int(r["P"])
    n = int(r["n_per_pond"])
    k = int(r["k_collectors"])
    N = P * n
    Cc = 2 * n + 2
    Cs = 2 * P + 1
    Cd = 2 * N + 2
    waves = math.ceil(P / k)
    crit = waves * Cc + Cs + Cd
    seq = P * Cc + Cs + Cd
    check(int(r["C_critical_path"]) == crit, "J: critical path mismatch")
    check(int(r["C_aggregate_sequential"]) == seq, "J: sequential mismatch")

# paper-critical endpoints
j = [r for r in rows("expJ_collector_parallelism.csv") if r["P"] == "200" and r["n_per_pond"] == "20"]
by_k = {int(r["k_collectors"]): r for r in j}
check(int(by_k[1]["C_critical_path"]) == 16803, "J endpoint k=1")
check(int(by_k[200]["C_critical_path"]) == 8445, "J endpoint k=P")

print("VERIFICATION PASSED")
