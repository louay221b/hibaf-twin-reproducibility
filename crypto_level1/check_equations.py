"""
Executable check of the HiBaF algebra on a toy genus-2 Jacobian (NO security).
1. Schnorr-like signature correctness: s = u - e x,  sL + eP = U.
2. Batch relation R = beta L - sum a_i U_i + sum a_i e_i P_i equals sum a_i (s_i L + e_i P_i - U_i).
3. Straus MSM gives the same R as the Base evaluation.
4. Cofactor issue: a report with U' = U + T (T of order 2) fails individual verification but
   passes the batch equation whenever alpha_i is even (prob ~1/2) if no subgroup check is done.
5. Cofactored batch check [h]R = O accepts the same report deterministically -> shows that
   "cofactor-aware" verification changes the accepted set; individual and batch must use the same rule.
6. AES-128-GCM round trip (Decrypt(Encrypt(m)) = m) with the HiBaF AD/nonce layout and the ratchet.
"""
import random, hashlib, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from g2toy import find_curve
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

rng = random.Random(20261015)
p = 1009
J, f, N = find_curve(p, want_cofactor=2, seed=7)
h = 2; q = N // h
print(f"toy curve over F_{p}: f={f}, #J={N} = {h} * {q}")

# generator of the order-q subgroup and an order-2 element T
while True:
    L = J.mul(h, J.random_element(rng))
    if L != J.O: break
assert J.mul(q, L) == J.O
while True:
    X = J.random_element(rng); T = J.mul(q, X)
    if T != J.O: break
assert J.mul(2, T) == J.O
print("generator L has order q; T has order 2")

def H2(*parts):
    return int.from_bytes(hashlib.blake2s(b"H2|" + b"|".join(str(x).encode() for x in parts)).digest(), "big") % q

# --- 1. signature correctness ---
def keygen():
    x = rng.randrange(1, q); return x, J.mul(x, L)
def sign(x, ctx):
    u = rng.randrange(1, q); U = J.mul(u, L); e = H2(ctx, U); s = (u - e*x) % q; return U, s, e
def verify(P, ctx, U, s):
    e = H2(ctx, U); return J.add(J.mul(s, L), J.mul(e, P)) == U

keys = [keygen() for _ in range(12)]
reports = []
for i, (x, P) in enumerate(keys):
    ctx = ("ID%d" % i, 7, "rho", "tau", i)
    U, s, e = sign(x, ctx); reports.append((P, ctx, U, s))
    assert verify(P, ctx, U, s)
print("1. individual Schnorr-like verification sL+eP=U holds for all honest reports")

# --- 2/3. batch relation, base vs Straus ---
def batch_base(reps, alphas):
    beta = sum(a*s for a, (_, _, _, s) in zip(alphas, reps)) % q
    R = J.mul(beta, L)
    for a, (P, ctx, U, s) in zip(alphas, reps):
        e = H2(ctx, U)
        R = J.add(R, J.neg(J.mul(a, U)))
        R = J.add(R, J.mul(a*e % q, P))
    return R
def straus(pairs):
    # interleaved (joint) double-and-add, window 1
    nb = max(k.bit_length() for k, _ in pairs); R = J.O
    for b in range(nb-1, -1, -1):
        R = J.add(R, R)
        for k, Pt in pairs:
            if (k >> b) & 1: R = J.add(R, Pt)
    return R
def batch_msm(reps, alphas):
    beta = sum(a*s for a, (_, _, _, s) in zip(alphas, reps)) % q
    pairs = [(beta, L)]
    for a, (P, ctx, U, s) in zip(alphas, reps):
        e = H2(ctx, U); pairs.append(((-a) % q, U)); pairs.append((a*e % q, P))
    return straus(pairs)
alphas = [rng.randrange(1, q) for _ in reports]
Rb, Rm = batch_base(reports, alphas), batch_msm(reports, alphas)
assert Rb == J.O and Rm == J.O
print("2/3. batch residual R = O for an all-valid batch; Base and Straus-MSM evaluations agree")

# bad report (wrong s) -> batch rejects for random alphas
bad = list(reports); P0, c0, U0, s0 = bad[3]; bad[3] = (P0, c0, U0, (s0+1) % q)
fails = sum(batch_msm(bad, [rng.randrange(1, q) for _ in bad]) != J.O for _ in range(200))
print(f"   modified s: batch rejected {fails}/200 trials (expected 200)")

# --- 4. small-order component without subgroup check ---
torsion = list(reports); P0, c0, U0, s0 = torsion[5]
U_bad = J.add(U0, T)                  # U' = U + T, T of order 2
# signer must recompute e over U' for the forgery to be consistent: attacker who knows nothing
# can't do that; but a *dishonest sensor* (key owner) can sign with U' committed:
x5 = keys[5][0]; u = rng.randrange(1, q)
U_bad = J.add(J.mul(u, L), T); e = H2(c0, U_bad); s_bad = (u - e*x5) % q
torsion[5] = (P0, c0, U_bad, s_bad)
assert not verify(P0, c0, U_bad, s_bad)
acc = 0; trials = 400
for _ in range(trials):
    al = [rng.randrange(1, q) for _ in torsion]
    acc += batch_msm(torsion, al) == J.O
print(f"4. report with U'=U+T (T order 2): individual verify = REJECT, batch accepted {acc}/{trials} "
      f"(~1/2 expected) -> Prop. 'batch soundness 1/(q-1)' fails without subgroup check")
in_sub = J.mul(q, U_bad) == J.O
print(f"   subgroup check q*U' == O ? {in_sub} -> explicit check detects it (cost: one extra scalar mult)")
# --- 5. cofactored rule ---
acc_c = sum(J.mul(h, batch_msm(torsion, [rng.randrange(1, q) for _ in torsion])) == J.O for _ in range(100))
print(f"5. cofactored batch rule [h]R=O accepts {acc_c}/100 -> must pair with cofactored individual rule [h](sL+eP-U)=O")

# --- 6. AEAD + ratchet ---
def KDF(K, *parts): return hashlib.blake2s(b"|".join(str(x).encode() for x in parts), key=K, digest_size=16).digest()
def ratchet(K, w): return hashlib.blake2s(b"ratchet|" + K + str(w).encode()).digest()
K0 = os.urandom(32); Ks = {0: K0}
for w in range(1, 5): Ks[w] = ratchet(Ks[w-1], w-1)
w = 3; rho = os.urandom(16).hex(); tau = 2; t = 1234
r = os.urandom(8); c = (1).to_bytes(4, "big"); nonce = r + c
k = KDF(Ks[w], "S1", "BE", w, rho, tau)
AD = f"S1|{w}|{rho}|{tau}|{t}|".encode() + nonce
m = b"DO=6.81mg/L"
ct = AESGCM(k).encrypt(nonce, m, AD)
assert AESGCM(k).decrypt(nonce, ct, AD) == m
try:
    AESGCM(KDF(Ks[w], "S1", "BE", w, "other-rho", tau)).decrypt(nonce, ct, AD); print("ERR")
except Exception:
    pass
print(f"6. AES-128-GCM: Decrypt(Encrypt(m)) = m holds; |C||T| = {len(ct)*8} bits for an {len(m)}-byte reading; "
      "decryption with a different rho_w fails (window binding)")
