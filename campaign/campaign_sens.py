#!/usr/bin/env python3
"""Added sensitivity checks (does not replace the published campaign). Same scenarios/seeds/calibration as
campaign_hw3_beaconfix.py (hwPi). Patched simulator adds --indTheta (default keeps theta=1 for ind).
S1: back-end cost tHecmBe in {1.19, 0.86} ms for A2 and E(10 attackers), variants msm/base/ind.
S2: B1 (ind) audit rate theta=0.25 for A (100,500 sensors), A2, E(10 attackers)."""
import sys, time, itertools, os
from multiprocessing import Pool
import campaign as C0
HW = dict(tHecmSensor=102.666, tHecmCol=1.706, tHecmSt=1.706)
A2 = dict(nSensors=100, reportInterval=0.25, simTime=70, warmup=20, drain=10)
E10 = dict(nSensors=100, reportInterval=0.5, attackRate=2, defenses=0, attackStart=20, warmup=20, drain=10, simTime=70, attackers=10)
def jobs():
    J = []
    def add(tag, variants, base, **extra):
        for v in variants:
            for r in C0.SEEDS:
                a = dict(base); a.update(HW); a.update(extra); a.update(variant=v, run=r, tag=tag); J.append(a)
    for be in (1.19, 0.86):
        add(f"S1_A2_be{be}", ["msm", "base", "ind"], A2, tHecmBe=be)
        add(f"S1_E_be{be}", ["msm", "base", "ind"], E10, tHecmBe=be)
    add("S2_A100_th025", ["ind"], dict(nSensors=100, reportInterval=10, simTime=330), indTheta=0.25)
    add("S2_A500_th025", ["ind"], dict(nSensors=500, reportInterval=10, simTime=330), indTheta=0.25)
    add("S2_A2_th025", ["ind"], A2, indTheta=0.25)
    add("S2_E_th025", ["ind"], E10, indTheta=0.25)
    return J
if __name__ == "__main__":
    if not os.path.isfile(C0.BIN):
        raise SystemExit("Build the sensitivity simulator or set HIBAF_NS3_BIN")
    J = jobs(); J.sort(key=lambda a: -(a.get("nSensors", 100) / a.get("reportInterval", 10)))
    print(len(J), "jobs", flush=True); done = 0; t0 = time.time()
    with Pool(2) as p:
        for _ in p.imap_unordered(C0.run, J):
            done += 1
            if done % 20 == 0: print(f"{done}/{len(J)} elapsed {time.time()-t0:.0f}s", flush=True)
    print("ALL DONE", flush=True)