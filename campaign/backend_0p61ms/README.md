# Back-end re-calibration: 0.61 ms/HECM (latest uploaded scripts)

The user's `last script.zip` (dated 2026-11-20) contains a separate re-run at **0.61 ms/HECM** in the back end instead of the former **0.10 ms/HECM**. The 0.61 value is described as "measured best of nine"; the nine raw timing samples were not provided for independent confirmation. The original source comments retain the earlier assumptions; command-line values in these scripts override them.

These scripts are portable adaptations of the delivered `campaign.py`, `campaign_hw2.py`, `campaign_hw3_beaconfix.py` and `campaign_hw_all.py`: only absolute paths, output isolation and the explicitly configured cost were changed. The special 1.19 ms BEsens test remains 1.19 ms, because the per-configuration grid takes precedence over the 0.61 ms default. Historical 0.10 ms code/data remain untouched.

Build ns-3.49 with `ns3/hibaf-sim_v33.cc` as `scratch/hibaf/hibaf-sim.cc`. From the repository root run:

```bash
python3 campaign/backend_0p61ms/campaign_hw_all.py 2
python3 campaign/backend_0p61ms/campaign_hw3_beaconfix.py 2
```

Override `HIBAF_NS3_BIN` if necessary, and keep runs in different directories for different calibrations. The author reports 2,670 original-grid runs and 510 beacon-fix runs, with 180 A overlaps (3,000 distinct simulations). The uploaded ZIP **does not contain** `all_runs_hwall_0p61.csv`, `all_runs_hwPi_beaconfix_0p61.csv`, or `config_means_old_vs_new.csv`. Until those are uploaded, the numerical outcomes of the 0.61 ms rerun cannot be independently checked from this repository. No ns-3 rerun was performed during publication of these scripts.

The file `make_figures_0p61.py` in the source ZIP uses nonportable paths and retains an obsolete "vs B4" axis label. For the corrected Monte Carlo figure "vs B2", use `analytic/make_fig7_mc.py` instead. The other analytical, Tamarin, curve and hardware files in the ZIP are historical copies; original versions remain archived in their respective folders.
