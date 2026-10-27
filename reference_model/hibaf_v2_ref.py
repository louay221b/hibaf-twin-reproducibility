"""
HiBaF v2 — executable reference model of the corrected protocol (MSM native).

Group: toy genus-2 Jacobian of PRIME order q (no cofactor) over F_1009 — correctness only,
no security.  Symmetric primitives are real: AES-128-GCM (cryptography), keyed BLAKE2s.

Corrections implemented relative to the submitted manuscript (audit IDs in brackets):
  [C4] prime-order group + canonical decoding  => batch soundness 1/q holds, no subgroup mult.
  [C6] sensor--BE enrolment by signed ephemeral HEC-DH (SIGMA-like, PFS); TTP only certifies signing keys.
  [C7] forward-secure PRG ratchet per epoch (E windows), state persisted in NVM.
  [M2] back-end dedupe inside the ingestion loop.
  [M3] sensor--collector link MAC pre-filter, per-identity quota, negative cache.
  [M4] sensors use a monotonic window rule (NVM w_last); expiry is enforced by collectors.
  [M12] key-prefixed challenge, s < q and canonical-encoding checks; equivocation evidence.
  [C3] MSM (Straus, short coefficients) at every verification point + adaptive batch controller.
"""
import hashlib, hmac, os, random, math
from dataclasses import dataclass, field
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from g2toy import Jacobian

# ----------------------------------------------------------------- group
P_FIELD = 1009
F_CURVE = [397, 903, 494, 618, 80, 1]
Q = 1018697                      # #J(F_p), prime
J = Jacobian(P_FIELD, F_CURVE)
_rng = random.Random(1)
while True:
    L = J.random_element(_rng)
    if L != J.O: break           # prime order => any non-identity element generates
assert J.mul(Q, L) == J.O

def enc_point(D):
    """Mumford (u, v): degree byte, the deg(u) non-leading coefficients of monic u, then v; zero padded."""
    deg = len(D[0]) - 1
    u = list(D[0][:deg]) + [0]*(2-deg)
    v = list(D[1]) + [0]*(2-len(D[1]))
    return bytes([deg]) + b"".join(x.to_bytes(2, "big") for x in (u[0], u[1], v[0], v[1]))

def dec_point(b):
    """Canonical decoding: rejects non-reduced coordinates, wrong degree, invalid divisors."""
    if len(b) != 9 or b[0] > 2: raise ValueError("format")
    deg = b[0]; c = [int.from_bytes(b[1+2*i:3+2*i], "big") for i in range(4)]
    if any(x >= P_FIELD for x in c): raise ValueError("non-canonical coordinate")
    u = [c[0], c[1], 1][:deg+1] if deg == 2 else ([c[0], 1] if deg == 1 else [1])
    v = [c[2], c[3]][:deg]
    if deg < 2 and any(c[deg:2]) : raise ValueError("non-canonical u padding")
    if any(c[2+deg:4]): raise ValueError("non-canonical v padding")
    while v and v[-1] == 0: v.pop()
    D = (tuple(u), tuple(v))
    if not J.is_valid(D): raise ValueError("not a reduced divisor on C")
    return D

def H(tag, *parts, n=32):
    h = hashlib.blake2s(digest_size=n, person=tag.encode()[:8].ljust(8, b"\0"))
    for x in parts:
        x = x if isinstance(x, bytes) else str(x).encode()
        h.update(len(x).to_bytes(4, "big") + x)          # unambiguous framing
    return h.digest()
def H2(*parts):
    """challenge hash to Z_q: BLAKE2b-512 (framed) reduced mod Q, statistically close to uniform"""
    h = hashlib.blake2b(digest_size=64, person=b"HiBaF-H2")
    for x in parts:
        x = x if isinstance(x, bytes) else str(x).encode(); h.update(len(x).to_bytes(4, "big") + x)
    return int.from_bytes(h.digest(), "big") % Q
def PRF(key, tag, *parts, n=32):
    h = hashlib.blake2s(key=key, digest_size=n, person=tag.encode()[:8].ljust(8, b"\0"))
    for x in parts:
        x = x if isinstance(x, bytes) else str(x).encode()
        h.update(len(x).to_bytes(4, "big") + x)
    return h.digest()

