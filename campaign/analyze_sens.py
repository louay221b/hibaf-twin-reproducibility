#!/usr/bin/env python3
"""Analyze supplementary sensitivity runs from per-run summary.csv files.

The archived paper data are not generated here. Provide the v33 baseline CSV
explicitly. Only collected raw runs are analyzed; missing inputs raise errors.
"""
import argparse
import csv
import glob
import math
from pathlib import Path
from statistics import mean, stdev

COLUMNS = ("pdr", "syncSuccess", "e2eMean", "e2eP95", "colCpuUtil", "hecmPerVerified")
TC = 2.045  # Student-t df=29, two-sided 95% (30 seeds)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def describe(rows, label):
    if len(rows) != 30:
        raise ValueError(f"{label}: expected 30 seed rows, got {len(rows)}")
    print(f"{label} (n=30)")
    for metric in COLUMNS:
        values = [float(x[metric]) for x in rows]
        average = mean(values)
        halfwidth = TC * stdev(values) / math.sqrt(len(values))
        print(f"  {metric}: {average:.6f} +/- {halfwidth:.6f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=Path("runs"))
    ap.add_argument("--baseline-csv", type=Path, required=True,
                    help="Revised 30-seed baseline, all_runs_hwPi_beaconfix.csv")
    args = ap.parse_args()
    if not args.baseline_csv.is_file():
        ap.error(f"Missing revised baseline CSV: {args.baseline_csv}")
    baseline = read_rows(args.baseline_csv)
    paths = glob.glob(str(args.runs / "*" / "summary.csv"))
    if not paths:
        ap.error(f"No per-run sensitivity summary.csv files under {args.runs}")
    recent = [read_rows(p)[0] for p in paths]
    def pick(data, tag, variant, **attrs):
        rows = [r for r in data if r["tag"] == tag and r["variant"] == variant]
        for k, v in attrs.items():
            rows = [r for r in rows if r.get(k) == str(v)]
        return rows

    for sc, old, attrs in (
        ("A2", "H_A2_hwPi", {"reportInterval": "0.25"}),
        ("E", "H_E_hwPi", {"attackers": "10"})):
        for variant in ("msm", "base", "ind"):
            describe(pick(baseline, old, variant, **attrs), f"{sc} {variant} BE=0.10 baseline")
            for value in ("0.86", "1.19"):
                describe(pick(recent, f"S1_{sc}_be{value}", variant),
                         f"{sc} {variant} BE={value} sensitivity")
    for sc, old, attrs, new in (
        ("A100", "H_A_hwPi", {"nSensors": "100"}, "S2_A100_th025"),
        ("A500", "H_A_hwPi", {"nSensors": "500"}, "S2_A500_th025"),
        ("A2", "H_A2_hwPi", {"reportInterval": "0.25"}, "S2_A2_th025"),
        ("E", "H_E_hwPi", {"attackers": "10"}, "S2_E_th025")):
        describe(pick(baseline, old, "ind", **attrs), f"{sc} B1 theta=1 baseline")
        describe(pick(recent, new, "ind"), f"{sc} B1 theta=0.25 sensitivity")


if __name__ == "__main__":
    main()
