"""Validate main 0.61 ms/HECM configuration grids without executing ns-3."""
import sys
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend_0p61ms"))
import campaign_hw_all as final_all
import campaign_hw2 as final_sub

def check(jobs, expected):
    assert len(jobs) == expected, (len(jobs), expected)
    keys = [tuple(sorted((str(k), str(v)) for k, v in j.items() if k != "run"))
            for j in jobs]
    sizes = Counter(keys)
    assert all(v == 30 for v in sizes.values()), "Every configuration must have 30 seeds"
    assert all(1 <= j["run"] <= 30 for j in jobs)
    for j in jobs:
        if j.get("tag") == "HW_BEsens":
            assert j.get("tHecmBe") == 1.19
        elif "tHecmBe" in j:
            assert j["tHecmBe"] == 0.61
    return len(sizes)

a, b = final_all.jobs(), final_sub.jobs()
assert check(a, 2670) == 89
assert check(b, 510) == 17
assert all(j.get("tHecmBe") == 0.61 for j in b)
print("PASS: 2,670 and 510 seed-level jobs, back-end cost 0.61 ms, BEsens 1.19 ms override")
print("NOTE: 3,000 distinct runs count removes 180 duplicate A cases; no simulations were run.")
