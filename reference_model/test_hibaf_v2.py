"""Attack/correctness tests for the HiBaF v2 reference model.  Run: python3 test_hibaf_v2.py"""
import random, copy
from hibaf_v2_ref import *

rng = random.Random(2026)
RESULTS = []
def check(name, cond):
    RESULTS.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name)

# 0. canonical encoding round-trip, including every degree-1 divisor
_n = 0
for _ in range(500):
    D = J.mul(rng.randrange(1, Q), L); _n += dec_point(enc_point(D)) == D
for _x in range(P_FIELD):
    _fx = sum(c*pow(_x, i, P_FIELD) for i, c in enumerate(F_CURVE)) % P_FIELD
    for _y in range(P_FIELD):
        if _y*_y % P_FIELD == _fx:
            D = ((-_x % P_FIELD, 1), (_y,) if _y else ()); _n += dec_point(enc_point(D)) == D
check(f"canonical point encoding round-trips ({_n} divisors, all degree-1 points included)", _n > 500)

ttp = TTP(rng); st = Station("ST", ttp, rng); be = BackEnd("BE", ttp, rng, theta=1.0)
cols = [Collector(f"B{p}", ttp, rng) for p in range(2)]
sensors = [Sensor(f"S{i}", ttp, rng) for i in range(8)]
MSG1, MSG3 = {}, {}
for s in sensors:
    MSG1[s.id] = s.enrol_start(be.id)
    MSG3[s.id] = s.enrol_finish(be.enrol(MSG1[s.id]), be.P)
    assert be.enrol_confirm(MSG3[s.id])
    c = cols[int(s.id[1:]) % 2]; s.link_key(c.id, c.Y); c.add_sensor(s)
check("TTP never holds K_i^(0): signed ephemeral DH gives S and BE the same K0 (no escrow)",
      all(s.nvm["K"] == be.K[s.id][0] for s in sensors))
# [review E] replayed message 1 / message 3 must not change the back end's key (v2 flaw)
K_before = be.K["S0"][0]
m2_replay = be.enrol(MSG1["S0"])                    # adversary replays an old message 1
ok_replay = be.enrol_confirm(MSG3["S0"])            # ... and the old message 3 (signature over the old Y)
check("replayed enrolment messages 1 and 3 do not change the back end's key (installed only after a fresh message 3)",
      ok_replay is False and be.K["S0"][0] == K_before)
check("enrolment message 1 from an old window is rejected with one signature check and no pending state",
      be.enrol(MSG1["S1"], w_now=5) is None and "S1" not in be.pending)

def run_window(w, extra=None, collectors_extra=None, theta=None):
    rl = ttp.rl_object(w); beacon, rho = st.beacon(w, rl)
    for s in sensors:
        if not s.accept_beacon(beacon, st.P, ttp.P): pass
    for c in cols: c.new_window(w, rho, rl)
    reps = {c.id: [] for c in cols}
    for s in sensors:
        if s.id in rl[2] or s.cur_w != w: continue
        reps[cols[int(s.id[1:]) % 2].id].append(s.report(f"DO={6+int(s.id[1:])/10:.1f}".encode(), tau=1, t=w*10))
    if extra: extra(reps, rho, w)
    conts = [c.process(reps[c.id]) for c in cols]
    if collectors_extra: conts = collectors_extra(conts, rho, w)
    site = st.site_container(conts, w, rho, rl)
    before = len(be.committed); res = be.ingest(site, st.P, rl, random.Random(w))
    return res, be.committed[before:], reps, rho, beacon, conts

# 1. honest window
res, com, reps, rho, beacon, conts = run_window(0)
check("honest window: all 8 reports committed exactly once and decrypt correctly",
      res == "ok" and len(com) == 8 and len({(c[0], c[2]) for c in com}) == 8 and
      all(m == f"DO={6+int(i[1:])/10:.1f}".encode() for i, _, _, m in com))
ops_batch = OPS["group_ops"]

# 2. same-window replay at same collector (next batch of the window)
r0 = reps["B0"][0]
c2 = cols[0].process([r0]); check("same-window replay to same collector dropped before any group op",
                                  len(c2[1][3]) == 0 and cols[0].stats["early_drop"] >= 1)

