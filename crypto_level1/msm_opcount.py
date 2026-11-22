"""Analytical group-operation estimates (additions + doublings, unit cost) for 128-bit-security
genus-2 parameters (|q| ~ 254 bits). These are TEXTBOOK COST FORMULAS, not measurements."""
import math
b = 254
def wnaf_single(bits, w=4):   # one variable-base scalar mult, w-NAF
    return bits + bits/(w+1) + 2**(w-2)
def straus(terms, w=4):        # interleaved w-NAF, shared doublings
    return b + sum(bits/(w+1) + 2**(w-2) for bits in terms)
def pippenger(terms):
    N = len(terms); best = None
    for c in range(2, 18):
        cost = math.ceil(b/c)*(N + 2**(c+1)) + b
        best = cost if best is None or cost < best else best
    return best
print(f"{'n':>4} {'indiv(2n wNAF)':>15} {'indiv Shamir':>13} {'Base batch':>11} {'Straus':>9} {'Pippenger':>10} {'Straus,short a':>15} {'best MSM speed-up vs indiv-Shamir':>34}")
for n in [1, 10, 50, 100, 250, 500, 1000]:
    indiv = n*(2*wnaf_single(b)+1)
    shamir = n*(straus([b, b]))
    base = (2*n+1)*wnaf_single(b) + 2*n
    full = [b]*(2*n+1)
    st = straus(full); pip = pippenger(full)
    short = [b] + [128]*n + [b]*n        # alpha_i short (128-bit) on U_i terms, a_i e_i full on P_i
    st_s = straus(short)
    best = min(st, pip, st_s)
    print(f"{n:>4} {indiv:>15.0f} {shamir:>13.0f} {base:>11.0f} {st:>9.0f} {pip:>10.0f} {st_s:>15.0f} {shamir/best:>34.2f}")
