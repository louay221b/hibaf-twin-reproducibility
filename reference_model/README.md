# HiBaF-Twin reference model

The archived core suite currently contains **35 regression checks**. The independent supplemental test `test_deferred_ad.py` covers the 36th check reported in the revised manuscript: AES-GCM with deferred associated data (only the final tag is transmitted; a failure before completion retires the nonce).

## Run

Requires Python 3 and `cryptography`.

```bash
python -m pip install cryptography
python reference_model/test_hibaf_v2.py
python reference_model/test_deferred_ad.py
```

Expected outcomes: `35/35 checks passed` and `1/1 deferred-associated-data regression check passed`, respectively. The existing `test_output.txt` is an archived 35-check transcript and is not rewritten or presented as a fresh run.

**Scope:** `g2toy.py` uses a deliberately small toy genus-2 Jacobian for functional testing. These checks do not independently establish real-curve cryptographic security or re-execute the ns-3, physical hardware, or Tamarin experiments.