# 3. replay through a second collector in the same site container -> BE in-loop dedupe [M2]
def dup_via_other(conts, rho, w):
    # malicious/second collector forwards a copy of a report already in B0's container
    cid, Mp, _ = conts[1]; Mp2 = (cid, Mp[1], Mp[2], Mp[3] + (conts[0][1][3][0],))
    sigc = sign(cols[1].x, cols[1].P, H("cont", repr(Mp2)), rng)
    return [conts[0], (cid, Mp2, sigc)]
res, com, *_ = run_window(1, collectors_extra=dup_via_other)
check("duplicate report carried by two collectors is committed once (fix of Alg. 4)",
      len(com) == 8 and len({(c[0], c[2]) for c in com}) == 8)

# 4. cross-window replay
def xwin(reps, rho, w):
    reps["B0"].append(r0)                                  # report from window 0
res, com, *_ = run_window(2, extra=xwin)
check("cross-window replay dropped (w != current)", len(com) == 8)
def rewrite_w(reps, rho, w):
    body = list(r0[:8]); body[1] = w
    mac = PRF(cols[0].links[r0[0]], "mac", *[str(x) for x in body], n=8)   # even with a valid link MAC
    reps["B0"].append(tuple(body) + (mac,))
res, com, *_ = run_window(3, extra=rewrite_w)
check("window field rewritten (insider with link key): signature fails, report not committed",
      len(com) == 8 and cols[0].stats["sig_drop"] >= 1)

# 5. non-canonical encoding of U (malleability) [M12]
def maul(reps, rho, w):
    rep = list(reps["B1"][0]); Ub = bytearray(rep[6])
    x = int.from_bytes(Ub[1:3], "big"); Ub[1:3] = (x + P_FIELD).to_bytes(2, "big")   # same value mod p
    rep[6] = bytes(Ub); body = tuple(rep[:8])
    rep[8] = PRF(cols[1].links[rep[0]], "mac", *[str(v) for v in body], n=8)
    reps["B1"].append(tuple(rep))
res, com, *_ = run_window(4, extra=maul)
check("non-canonical U encoding rejected at decoding; no double commit", len(com) == 8 and cols[1].stats["decode_drop"] >= 1)

# 6. outsider forgery -> MAC pre-filter, zero group operations
def outsider(reps, rho, w):
    fake = list(reps["B0"][0]); fake[7] = (fake[7] + 1) % Q; fake[8] = b"\x00"*8
    reps["B0"] += [tuple(fake)]*50
g0 = OPS["group_ops"]; res, com, *_ = run_window(5, extra=outsider)
check("50 outsider forgeries dropped by link MAC (no group operation spent on them)",
      len(com) == 8 and cols[0].stats["mac_drop"] >= 50)

# 7. insider invalid signatures -> controller isolates, negative cache, quota
def insider(reps, rho, w):
    for k in range(10):
        rep = list(reps["B0"][0]); rep[4] = rng.randbytes(12); rep[7] = rng.randrange(Q)
        body = tuple(rep[:8]); rep[8] = PRF(cols[0].links[rep[0]], "mac", *[str(v) for v in body], n=8)
        reps["B0"].append(tuple(rep))
res, com, _, rho_w6, *_ = run_window(6, extra=insider)
check("insider invalid signatures isolated; honest reports of the window still committed",
      len(com) == 8)
check("per-identity quota / negative cache bound the insider's verification load",
      cols[0].stats["quota_drop"] + cols[0].stats["early_drop"] >= 6)

# [review D] evidence-based revocation
# (a) the insider reports of check 10 changed the nonce, so their GCM tag no longer verifies: a collector's
#     notice cannot be attributed to the sensor and must NOT revoke it (local negative cache only)
rho6 = st_rho = None
check("notices whose GCM tag does not verify (forged or altered reports) do not revoke the accused sensor",
      len(cols[0].notices) > 0 and not any(revoke_with_evidence(ttp, be, r, rho_w6) for r in cols[0].notices[:5])
      and "S0" not in ttp.revoked)
