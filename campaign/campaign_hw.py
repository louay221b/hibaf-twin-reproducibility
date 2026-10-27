#!/usr/bin/env python3
"""Recalibration with the MEASURED ESP32 cost (ESP32-D0WD-V3, 240 MHz, ESP-IDF v5.4.1, hw_bench.c,
median of 7: 102.666 ms per 254-bit scalar multiplication; hardware_harness/results/esp32_results.txt) for sensors,
and the still-EMULATED Cortex-A72 range (1.12 / 2.78 ms) for collectors and station. Same scenarios,
variants, seeds and parameters as the H_* recalibration in campaign_rev.py."""
import sys, time, itertools
from multiprocessing import Pool
import campaign as C0
PLAT = {"hwLow": dict(tHecmSensor=102.666, tHecmCol=1.12, tHecmSt=1.12),
        "hwHigh": dict(tHecmSensor=102.666, tHecmCol=2.78, tHecmSt=2.78)}
def jobs():
    J = []
    def add(tag, variants, grid, base):
        keys = list(grid)
        for vals in itertools.product(*[grid[k] for k in keys]):
            for v in variants:
                for r in C0.SEEDS:
                    a = dict(base); a.update(zip(keys, vals)); a.update(variant=v, run=r, tag=tag); J.append(a)
    for pk, pv in PLAT.items():
        add("H_A_" + pk, ["msm", "base", "ind"], {"nSensors": [100, 500]}, dict(reportInterval=10, simTime=330, **pv))
        add("H_A2_" + pk, ["msm", "base", "ind"], {"reportInterval": [0.25]}, dict(nSensors=100, simTime=70, warmup=20, drain=10, **pv))
        add("H_E_" + pk, ["msm", "msmfix", "base", "ind"], {"attackers": [0, 10]},
            dict(nSensors=100, reportInterval=0.5, attackRate=2, defenses=0, attackStart=20, warmup=20, drain=10, simTime=70, **pv))
    return J
if __name__ == "__main__":
    if not C0.Path(C0.BIN).is_file():
        raise SystemExit(f"ns-3 binary not found: {C0.BIN}. Build ns-3.49 or set HIBAF_NS3_BIN.")
    J = jobs(); J.sort(key=lambda a: -(a.get("nSensors", 100) / a.get("reportInterval", 10)))
    print(len(J), "jobs", flush=True); done = 0; t0 = time.time()
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 2) as p:
        for _ in p.imap_unordered(C0.run, J):
            done += 1
            if done % 25 == 0: print(f"{done}/{len(J)} elapsed {time.time()-t0:.0f}s", flush=True)
    print("ALL DONE", flush=True)
