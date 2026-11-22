#!/usr/bin/env python3
"""Historical scenario R: replay injection in ns-3. One outsider per collector area records honest frames and re-sends
byte-identical copies (valid link MAC), half from the current window and half from earlier windows, at
replayRate frames/s per area. Same topology, parameters, seeds and calibration as historical scenario A (100 sensors,
one report per 10 s). 30 RNG runs per configuration. For final hardware-calibrated R use campaign_hw_all.py."""
import sys, time, itertools
from multiprocessing import Pool
import campaign as C0
def jobs():
    J = []
    for rr, v, r in itertools.product([0, 1, 5, 10, 20], ["msm", "ind", "base"], C0.SEEDS):
        J.append(dict(tag="R", variant=v, run=r, nSensors=100, reportInterval=10, simTime=330,
                      replayRate=rr, replayOldFrac=0.5, attackStart=60))
    return J
if __name__ == "__main__":
    J = jobs(); print(len(J), "jobs", flush=True); done = 0; t0 = time.time()
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 2) as p:
        for _ in p.imap_unordered(C0.run, J):
            done += 1
            if done % 50 == 0: print(f"{done}/{len(J)} elapsed {time.time()-t0:.0f}s", flush=True)
    print("ALL DONE", flush=True)