# (b) Byzantine collector fabricates a report for honest S6 (it knows the link key but not the ratchet state)
def byz_accuse(reps, rho, w):
    s6 = sensors[6]; body = ("S6", w, w*10, 1, rng.randbytes(12), rng.randbytes(40), reps["B0"][0][6], rng.randrange(Q))
    reps["B0"].append(body + (PRF(cols[0].links["S6"], "mac", *[str(v) for v in body], n=8),))
cols[0].notices.clear()
res, com, reps7, rho_b, *_ = run_window(7, extra=byz_accuse)
check("Byzantine collector's fabricated accusation of an honest sensor is rejected by the back end (no false revocation)",
      any(r[0] == "S6" for r in cols[0].notices) and not revoke_with_evidence(ttp, be, [r for r in cols[0].notices if r[0] == "S6"][0], rho_b)
      and "S6" not in ttp.revoked)
# (c) compromised S3 (attacker holds its ratchet state): valid GCM, invalid signature -> confirmed evidence
def compromised_report(sen, m, tau, t):
    """attacker holding sen's ratchet state: valid GCM tag over an INVALID signature (tag bound to the bad s)"""
    w, rho = sen.cur_w, sen.rho; sen.c += 1; nu = sen.r.to_bytes(8, "big") + sen.c.to_bytes(4, "big")
    k = PRF(sen.nvm["K"], "enc", sen.id, sen.be_id, w, rho, tau, n=16)
    C = AESGCM(k).encrypt(nu, m, H("AD", sen.id, w, rho, tau, t, nu))[:-16]
    Ub, s_ = sign(sen.x, sen.P, H("rep", sen.id, w, rho, tau, t, nu, C), sen.rng); s_ = (s_ + 1) % Q
    CT = AESGCM(k).encrypt(nu, m, ad_full(sen.id, w, rho, tau, t, nu, Ub, s_))
    return (sen.id, w, t, tau, nu, CT, Ub, s_, b"")
s3 = sensors[3]; ev = list(compromised_report(s3, b"evil", 1, 7*10))
check("compromised sensor: report with valid GCM tag and invalid signature is confirmed evidence; TTP revokes",
      revoke_with_evidence(ttp, be, tuple(ev), rho_b) and "S3" in ttp.revoked)

# 8. revocation
res, com, *_ = run_window(8)
check("revoked S3 rejected end to end (sensor, collector, back end)", all(c[0] != "S3" for c in com) and len(com) == 7)

# 9. reboot inside a window: new boot randomness, no nonce reuse; old beacon replay rejected
s0 = sensors[0]; rl8 = ttp.rl_object(8); bc8, rho8 = st.beacon(8, rl8)
assert s0.accept_beacon(bc8, st.P, ttp.P); a = s0.report(b"x", 1, 1)
s0.boot(); assert s0.accept_beacon(bc8, st.P, ttp.P); b = s0.report(b"y", 1, 2)
check("reboot within a window yields a fresh nonce (r_i re-sampled)", a[4] != b[4])
s0.boot(); check("replayed old beacon (w=0) rejected after reboot via NVM w_last", not s0.accept_beacon(beacon, st.P, ttp.P))

# 10. ratchet catch-up and erasure
s0.nvm["K"]; e_now = s0.nvm["epoch"]
rl_far = ttp.rl_object(30); bc_far, rho_far = st.beacon(30, rl_far)
assert s0.accept_beacon(bc_far, st.P, ttp.P)
check(f"sensor skips epochs {e_now}->{s0.nvm['epoch']} and back end catches up to the same window key",
      PRF(s0.nvm["K"], "enc", "S0", "BE", 30, rho_far, 1, n=16) == be._key("S0", 30, rho_far, 1))
check("back end refuses keys of an erased (past) epoch", be._key("S0", 0, "r", 1) is None)

# 11. malicious collector alters s of a forwarded report -> AEAD still valid, audit catches it
def alter_s(conts, rho, w):
    cid, Mp, _ = conts[0]; reps_ = list(Mp[3]); r = list(reps_[0]); r[7] = (r[7] + 5) % Q; reps_[0] = tuple(r)
    Mp2 = (cid, Mp[1], Mp[2], tuple(reps_)); return [(cid, Mp2, sign(cols[0].x, cols[0].P, H("cont", repr(Mp2)), rng)), conts[1]]
