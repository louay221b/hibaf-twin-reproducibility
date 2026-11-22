"""
Measured timing of genus-2 Jacobian arithmetic over F_p, p = 2^127 - 1 (the field size of
128-bit-security genus-2 proposals), Cantor's algorithm in pure Python.

PURPOSE: obtain *ratios* T_MSM(m) / T_HECM and T_indiv / T_HECM for the verification
algorithms used by HiBaF.  Absolute times are Python-on-x86 and are NOT representative of
an optimized implementation; ratios are driven by group-operation counts and are used to
scale the authors' platform HECM measurements in the ns-3 calibration.

The curve is a random squarefree quintic; its group order is NOT computed and no security
is claimed.  Scalars are 254-bit (subgroup size of a 128-bit-security genus-2 Jacobian).
"""
import random, time, json, math, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from g2toy import Jacobian, Fp2Poly

if os.environ.get("CURVE") == "hibaf":
    # certified HiBaF-Twin curve: y^2 = x^5 + 8 over F_p, p = 2^127 - 2437, prime-order Jacobian
    p = 2**127 - 2437; f = [8, 0, 0, 0, 0, 1]
    rng = random.Random(int(os.environ.get("BENCH_SEED", "127")))
    P = Fp2Poly(p)
else:
    p = 2**127 - 1
    rng = random.Random(int(os.environ.get("BENCH_SEED", "127")))
    P = Fp2Poly(p)
    while True:
        f = [rng.randrange(p) for _ in range(5)] + [1]
        df = P.trim([i*c for i, c in enumerate(f)][1:])
        if len(P.xgcd(f, df)[0]) == 1: break
J = Jacobian(p, f)

