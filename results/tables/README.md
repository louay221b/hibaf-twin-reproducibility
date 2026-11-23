# HiBaF-Twin — current 0.61 ms simulation datasets

Only the latest verified main-campaign CSV files are retained in the active results folder:

| File | Meaning |
|---|---|
| [`all_runs_hwall_0p61.csv`](all_runs_hwall_0p61.csv) | 2,670 rows: 89 configurations × 30 seeds |
| [`all_runs_hwPi_beaconfix_0p61.csv`](all_runs_hwPi_beaconfix_0p61.csv) | 510 rows: 17 configurations × 30 seeds |
| [`config_means_old_vs_new.csv`](config_means_old_vs_new.csv) | 80 old-vs-new configuration means; **new** means verified using the latest per-run CSV |

The first and second CSVs contain **180 identical A runs** (six configurations × 30 seeds), so the total is **3,000 distinct executions**, or 100 configurations × 30 seeds. The files match the author's 23 November 2026 upload byte-for-byte.

Re-validate without ns-3:

```bash
python results/verify_latest_run_inventory.py
```

The 0.61 ms back-end cost comes from the current campaign scripts, not a dedicated field in the CSV. The special `HW_BEsens` rows test 1.19 ms instead. The old `_o` comparison means remain unverified against their exact original baseline files.

**Historical 3,510-run CSVs and their derived tables, PDF/PNG figures and old per-packet traces were deleted from the active branch** because they do not represent the final published 0.61 ms campaign. They may still be retrievable from Git history.

Remaining unpublished evidence: raw per-seed outputs of 480 supplementary sensitivity runs, nine individual back-end timing samples, and the physical AES-GCM benchmark measurement log.