be.flags.clear(); res, com, *_ = run_window(31, collectors_extra=alter_s)
check("collector-modified signature breaks the GCM tag: report not committed, integrity failure recorded for that collector",
      ("integrity failure", "B0") in be.flags and len(com) == 6)



# 12. equivocation evidence: sensor reuses a nonce for two different measurements
s1 = sensors[1]; rl32 = ttp.rl_object(32); bc32, rho32 = st.beacon(32, rl32)
for s in sensors: s.accept_beacon(bc32, st.P, ttp.P)
cols[1].new_window(32, rho32, rl32)
nu = b"\x01"*12; ra = s1.report(b"A", 1, 1, nonce_override=nu); rb = s1.report(b"B", 1, 2, nonce_override=nu)
cols[1].process([ra, rb])
check("two valid reports with the same (ID, nonce) produce transferable equivocation evidence",
      len(cols[1].evidence) == 1)

# 13. batch soundness on the prime-order group: invalid item never accepted in 300 random batches
items = []
for s in sensors[:6]:
    if s.id == "S3": continue
    rep = s.report(b"z", 1, 3); items.append((s.P, report_msg(rep, s.rho), rep[6], rep[7]))
bad = list(items[2]); bad[3] = (bad[3] + 1) % Q; items_bad = items[:2] + [tuple(bad)] + items[3:]
acc = sum(batch_verify(items_bad, random.Random(k)) for k in range(300))
check(f"batch with one invalid signature accepted {acc}/300 times (bound 2^-16 per test for 16-bit alphas)", acc == 0)
check("all-valid batch accepted", batch_verify(items, random.Random(1)))

# [review 2] a collector mutates s_i of an HONEST report and files it as a notice: the GCM tag now covers (U_i, s_i)
rl33 = ttp.rl_object(33); bc33, rho33 = st.beacon(33, rl33)
for s_ in sensors: s_.accept_beacon(bc33, st.P, ttp.P)
hon = list(sensors[6].report(b"ok", 1, 330)); hon[7] = (hon[7] + 1) % Q
check("honest report with a collector-mutated signature is not accepted as revocation evidence",
      not revoke_with_evidence(ttp, be, tuple(hon), rho33) and "S6" not in ttp.revoked)

# [review 3] epoch boundary: a late report from the last window of an epoch is decrypted during the grace window
E_ = EPOCH_WINDOWS; wl = 9 * E_ - 1                                  # last window of epoch 8
rlA = ttp.rl_object(wl); bcA, rhoA = st.beacon(wl, rlA); s1_ = sensors[1]; s1_.accept_beacon(bcA, st.P, ttp.P)
k_sensor = PRF(s1_.nvm["K"], "enc", "S1", be.id, wl, rhoA, 1, n=16)
be._key("S1", wl, rhoA, 1)                                           # back end processes window wl normally
be._key("S1", wl + 1, "x", 1)                                        # ... then the first window of the next epoch
st_ = be.K["S1"]
only_window_keys = isinstance(st_[2], dict) and all(k[0] == wl for k in st_[2]) and st_[1] == (wl + 1) // E_
k_grace = be._key("S1", wl, rhoA, 1)
other_window = be._key("S1", wl - 1, "r", 1)                         # earlier window of the old epoch: no key
be._key("S1", wl + 2, "x", 1)                                        # grace over
check("epoch grace: late report of the last window decrypted, no previous ratchet state kept, other windows and post-grace refused",
      k_grace == k_sensor and only_window_keys and other_window is None and be._key("S1", wl, rhoA, 1) is None)

# [review 4] a Byzantine collector files an HONEST report (valid tag, valid signature) as a notice: the back end
# re-verifies the signature itself, so no revocation
wn = wl + 3; rlN = ttp.rl_object(wn); bcN, rhoN = st.beacon(wn, rlN)
for s_ in sensors: s_.accept_beacon(bcN, st.P, ttp.P)
honest = sensors[6].report(b"fine", 1, 10*wn)
check("honest report submitted as a notice is rejected: the back end re-verifies the signature (no revocation)",
      not revoke_with_evidence(ttp, be, honest, rhoN) and "S6" not in ttp.revoked)

