# HiBaF-Twin ns-3 experiments — current source

The authoritative simulator is [`../ns3/hibaf-sim.cc`](../ns3/hibaf-sim.cc) (ns-3.49). Build it into `ns-3.49/scratch/hibaf/` with the standard scratch name `hibaf-sim.cc`.

## Current 0.61 ms/HECM main campaign

The current code is in [`backend_0p61ms/`](backend_0p61ms/). The two launchers are:

```bash
python campaign/backend_0p61ms/campaign_hw_all.py 2
python campaign/backend_0p61ms/campaign_hw3_beaconfix.py 2
```

The grids contain 2,670 and 510 jobs respectively. There are 180 overlapping A cases, yielding **3,000 distinct runs**. The hardware-calibrated costs are ESP32=102.666 ms/HECM, Raspberry Pi 4=1.706 ms/HECM, back end=0.61 ms/HECM, except the explicitly modeled 1.19 ms/HECM BEsens cases. Verify the inputs without running ns-3 with `python campaign/verify_latest_campaign.py`.

Set `HIBAF_NS3_BIN` for a nondefault simulator binary path, and `HIBAF_RUNS_DIR` to control output. Never reuse the same output directory for runs using a different back-end HECM calibration. Existing `summary.csv` files are skipped.

## Complementary experimental sources

- `campaign_rev.py`, `campaign_replay.py` — auxiliary defenses/replay campaigns from the supplied latest ZIP.
- `campaign_sens.py`, `analyze_sens.py` — previously supplied independent audit/backend sensitivity experiments (0.10, 0.86, 1.19 ms and B1 audit-rate variations), whose baselines are **not** the current 0.61 ms campaign.
- `campaign_common.py` — common 0.10 ms **auxiliary** runner imported by the above supplemental scripts, not an alternative main-calibration driver.
- `analyze_hwall.py`, `analyze_pi_beaconfix.py`, `analyze_replay.py`, and `analyze_sens.py` — current/supplemental reproducibility analyses. `analyze_hwall.py` and `analyze_pi_beaconfix.py` now read the active `runs_*_0p61ms` directories and write to `results/generated/backend_0p61ms/`; all analysis scripts require the corresponding raw summaries/CSVs.

For the `--indTheta` flag compile `../ns3/hibaf-sim_sensitivity.cc` in place of the main simulator, then run the sensitivity campaign separately; do not use it to recreate the main run grid without identifying that variant.

## Data provenance and remaining gaps

The three 0.61 ms result tables were subsequently supplied (23 November 2026) and are now at `results/tables/all_runs_hwall_0p61.csv`, `results/tables/all_runs_hwPi_beaconfix_0p61.csv`, and `results/tables/config_means_old_vs_new.csv`. Run `python results/verify_latest_run_inventory.py` to check row counts, seed grids, numerical overlaps and the newly measured aggregate means. The 480 individual per-seed supplementary sensitivity summaries remain unavailable. The old 3,510-run tables, plots and packet traces have been removed from the active branch. No ns-3 rerun was performed for the CSV upload.

**Removed older material:** the former `analyze.py`, `analyze_hw.py`, `analyze_pi.py` and `analyze_rev.py` utilities generated the old 3,510-run figures and original-calibration tables. They are no longer part of the active scientific release; use the 0.61 ms scripts and latest data instead.
