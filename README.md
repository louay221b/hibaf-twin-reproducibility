# HiBaF-Twin — reproducibility package

**Current release (November 2026):** authoritative scripts and experimental results for the corrected HiBaF-Twin study, calibrated with ESP32 = **102.666 ms/HECM**, Raspberry Pi 4 = **1.706 ms/HECM**, and back end = **0.61 ms/HECM** (except the explicitly tested 1.19 ms BEsens case). The latest author-supplied source archive is `last script.zip` (20 November 2026); the current run CSVs were uploaded on 23 November 2026. Old 3,510-run experiments, superseded estimated-energy scripts, earlier figures and packet traces have been **removed from the active branch**, not presented as current results.

## Main reproducibility entry points

| Area | Current source / results | Purpose |
|---|---|---|
| Protocol and 36 checks | [`reference_model/`](reference_model/) | Single current reference model, deferred GCM associated data, nonce retirement, and regression checks |
| ns-3 simulator | [`ns3/hibaf-sim.cc`](ns3/hibaf-sim.cc) | Corrected ns-3.49 simulator; cryptographic CPU work is simulated using calibrated delays |
| Main 0.61 ms campaigns | [`campaign/backend_0p61ms/`](campaign/backend_0p61ms/) | Original 2,670-run grid plus 510-run beacon-fix grid, 180 overlapping runs |
| Current simulation data | [`results/tables/`](results/tables/) | 3,000 distinct per-seed runs; 100 configurations × 30 seeds |
| Simulation integrity check | [`results/verify_latest_run_inventory.py`](results/verify_latest_run_inventory.py) | Checks overlapping runs, seed completeness, and 80 current configuration means |
| Monte Carlo and controller attacks | [`analytic/`](analytic/) | Current Monte Carlo, replay, adaptive-controller and adversarial checks |
| Cryptography and curve | [`crypto_level1/`](crypto_level1/), [`curve/`](curve/) | Arithmetic, order certificates and MSM calibration |
| Symbolic security | [`tamarin/`](tamarin/) | Current formal models and negative-example models used to explain design fixes |
| Hardware measurements | [`hardware_harness/`](hardware_harness/), [`platform/`](platform/) | ESP32 and Raspberry Pi implementation and benchmark evidence |

### Validate the published results

From the repository root, with Python 3.10+:

```bash
python -m pip install cryptography numpy pandas scipy matplotlib
python reference_model/test_hibaf_v2.py
python campaign/verify_latest_campaign.py
python results/verify_latest_run_inventory.py
```

Expected: **36/36** executable reference checks; 2,670+510 campaign jobs; **3,000 distinct run records** (2,670+510−180). The inventory validator also checks that the 80 new-calibration means in `config_means_old_vs_new.csv` agree with the per-seed data. The old-calibration `_o` means in that comparison CSV have not been independently revalidated.

### Rerun the current ns-3 campaign

Build ns-3.49 using `ns3/hibaf-sim.cc` as `scratch/hibaf/hibaf-sim.cc`. Then:

```bash
python campaign/backend_0p61ms/campaign_hw_all.py 2
python campaign/backend_0p61ms/campaign_hw3_beaconfix.py 2
```

Set `HIBAF_NS3_BIN` to the compiled executable path when needed. Do not mix results from different back-end calibrations in one output directory. Both launchers enumerate 30 independent RNG seeds per configuration. See [campaign documentation](campaign/README.md).

To reproduce the current Monte Carlo figure with the corrected **"vs. B2"** label, run `python analytic/make_fig7_mc.py`. To generate the current 0.61-ms scalability and related figures, run `python campaign/backend_0p61ms/make_figures_0p61.py`.

## Scope and outstanding evidence

- The published CSVs match the 0.61 ms main study, not the removed historical 3,510-run calibration. Detailed older per-packet traces and old PDF/PNG plot artifacts were removed to prevent confusing them with current results. The current plot scripts are preserved so figures can be regenerated.
- The [supplementary sensitivity](results/sensitivity/) remains available **as a distinct experiment** (its original baseline is 0.10 ms/HECM, with additional 0.86/1.19 ms tests). It is not silently merged into the main 0.61 ms dataset; per-seed outputs from its additional 480 runs are still not published.
- The 0.61 ms back-end figure is described by the authors as the best of nine measured timings; the nine raw measurements have not been published here. The physical AES-GCM timing log is also still missing.
- `ns3/hibaf-sim_sensitivity.cc` is an optional sensitivity variant that adds `--indTheta`. Do not use it as the unlabelled main simulator.
- Symbolic Tamarin results have specific scope and bounds; flawed or older *counterexample models* are retained only as research evidence for why the final security fixes were necessary.
- Hardware benchmarks do not constitute a full hardware end-to-end IoT deployment. Energy is estimated from cryptographic runtime and nominal power, not from direct electrical power measurements.

**Cleanup policy:** the current branch excludes outdated main-run CSVs, figures, per-packet traces, and historical analyses. Removed files may still exist in **Git commit history**, which is separate from the clean current working tree.
