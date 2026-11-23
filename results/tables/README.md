# Main HiBaF-Twin simulation datasets

This folder holds both **current 0.61 ms/HECM** and **historical** simulation datasets. Avoid mixing them.

| File | Calibration | Scope |
|---|---|---|
| `all_runs_hwall_0p61.csv` | Current 0.61 ms back end | 2,670 runs = 89 configurations × 30 seeds |
| `all_runs_hwPi_beaconfix_0p61.csv` | Current 0.61 ms back end | 510 runs = 17 configurations × 30 seeds |
| `config_means_old_vs_new.csv` | Old vs. 0.61 ms | 80 matched configuration mean comparisons |
| `all_runs_original_3510.csv`, `all_runs.csv` | Historical | Original 3,510-run study, **not** the current paper |

The second current CSV contains 180 `H_A_hwPi` rows corresponding to `HW_A` rows in the first CSV. Numerical values in every metric match across the two sources; superficial numeric spellings like `10` versus `10.0` do not indicate different runs. Therefore, the main campaign contains **3,000 distinct runs** (100 configurations × 30 independent seeds).

Run `python results/verify_latest_run_inventory.py` from the repo root to check all 3,180 stored rows, deduplicated counts, seed completeness, and the 80 new-calibration summary means.

**Provenance and limits:** These CSVs were supplied by the author on 2026-11-23, validated and committed byte-for-byte without generating or changing any simulated outcome. `tHecmBe` is not a CSV column; the 0.61 ms calibration is documented by the corresponding launch scripts. Some special `HW_BEsens` runs intentionally use 1.19 ms. The old-calibration `_o` values in `config_means_old_vs_new.csv`, the nine individual back-end timing samples, the 480 newer sensitivity run summaries, and the physical AES-GCM measurement log have not all been independently validated or published.