def rand_point():
    while True:
        x = rng.randrange(p); fx = sum(c*pow(x, i, p) for i, c in enumerate(f)) % p
        if fx and pow(fx, (p-1)//2, p) == 1:
            y = pow(fx, (p+1)//4, p); assert y*y % p == fx
            return ((-x % p, 1), (y,))
def rand_elem(): return J.add(rand_point(), rand_point())

# --------- scalar multiplication algorithms (all count group ops via J.adds) ---------
def wnaf(k, w):
    out = []
    while k:
        if k & 1:
            d = k % (1 << w)
            if d >= (1 << (w-1)): d -= (1 << w)
            k -= d
        else: d = 0
        out.append(d); k >>= 1
    return out
def precompute_odd(D, w):
    D2 = J.add(D, D); tbl = {1: D}; cur = D
    for i in range(3, 1 << (w-1), 2):
        cur = J.add(cur, D2); tbl[i] = cur
    return tbl
def smul(k, D, w=4):
    tbl = precompute_odd(D, w); digs = wnaf(k, w); R = J.O
    for d in reversed(digs):
        R = J.add(R, R)
        if d > 0: R = J.add(R, tbl[d])
        elif d < 0: R = J.add(R, J.neg(tbl[-d]))
    return R
def straus(pairs, w=4):
    tabs = [precompute_odd(D, w) for _, D in pairs]
    digs = [wnaf(k, w) for k, _ in pairs]
    nb = max(len(d) for d in digs); R = J.O
    for b in range(nb-1, -1, -1):
        R = J.add(R, R)
        for dg, tb in zip(digs, tabs):
            if b < len(dg) and dg[b]:
                d = dg[b]; R = J.add(R, tb[d] if d > 0 else J.neg(tb[-d]))
    return R
def pippenger(pairs, c=None):
    m = len(pairs); nbits = max(k.bit_length() for k, _ in pairs)
    if c is None: c = max(2, int(math.log2(m)) - 1)
    R = J.O
    for win in range((nbits + c - 1)//c - 1, -1, -1):
        for _ in range(c): R = J.add(R, R)
        buckets = [None]*(1 << c)
        for k, D in pairs:
            idx = (k >> (win*c)) & ((1 << c) - 1)
            if idx: buckets[idx] = D if buckets[idx] is None else J.add(buckets[idx], D)
        run, acc = J.O, J.O
        for idx in range((1 << c) - 1, 0, -1):
            if buckets[idx] is not None: run = J.add(run, buckets[idx])
            acc = J.add(acc, run)
        R = J.add(R, acc)
    return R

def timed(fn, reps=1):
    J.adds = 0; t = time.perf_counter()
    for _ in range(reps): out = fn()
    return (time.perf_counter() - t)/reps, J.adds/reps, out

# --------- correctness of the implementations on this field ---------
A, B = rand_elem(), rand_elem()
a, b = rng.getrandbits(254), rng.getrandbits(254)
assert smul(a+b, A) == J.add(smul(a, A), smul(b, A))
ref = J.add(smul(a, A), smul(b, B))
assert straus([(a, A), (b, B)]) == ref and pippenger([(a, A), (b, B)], c=4) == ref
print("implementation self-checks passed (wNAF, Straus, Pippenger agree)")

res = {}
t_add, _, _ = timed(lambda: J.add(A, B), 300)
t_dbl, _, _ = timed(lambda: J.add(A, A), 300)
t_hecm, ops_hecm, _ = timed(lambda: smul(rng.getrandbits(254), A), 20)
t_ind, ops_ind, _ = timed(lambda: straus([(rng.getrandbits(254), A), (rng.getrandbits(254), B)]), 10)
res.update(T_add_ms=t_add*1e3, T_dbl_ms=t_dbl*1e3, T_hecm_ms=t_hecm*1e3, ops_hecm=ops_hecm,
           T_indiv_shamir_ms=t_ind*1e3, ops_indiv=ops_ind)
print(f"T_add={t_add*1e3:.3f} ms  T_dbl={t_dbl*1e3:.3f} ms  T_HECM={t_hecm*1e3:.2f} ms ({ops_hecm:.0f} ops)  "
      f"T_ind(2-term Straus)={t_ind*1e3:.2f} ms ({ops_ind:.0f} ops) -> ratio {t_ind/t_hecm:.3f} HECM")

pts = [rand_elem() for _ in range(64)]
rows = []
for n in [1, 5, 10, 25, 50, 100, 250, 500]:
    m = 2*n + 1
    pairs_full = [(rng.getrandbits(254), pts[i % 64]) for i in range(m)]
    # short-coefficient variant: alpha_i 128-bit on the U_i terms (n of them), full on L and alpha_i e_i P_i
    pairs_short = [(rng.getrandbits(254), pts[0])] + [(rng.getrandbits(128), pts[i % 64]) for i in range(n)] + \
                  [(rng.getrandbits(254), pts[(i+7) % 64]) for i in range(n)]
    reps = 3 if m < 60 else 1
    ts, os_, _ = timed(lambda: straus(pairs_full, w=4 if m < 100 else 5), reps)
    tss, oss, _ = timed(lambda: straus(pairs_short, w=4 if m < 100 else 5), reps)
    tp, op, _ = timed(lambda: pippenger(pairs_full), reps) if m >= 21 else (float('nan'), float('nan'), None)
    best = min(x for x in [ts, tss, tp] if x == x)
    row = dict(n=n, terms=m, straus_ms=ts*1e3, straus_ops=os_, straus_short_ms=tss*1e3, straus_short_ops=oss,
               pippenger_ms=tp*1e3, pippenger_ops=op,
               rho_best_over_hecm=best/t_hecm, rho_indiv_total_over_hecm=n*t_ind/t_hecm,
               base_batch_over_hecm=(2*n+1) + 2*n*t_add/t_hecm,
               speedup_vs_indiv=n*t_ind/best, speedup_vs_base=((2*n+1)*t_hecm + 2*n*t_add)/best)
    rows.append(row)
    print(f"n={n:4d} m={m:5d} Straus {ts*1e3:9.1f} ms | Straus-short {tss*1e3:9.1f} ms | Pippenger {tp*1e3:9.1f} ms "
          f"| best/HECM={best/t_hecm:7.2f} | indiv/HECM={n*t_ind/t_hecm:7.2f} | speed-up vs indiv {n*t_ind/best:4.2f}x, vs Base {row['speedup_vs_base']:4.2f}x", flush=True)
res["rows"] = rows
json.dump(res, open(os.path.join(os.path.dirname(__file__), os.environ.get("BENCH_OUT", "bench_g2_127.json")), "w"), indent=1)
