"""Shared constants/helpers. All arithmetic on times is done in integer microseconds
so that feasibility tests (<=) never suffer floating-point boundary errors.
No randomness is used anywhere in Experiments H, I, J (fully deterministic)."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "csv"
FIG = ROOT / "figures"
for _p in (CSV, FIG):
    _p.mkdir(parents=True, exist_ok=True)

def ceil_div(a, b):
    return -(-a // b)

def c_dt(N):            # exact manuscript DT data-path HECM count (as specified)
    return 2 * N + 2

def c_collector(n):     # complete all-valid pond data path: 2n+1 (batch) + 1 (container signature)
    return 2 * n + 2

def c_station(P):       # 2 per container verification + 1 site-container signature
    return 2 * P + 1

def window_us(delta_s):
    return delta_s * 10**6