# ----------------------------------------------------------------- MSM (Straus, window 1, enough for toy q)
OPS = {"group_ops": 0}
def msm(pairs):
    J.adds = 0
    nb = max((k % Q).bit_length() for k, _ in pairs) if pairs else 0
    R = J.O
    for b in range(nb-1, -1, -1):
        R = J.add(R, R)
        for k, D in pairs:
            if ((k % Q) >> b) & 1: R = J.add(R, D)
    OPS["group_ops"] += J.adds
    return R

# ----------------------------------------------------------------- Schnorr-like signature (key-prefixed)
def keygen(rng):
    x = rng.randrange(1, Q); return x, J.mul(x, L)
def sign(x, P, msg, rng):
    u = rng.randrange(1, Q); U = J.mul(u, L)
    e = H2(enc_point(P), msg, enc_point(U)); return enc_point(U), (u - e*x) % Q
def sig_terms(P, msg, Ub, s):
    U = dec_point(Ub)                          # raises on non-canonical
    if not (0 <= s < Q): raise ValueError("s out of range")
    e = H2(enc_point(P), msg, Ub)
    return U, s, e
def verify_one(P, msg, Ub, s):
    try: U, s, e = sig_terms(P, msg, Ub, s)
    except ValueError: return False
    return msm([(s, L), (e, P), (Q-1, U)]) == J.O          # sL + eP - U = O
def batch_verify(items, rng, short_bits=16):
    """items: list of (P, msg, Ub, s). One MSM, short random coefficients (alpha_1 = 1)."""
    terms, beta = [], 0
    for idx, (P, msg, Ub, s) in enumerate(items):
        U, s, e = sig_terms(P, msg, Ub, s)
        a = 1 if idx == 0 else rng.randrange(1, 1 << short_bits)
        beta += a*s; terms += [((-a) % Q, U), ((a*e) % Q, P)]
    # merge coefficients of repeated public keys (same sensor, several reports)
    merged = {}
    for k, D in terms: merged[D] = (merged.get(D, 0) + k) % Q
    pairs = [(beta % Q, L)] + [(k, D) for D, k in merged.items() if k]
    return msm(pairs) == J.O

# ----------------------------------------------------------------- MSM-aware adaptive batch controller
C_IND = 1.152          # individual verification cost in HECM units (measured ratio, bench_g2_127)
_MSM_PTS = [(3, 1.19), (11, 2.25), (21, 5.05), (51, 9.08), (101, 15.75), (201, 32.43), (501, 80.69), (1001, 171.69)]
def c_msm(m):
    """T_MSM(m)/T_HECM, piecewise-linear interpolation of the measured ratios."""
    if m <= _MSM_PTS[0][0]: return _MSM_PTS[0][1] * m / _MSM_PTS[0][0]
    for (m0, c0), (m1, c1) in zip(_MSM_PTS, _MSM_PTS[1:]):
        if m <= m1: return c0 + (c1-c0)*(m-m0)/(m1-m0)
    m0, c0 = _MSM_PTS[-1]; return c0*m/m0
def c_batch(b): return c_msm(2*b+1)
def expected_cost(b, g, mu):
    """Two-stage (Dorfman) group testing with MSM batch tests.
    Stage 1: test all b. If it fails: split into g groups, test each; failing groups -> individual."""
    p_fail = 1 - (1-mu)**b
    if g <= 1:
        return c_batch(b) + p_fail * b * C_IND
    sz = b / g; pg = 1 - (1-mu)**sz
    return c_batch(b) + p_fail * (g*c_batch(sz) + g*pg/p_fail*sz*C_IND if p_fail > 0 else 0)
def worst_case_cost(b, g):
    return c_batch(b) + (g*c_batch(b/g) if g > 1 else 0) + b*C_IND

