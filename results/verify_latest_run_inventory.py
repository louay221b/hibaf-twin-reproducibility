#!/usr/bin/env python3
"""Validate published 0.61 ms HiBaF-Twin CSVs without re-running ns-3.

The source tables contain 2,670 and 510 rows. Six configurations (180 runs)
are present in both; the canonical total is 3,000 distinct simulations.
The exact nine timing samples and old 0.10 ms per-run data are not verified here.
"""
import csv
import math
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean

TABLES = Path(__file__).resolve().parent / "tables"
CONFIG = ("tag", "variant", "nSensors", "reportInterval", "radius",
          "wanDelayMs", "wanLoss", "wanRate", "attackers", "attackRate",
          "defenses", "outsiderRate", "burst", "outage", "evidence",
          "byzNoticeRate", "sharedChannel", "pondSpacing",
          "beaconStagger", "replayRate")
COMPARE = ("tag", "variant", "nSensors", "reportInterval", "radius",
           "wanLoss", "wanDelayMs", "wanRate", "attackers", "defenses",
           "outage", "burst", "beaconStagger", "replayRate")
METRICS = ("e2eMean", "e2eP95", "e2eP99", "syncSuccess")
SEEDS = set(range(1, 31))

def read(name):
    with (TABLES / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))

def normalized(v):
    if v == "":
        return ""
    try:
        return Decimal(v).normalize()
    except InvalidOperation:
        return v

def cfg(row, columns):
    return tuple(normalized(row[c]) for c in columns)

def verify_groups(rows, count, configs, label):
    assert len(rows) == count, (label, "wrong number of rows", len(rows))
    groups = defaultdict(list)
    for row in rows:
        assert 0 <= float(row["pdr"]) <= 1, (label, "invalid pdr", row)
        assert 0 <= float(row["syncSuccess"]) <= 1, (label, "invalid sync", row)
        groups[cfg(row, CONFIG)].append(int(row["run"]))
    assert len(groups) == configs, (label, len(groups))
    assert all(len(v) == 30 and set(v) == SEEDS for v in groups.values()), label
    return groups

def main():
    a = read("all_runs_hwall_0p61.csv")
    b = read("all_runs_hwPi_beaconfix_0p61.csv")
    m = read("config_means_old_vs_new.csv")
    verify_groups(a, 2670, 89, "hwall")
    verify_groups(b, 510, 17, "hwPi")
    left = {(r["variant"], r["nSensors"], r["run"]): r
            for r in a if r["tag"] == "HW_A"}
    right = {(r["variant"], r["nSensors"], r["run"]): r
             for r in b if r["tag"] == "H_A_hwPi"}
    assert len(right) == 180 and set(right) <= set(left)
    for key in right:
        ra, rb = left[key], right[key]
        for c in ra:
            if c != "tag":
                assert normalized(ra[c]) == normalized(rb[c]), (key, c)
    grouped = defaultdict(list)
    for row in a:
        grouped[cfg(row, COMPARE)].append(row)
    assert len(m) == 80
    for row in m:
        entries = grouped[cfg(row, COMPARE)]
        assert len(entries) == 30, ("comparison config", cfg(row, COMPARE))
        for metric in METRICS:
            observed = mean(float(x[metric]) for x in entries)
            expected = float(row[metric + "_n"])
            assert math.isclose(observed, expected, rel_tol=1e-6, abs_tol=1e-6), (
                cfg(row, COMPARE), metric, observed, expected)
    print("PASS: 2,670 + 510 - 180 = 3,000 unique runs")
    print("PASS: 89 + 17 - 6 = 100 configurations, each with 30 distinct seeds")
    print("PASS: 180 overlapping A runs are numerically identical")
    print("PASS: 80 new-calibration summary rows agree with seed-level means")
    print("NOTE: old-calibration _o means and raw hardware timing samples not verified")

if __name__ == "__main__":
    main()
