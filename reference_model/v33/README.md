# Original v33 reference model

The three Python files and the original archived test transcript in this directory are byte-for-byte copies from the v33 reproducibility archive. Run:

```bash
python -m pip install cryptography
python reference_model/v33/test_hibaf_v2.py
```

Expected archived outcome: 36/36. The transcript was produced on 2026-10-29. The older root-level 35-check suite and separate deferred-AD test are retained, not counted again. The toy Jacobian is a functional reference model, not production cryptography.
