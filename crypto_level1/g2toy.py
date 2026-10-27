"""
Toy genus-2 Jacobian (Cantor's algorithm) used ONLY to check the algebraic
correctness of the HiBaF equations. Parameters are tiny and offer no security.
Model: y^2 = f(x), deg f = 5, monic, over F_p (imaginary model, h = 0).
Divisors in Mumford representation (u, v), polys as coefficient lists low->high.
"""
import random

class Fp2Poly:
    def __init__(self, p): self.p = p
    def trim(self, a):
        a = [c % self.p for c in a]
        while a and a[-1] == 0: a.pop()
        return a
    def add(self, a, b):
        n = max(len(a), len(b)); return self.trim([(a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(n)])
    def neg(self, a): return self.trim([-c for c in a])
    def sub(self, a, b): return self.add(a, self.neg(b))
    def mul(self, a, b):
        if not a or not b: return []
        r = [0]*(len(a)+len(b)-1)
        for i, x in enumerate(a):
            for j, y in enumerate(b): r[i+j] += x*y
        return self.trim(r)
    def divmod(self, a, b):
        a = self.trim(a); b = self.trim(b); p = self.p
        if not b: raise ZeroDivisionError
        inv = pow(b[-1], p-2, p); q = [0]*max(0, len(a)-len(b)+1); r = a[:]
        while len(r) >= len(b) and r:
            c = r[-1]*inv % p; d = len(r)-len(b); q[d] = c
            r = self.sub(r, [0]*d + [c*x for x in b])
        return self.trim(q), r
    def mod(self, a, b): return self.divmod(a, b)[1]
    def monic(self, a):
        a = self.trim(a); inv = pow(a[-1], self.p-2, self.p); return [c*inv % self.p for c in a]
    def xgcd(self, a, b):
        # returns d, s, t with d = s a + t b, d monic
        r0, r1, s0, s1, t0, t1 = self.trim(a), self.trim(b), [1], [], [], [1]
        while r1:
            q, r = self.divmod(r0, r1)
            r0, r1 = r1, r
            s0, s1 = s1, self.sub(s0, self.mul(q, s1))
            t0, t1 = t1, self.sub(t0, self.mul(q, t1))
        inv = pow(r0[-1], self.p-2, self.p)
        return [c*inv % self.p for c in r0], [c*inv % self.p for c in s0], [c*inv % self.p for c in t0]

class Jacobian:
    def __init__(self, p, f):
        self.p = p; self.P = Fp2Poly(p); self.f = self.P.trim(f); self.O = ((1,), ())
        self.adds = 0
    def norm(self, u, v): return (tuple(self.P.monic(u)), tuple(self.P.mod(v, u)) if len(u) > 1 else ())
    def add(self, D1, D2):
        self.adds += 1
        P = self.P; u1, v1 = list(D1[0]), list(D1[1]); u2, v2 = list(D2[0]), list(D2[1])
        d1, e1, e2 = P.xgcd(u1, u2)
        d, c1, s3 = P.xgcd(d1, P.add(v1, v2))
        s1, s2 = P.mul(c1, e1), P.mul(c1, e2)
        u = P.divmod(P.mul(u1, u2), P.mul(d, d))[0]
        num = P.add(P.add(P.mul(P.mul(s1, u1), v2), P.mul(P.mul(s2, u2), v1)), P.mul(s3, P.add(P.mul(v1, v2), self.f)))
        v = P.mod(P.divmod(num, d)[0], u) if len(u) > 1 else []
        while len(u) - 1 > 2:
            u = P.divmod(P.sub(self.f, P.mul(v, v)), u)[0]
            v = P.mod(P.neg(v), u)
        u = P.monic(u)
        v = P.mod(v, u) if len(u) > 1 else []
        return (tuple(u), tuple(v))
    def neg(self, D): return (D[0], tuple(self.P.neg(list(D[1]))))
    def mul(self, k, D):
        R, Q = self.O, D
        if k < 0: k, Q = -k, self.neg(D)
        while k:
            if k & 1: R = self.add(R, Q)
            Q = self.add(Q, Q); k >>= 1
        return R
    def is_valid(self, D):
        u, v = list(D[0]), list(D[1])
        if u == [1]: return v == []
        return self.P.mod(self.P.sub(self.P.mul(v, v), self.f), u) == [] and len(u)-1 <= 2
    def random_point(self, rng):
        p = self.p
        while True:
            x = rng.randrange(p); fx = sum(c*pow(x, i, p) for i, c in enumerate(self.f)) % p
            if fx == 0: continue
            if pow(fx, (p-1)//2, p) == 1:
                y = next(t for t in range(p) if t*t % p == fx)  # tiny p only
                return ((-x % p, 1), (y,))
    def random_element(self, rng):
        return self.add(self.random_point(rng), self.random_point(rng))

def bsgs_order_in(J, D, lo, hi):
    """Return all N in [lo,hi] with N*D = O (baby-step giant-step)."""
    m = int((hi-lo)**0.5) + 1
    baby = {}; R = J.O
    for j in range(m):
        baby.setdefault(R, []).append(j); R = J.add(R, D)
    G = J.neg(J.mul(m, D)); cur = J.mul(lo, D); out = []
    i = 0
    while lo + i*m <= hi:
        # want lo + i m + j with (lo+im+j) D = O  <=> j D = -(lo+im) D
        target = J.neg(cur)
        for j in baby.get(target, []):
            N = lo + i*m + j
            if N <= hi: out.append(N)
        cur = J.add(cur, J.mul(m, D)); i += 1
    return out

def is_prime(n):
    if n < 2: return False
    i = 2
    while i*i <= n:
        if n % i == 0: return False
        i += 1
    return True

def find_curve(p, want_cofactor, seed=1):
    rng = random.Random(seed)
    lo = int((p**0.5 - 1)**4) + 1; hi = int((p**0.5 + 1)**4)
    while True:
        f = [rng.randrange(p) for _ in range(5)] + [1]
        # squarefree check via gcd(f, f')
        P = Fp2Poly(p); df = P.trim([i*c for i, c in enumerate(f)][1:])
        if len(P.xgcd(f, df)[0]) > 1: continue
        J = Jacobian(p, f)
        cands = None
        for _ in range(4):
            D = J.random_element(rng)
            s = set(bsgs_order_in(J, D, lo, hi)); cands = s if cands is None else cands & s
            if cands is not None and len(cands) <= 1: break
        if not cands or len(cands) != 1: continue
        N = cands.pop()
        if N % want_cofactor == 0 and is_prime(N // want_cofactor):
            return J, f, N
