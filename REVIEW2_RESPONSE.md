# Response to the correctness review (second review)

| Point | Verdict | Change | Evidence |
|---|---|---|---|
| Prop. 6 revocation soundness false (signature not under the GCM tag) | Correct, real flaw | Sign-then-tag: C_i computed first (GCM ciphertext is AD-independent), signature over C_i, tag over AD_i‖U_i‖s_i, C_i. Same report size; one extra GHASH pass | Tamarin: tag-excludes-signature variant falsified (8 steps), fixed variant verified (9); checks 22, 26 |
| Attribution in Prop. 5 / check 21 ambiguous | Correct | Altered reports now fail GCM; integrity failures recorded per collector but stated as not proof; audit covers unverified forwarding | Prop. 5 rewritten; check 22 |
| Assumption list incomplete (CDH, signature, MAC) | Correct | Assumption 3 (CDH); EUF-CMA and MAC security stated; Adv_enrol tied to CDH + SIGMA | Sec. III-D, V |
| Unsigned enrolment message 1 (DoS amplification; Fig. 2 inconsistent) | Correct | Message 1 signed and bound to current window; one pending session per identity; Fig. 2 redrawn with 3 messages | Tamarin enrolment re-verified (14/18/20/8/11 steps); check 4 |
| Epoch boundary drops late reports | Correct | Back end keeps previous epoch state until the grace period of the new epoch's first window ends | check 27 |
| Tamarin "replay resistance" overstated | Correct | Abstract/conclusion: window binding + revocation soundness; injective agreement stated as given the replay cache | Sec. V-B |
| Flash wear 1.05 M writes/yr | Correct | Window index in RAM; NVM written once per epoch (8,760/yr); reboot floor = first window of stored epoch | Alg. 1, check 19 |
| 4.5–5.0× vs individual | Correct | 4.1–4.6× against c1 = 1.15 | Sec. VI-B |
| 0.32–0.34 vs Table (0.31 at n = 50) | Correct | 0.31–0.34 | Sec. VI-B |
| Abstract conflates PDR and delay | Correct | "99.9% delivery, mean delay 0.25 s (p95 0.30 s)" | Abstract |
| 99.8% under attack not scoped | Correct | Scoped to scenario D | Abstract, VI-I, VII |
| Controller guarantee conditions missing in abstract | Correct | "independent invalid reports and accurate rate estimate" | Abstract, VII |
| W(1,1) = 2c1 by Eq. (4) | Correct | b = 1 defined as the individual verification itself | Sec. IV-E |
| 2-term vs 3-term | Correct | Table IV: 2×2 | Table IV |
| 0.302 s vs "within 0.30 s" | Correct | "about 0.3 s (0.29–0.30 s on average)" | VI, VII |
| Citation [42] (Bos et al.) | Correct | Index-calculus statement now cites Gaudry–Thomé–Thériault–Diem, Math. Comp. 76(257):475–492, 2007 | Sec. III-D |

No simulation rerun is needed: report sizes and cryptographic costs are unchanged (the extra GHASH pass is < 0.3% of a scalar multiplication), enrolment and NVM writes are not modelled in ns-3.

# Third review round

