# HiBaF-Twin reference model

This directory contains the executable Python reference model and 35 regression checks reported in Table III of the HiBaF-Twin manuscript.

## Run

Requires Python 3 and the `cryptography` package.

```bash
python -m pip install cryptography
python test_hibaf_v2.py
```

Expected final line: `35/35 checks passed`.

The additional check tests two cases: byte-identical copies of a pending report are dropped before consuming the per-identity quota or entering MSM verification; distinct valid reports sharing an (ID, nonce) produce equivocation evidence.

**Scope:** `g2toy.py` uses an intentionally small toy genus-2 Jacobian for correctness tests only. This test suite does not establish production-level cryptographic security or replace the hardware, curve-certificate, Tamarin, or ns-3 experiments.

Other directories at the repository root were already present and are not changed by this update.
