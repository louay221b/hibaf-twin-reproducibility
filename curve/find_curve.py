"""
Search a prime-order genus-2 Jacobian for HiBaF-Twin.

Family  C_a : y^2 = x^5 + a  over F_p,  p = 2^127 - c,  p = 1 (mod 5).
C_a has CM by Z[zeta_5]; its Frobenius pi is, up to a 10th root of unity (which selects the
twist a mod (F_p^*)^10), the element beta*sigma_2(beta) where (beta) is a prime of Z[zeta_5]
above p.  Hence #J(C_a)(F_p) = N_{K/Q}(1 - pi) for one of the 20 candidates
pi = e * beta * sigma_k(beta), e in {+-zeta^j}, k in {2,3}.

Rigorous certification (independent of the CM theory used to generate candidates):
if N is prime, N lies in the Hasse-Weil interval and N*D = O for a random D != O on the
actual curve, then ord(D) = N divides #J, and because the Hasse-Weil interval
[(sqrt p - 1)^4, (sqrt p + 1)^4] has width < N, #J = N.
"""
import sys, random, json, math
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "reference_model"))
from sympy import isprime, ZZ
from sympy.ntheory import sqrt_mod
from sympy.polys.matrices import DomainMatrix
from g2toy import Jacobian, Fp2Poly

# ---------------- Z[zeta5] arithmetic, basis 1, z, z^2, z^3 ; z^4 = -1 - z - z^2 - z^3
def zmul(a, b):
    c = [0]*7
    for i in range(4):
        for j in range(4):
            c[i+j] += a[i]*b[j]
    for k in range(6, 3, -1):          # reduce z^k, k>=4: z^k = z^(k-4) * z^4
        t = c[k]; c[k] = 0
        for i in range(4): c[k-4+i] -= t
    return c[:4]
def zpow_z(e):                          # z^e as vector
    e %= 5
    if e == 4: return [-1, -1, -1, -1]
    v = [0]*4; v[e] = 1; return v
def sigma(a, k):                        # z -> z^k
    r = [0]*4
    for i in range(4):
        zi = zpow_z(i*k)
        for t in range(4): r[t] += a[i]*zi[t]
    return r
def znorm(a):
    n = a
    for k in (2, 3, 4): n = zmul(n, sigma(a, k))
    assert n[1] == n[2] == n[3] == 0, n
    return n[0]
def zsub(a, b): return [x-y for x, y in zip(a, b)]

def prime_above(p):
    """Generator of a prime of Z[zeta5] above p (p = 1 mod 5), via LLL on the ideal (p, z - r)."""
    g = 2
    while True:
        r = pow(g, (p-1)//5, p)
        if r != 1: break
        g += 1
    B = [[p, 0, 0, 0], [(-r) % p, 1, 0, 0], [(-r*r) % p, 0, 1, 0], [(-r*r*r) % p, 0, 0, 1]]
    M = DomainMatrix([[ZZ(x) for x in row] for row in B], (4, 4), ZZ).lll().to_Matrix()
    for i in range(4):
        v = [int(x) for x in M.row(i)]
        if abs(znorm(v)) == p: return v
    for i in range(4):                  # small combinations
        for j in range(4):
            for s in (1, -1):
                v = [int(a) + s*int(b) for a, b in zip(M.row(i), M.row(j))]
                if i != j and abs(znorm(v)) == p: return v
    raise ValueError("no generator found")

def candidates(p):
    beta = prime_above(p)
    lo, hi = math.isqrt(p) - 1, math.isqrt(p) + 2
    lo, hi = (lo)**4, (hi)**4
    out = set()
    for k in (2, 3):
        alpha = zmul(beta, sigma(beta, k))
        for sgn in (1, -1):
            for j in range(5):
                pi = zmul(alpha, zpow_z(j)); pi = [sgn*x for x in pi]
                N = znorm(zsub([1, 0, 0, 0], pi))
                if lo <= N <= hi: out.add(N)
    return sorted(out)

def random_divisor(J, f, p, rng):
    def pt():
        while True:
            x = rng.randrange(p); fx = sum(c*pow(x, i, p) for i, c in enumerate(f)) % p
            if fx and pow(fx, (p-1)//2, p) == 1:
                y = sqrt_mod(fx, p); return ((-x % p, 1), (y,))
    return J.add(pt(), pt())

def certify(p, a, N, rng, tries=3):
    f = [a % p, 0, 0, 0, 0, 1]
    J = Jacobian(p, f)
    for _ in range(tries):
        D = random_divisor(J, f, p, rng)
        if D == J.O or J.mul(N, D) != J.O: return False
    return True

if __name__ == "__main__":
    rng = random.Random(2026)
    found = []
    c = 1
    while len(found) < 1:
        c += 2
        p = 2**127 - c
        if p % 5 != 1 or not isprime(p): continue
        cands = [N for N in candidates(p) if isprime(N)]
        if not cands: continue
        print(f"p = 2^127 - {c}: {len(cands)} prime candidate order(s)", flush=True)
        for a in range(1, 200):
            for N in cands:
                if certify(p, a, N, rng):
                    found.append(dict(c=c, p=p, a=a, N=N)); print("  CERTIFIED a =", a, "N =", N, flush=True); break
            if found: break
    with (HERE / "curve.json").open("w", encoding="utf-8") as fh:
        json.dump(found[0], fh, indent=1)