| Point | Verdict | Change | Evidence |
|---|---|---|---|
| Grace period weakens epoch FS | Correct | At an epoch change the back end keeps only the last window's derived keys, erases K^(c-1) immediately, erases the window keys after the grace period; Theorem 1, requirement 4 and the compromise table state the single exposed window | check 27 (also asserts no previous ratchet state is kept and other windows are refused) |
| IV-G does not say BE re-verifies the signature | Correct | Text and Algorithm 4: BE re-verifies; evidence = valid tag AND invalid signature | check 28 (honest report filed as notice) |
| Enrolment message 1 replayable within its window | Correct | Cache of message 2 per (ID, X) for current and previous window; replay gets the cached reply, no work, pending session untouched; tolerance w ∈ {current, previous} | check 30 |
| CDH vs Gap-CDH | Correct | Assumption 3 is Gap-CDH; listed in the adversary model | Sec. III |
| 0.1 ms vs 0.3% | Correct | 0.35% at 28.62 ms, 0.15% at 66–99 ms | Sec. IV-C |
| Lazy-collector detection narrower | Correct | Prop. 5: detection concerns reports from compromised sensors; skipping verification of honest reports is undetectable but harmless | Prop. 5 |
| Audit evidence and revocation | Correct | Audit-found valid-tag/invalid-signature report revokes the sensor and flags the collector | check 29 |
| 0.26–0.28 vs 0.25–0.28 | Correct | 0.25–0.28 throughout | Abstract, VII |
| p95 0.30 s untraceable | Correct | Scenario A text cites p95 0.300 s at 500 sensors (Table S2) | Sec. VI |
| Shared-channel claim in conclusion | Correct | Scoped to light load; 0.85–0.90 at 50 reports/s | VII |
| Table XV check 18 | Correct | Replay: checks 6–8, 19 | Table XV |

# Fourth review round

| Point | Verdict | Change | Evidence |
|---|---|---|---|
| Prop. 6 needs GCM with deferred AD | Correct | Route chosen: keep split mode (no extra bytes, no ns-3 rerun). Assumption 2 now states INT-CTXT for deferred associated data, justified by GCM's Wegman–Carter structure (McGrew–Viega ePrint 2004/193; Iwata–Ohashi–Minematsu, CRYPTO 2012, LNCS 7417:31–49); implementation with two standard one-shot GCM calls (first tag discarded, one tag released per nonce) | Sec. III-D, IV-C, Prop. 6 |
| Lazy ratcheting | Correct | Back end advances every sensor's state at each epoch boundary (Algorithm 4); sensors advance on accepting a beacon of a new epoch; Theorem 1 defines c as the epoch of the stored state | check 32 (silent sensor) |
| Grace exception not carried through | Correct | Table XV, V-B3, VI-J and the Tamarin paragraph qualified; Tamarin FS lemma stated as proved without grace retention | text |
| TTP key: Conf = Y too strong | Correct | Conf = P: already-enrolled sensors keep confidentiality; sensors enrolled/re-enrolled during compromise do not (rogue back end); Prop. 7 and V-B3 reworded | Table VII |
| Enrolment work unbounded for compromised sensor | Correct | At most one new X per identity per window | check 31 |
| Tamarin caveats in abstract / Table I | Correct | "report agreement given the replay caches"; Table I legend caveat | Abstract, Table I |
| Table VII Byzantine collector Auth footnote | Correct | Footnote: committed data rest on GCM; audit only detects unverified forwarding of compromised sensors' reports | Table VII |
| Enrolment window liveness | Correct | One-line liveness note | Sec. IV-A |

# Fifth review round

