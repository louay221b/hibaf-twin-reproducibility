#!/usr/bin/env python3
"""Revision campaign (response to review): evidence-based revocation (D), Byzantine-collector
false accusations (Dz), shared 802.15.4 channel with/without beacon staggering (G), and
recalibration with emulated platform costs (H_*). 30 RNG runs per configuration."""
import sys, time
from multiprocessing import Pool
import campaign as C0
import itertools

# emulated platform costs (ms per 254-bit scalar multiplication), platform/platform_estimates.json
PLAT = {"emuLow": dict(tHecmSensor=65.82, tHecmCol=1.12, tHecmSt=1.12),
        "emuHigh": dict(tHecmSensor=98.74, tHecmCol=2.78, tHecmSt=2.78)}

def jobs():
    J = []
    def add(tag, variants, grid, base):
        keys = list(grid)
        for vals in itertools.product(*[grid[k] for k in keys]):
            for v in variants:
                for r in C0.SEEDS:
                    a = dict(base); a.update(zip(keys, vals)); a.update(variant=v, run=r, tag=tag)
                    J.append(a)
    add("Dev", ["msm", "base"], {"attackers": [1, 4, 10], "defenses": [1, 0]},
        dict(nSensors=100, reportInterval=10, attackRate=0.5, outsiderRate=2, attackStart=60, simTime=330, evidence=1))
    add("Dz", ["msm"], {"evidence": [0, 1]},
        dict(nSensors=100, reportInterval=10, byzNoticeRate=0.1, attackStart=60, simTime=330))
    add("G", ["msm"], {"pondSpacing": [50, 100, 200], "beaconStagger": [0, 0.04], "reportInterval": [10, 2]},
        dict(nSensors=100, sharedChannel=1, simTime=190, warmup=30, drain=15))
    for pk, pv in PLAT.items():
        add("H_A_" + pk, ["msm", "base", "ind"], {"nSensors": [100, 500]}, dict(reportInterval=10, simTime=330, **pv))
        add("H_A2_" + pk, ["msm", "base", "ind"], {"reportInterval": [0.25]},
            dict(nSensors=100, simTime=70, warmup=20, drain=10, **pv))
        add("H_E_" + pk, ["msm", "msmfix", "base", "ind"], {"attackers": [0, 10]},
            dict(nSensors=100, reportInterval=0.5, attackRate=2, defenses=0, attackStart=20, warmup=20, drain=10, simTime=70, **pv))
    return J

if __name__ == "__main__":
    J = jobs()
    J.sort(key=lambda a: -(a.get("nSensors", 100) / a.get("reportInterval", 10)))
    print(len(J), "jobs", flush=True)
    done = 0; t0 = time.time()
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 2) as p:
        for dt in p.imap_unordered(C0.run, J):
            done += 1
            if done % 50 == 0:
                print(f"{done}/{len(J)} elapsed {time.time()-t0:.0f}s", flush=True)
    print("ALL DONE", flush=True)
