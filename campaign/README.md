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
- `analyze.py`, `analyze_hwall.py`, `analyze_pi_beaconfix.py`, `analyze_replay.py`, and related scripts — reproducibility analyses. `analyze_hwall.py` and `analyze_pi_beaconfix.py` now read the active `runs_*_0p61ms` directories and write to `results/generated/backend_0p61ms/`; all analysis scripts require the corresponding raw summaries/CSVs.

For the `--indTheta` flag compile `../ns3/hibaf-sim_sensitivity.cc` in place of the main simulator, then run the sensitivity campaign separately; do not use it to recreate the main run grid without identifying that variant.

## Data provenance and remaining gaps

The supplied `last script.zip` contains code but omits `all_runs_hwall_0p61.csv`, `all_runs_hwPi_beaconfix_0p61.csv` and `config_means_old_vs_new.csv`. It does not contain raw per-seed summaries for the newer supplementary sensitivity checks. The older results under `results/tables/` are preserved as historical, not relabeled as current. No new simulations have been executed by this repository cleanup.
