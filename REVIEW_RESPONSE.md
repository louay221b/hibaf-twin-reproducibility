# Response to the pre-submission review (HiBaF-Twin)

| Review point | Verdict | Change | Evidence |
|---|---|---|---|
| A. Curve order "certified" from random divisors | Partly valid: the argument needs only one D≠O, but primality of q was only a probable-prime test and the wording suggested sampling | Deterministic proof: ECPP certificates for q and p; qL = O; exact Hasse–Weil check; text and Table III rewritten | `curve/cert/` |
| B. Controller worst case vs. "below individual verification" | Valid | Three guarantees separated (finite worst case per batch, budget Γ, expected cost ≤ c1 when μ̂ is accurate); Γ ≥ c1 feasibility check; worst case 1.96 HECM/report stated as above individual verification | Prop. "Bounded verification work"; controller algorithm |
| C. GCM nonce uniqueness, NVM atomicity | Valid (wording) | R9 reworded; lifetime bound (<2^-40 worst case over 10 years, <2^-52 at one reboot/day); two-slot atomic ratchet update | Protocol (sensor report); Security (nonce bound) |
| D. Revocation by a Byzantine collector | Valid (real flaw) | Revocation only on back-end-validated evidence (valid GCM tag + invalid signature); Prop. "Revocation soundness"; ns-3: 24 false revocations/run without, 0 with | Dz, Dev, checks 13–15 |
| E. Enrolment under-specified | Valid (real flaw: replayed message 1 overwrote BE's key) | Three-message SIGMA-I enrolment with key confirmation, certificate checks, session handling; Tamarin verifies 5 lemmas; old version falsified | `tamarin/` |
| F. Clockless freshness | Valid (wording) | Data-age bound and missed-window behaviour stated; Byzantine station = availability | Protocol (window beacon) |
| ns-3 relies on calibrated delays | Valid | Emulated ESP32/A72 costs (exact instruction counts, modelled times) and ns-3 rerun; Base no longer collapses with faster A72 costs — reported | Tables platform, recal |
| Interference-free ponds | Valid | Shared-channel scenario G; found beacon collisions, fixed with per-collector offsets | Table G |
| Baselines with different security | Valid (presentation) | Security-equivalent vs lower-security variants separated | Evaluation (variants) |
| Forward-secrecy scope | Valid | Abstract and text state 3-epoch bound for Tamarin FS | Abstract; Tamarin subsection |
| Audit vs. GCM guarantees | Valid | Stated explicitly | Protocol (station and back end) |
| "No attack report committed" is empirical | Valid | Labelled as observation; guarantees cited | Robustness summary |
| Reproducibility 2.5/5 | Package existed but was not linked | Availability statement (DOI placeholder to fill on deposit) | Conclusion |
| Elsevier format | Venue decision | IEEE version updated; Elsevier version not yet synchronized | — |

Still open: measurements of a constant-time implementation on real ESP32 and Raspberry Pi 4 hardware; depositing the package to obtain a DOI.
