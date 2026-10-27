#!/usr/bin/env python3
"""HiBaF v2 ns-3 campaign runner: scenarios A-F, 30 independent RNG runs per configuration.
Each run writes its own summary.csv under runs/<job>/; analyze.py consolidates them."""
import itertools, os, subprocess, sys, json, time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = os.environ.get("HIBAF_NS3_BIN", str(ROOT / "ns-3.49" / "build" / "scratch" / "hibaf" / "ns3.49-hibaf-sim-optimized"))
OUT = os.environ.get("HIBAF_RUNS_DIR", str(ROOT / "runs"))
SEEDS = range(1, 31)

def jobs():
    J = []
    def add(tag, variants, grid, base):
        keys = list(grid)
        for vals in itertools.product(*[grid[k] for k in keys]):
            for v in variants:
                for r in SEEDS:
                    a = dict(base); a.update(zip(keys, vals)); a.update(variant=v, run=r, tag=tag)
                    J.append(a)
    # A: scalability (light realistic load: one report / 10 s per sensor)
    add("A", ["msm", "msmfix", "base", "ind", "sym"], {"nSensors": [10, 50, 100, 250, 500]},
        dict(reportInterval=10, simTime=330))
    # A2: traffic intensity (network load), 100 sensors in 4 ponds
    add("A2", ["msm", "base", "ind", "sym"], {"reportInterval": [10, 2, 1, 0.5, 0.25]},
        dict(nSensors=100, simTime=70, warmup=20, drain=10))
    # B: degradation — natural loss via distance; external WAN loss
    add("B1", ["msm", "ind"], {"radius": [25, 50, 75, 100, 125, 150, 175]}, dict(nSensors=100, reportInterval=10, simTime=330))
    add("B2", ["msm", "ind"], {"wanLoss": [0.01, 0.05, 0.10]}, dict(nSensors=100, reportInterval=10, simTime=330))
    # C: digital-twin synchronisation vs WAN delay / rate
    add("C", ["msm", "ind"], {"wanDelayMs": [10, 40, 150, 300], "wanRate": ["10Mbps", "128kbps"]},
        dict(nSensors=100, reportInterval=10, simTime=330))
    # D: security events — insider attackers (invalid signatures), outsider forgeries, defenses on/off
    add("D", ["msm", "base"], {"attackers": [1, 4, 10], "defenses": [1, 0]},
        dict(nSensors=100, reportInterval=10, attackRate=0.5, outsiderRate=2, attackStart=60, simTime=330))
    # E: MSM effectiveness / ablation under invalid-report stress (pre-revocation worst case)
    add("E", ["msm", "msmfix", "base", "ind"], {"attackers": [0, 1, 5, 10]},
        dict(nSensors=100, reportInterval=0.5, attackRate=2, defenses=0, attackStart=20, warmup=20, drain=10, simTime=70))
    # F: constrained operation — alarm burst, WAN outage, narrow WAN
    add("F_burst", ["msm", "ind"], {"burstInterval": [1.0]},
        dict(nSensors=100, reportInterval=10, burstStart=120, burstDur=60, simTime=330))
    add("F_burst_aq", ["msm", "ind"], {"burstInterval": [1.0]},
        dict(nSensors=100, reportInterval=10, burstStart=120, burstDur=60, quotaMinInterval=1.0, simTime=330))
    add("F_outage", ["msm", "ind"], {"wanOutageDur": [30]},
        dict(nSensors=100, reportInterval=10, wanOutageStart=120, simTime=330))
    add("F_lowwan", ["msm", "ind"], {"wanRate": ["64kbps"]}, dict(nSensors=100, reportInterval=10, simTime=330))
    return J

def name(a):
    return "_".join(f"{k}-{a[k]}" for k in sorted(a))

def run(a):
    d = os.path.join(OUT, name(a))
    if os.path.exists(os.path.join(d, "summary.csv")):
        return 0
    os.makedirs(d, exist_ok=True)
    args = [BIN] + [f"--{k}={v}" for k, v in a.items()] + [f"--out={d}"]
    if a["tag"] == "C" and a["run"] == 1:
        args.append("--perReport=1")
    t = time.time()
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        open(os.path.join(d, "error.txt"), "w").write(r.stderr[-4000:])
    return time.time() - t

if __name__ == "__main__":
    if not Path(BIN).is_file():
        raise SystemExit(f"ns-3 binary not found: {BIN}. Build ns-3.49 or set HIBAF_NS3_BIN.")
    J = jobs()
    # heavy jobs first for better load balance
    J.sort(key=lambda a: -(a.get("nSensors", 100) / a.get("reportInterval", 10)))
    print(len(J), "jobs", flush=True)
    done = 0; t0 = time.time()
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 2) as p:
        for dt in p.imap_unordered(run, J):
            done += 1
            if done % 50 == 0:
                print(f"{done}/{len(J)} elapsed {time.time()-t0:.0f}s", flush=True)
    print("ALL DONE", flush=True)
