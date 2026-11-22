# Portable analytical evaluation

Run these scripts from **any working directory** on Windows, Linux, or macOS. Input paths are resolved relative to the location of each script and the root of this repository; no `/home/claude` directory is required.

## Python dependencies

```bash
python -m pip install numpy pandas matplotlib scipy
```

## Reproduce

From the repository root:

```bash
# Monte Carlo: 10,000 windows per configuration; may take some time
python analytic/eval_analytic.py

# Figures, scalability estimates, and computational energy
python analytic/eval_analytic2.py

# Generate LaTeX tables
python analytic/eval_tables_v3.py

# Render archived ns-3 figures and comparison tables
python analytic/analyze_fig.py
```

The second and third commands also work directly from the **archived** `analytic/mc_mixed.csv` and `analytic/mc_replay.csv` without rerunning Monte Carlo.

## Inputs and outputs

| Source | Repository-relative location |
|---|---|
| MSM calibration ratios | `crypto_level1/bench_g2_127_calibration.json` |
| Platform estimates (emulated values) | `platform/platform_estimates.json` |
| Archived ns-3 runs | `results/tables/all_runs_original_3510.csv` |
| Monte Carlo results and analytical figures | `analytic/` |
| Generated LaTeX tables | `analytic/generated_tables/` |
| Archived ns-3 figures | `analytic/figures_generic/` |
| Archived ns-3 summaries | `analytic/tables_generic/` |

`analytic/generated_tables/` is generated within this repository, since the article's LaTeX source directory is not part of this reproducibility package. Copy the generated tables into your manuscript project if needed.

**Evidence boundaries:** these scripts analyse archived runs, Monte Carlo outputs, measured calibration *ratios*, previously reported hardware values, and explicitly labelled emulated cost estimates. They do not execute cryptographic operations on the physical ESP32 or Raspberry Pi 4. Changing path resolution does not change experimental parameters or calculations.
