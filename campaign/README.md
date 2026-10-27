# HiBaF-Twin ns-3 reproducibility campaigns

These scripts run against **ns-3.49**, using `ns3/hibaf-sim.cc` and the program built following the repository's main README.

## Paths

By default, `campaign/campaign.py` looks for the compiled executable at
`ns-3.49/build/scratch/hibaf/ns3.49-hibaf-sim-optimized` relative to the repository root.
It writes run summaries to `runs/<configuration>/summary.csv`.

Set the following environment variables if you use a different location:

- `HIBAF_NS3_BIN`: absolute path to the compiled ns-3 program
- `HIBAF_RUNS_DIR`: directory containing run-specific subdirectories

Both are optional; the defaults work when ns-3.49 is built in the repository root as shown in the main README. Run summaries are intentionally ignored by Git because a full campaign may produce many files.

## Execution

```bash
python3 campaign/campaign.py 2
python3 campaign/analyze.py

python3 campaign/campaign_rev.py 2
python3 campaign/analyze_rev.py

python3 campaign/campaign_hw.py 2
python3 campaign/analyze_hw.py

python3 campaign/campaign_hw2.py 2
python3 campaign/analyze_pi.py
```

The integer argument is the number of worker processes; `2` is a reproducible starting configuration, not a required parameter of the protocol. Recalibration jobs reuse the original random-seed and scenario grids documented in their source.

`campaign/analyze.py` generates figures and tables in `results/figures/` and `results/tables/`. Revised outputs are written to `results/tables/`; hardware recalibration summaries are written to `results/rev_H_hw.csv` and `results/rev_H_pi.csv`.

**Note:** the archived summary CSVs are already available in `results/`. Re-running a full ns-3 campaign can be time-consuming, and the new raw `runs/` directory must be generated before the analysis scripts can merge it.

**Evidence boundaries:** ns-3 models cryptographic CPU work as calibrated delays. The emulated Cortex-A72 estimates and the hardware timings must remain distinguished as stated in the main README.