| Point | Verdict | Change | Evidence |
|---|---|---|---|
| Two GCM calls under one nonce: first tag must never leak | Correct | Implementation rules in Sec. IV-C: first tag overwritten at once, never logged, retried, written to NVM or exposed via debug; failure between calls retires the nonce; fault/side-channel protection must cover the buffer. Supplement explains why (two tags per nonce give a solvable GHASH equation in H) | Sec. IV-C; Supp. S-VII, Remark 1 |
| Deferred-AD INT-CTXT is a non-standard assumption | Correct | Closed rather than disclosed: Assumption 3 is now only "BLAKE2s is a PRF, AES-128 is a PRP"; a direct proof for 96-bit nonces (Supplementary Lemma S1) bounds the deferred-AD forgery advantage by Adv_prp + N^2/2^129 + q_v*l/2^128. "Well founded" wording removed; the proof is stated as our own pen-and-paper argument, not machine-checked. The separate-MAC route is named in VI-J as the alternative that would rely on standard INT-CTXT only | Sec. III-D, Prop. 6, Supp. S-VII |
| Abstract "AES-GCM assumptions" | Correct | Abstract now: AES pseudorandom-permutation assumption, with a direct proof that GCM tags stay unforgeable when the associated data is fixed after the ciphertext | Abstract |
| Eager ratchet makes epoch-boundary load bursty | Correct | VI-F: S(1+n_tau) PRF calls fall in one window; can be spread by deriving K^(c) and the window-(cE-1) keys during window cE-1 | Sec. VI-F |
| Idle sensor cannot ratchet without beacons | Correct | Stated as an accepted limitation in VI-J (sensor-side exposure unbounded in wall-clock time), and below Theorem 1 | new check 33 |
| Retention precomputation and per-type keys | Correct | Table X back-end PRF count is now N + S(1+n_tau)/E with a footnote; Algorithm 4 says one retained key per report type; n_tau = 2 in the reference model | Table X, Alg. 4, new check 34 |
| Table XV evidence for state compromise | Correct | Now cites checks 20-21, 27, 32-34 and both Tamarin ratchet models; outcome notes that an idle sensor's stored epoch may lag | Table XV |
| Theorem 1: idle sensor lag | Correct | Sentence below the theorem: c is the stored epoch; the back end's is always current, an idle sensor's lags | Sec. V-B1 |
| Tamarin claim about an unrun model | Correct | Ran the extended model instead of rephrasing: `hibaf_v3_fs_grace.spthy` (Tamarin 1.10.0) verifies forward secrecy with the grace exception (64 steps), secrecy of non-last windows (21), secrecy after the grace period (18), and reachability of the grace exposure (9) | Table VI, `tamarin/fs_grace.log` |
| Rate limit vs. honest re-enrolment after reboot | Correct | Clause added: an honest sensor with a new X in the same window waits at most one window (liveness only) | Sec. IV-A |

Reference model: 35/35 checks pass (`reference_model/test_output.txt`). No ns-3 rerun: report format and sizes are unchanged.

# Self-check of the current version (consistency pass)

| Issue found | Type | Fix |
|---|---|---|
| Table VII: back end compromise listed revocation as preserved (Y) | Error | Now N, with footnote: a compromised back end holds every window key and can fabricate evidence; Prop. 6 assumes an uncorrupted back end |
| Nonce bound: "rebooted twice in every window" gives 2^-39.1, not < 2^-40 | Numeric error | Reworded to one reboot per window (B_w = 2, 2^-40.7); evidence table aligned |
| c1 defined as C_MSM(3), but every number uses the 2-term individual verification (1.152 HECM; MSM at n = 1 is 1.19) | Inconsistency | c1 = C_MSM(2), the individual verification |
| "As mu -> 0 the controller picks the largest admissible batch", but it picks b = 64 (c(b)/b is flat; b = 128 is admissible) | Contradiction with Sec. VI-E | Reworded: lowest per-report cost, b = 64 with the measured costs |
| N_w used both for the collector's negative cache and for the back end's committed (ID, nu) set | Notation clash | Back-end set renamed M_w (Alg. 4, Prop. 5, attacks paragraph) |
| Prop. 4 and Prop. 6 statements cited plain INT-CTXT | Inconsistent with Assumption 3 / Lemma S1 | Both now cite the deferred-AD INT-CTXT (Lemma S1) and, for Prop. 6, the one-tag-per-nonce condition |
| Alg. 1 placed beacon verification and ratcheting inside per-report construction, the text says once per window / on accepting a beacon | Inconsistency | Alg. 1 lines annotated: once per window, on accepting the beacon |
| Energy: "two BLAKE2s calls" (H2 is BLAKE2b) and the second GCM call not counted; beacon verification used the ESP32 ratio 1.17 without saying so | Undisclosed modelling choices | Wording fixed; table note states the second GCM call (about 0.02 mJ) is excluded and the 1.17 ratio used |
| Discussion stated the controller's expected-cost guarantee without the independence / accurate-estimate condition | Overstatement | Condition added (as in abstract and Prop. 3) |
| Conclusion's Tamarin sentence omitted the grace-retention model | Inconsistency with abstract | Added |
| Source zip contained nine unused, outdated table files (e.g., "All 32 Pass") | Packaging | Removed |