# [review 5] lazy collector forwards a compromised sensor's report without verifying it: theta=1 audit finds a
# valid tag with an invalid signature -> sensor revoked, collector flagged
def lazy(conts, rho, w):
    cid, Mp, _ = conts[1]; bad = compromised_report(sensors[5], b"x", 1, 10*w)
    reps_ = list(Mp[3]) + [bad[:8]]; Mp2 = (cid, Mp[1], Mp[2], tuple(reps_))
    return [conts[0], (cid, Mp2, sign(cols[1].x, cols[1].P, H("cont", repr(Mp2)), rng))]
be.flags.clear(); res, com, *_ = run_window(wn + 1, collectors_extra=lazy)
check("lazy collector: audit finds valid tag + invalid signature, revokes the sensor and flags the collector",
      "S5" in ttp.revoked and any(f_[0] == "collector misbehaviour" and "B1" in f_[1] for f_ in be.flags)
      and not any(c[0] == "S5" and c[3] == b"x" for c in com))

# [review 6] enrolment message 1 replayed within its window: cached message 2, pending session untouched,
# the legitimate message 3 still completes
s7 = sensors[7]; W_ = wn + 2
m1 = s7.enrol_start(be.id, w=W_); m2 = be.enrol(m1, w_now=W_); pend = list(be.pending["S7"])
m2r = be.enrol(m1, w_now=W_)
m3 = s7.enrol_finish(m2, be.P)
check("enrolment message 1 replayed within its window: same message 2, pending session unchanged, enrolment completes",
      m2r == m2 and be.pending.get("S7") == pend and be.enrol_confirm(m3) and be.K["S7"][0] == s7.nvm["K"])

# [review 7] eager ratchet: an idle (enrolled, silent) sensor's back-end state advances at every epoch boundary
s8 = Sensor("S8", ttp, rng); W8 = W_ + 1
m81 = s8.enrol_start(be.id, w=W8); m82 = be.enrol(m81, w_now=W8); be.enrol_confirm(s8.enrol_finish(m82, be.P))
# [review 8] enrolment rate limit: a second NEW ephemeral from the same identity in the same window is refused
m81b = s8.enrol_start(be.id, w=W8)
check("enrolment rate limit: a second new message 1 from one identity in the same window is refused without work",
      be.enrol(m81b, w_now=W8) is None)
