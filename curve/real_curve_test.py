"""HiBaF signatures, MSM batch verification and 64-byte canonical encoding on the certified curve
C: y^2 = x^5 + 8 over F_p, p = 2^127 - 2437, #J = N (prime, 254 bits)."""
import sys, json, random, hashlib, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CURVE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "reference_model"))
from g2toy import Jacobian
with (CURVE_DIR / "curve.json").open(encoding="utf-8") as fh:
    c = json.load(fh)
with (CURVE_DIR / "curve_validation.json").open(encoding="utf-8") as fh:
    V = json.load(fh)
p, a, N = c["p"], c["a"], c["N"]
J = Jacobian(p, [a, 0, 0, 0, 0, 1])
L = (tuple(int(t) for t in V["generator_L"]["u"]), tuple(int(t) for t in V["generator_L"]["v"]))
rng = random.Random(99)
res = {}

def enc(D):
    """64 bytes: u0 || u1 || v0 || v1 (16 bytes each, p < 2^127); deg(u) in the spare top bits of u0, u1."""
    deg = len(D[0]) - 1
    u = list(D[0][:deg]) + [0]*(2-deg); v = list(D[1]) + [0]*(2-len(D[1]))
    u0 = u[0] | ((deg & 1) << 127); u1 = u[1] | ((deg >> 1) << 127)
    return b"".join(x.to_bytes(16, "big") for x in (u0, u1, v[0], v[1]))
def dec(b):
    if len(b) != 64: raise ValueError
    cs = [int.from_bytes(b[16*i:16*i+16], "big") for i in range(4)]
    deg = (cs[0] >> 127) | ((cs[1] >> 127) << 1); cs[0] &= (1 << 127) - 1; cs[1] &= (1 << 127) - 1
    if deg > 2 or any(x >= p for x in cs): raise ValueError
    u = ([cs[0], cs[1], 1] if deg == 2 else [cs[0], 1] if deg == 1 else [1])
    if any(cs[deg:2]) or any(cs[2+deg:]): raise ValueError
    v = cs[2:2+deg]
    while v and v[-1] == 0: v.pop()
    D = (tuple(u), tuple(v))
    if not J.is_valid(D): raise ValueError
    return D
def H2(*xs):   # 512-bit output reduced mod N: statistical distance <= 2^-258 (256 bits would give 2^-62.7)
    return int.from_bytes(hashlib.blake2b(b"|".join(xs), digest_size=64, person=b"HiBaF-H2").digest(), "big") % N
def straus(pairs):
    nb = max(k.bit_length() for k, _ in pairs); R = J.O
    for bit in range(nb-1, -1, -1):
        R = J.add(R, R)
        for k, D in pairs:
            if (k >> bit) & 1: R = J.add(R, D)
    return R

# degree-1 divisor round trip (rare case)
P1 = ((p - 1, 1), (int(V["generator_L"]["from_points"][0][1]),))
assert dec(enc(P1)) == P1
# keys and signatures
n = 6
keys = []
for i in range(n):
    x = rng.randrange(1, N); keys.append((x, J.mul(x, L)))
sigs = []
for i, (x, P) in enumerate(keys):
    msg = f"report-{i}".encode(); u = rng.randrange(1, N); U = J.mul(u, L)
    e = H2(enc(P), msg, enc(U)); s = (u - e*x) % N
    sigs.append((P, msg, enc(U), s))
ok = all(J.add(J.mul(s, L), J.mul(H2(enc(P), m, Ub), P)) == dec(Ub) for P, m, Ub, s in sigs)
res["individual_verify_all_valid"] = ok
res["encoding_bytes_U"] = len(sigs[0][2])
res["encoding_roundtrip"] = all(dec(Ub) == dec(enc(dec(Ub))) for _, _, Ub, _ in sigs)

def batch(items, alphas):
    beta = sum(al*s for al, (_, _, _, s) in zip(alphas, items)) % N
    pairs = [(beta, L)]
    for al, (P, m, Ub, s) in zip(alphas, items):
        e = H2(enc(P), m, Ub); pairs += [((-al) % N, dec(Ub)), ((al*e) % N, P)]
    return straus(pairs) == J.O
alph = [1] + [rng.getrandbits(128) | 1 for _ in range(n-1)]
res["batch_all_valid"] = batch(sigs, alph)
bad = list(sigs); P, m, Ub, s = bad[3]; bad[3] = (P, m, Ub, (s+1) % N)
res["batch_detects_invalid_5_trials"] = sum(not batch(bad, [1] + [rng.getrandbits(128) | 1 for _ in range(n-1)]) for _ in range(5))
# non-canonical encoding rejected
Ub = bytearray(sigs[0][2]); x = (int.from_bytes(Ub[32:48], "big") + p)   # v0 + p < 2^128, same value mod p
try:
    Ub[32:48] = x.to_bytes(16, "big"); dec(bytes(Ub)); res["noncanonical_rejected"] = False
except (ValueError, OverflowError):
    res["noncanonical_rejected"] = True
# off-curve point rejected
Ub = bytearray(sigs[0][2]); Ub[-1] ^= 1
try: dec(bytes(Ub)); res["offcurve_rejected"] = False
except ValueError: res["offcurve_rejected"] = True
print(json.dumps(res, indent=1))
with (CURVE_DIR / "real_curve_test.json").open("w", encoding="utf-8") as fh:
    json.dump(res, fh, indent=1)
