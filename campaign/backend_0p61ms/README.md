# Back-end re-calibration: 0.61 ms/HECM (latest uploaded scripts)

The user's `last script.zip` (dated 2026-11-20) contains a separate re-run at **0.61 ms/HECM** in the back end instead of the former **0.10 ms/HECM**. The 0.61 value is described as "measured best of nine"; the nine raw timing samples were not provided for independent confirmation. The original source comments retain the earlier assumptions; command-line values in these scripts override them.

These scripts are portable adaptations of the delivered `campaign.py`, `campaign_hw2.py`, `campaign_hw3_beaconfix.py` and `campaign_hw_all.py`: only absolute paths, output isolation and the explicitly configured cost were changed. The special 1.19 ms BEsens test remains 1.19 ms, because the per-configuration grid takes precedence over the 0.61 ms default. The outdated main-calibration 0.10 ms CSVs and generated plot files have since been removed from `main`; independent supplementary sensitivity code is retained separately.

Build ns-3.49 with `ns3/hibaf-sim.cc` as `scratch/hibaf/hibaf-sim.cc`. From the repository root run:

```bash
python3 campaign/backend_0p61ms/campaign_hw_all.py 2
python3 campaign/backend_0p61ms/campaign_hw3_beaconfix.py 2
```

Override `HIBAF_NS3_BIN` if necessary, and keep runs in different directories for different calibrations. The author reports 2,670 original-grid runs and 510 beacon-fix runs, with 180 A overlaps (3,000 distinct simulations). Those three files were later supplied and published in `results/tables/` on 23 November 2026. Run `python results/verify_latest_run_inventory.py` to verify the 3,000 distinct runs and the 80 new-calibration configuration means. The `_o` old-calibration mean columns have not been independently checked against an exact matching old 0.10 ms per-run CSV, and raw device timing samples remain required for full hardware provenance. No ns-3 rerun was performed during publication.

The file `make_figures_0p61.py` in the source ZIP uses nonportable paths and retains an obsolete "vs B4" axis label. For the corrected Monte Carlo figure "vs B2", use `analytic/make_fig7_mc.py` instead. The current analytical, Tamarin, curve and hardware sources are stored in their dedicated directories; previous compiled/output duplicates have been removed when not needed for validation.
