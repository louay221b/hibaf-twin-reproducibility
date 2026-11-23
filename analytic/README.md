# HiBaF-Twin analytical models — active version

The analytical part of the latest study consists of:
- `eval_analytic.py` with `mc_mixed.csv` and `mc_replay.csv`: mixed-validity and replay Monte Carlo data;
- `make_fig7_mc.py`: regenerates the latest Monte Carlo figure with the **vs. B2** axis;
- `mc_alg2.py`: checks the two-stage adaptive-batch controller;
- `adversarial/adv_controller.py`, `adversarial/fig_adv.py`, `adversarial/adv_summary.csv`: controller attack patterns, figure, and original summary;
- `be_sens.py`: **supplementary**, separately calibrated back-end sensitivity experiment.

To run:

```bash
python -m pip install numpy pandas scipy matplotlib
python analytic/make_fig7_mc.py
python analytic/adversarial/fig_adv.py
```

To rerun the Monte Carlo experiment (rather than plot the supplied outputs): `python analytic/eval_analytic.py`.

**The older** `eval_analytic2.py`, `eval_tables_v3.py`, `energy.csv`, `scalability.json`, and `tables_v3.json` **were intentionally removed**. Those artifacts still used previous emulated HECM times (notably 28.62 ms for ESP32 and 4.20 ms for Pi 4) and could misrepresent the latest hardware-calibrated results.

The current simulator-data-dependent figure generator is `python campaign/backend_0p61ms/make_figures_0p61.py`, which uses `results/tables/all_runs_hwall_0p61.csv` and the supplied MSM calibration. Never re-use old 3,510-run plots as results of the current 0.61 ms campaign.

Security and hardware claims have separate evidence in `reference_model/`, `tamarin/` and `hardware_harness/`.
