# HiBaF-Twin v2 — Phase 6: independent reviewer assessment and revision checklist

Status of the revised manuscript `paper/main.tex` and of the evidence in this package.
"Done" means the item is implemented **and** backed by executed code or a completed proof run in this package.

## Reviewer 1 — Cryptography and formal security

**Resolved in v2**
- Algebraic correctness: Prop. 1 derives the signature, batch and GCM identities; the reference model (`reference_model/`) executes them (20/20 checks).
- Batch soundness: prime-order group plus canonical decoding gives a bound of 1/(2^ℓα−1). The cofactor counter-example was executed (202/400 false accepts on a cofactor-2 toy curve).
- Key escrow: the TTP no longer provisions K_i. Enrolment is signed ephemeral DH, verified in Tamarin (PFS secrecy and agreement).
- Forward secrecy: a two-output PRF ratchet per epoch with a hybrid proof sketch (Bellare–Yee), stated only for epochs before the corruption.
- Back-end duplicate commit (Alg. 4 bug), encoding malleability and the key-prefixed challenge: fixed and tested.
- θ-audit reframed as collector accountability. AEAD already authenticates the sensor to the back end (symbolic lemma `agreement_aead_only`).

**Remaining risks**
1. ~~No concrete curve~~ **Resolved:** certified prime-order curve y² = x⁵ + 8 over F_(2¹²⁷−2437) (254-bit order, ≈2^125.7 rho, embedding degree 251 bits); see `curve/`. A reviewer may question the CM (special) structure, which costs ≈1.2 bits against rho; this is acknowledged in the paper.
2. The computational proofs are sketches. A reviewer may ask for full game-hopping proofs of Thm. 1 and Prop. 4. *(Moderate.)*
3. Enrolment indistinguishability is supported symbolically and by citing SIGMA, not by a computational proof. *(Moderate.)*
4. Tamarin coverage is split across models. The unbounded-chain inductive lemma ran out of memory, so forward secrecy is proved on a 3-epoch bounded model; see `tamarin/` logs and Table 6. State this bound explicitly in the paper. *(Minor/Moderate.)*
5. No side-channel analysis of MSM or scalar multiplication on ESP32. *(Moderate for the IoT venue.)*

## Reviewer 2 — IoT networking and ns-3

**Resolved in v2**
- A full ns-3.49 simulator of the real protocol: real message sizes, 6LoWPAN fragmentation, 802.15.4 CSMA/CA, beacons with rebroadcast, TCP backhaul, WAN loss and outages, insider/outsider attackers and revocation push.
- Scenarios A–F with 30 independent runs per configuration, 95% CIs, Welch tests and Hedges' g.
- MSM ablation (Base) and controller ablation (MSM, no controller), plus same-security (B1) and weaker-security (Sym) baselines.

**Remaining risks**
1. Cryptography is a calibrated delay, not executed in ns-3. The absolute times inherit the authors' ESP32/RPi4 scalar-multiplication values, which are internally inconsistent with their HAdd value. **Re-measure on hardware.** *(Major.)*
2. Ponds are interference-free (separate channels), there is no mobility, and radio energy assumes ideal duty-cycled listening. *(Moderate.)*
3. The back-end scalar-multiplication time (0.10 ms) is assumed. *(Minor; the back end is never the bottleneck.)*
4. A reviewer may ask for testbed validation (e.g. a few real 802.15.4 nodes) to calibrate PDR and energy. *(Moderate.)*

## Reviewer 3 — Novelty and fit for Elsevier Internet of Things

**Strengths:** honest systems contribution; the MSM controller with closed-form expected and worst-case costs; a corrected and complete threat model; three-level evaluation; full reproducibility package.

**Risks**
1. The novelty is integrative: every primitive is standard. The paper now says so explicitly. Reviewers may still judge the contribution incremental unless the controller and bounded-work result are emphasised. *(Moderate.)*
2. Results show that MSM does **not** reduce end-to-end delay under realistic aquaculture load; the radio is the bottleneck. The paper must keep presenting MSM's benefit as CPU/energy headroom and robustness under injection. Overclaiming here would be caught. *(Moderate.)*
3. The bibliography could not be verified: `survey.bib` was not supplied. Added references are in `hibaf_added.bib` and must be checked (DOIs, pages). *(Major for desk check.)*
4. Figures 1, 2 and 5 are now TikZ. The authors' original PNG workflow figure, which showed the TTP provisioning K_i, must not be reused.

## Major-revision checklist (before submission)

- [x] Prime-order genus-2 curve certified (`curve/`); ℓ_U = 64 bytes, ℓ_q = 32 bytes.
- [ ] Implement constant-time genus-2 arithmetic and MSM on ESP32 and RPi4; measure T_HECM, T_MSM(m) and energy with ≥30 repetitions; re-run `campaign.py` with the new constants (one-line change in `hibaf-sim.cc`).
- [ ] Merge `survey.bib` and `hibaf_added.bib`; verify every entry.
- [ ] Compile with the real `elsarticle` class and check page layout and figure placement.
- [ ] Decide the epoch length E (flash wear vs FS granularity) for the case study.
- [ ] Optionally: full game-hopping proofs in an appendix; testbed calibration of ns-3.
- [ ] Confirm the CRediT roles.