class BatchController:
    """Inputs: queue length, EWMA invalid-rate estimate mu_hat, deadline budget (HECM units).
    Output: (batch size b, groups g) or ('individual'). O(|grid|) per decision, table-driven in practice."""
    B_GRID = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
    G_GRID = [1, 2, 4, 8, 16]
    def __init__(self, lam=0.2, mu0=0.0, b_max=512):
        self.mu, self.lam, self.b_max = mu0, lam, b_max
    def decide(self, queue_len, budget=float("inf")):
        best = (C_IND, 1, 1)                                   # individual verification
        for b in self.B_GRID:
            if b > min(queue_len, self.b_max): break
            for g in self.G_GRID:
                if g > b: break
                if worst_case_cost(b, g) > budget: continue
                c = expected_cost(b, g, self.mu) / b
                if c < best[0]: best = (c, b, g)
        return best[1], best[2], best[0]
    def update(self, n_tested, n_invalid):
        if n_tested: self.mu = (1-self.lam)*self.mu + self.lam*(n_invalid/n_tested)

def verify_with_controller(items, ctrl, rng):
    """Returns (valid_mask, cost_in_group_ops). Uses ctrl.decide on the queue."""
    ok = [False]*len(items); i = 0
    while i < len(items):
        b, g, _ = ctrl.decide(len(items) - i)
        chunk = list(range(i, min(i+b, len(items)))); i += len(chunk)
        def run(idxs):
            try: return batch_verify([items[k] for k in idxs], rng)
            except ValueError: return False
        if len(chunk) == 1:
            ok[chunk[0]] = verify_one(*items[chunk[0]]); continue
        if run(chunk):
            for k in chunk: ok[k] = True
            ctrl.update(len(chunk), 0); continue
        groups = [chunk[j::g] for j in range(g)] if g > 1 else [chunk]
        bad = 0
        for grp in groups:
            if g > 1 and run(grp):
                for k in grp: ok[k] = True
                continue
            for k in grp:
                ok[k] = verify_one(*items[k]); bad += (not ok[k])
        ctrl.update(len(chunk), bad)
    return ok

# ----------------------------------------------------------------- entities
EPOCH_WINDOWS = 4                 # E windows per ratchet epoch (toy value)
REPORT_TYPES = (1, 2)             # report types tau
NONCE_R_BITS, NONCE_C_BITS = 64, 32

@dataclass
class TTP:
    rng: random.Random
    x: int = 0; P: tuple = None; certs: dict = field(default_factory=dict); revoked: set = field(default_factory=set); rl_version: int = 0
    def __post_init__(self): self.x, self.P = keygen(self.rng)
    def certify(self, ident, Psig, Yka):
        msg = H("cert", ident, enc_point(Psig), enc_point(Yka))
        self.certs[ident] = (Psig, Yka, sign(self.x, self.P, msg, self.rng)); return self.certs[ident]
    def revoke(self, ident): self.revoked.add(ident); self.rl_version += 1
    def rl_object(self, w):
        body = H("RL", w, self.rl_version, *sorted(self.revoked))
        return (w, self.rl_version, frozenset(self.revoked), sign(self.x, self.P, body, self.rng))

def rl_valid(ttpP, rl, w):
    ww, ver, rset, (Ub, s) = rl
    return ww == w and verify_one(ttpP, H("RL", ww, ver, *sorted(rset)), Ub, s)

