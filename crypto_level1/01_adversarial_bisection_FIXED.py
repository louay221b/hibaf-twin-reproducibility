import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

SEED = 20260603
N_WINDOWS = 10_000
BATCH_SIZES = [10, 50, 100, 500]
INVALID_RATES = [0.00, 0.01, 0.05, 0.10, 0.25]
REPLAY_SHARES = [0.00, 0.10, 0.25, 0.50]

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
RESULTS.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)

def recursive_bisection_cost(invalid):
    invalid = np.asarray(invalid, dtype=np.int8)
    n = len(invalid)
    if n == 0:
        return 0, 0, 0, 0

    prefix = np.zeros(n + 1, dtype=np.int32)
    prefix[1:] = np.cumsum(invalid)

    def invalid_count(left, right):
        return prefix[right] - prefix[left]

    def recurse(left, right):
        m = right - left
        if m == 1:
            return 2, 1, 0, 1

        hecm = 2 * m + 1
        hadd = 2 * m - 1
        batch_tests = 1
        individual_tests = 0

        if invalid_count(left, right) == 0:
            return hecm, hadd, batch_tests, individual_tests

        mid = left + m // 2
        a = recurse(left, mid)
        b = recurse(mid, right)
        return (hecm+a[0]+b[0], hadd+a[1]+b[1], batch_tests+a[2]+b[2], individual_tests+a[3]+b[3])

    return recurse(0, n)

def run_mixed_validity():
    rng = np.random.default_rng(SEED)
    rows = []
    for n in BATCH_SIZES:
        ref = 2 * n
        for mu in INVALID_RATES:
            hs, ads, bt, it = [], [], [], []
            for _ in range(N_WINDOWS):
                invalid = rng.random(n) < mu
                h, a, b, i = recursive_bisection_cost(invalid)
                hs.append(h); ads.append(a); bt.append(b); it.append(i)
            hs = np.asarray(hs, dtype=float)
            rows.append({
                "n": n,
                "invalid_rate_pct": 100*mu,
                "mean_hecm": hs.mean(),
                "mean_hadd": np.mean(ads),
                "mean_batch_tests": np.mean(bt),
                "mean_individual_tests": np.mean(it),
                "overhead_vs_individual_pct": 100*(hs.mean()-ref)/ref,
                "median_hecm": np.median(hs),
                "std_hecm": np.std(hs),
                "p95_hecm": np.percentile(hs, 95),
            })
    return pd.DataFrame(rows)

def run_replay_filtering():
    rng = np.random.default_rng(SEED)
    rows = []
    for n in BATCH_SIZES:
        for replay_share in REPLAY_SHARES:
            p = [
                (1-replay_share)*0.95, # normal valid
                replay_share/4,       # a cross-window
                replay_share/4,       # b accepted same-window replay
                replay_share/4,       # c exact duplicate
                replay_share/4,       # d modified reused nonce
                (1-replay_share)*0.05 # e invalid unseen nonce
            ]
            filtered, baseline = [], []
            for _ in range(N_WINDOWS):
                classes = rng.choice(6, size=n, p=p)

                keep = np.isin(classes, [0,4,5])
                fclasses = classes[keep]
                finvalid = np.isin(fclasses, [4,5])
                filtered.append(recursive_bisection_cost(finvalid)[0])

                binvalid = np.isin(classes, [1,4,5])
                baseline.append(recursive_bisection_cost(binvalid)[0])

            mf, mb = np.mean(filtered), np.mean(baseline)
            rows.append({
                "n": n,
                "replay_share_pct": 100*replay_share,
                "mean_hecm_B4": mb,
                "mean_hecm_filtered": mf,
                "hecm_saving_pct": 100*(1-mf/mb),
            })
    return pd.DataFrame(rows)

mixed = run_mixed_validity()
replay = run_replay_filtering()
mixed.to_csv(RESULTS/"mixed_fixed.csv", index=False)
replay.to_csv(RESULTS/"replay_fixed.csv", index=False)

fig, axes = plt.subplots(1,2,figsize=(12,4.8))
ax = axes[0]
for n in BATCH_SIZES:
    d = mixed[mixed["n"]==n]
    ax.plot(d["invalid_rate_pct"], d["overhead_vs_individual_pct"], marker="o", linewidth=1.8, label=fr"$n={n}$")
ax.set_title("(a) Mixed-validity overhead")
ax.set_xlabel("Invalid-report probability (%)")
ax.set_ylabel("HECM overhead vs. individual verification (%)")
ax.set_xticks([0,1,5,10,25])
ax.set_yscale("log")
ax.grid(True, which="both", alpha=0.3)
ax.legend()

ax = axes[1]
for n in BATCH_SIZES:
    d = replay[replay["n"]==n]
    ax.plot(d["replay_share_pct"], d["hecm_saving_pct"], marker="o", linewidth=1.8, label=fr"$n={n}$")
ax.set_title("(b) Replay-filtering savings")
ax.set_xlabel("Replay-related share of submitted reports (%)")
ax.set_ylabel("HECM workload reduction vs. B4 (%)")
ax.set_xticks([0,10,25,50])
ax.set_ylim(bottom=0)
ax.grid(True, alpha=0.3)
ax.legend()

plt.tight_layout()
plt.savefig(FIGURES/"fig5_adversarial_robustness_combined.pdf", bbox_inches="tight")
plt.savefig(FIGURES/"fig5_adversarial_robustness_combined.png", dpi=300, bbox_inches="tight")
print(mixed.to_string(index=False))
print(replay.to_string(index=False))
