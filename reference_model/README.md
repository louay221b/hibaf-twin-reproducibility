# HiBaF-Twin — executable reference model (current)

This directory contains the **single authoritative 36-check suite** from the author's `last script.zip` (20 November 2026). The source and archived pass transcript match the 36-check version (including pending duplicate handling, deferred AES-GCM associated data and nonce retirement).

```bash
python -m pip install cryptography
python reference_model/test_hibaf_v2.py
```

Expected archived output: `36/36 checks passed`. The transcript in `test_output.txt` is an archived run rather than evidence that this repository's CI executed the model on a physical board.

`g2toy.py` implements a deliberately small toy Jacobian for correctness checks, not real-curve production cryptography; see `curve/` and `hardware_harness/` for the corresponding certificate and hardware measurements. The old 35-check model and standalone 36th regression script were removed as duplicates.