Rechecked and consistent: curve parameters (254-bit q, rho 2^125.7, Hasse width 2^194, p mod 4 and 5), report and frame sizes, NVM write counts, battery days (184/145/67/43), capacity limits (3.75/21.8/0.62/3.64 ms), Gamma = 238, operation-count table, B3 savings, worst case 1.96 HECM, energy values, scenario numbers against Tables D, F, G and the recalibration table. Paper still 22 pages; 0 undefined references.


# ESP32 hardware results and IEEE IoT Journal compaction

| Change | Evidence |
|---|---|
| ESP32 timings replaced by hardware measurements (102.7 ms per HECM; ratios within 1% of the emulated instruction counts; 1.56 CPI) | `hardware_harness/results/esp32_results.txt`, Table (platform), Supp. Table S7 |
| ns-3 recalibration rerun with the measured ESP32 cost (1,020 runs): PDR unchanged; sensor energy 74.1 mJ/report (about 42 days on 2000 mAh, 3.7 V); MSM saves 49% vs Base; injection cost 1.02-1.03 HECM/report | `results/rev_H_hw.csv`, recalibration table |
| Energy table: measured ESP32 columns (report 27.1 mJ, beacon+RL 63.8 mJ); power is nominal (0.264 W), not measured | energy table note |
| Compact IEEE IoT Journal version (15 pages): secondary tables/figures moved to the supplement (S-IX), prose tightened, no claim removed | `HiBaF-Twin_IoTJ.pdf`, supplement S-IX |
| Raspberry Pi 4 still emulated (measurement pending) | text and table labels |


# Raspberry Pi 4 hardware results and self-contained IoTJ version

| Change | Evidence |
|---|---|
| Cortex-A72 timings replaced by Raspberry Pi 4 measurements (1.71 ms per HECM at 1.8 GHz = 2.05 ms at the 1.5 GHz of the emulation model, inside its 1.12-2.78 ms range; MSM 0.253-0.278 HECM/report for n >= 50 on hardware) | `hardware_harness/results/pi_results.csv`, platform table |
| Final ns-3 recalibration with both measured costs (510 runs): PDR 0.999; sensor 74.1 mJ/report (about 42 days); collector CPU 4.9 vs 10.1 (B1) vs 17.5% (Base) at 400 reports/s; injection 1.02 vs 1.28 vs 4.60 HECM/report | `results/rev_H_pi.csv`, recalibration table |
| Energy table now: earlier values vs measured (collector batch of 100: 0.155 J MSM, 0.683 J individual, 1.17 J Base) | energy table |
| IoTJ version made self-contained (no supplement): GCM deferred-AD proof as Appendix A, attack-check and Tamarin tables restored, other material cited from this package | `HiBaF-Twin_IoTJ.pdf` |

# Correctness check after the hardware update

| Issue | Fix |
|---|---|
| Abstract/conclusion quoted the mean delay (0.25 s) from the main campaign only; with the measured costs it is 0.31 s (p95 0.36 s) | Both values stated, with their calibration |
| Recalibration uses measured time per HECM but the simulator's MSM ratios from the calibration run (0.31-0.34 HECM/report), 10-25% above the hardware ratios (0.25-0.28) | Stated in the recalibration text (MSM benefits understated, not overstated) |
| Provenance of the 28.62 / 4.20 ms values and their gap to the measured 102.7 / 1.71 ms not explained | Sentence added in Section VI-B |
| Budget Gamma = 238 holds for 4.20 ms only | Now: 238 with 4.20 ms, 586 with the measured 1.71 ms |

All hardware-derived numbers in the text and tables were recomputed from `pi_results.csv` and `esp32_results.txt`; all recalibration numbers from `rev_H_pi.csv`; every number in the abstract appears in the body. Both versions compile with 0 undefined references and no overfull boxes.
