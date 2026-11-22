#!/usr/bin/env python3
"""Rerun of campaign_hw2 (hwPi: ESP32 102.666 ms, Pi 4 1.706 ms) after the beacon fix: a sensor verifies
each window's beacon once (Algorithm 1); rebroadcast copies received while the first copy is being
verified are dropped. Same scenarios, variants, seeds and parameters. Output: runs_beaconfix/."""
import os, sys, time
from pathlib import Path
from multiprocessing import Pool
os.environ.setdefault("HIBAF_RUNS_DIR", str(Path(__file__).resolve().parents[1] / "runs_beaconfix"))
import campaign as C0
import campaign_hw2 as H
if __name__ == "__main__":
    J = H.jobs(); J.sort(key=lambda a: -(a.get("nSensors", 100) / a.get("reportInterval", 10)))
    print(len(J), "jobs", flush=True); done = 0; t0 = time.time()
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 2) as p:
        for _ in p.imap_unordered(C0.run, J):
            done += 1
            if done % 50 == 0: print(f"{done}/{len(J)} elapsed {time.time()-t0:.0f}s", flush=True)
    print("ALL DONE", flush=True)
