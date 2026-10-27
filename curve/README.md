# Certified genus-2 curve: reproducibility

The curve parameters, primality evidence, Hasse–Weil checks, generator data, and canonical-encoding checks are provided in this directory.

## Verify

Run from any working directory, using the Python dependencies `sympy` and the included `reference_model/g2toy.py`:

```bash
python3 curve/validate_curve.py
python3 curve/real_curve_test.py
```

For the independent prime-order certificate script, also install PARI/GP so that its `gp` executable is available on the system path:

```bash
python3 curve/cert/certify_order.py
```

Outputs are written beside the corresponding scripts as `curve_validation.json`, `real_curve_test.json` and `cert/order_certificate_check.json`. The original archived outputs and ECPP certificate files remain present.

The first-stage `find_curve.py` performs a potentially expensive CM search and is not required just to verify the **provided** certified parameters.

## Cross-platform prerequisites

Python 3.10+ and `sympy` are required; on Windows use `py -3 -m pip install sympy` and replace `python3` in the commands above with `py -3`. The scripts resolve reference-model imports and JSON paths from their own location, not the current working directory. PARI/GP is optional for other curve checks but mandatory for the ECPP proof command; install it separately on Linux/WSL or ensure `gp` is on PATH. The potentially expensive validation and CM discovery stages should not be treated as quick smoke tests.
