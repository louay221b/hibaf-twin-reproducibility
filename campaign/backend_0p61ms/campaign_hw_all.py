#!/usr/bin/env python3
"""Hardware-calibrated 0.61 ms/HECM back-end re-run of the paper's ns-3 scenarios.
Same scenarios, variants, seeds and parameters as campaign.py / campaign_rev.py / campaign_replay.py / be_sens.py;
Measured ESP32 102.666 ms and Raspberry Pi 4 1.706 ms per HECM; the back-end default is 0.61 ms/HECM,
with the dedicated 1.19 ms BEsens case overriding this default. Simulator: corrected hibaf-sim.cc with the beacon fix. Output: runs_hwall/ (tags prefixed HW_)."""
import itertools, os, sys, time
from pathlib import Path
from multiprocessing import Pool
os.environ.setdefault("HIBAF_RUNS_DIR", str(Path(__file__).resolve().parents[2] / "runs_hwall_0p61ms"))
import campaign as C0
HW = dict(tHecmSensor=102.666, tHecmCol=1.706, tHecmSt=1.706, tHecmBe=0.61)
def jobs():
    J = []
    def add(tag, variants, grid, base):
        keys = list(grid)
        for vals in itertools.product(*[grid[k] for k in keys]):
            for v in variants:
                for r in C0.SEEDS:
                    a = dict(base); a.update(HW); a.update(zip(keys, vals)); a.update(variant=v, run=r, tag="HW_" + tag); J.append(a)
    add("A", ["msm", "ind", "base", "sym"], {"nSensors": [10, 50, 100, 250, 500]}, dict(reportInterval=10, simTime=330))
    add("B1", ["msm", "ind"], {"radius": [25, 50, 75, 100, 125, 150, 175]}, dict(nSensors=100, reportInterval=10, simTime=330))
    add("B2", ["msm", "ind"], {"wanLoss": [0.01, 0.05, 0.10]}, dict(nSensors=100, reportInterval=10, simTime=330))
    add("Dev", ["msm", "base"], {"attackers": [1, 4, 10], "defenses": [1, 0]},
        dict(nSensors=100, reportInterval=10, attackRate=0.5, outsiderRate=2, attackStart=60, simTime=330, evidence=1))
    add("Dz", ["msm"], {"evidence": [0, 1]}, dict(nSensors=100, reportInterval=10, byzNoticeRate=0.1, attackStart=60, simTime=330))
    add("F_burst", ["msm", "ind"], {"burstInterval": [1.0]}, dict(nSensors=100, reportInterval=10, burstStart=120, burstDur=60, simTime=330))
    add("F_burst_aq", ["msm", "ind"], {"burstInterval": [1.0]},
        dict(nSensors=100, reportInterval=10, burstStart=120, burstDur=60, quotaMinInterval=1.0, simTime=330))
    add("F_outage", ["msm", "ind"], {"wanOutageDur": [30]}, dict(nSensors=100, reportInterval=10, wanOutageStart=120, simTime=330))
    add("G", ["msm"], {"pondSpacing": [50, 100, 200], "beaconStagger": [0, 0.04], "reportInterval": [10, 2]},
        dict(nSensors=100, sharedChannel=1, simTime=190, warmup=30, drain=15))
    add("R", ["msm", "ind", "base"], {"replayRate": [0, 1, 5, 10, 20]}, dict(nSensors=100, reportInterval=10, simTime=330, replayOldFrac=0.5, attackStart=60))
    add("BEsens", ["msm", "ind"], {"tHecmBe": [1.19]}, dict(nSensors=500, reportInterval=10, simTime=330))
    return J
if __name__ == "__main__":
    J = jobs(); J.sort(key=lambda a: -(a.get("nSensors", 100) / a.get("reportInterval", 10)))
    print(len(J), "jobs", flush=True); done = 0; t0 = time.time()
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 2) as p:
        for _ in p.imap_unordered(C0.run, J):
            done += 1
            if done % 100 == 0: print(f"{done}/{len(J)} elapsed {time.time()-t0:.0f}s", flush=True)
    print("ALL DONE", flush=True)
