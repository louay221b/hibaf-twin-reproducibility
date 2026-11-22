#!/usr/bin/env python3
"""Verify the final v33 run inventory without changing archived results."""
from pathlib import Path
import pandas as pd

tables = Path(__file__).resolve().parent / "tables"
a = pd.read_csv(tables / "all_runs_hwall.csv")
b = pd.read_csv(tables / "all_runs_hwPi_beaconfix.csv")
assert len(a) == 2670 and len(b) == 510
keys = ["variant", "nSensors", "run"]
aa, bb = a[a.tag == "HW_A"], b[b.tag == "H_A_hwPi"]
x = aa.merge(bb, on=keys, suffixes=("_a", "_b"), validate="one_to_one")
assert len(x) == 180
for c in (set(a.columns) & set(b.columns)) - set(keys) - {"tag", "tagx"}:
    left, right = x[c+"_a"], x[c+"_b"]
    assert (left.eq(right) | (left.isna() & right.isna())).all(), c
for frame in (a,b):
    # Check seed-level counts for every archived configuration using the reported configuration columns.
    cols = ["tag", "variant", "nSensors", "reportInterval", "radius", "wanDelayMs", "wanLoss", "wanRate",
            "attackers", "attackRate", "defenses", "outsiderRate", "burst", "outage", "evidence",
            "byzNoticeRate", "sharedChannel", "pondSpacing", "beaconStagger", "replayRate"]
    for _, group in frame.groupby(cols, dropna=False):
        assert len(group) == 30 and set(group.run) == set(range(1,31))
print("2,670 + 510 - 180 = 3,000 distinct runs (100 configurations)")
print("The 60 HW_BEsens runs are already included in the 2,670-run archive.")