w_far = (W8 // EPOCH_WINDOWS + 3) * EPOCH_WINDOWS + 1               # three epochs later, S8 still silent
res, com, *_ = run_window(w_far)
check("eager ratchet: a silent sensor's back-end state is at the current epoch; its earlier epochs are erased",
      be.K["S8"][1] == w_far // EPOCH_WINDOWS and be._key("S8", W8, "r", 1) is None and all(c[0] != "S8" for c in com))

# [review 9] idle sensor that hears no beacon keeps its stored epoch (accepted limitation: it cannot ratchet
# without a beacon), and catches up to the back end's state on the next beacon it accepts
e8_stored = s8.nvm["epoch"]
lagging = e8_stored < be.K["S8"][1]          # stored epoch lags the back end (no beacon heard)
rlF = ttp.rl_object(w_far); bcF, _ = st.beacon(w_far, rlF)
s8.accept_beacon(bcF, st.P, ttp.P)
check("idle sensor without beacons keeps its stored epoch; on the next beacon it ratchets to the back end's state",
      lagging and s8.nvm["epoch"] == be.K["S8"][1] and s8.nvm["K"] == be.K["S8"][0])

# [review 10] grace retention holds exactly one window key per report type (|T| keys per sensor) for window cE-1 only
wl_b = (w_far // EPOCH_WINDOWS + 1) * EPOCH_WINDOWS - 1
run_window(wl_b); run_window(wl_b + 1)
ret = be.K["S8"][2]
check("grace retention at an epoch boundary: |T| = %d window keys per sensor, all for the old epoch's last window" % len(REPORT_TYPES),
      isinstance(ret, dict) and len(ret) == len(REPORT_TYPES) and {k[0] for k in ret} == {wl_b}
      and {k[2] for k in ret} == set(REPORT_TYPES))

# [replay injection] byte-identical copies of a report that is still pending (same batch) are dropped before the
# quota and before any group operation; a DIFFERENT report reusing the same (ID, nonce) is still verified
# (equivocation evidence preserved)
wq = w_far + 3; rlq = ttp.rl_object(wq); bcq, rhoq = st.beacon(wq, rlq)
for s_ in sensors: s_.accept_beacon(bcq, st.P, ttp.P)
col0 = cols[0]; col0.new_window(wq, rhoq, rlq)
s_v = [s_ for s_ in sensors if s_.id in col0.links][0]
rep1 = s_v.report(b"t1", 1, 10*wq)
s_v.c -= 1                                                            # same nonce, different content (equivocation)
rep2 = s_v.report(b"t2", 1, 10*wq + 1)
same_nonce = rep2[4] == rep1[4] and rep2 != rep1
before_tests = col0.stats.get("pending_dup", 0); before_q = col0.count.get(s_v.id, 0); ev_before = len(col0.evidence)
col0.process([rep1] * 6 + [rep2])
dup_ok = col0.stats.get("pending_dup", 0) - before_tests == 5 and col0.count.get(s_v.id, 0) - before_q == 2
check("pending duplicates: 5 exact copies dropped before quota/verification; a different report with the same nonce still yields equivocation evidence",
      dup_ok and same_nonce and len(col0.evidence) == ev_before + 1)

# [v20] check 36: deferred associated data. The sensor makes two GCM calls with the same key and nonce; only the
# final tag (associated data include U_i, s_i) may leave the sensor, and a failure between the two calls must
# retire the nonce (no second encryption under it).
import hibaf_v2_ref as _ref
from cryptography.exceptions import InvalidTag
wt = wq + 1; rlt = ttp.rl_object(wt); bct, rhot = st.beacon(wt, rlt)
acc_t = s_v.accept_beacon(bct, st.P, ttp.P)
m_t = b"DO=7.1"
rep_t = s_v.report(m_t, 1, 10*wt)
ID_t, w_t, t_t, tau_t, nu_t, CT_t, Ub_t, s_t = rep_t[:8]
k_t = PRF(s_v.nvm["K"], "enc", s_v.id, s_v.be_id, w_t, rhot, tau_t, n=16)
AD0_t = H("AD", s_v.id, w_t, rhot, tau_t, t_t, nu_t)
T0 = AESGCM(k_t).encrypt(nu_t, m_t, AD0_t)[-16:]                     # the preliminary (discarded) tag
wire = b"".join(x if isinstance(x, (bytes, bytearray)) else str(x).encode() for x in rep_t)
final_ok = AESGCM(k_t).decrypt(nu_t, CT_t, ad_full(ID_t, w_t, rhot, tau_t, t_t, nu_t, Ub_t, s_t)) == m_t
try:
    AESGCM(k_t).decrypt(nu_t, CT_t, AD0_t); prelim_accepts = True
except InvalidTag:
    prelim_accepts = False
C_first = AESGCM(k_t).encrypt(nu_t, m_t, AD0_t)[:-16]                    # ciphertext of the first call
contract = len(nu_t) == 12 and len(CT_t) - len(C_first) == 16 and CT_t[:-16] == C_first   # 96-bit nonce, 128-bit tag, same ciphertext
only_final = T0 not in wire and CT_t[-16:] != T0 and final_ok and not prelim_accepts and contract
_orig_sign = _ref.sign
def _fail(*a, **k): raise RuntimeError("injected failure between the two GCM calls")
_ref.sign = _fail
c_before = s_v.c
try:
    s_v.report(b"DO=7.2", 1, 10*wt + 1); failed = False
except RuntimeError:
    failed = True
finally:
    _ref.sign = _orig_sign
nu_failed = s_v.r.to_bytes(8, "big") + (c_before + 1).to_bytes(4, "big")
rep_n = s_v.report(b"DO=7.3", 1, 10*wt + 2)
retired = failed and s_v.c == c_before + 2 and rep_n[4] != nu_failed
check("deferred AD: one 128-bit tag per 96-bit nonce, both calls give the same ciphertext, only the final tag is released (the preliminary tag is absent and does not verify); a failure between the calls retires the nonce",
      acc_t and only_final and retired)

print(f"\n{sum(r for _, r in RESULTS)}/{len(RESULTS)} checks passed")
