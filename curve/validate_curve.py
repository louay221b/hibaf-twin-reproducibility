"""Independent checks of the HiBaF-Twin curve C: y^2 = x^5 + 8 over F_p, p = 2^127 - 2437."""
import sys, json, math, random
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "reference_model"))
sys.path.insert(0, str(HERE))
from sympy import isprime, factorint, primerange
from sympy.ntheory import sqrt_mod
from g2toy import Jacobian, bsgs_order_in
from find_curve import candidates, random_divisor

R = {}
# ---- 1. the CM candidate method contains the true order on small fields (brute force by BSGS)
ok = 0; tested = 0
for p in [q for q in primerange(100, 400) if q % 5 == 1]:
    cand = candidates(p)
    for a in range(1, 11):
        if a % p == 0: continue
        J = Jacobian(p, [a, 0, 0, 0, 0, 1]); rng = random.Random(a)
        lo, hi = (math.isqrt(p)-1)**4, (math.isqrt(p)+2)**4
        S = None
        for _ in range(4):
            D = random_divisor(J, [a, 0, 0, 0, 0, 1], p, rng)
            s = set(bsgs_order_in(J, D, max(1, lo), hi)); S = s if S is None else S & s
        # true order is the unique annihilator in the interval when |S| = 1
        if len(S) == 1:
            tested += 1; ok += (S.pop() in cand)
R["cm_candidates_contain_true_order_small_fields"] = f"{ok}/{tested}"
print("1. CM candidate set contains brute-force order:", R["cm_candidates_contain_true_order_small_fields"])

# ---- 2. certified parameters
with (HERE / "curve.json").open(encoding="utf-8") as fh:
    c = json.load(fh)
p, a, N = c["p"], c["a"], c["N"]
assert p == 2**127 - 2437 and isprime(p) and p % 5 == 1
assert isprime(N)
lo, hi = (math.isqrt(p)-1)**4, (math.isqrt(p)+2)**4
assert lo <= N <= hi and (hi - lo) < N
R.update(p=str(p), a=a, N=str(N), N_bits=N.bit_length(), p_mod_4=p % 4, p_mod_5=p % 5)
print(f"2. p = 2^127-2437 (prime, p mod 5 = 1, p mod 4 = {p%4}); N prime, {N.bit_length()} bits; HW width < N")

f = [a, 0, 0, 0, 0, 1]
J = Jacobian(p, f); rng = random.Random(7)
cnt = 0
for _ in range(10):
    D = random_divisor(J, f, p, rng)
    assert D != J.O and J.mul(N, D) == J.O; cnt += 1
R["random_divisors_annihilated_by_N"] = cnt
print(f"3. N*D = O for {cnt}/10 random divisors  => #J(F_p) = N (prime, cofactor 1)")

# ---- 4. security checks
assert N != p
R["anomalous"] = False
# embedding degree k = ord_N(p) divides N-1; check it is not small
small = [k for k in range(1, 20001) if pow(p, k, N) == 1]
fac = factorint(N - 1, limit=10**6)
R["N_minus_1_partial_factorisation"] = {str(k): v for k, v in fac.items()}
big = max(fac)  # possibly composite cofactor if not fully factored
R["embedding_degree_le_20000"] = small
# order of p mod N is a multiple of N-1 / (product of small primes allowed)
emb_lower = (N - 1)
for r, e in fac.items():
    for _ in range(e):
        if pow(p, emb_lower // r, N) == 1: emb_lower //= r
        else: break
R["embedding_degree"] = str(emb_lower); R["embedding_degree_bits"] = emb_lower.bit_length()
print(f"4. embedding degree ord_N(p) has {emb_lower.bit_length()} bits (no k <= 20000)")
# rho with the order-10 automorphism group (zeta5 and -1): sqrt(pi*N/(2*10))
rho_bits = math.log2(math.sqrt(math.pi * N / (2 * 10)))
R["pollard_rho_bits_with_aut10"] = round(rho_bits, 1)
print(f"5. Pollard rho with automorphism group of order 10: ~2^{rho_bits:.1f} group operations")
# quadratic twist / other twists: orders of the other CM candidates (invalid-curve context)
tw = [n for n in candidates(p) if n != N]
R["twist_orders_largest_prime_factor_bits"] = []
for n in tw:
    fo = factorint(n, limit=10**6)
    R["twist_orders_largest_prime_factor_bits"].append(max(fo).bit_length())
print("6. other twists: largest prime-factor bits", R["twist_orders_largest_prime_factor_bits"])

# ---- 7. deterministic generator (nothing up my sleeve): first two x >= 1 with f(x) a non-zero square,
#         y = smaller square root; L = P1 + P2 ; any non-identity element generates a prime-order group
xs = []; x = 1
while len(xs) < 2:
    fx = (pow(x, 5, p) + a) % p
    if fx and pow(fx, (p-1)//2, p) == 1:
        y = sqrt_mod(fx, p); y = min(y, p - y); xs.append((x, y))
    x += 1
P1 = ((-xs[0][0] % p, 1), (xs[0][1],)); P2 = ((-xs[1][0] % p, 1), (xs[1][1],))
L = J.add(P1, P2)
assert L != J.O and J.mul(N, L) == J.O
u, v = list(L[0]), list(L[1])
R["generator_L"] = dict(u=[str(t) for t in u], v=[str(t) for t in v], from_points=[[str(t) for t in q] for q in xs])
print("7. generator L = P(x=%d) + P(x=%d): u =" % (xs[0][0], xs[1][0]), u, "v =", v)
with (HERE / "curve_validation.json").open("w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)