class Sensor:
    def __init__(self, ident, ttp, rng):
        self.id, self.rng = ident, rng
        self.x, self.P = keygen(rng); self.y, self.Y = keygen(rng)      # separate signing / key-agreement keys
        ttp.certify(ident, self.P, self.Y)
        self.nvm = {}            # persistent: epoch state, w_last
        self.boot()
    def enrol_start(self, be_id, w=0):
        """SIGMA-I style three-message signed ephemeral DH with key confirmation
        (verified in Tamarin, hibaf_v3_enrol.spthy). Message 1: (S, BE, X)."""
        self._a = self.rng.randrange(1, Q); X = J.mul(self._a, L); self.be_id = be_id
        self._Xb = enc_point(X)
        return (self.id, be_id, self._Xb, w, sign(self.x, self.P, H("e1", self.id, be_id, self._Xb, w), self.rng))
    def enrol_finish(self, msg2, be_P):
        """Message 2: (S, BE, Y, Sig_BE(e2,S,BE,X,Y), MAC_Km(e2,BE)) -> message 3."""
        sid, be_id, Yb, (Ub, s), tag = msg2
        Xb = self._Xb
        assert sid == self.id and verify_one(be_P, H("e2", sid, be_id, Xb, Yb), Ub, s), "BE signature"
        Z = enc_point(J.mul(self._a, dec_point(Yb))); del self._a              # ephemeral erased
        Km = H("mac", Z, self.id, be_id, Xb, Yb)
        assert hmac.compare_digest(tag, PRF(Km, "e2", be_id, n=16)), "BE key confirmation"
        K0 = H("enrol", Z, self.id, be_id, Xb, Yb)
        self.nvm.update(K=K0, epoch=0, w_last=-1)
        return (self.id, be_id, sign(self.x, self.P, H("e3", self.id, be_id, Xb, Yb), self.rng), PRF(Km, "e3", self.id, n=16))
    def link_key(self, coll_id, Ycol):
        self.klink = H("link", enc_point(J.mul(self.y, Ycol)), self.id, coll_id)
    def boot(self):
        self.r = self.rng.getrandbits(NONCE_R_BITS); self.c = 0; self.cur_w = None; self.w_ram = -1
    def _advance_to_epoch(self, e):
        while self.nvm["epoch"] < e:                           # forward-secure PRG step, old state overwritten
            self.nvm["K"] = PRF(self.nvm["K"], "next", self.nvm["epoch"]); self.nvm["epoch"] += 1
            self.nvm["w_last"] = self.nvm["epoch"] * EPOCH_WINDOWS                   # one NVM write per epoch
    def accept_beacon(self, beacon, st_P, ttp_P):
        Mw, (Ub, s) = beacon
        ID_ST, site, w, rho, Texp, rl = Mw
        if not verify_one(st_P, H("beacon", ID_ST, site, w, rho, Texp, rl[1]), Ub, s): return False
        if not rl_valid(ttp_P, rl, w): return False
        if w < max(self.nvm["w_last"], self.w_ram): return False   # monotonic: RAM index, NVM floor = first window of stored epoch
        if w // EPOCH_WINDOWS < self.nvm["epoch"]: return False
        self._advance_to_epoch(w // EPOCH_WINDOWS)
        if w != self.cur_w: self.c = 0
        self.cur_w, self.rho = w, rho; self.w_ram = w                  # no NVM write per window
        return True
    def report(self, m: bytes, tau, t, nonce_override=None):
        w, rho = self.cur_w, self.rho
        if self.c >= (1 << NONCE_C_BITS) - 1: raise RuntimeError("counter exhausted: wait for next window")
        self.c += 1
        nu = nonce_override or (self.r.to_bytes(8, "big") + self.c.to_bytes(4, "big"))
        k = PRF(self.nvm["K"], "enc", self.id, self.be_id, w, rho, tau, n=16)
        AD0 = H("AD", self.id, w, rho, tau, t, nu)
        C = AESGCM(k).encrypt(nu, m, AD0)[:-16]          # GCM ciphertext does not depend on AD; first tag discarded
        msg = H("rep", self.id, w, rho, tau, t, nu, C)
        Ub, s = sign(self.x, self.P, msg, self.rng)
        CT = AESGCM(k).encrypt(nu, m, ad_full(self.id, w, rho, tau, t, nu, Ub, s))   # same C; tag binds (U_i, s_i)
        assert CT[:-16] == C
        body = (self.id, w, t, tau, nu, CT, Ub, s)
        mac = PRF(self.klink, "mac", *[str(x) for x in body], n=8)
        return body + (mac,)

def report_msg(rep, rho):
    """the signature covers the GCM ciphertext C (without the tag), so collectors can verify it"""
    ID, w, t, tau, nu, CT, Ub, s = rep[:8]
    return H("rep", ID, w, rho, tau, t, nu, CT[:-16])
def ad_full(ID, w, rho, tau, t, nu, Ub, s):
    """GCM associated data: report context plus the signature (U_i, s_i), so the tag binds the signature"""
    return H("AD2", H("AD", ID, w, rho, tau, t, nu), Ub, s)

class Collector:
    def __init__(self, ident, ttp, rng, quota=4):
        self.id, self.rng, self.ttp = ident, rng, ttp
        self.x, self.P = keygen(rng); self.y, self.Y = keygen(rng); ttp.certify(ident, self.P, self.Y)
        self.links, self.accepted, self.neg, self.count = {}, {}, set(), {}
        self.quota = quota; self.ctrl = BatchController(); self.evidence = []; self.notices = []
        self.stats = dict(mac_drop=0, early_drop=0, quota_drop=0, decode_drop=0, sig_drop=0, accepted=0)
    def add_sensor(self, sensor):
        self.links[sensor.id] = H("link", enc_point(J.mul(self.y, sensor.Y)), sensor.id, self.id)
    def new_window(self, w, rho, rl):
        assert rl_valid(self.ttp.P, rl, w)
        self.w, self.rho, self.rl = w, rho, rl
        self.accepted, self.neg, self.count = {}, set(), {}
    def process(self, reports):
        cand = []
        pending_fingerprints = set()
        for rep in reports:
            body, mac = rep[:8], rep[8]
            ID, w, t, tau, nu, CT, Ub, s = body
            kl = self.links.get(ID)
            if kl is None or not hmac.compare_digest(mac, PRF(kl, "mac", *[str(x) for x in body], n=8)):
                self.stats["mac_drop"] += 1; continue                     # zero group operations
            if w != self.w or ID in self.rl[2] or ID in self.neg or (ID, nu) in self.accepted:
                self.stats["early_drop"] += 1; continue
            if rep in pending_fingerprints:
                self.stats["early_drop"] += 1
                continue

            pending_fingerprints.add(rep)

            self.count[ID] = self.count.get(ID, 0) + 1
            if self.count[ID] > self.quota: self.stats["quota_drop"] += 1; continue
            try: dec_point(Ub); assert 0 <= s < Q
            except (ValueError, AssertionError): self.stats["decode_drop"] += 1; continue
            cand.append(rep)
        items = [(self.ttp.certs[r[0]][0], report_msg(r, self.rho), r[6], r[7]) for r in cand]
        ok = verify_with_controller(items, self.ctrl, self.rng) if items else []
        out = []
        for rep, good in zip(cand, ok):
            ID, nu = rep[0], rep[4]
            if not good:
                self.stats["sig_drop"] += 1; self.neg.add(ID)                # negative cache (rest of window)
                self.notices.append(rep); continue                           # signed notice carries the report
            if (ID, nu) in self.accepted:                                    # two VALID reports, same nonce
                if self.accepted[(ID, nu)][5] != rep[5]: self.evidence.append((self.accepted[(ID, nu)], rep))
                continue
            self.accepted[(ID, nu)] = rep; out.append(rep[:8]); self.stats["accepted"] += 1
        Mp = (self.id, self.w, self.rho, tuple(out))
        return (self.id, Mp, sign(self.x, self.P, H("cont", repr(Mp)), self.rng))

class Station:
    def __init__(self, ident, ttp, rng):
        self.id, self.rng, self.ttp = ident, rng, ttp
        self.x, self.P = keygen(rng); ttp.certify(ident, self.P, self.P)
        self.ctrl = BatchController()
    def beacon(self, w, rl):
        rho = os.urandom(16).hex(); Texp = 1000*(w+1)
        Mw = (self.id, "site1", w, rho, Texp, rl)
        return (Mw, sign(self.x, self.P, H("beacon", self.id, "site1", w, rho, Texp, rl[1]), self.rng)), rho
    def site_container(self, containers, w, rho, rl):
        items = [(self.ttp.certs[c[0]][0], H("cont", repr(c[1])), c[2][0], c[2][1]) for c in containers]
        ok = verify_with_controller(items, self.ctrl, self.rng)          # MSM batch over P container signatures
        acc = [c for c, g in zip(containers, ok) if g and c[1][1] == w and c[1][2] == rho and c[0] not in rl[2]]
        Ms = (self.id, w, rho, rl[1], tuple(acc))
        return Ms, sign(self.x, self.P, H("site", repr(Ms)), self.rng)

class BackEnd:
    def __init__(self, ident, ttp, rng, theta=0.25):
        self.id, self.rng, self.ttp, self.theta = ident, rng, ttp, theta
        self.y, self.Y = keygen(rng); self.x, self.P = keygen(rng); ttp.certify(ident, self.P, self.Y)
        self.K, self.N, self.committed, self.flags, self.pending = {}, {}, [], [], {}
        self.rho_seen, self.e1_seen, self.e1_count = {}, {}, {}
    def enrol(self, msg1, w_now=0):
        """Message 1 -> message 2. Message 1 is signed and carries the current window, so stale or forged
        requests are rejected with one signature check and no state. Nothing is installed yet."""
        sid, be_id, Xb, w1, (U1, s1) = msg1
        if not (be_id == self.id and sid in self.ttp.certs and sid not in self.ttp.revoked): return None
        if w1 not in (w_now, w_now - 1): return None
        if (sid, Xb) in self.e1_seen: return self.e1_seen[(sid, Xb)][:5]                 # replay/retransmission: cached reply
        if self.e1_count.get((sid, w_now), 0) >= 1: return None                         # rate limit: one new X per identity per window
        if not verify_one(self.ttp.certs[sid][0], H("e1", sid, be_id, Xb, w1), U1, s1): return None
        self.e1_count = {k: v for k, v in self.e1_count.items() if k[1] >= w_now - 1}; self.e1_count[(sid, w_now)] = 1
        b = self.rng.randrange(1, Q); Yb = enc_point(J.mul(b, L))
        Z = enc_point(J.mul(b, dec_point(Xb)))                                  # ephemeral b dropped
        Km = H("mac", Z, sid, self.id, Xb, Yb); K0 = H("enrol", Z, sid, self.id, Xb, Yb)
        self.pending[sid] = [(Xb, Yb, Km, K0)]                                          # at most one pending session per identity
        msg2 = (sid, self.id, Yb, sign(self.x, self.P, H("e2", sid, self.id, Xb, Yb), self.rng), PRF(Km, "e2", self.id, n=16))
        self.e1_seen = {k: v for k, v in self.e1_seen.items() if v[5] >= w_now - 1}       # keep current and previous window
        self.e1_seen[(sid, Xb)] = msg2 + (w1,)
        return msg2
    def enrol_confirm(self, msg3):
        """Message 3: install K0 only if the sensor's signature over (X, Y) and its key-confirmation MAC verify."""
        sid, be_id, (Ub, s), tag = msg3
        for i, (Xb, Yb, Km, K0) in enumerate(self.pending.get(sid, [])):
            if verify_one(self.ttp.certs[sid][0], H("e3", sid, be_id, Xb, Yb), Ub, s) and \
               hmac.compare_digest(tag, PRF(Km, "e3", sid, n=16)):
                self.K[sid] = [K0, 0]; del self.pending[sid]                     # other pending sessions dropped
                return True
        return False
    def check_evidence(self, rep, rho):
        """Revocation evidence: True iff the report's GCM tag verifies under the sensor's window key
        (only S_i or a holder of its ratchet state can produce it) AND its signature is invalid."""
        ID, w, t, tau, nu, CT, Ub, s = rep[:8]
        k = self._key(ID, w, rho, tau)
        if k is None: return False
        try: AESGCM(k).decrypt(nu, CT, ad_full(ID, w, rho, tau, t, nu, Ub, s))
        except Exception: return False
        return not verify_one(self.ttp.certs[ID][0], report_msg(rep, rho), Ub, s)
    def _key(self, ID, w, rho, tau):
        """st = [K, epoch, retained]. When the ratchet advances to epoch e, the back end derives the window keys of
        the previous epoch's LAST window (w = e*E - 1, every report type, with that window's rho) and erases the
        previous ratchet state K^(e-1) at once. The retained window keys serve late reports during the grace window
        and are erased at window e*E + 1. A corruption within the grace window therefore exposes at most the
        reports of window e*E - 1, never the rest of epoch e-1."""
        st = self.K[ID]
        while len(st) < 3: st.append(None)
        self.rho_seen.setdefault(w, rho)
        e = w // EPOCH_WINDOWS
        while st[1] < e:
            if st[1] == e - 1:
                wl = e * EPOCH_WINDOWS - 1
                st[2] = {(wl, self.rho_seen.get(wl), t): PRF(st[0], "enc", ID, self.id, wl, self.rho_seen.get(wl), t, n=16)
                         for t in REPORT_TYPES} if wl in self.rho_seen else None
            st[0] = PRF(st[0], "next", st[1]); st[1] += 1                                # previous state overwritten
        if st[2] is not None and w >= st[1] * EPOCH_WINDOWS + 1: st[2] = None           # grace over: erase window keys
        if e == st[1]: return PRF(st[0], "enc", ID, self.id, w, rho, tau, n=16)
        if st[2] is not None: return st[2].get((w, rho, tau))
        return None                                                                     # erased epoch
    def epoch_tick(self, w, rho):
        """Called for every window: when a new epoch starts, advance EVERY enrolled sensor's state (eager ratchet),
        so an idle sensor's previous-epoch state is erased on time."""
        for ID in list(self.K): self._key(ID, w, rho, REPORT_TYPES[0])
    def ingest(self, site, st_P, rl, audit_rng):
        Ms, (Ub, s) = site
        if not verify_one(st_P, H("site", repr(Ms)), Ub, s): return "site signature invalid"
        _, w, rho, rlver, conts = Ms
        self.epoch_tick(w, rho)
        if not rl_valid(self.ttp.P, rl, w) or rlver != rl[1]: return "revocation object invalid"
        Nw = self.N.setdefault(w, set()); Q_w = []
        for cid, Mp, _ in conts:
            for rep in Mp[3]:
                ID, ww, t, tau, nu, CT, Ub2, s2 = rep
                if ww != w or ID in rl[2] or (ID, nu) in Nw: continue
                k = self._key(ID, w, rho, tau)
                if k is None: continue
                try: m = AESGCM(k).decrypt(nu, CT, ad_full(ID, w, rho, tau, t, nu, Ub2, s2))
                except Exception:
                    self.flags.append(("integrity failure", cid)); continue      # tampered in transit or bad sensor tag
                Nw.add((ID, nu))                                  # [M2] in-loop dedupe
                Q_w.append((cid, rep, m))
        audit = [x for x in Q_w if audit_rng.random() < self.theta]
        items = lambda xs: [(self.ttp.certs[r[0]][0], report_msg(r, rho), r[6], r[7]) for _, r, _ in xs]
        bad_cols = set()
        if audit and not all(verify_with_controller(items(audit), BatchController(), self.rng)):
            ok = verify_with_controller(items(audit), BatchController(mu0=1.0), self.rng)
            bad_cols = {c for (c, _, _), g in zip(audit, ok) if not g}
        if bad_cols:                                             # escalate per offending container only
            sus = [x for x in Q_w if x[0] in bad_cols]
            ok = verify_with_controller(items(sus), BatchController(mu0=1.0), self.rng)
            drop = {id(x) for x, g in zip(sus, ok) if not g}
            for x, g in zip(sus, ok):
                if not g: self.ttp.revoke(x[1][0])          # valid tag + invalid signature = evidence (Prop. revocation)
            Q_w = [x for x in Q_w if id(x) not in drop]; self.flags.append(("collector misbehaviour", bad_cols))
        for _, rep, m in Q_w: self.committed.append((rep[0], w, rep[4], m))
        return "ok"


def revoke_with_evidence(ttp, be, rep, rho):
    """Global revocation policy: the TTP revokes only on back-end-validated evidence."""
    if be.check_evidence(rep, rho):
        ttp.revoke(rep[0]); return True
    return False

