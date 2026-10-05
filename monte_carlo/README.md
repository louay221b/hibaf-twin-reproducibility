# Monte Carlo evaluation

This directory reproduces the analytical and Monte Carlo evaluation used for HiBaF-Twin.

## Run

```bash
python -m pip install -r requirements.txt
python -m hibaf_sim.run_all --config config/simulation_config.yaml --out results
```

The main Monte Carlo experiments use **10,000 reporting windows per configuration** with master seed **20260603**.

## Main experiments

- `exp_b_mixed_validity.py`: mixed-validity batch verification, including the current full-individual fallback and the evaluated recursive variant.
- `exp_c_replay.py`: replay filtering with accepted-nonce and current-batch duplicate semantics.
- `exp_g_window_sensitivity.py`: reporting-window / DT sensitivity.
- `exp_f_full_hierarchy.py`: platform-independent hierarchy-wide operation counts.

## Methodological boundary

No result in this directory is a physical-device benchmark. The literature value `T_HECM = 2.20 ms` is used only where explicitly labelled as the **Taji--Ghanimi reference-platform HECM-only lower-bound scenario**.
