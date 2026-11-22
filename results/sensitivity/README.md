# Additional sensitivity checks (November 2026)

These checks accompany, but do **not replace**, the revised HiBaF-Twin manuscript's 3,000-run main ns-3 campaign. They were supplied by the authors as an aggregate 30-seed analysis. No new simulator runs were executed when adding them to GitHub.

## Experiment matrix

| Check | Scenarios / settings | Variants | Seeds | Runs |
|---|---|---|---|---:|
| S1: Back-end HECM delay | A2 (100 sensors, 0.25 s/report) and E-off (100 sensors, 0.5 s/report, 10 attackers at 2 invalid reports/s each); back-end cost 0.86 or 1.19 ms/HECM | MSM, Base, B1 | 30 | 360 |
| S2: B1 audit rate | A (100 and 500 sensors), A2, E-off; B1 `--indTheta=0.25` versus the original `theta=1` | B1 | 30 | 120 |
| **Total** | | | | **480** |

Inputs are ESP32 102.666 ms/HECM, Raspberry Pi 4 1.706 ms/HECM and back-end baseline 0.10 ms/HECM. Both variants use the same seed ranges as the original comparison. The original network results are unchanged.

## Supplied aggregate results

The exact text provided with the campaign is in [`sensitivity_results.txt`](sensitivity_results.txt). Values are means with 95% CI half-widths over 30 runs. In scenario A2, increasing back-end cost from 0.10 to 1.19 ms/HECM changes MSM mean delay 0.2894 -> 0.2938 s, Base 0.3210 -> 0.3372 s and B1 0.2924 -> 0.3232 s. In E-off, the corresponding values are MSM 0.2594 -> 0.2630 s, Base 0.3285 -> 0.3415 s and B1 0.2864 -> 0.3091 s. PDR, synchronization success and collector CPU remain unchanged in the supplied summaries. Changing B1's audit rate from 1 to 0.25 changes A2 delay 0.2924 -> 0.2903 s and E-off delay 0.2864 -> 0.2849 s; it does not make B1 identical to MSM, whose batching policy also differs.

**Limitations:** This repository currently archives the aggregate sensitivity results but not the 480 individual `summary.csv` files or the revised campaign's complete 3,000-run CSVs. These must be published for independently checking all 30-seed averages, confidence intervals, and overlap handling. The current `results/tables/all_runs.csv` is historical original calibration, not the revised paper dataset. Do not present it as the basis of the new results.

## Reproduce supplementary cases

Copy `ns3/hibaf-sim_sensitivity.cc` to `ns-3.49/scratch/hibaf/hibaf-sim.cc`, compile it using the ns-3.49 instructions in the root README, and set `HIBAF_NS3_BIN` if the compiled executable has a custom path. From the repository root run:

```bash
python3 campaign/campaign_sens.py
python3 campaign/analyze_sens.py --runs runs --baseline-csv results/tables/all_runs_hwPi_beaconfix.csv
```

The analyzer requires actual per-seed run summaries and the revised campaign baseline CSV. Until those files are present, the archived aggregate text is the evidence available on this branch; the analyzer does not fabricate missing inputs. The auxiliary flag `--indTheta` affects B1 only; its default `-1` preserves the original B1 audit rate of 1.

## Interpretation of scenario E

`E-off` uses `defenses=0`: it disables the negative cache, per-identity quota, and evidence-based revocation so that invalid signatures continue to stress batch verification. It **does not** disable signature checking, window/freshness checks or replay filtering. Separate defense-enabled runs (`defenses=1`) are needed for the operational negative-caching/revocation comparison; they are **not** part of S1/S2.

## AES-GCM parameter

The network simulation uses 0.075 ms per sensor AEAD operation, whereas the separate measured full ESP32 AES-GCM call is 0.099 ms (240 MHz). The provided S1/S2 experiments did not vary this AEAD parameter; their outputs alone cannot prove that the discrepancy has zero network effect.
