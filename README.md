# HiBaF-Twin Reproducibility

Reproducibility material for the analytical and simulation-based evaluation of:

**HiBaF-Twin: Hierarchical Batch-Verified Freshness-Bound Secure Reporting Framework for Aquaculture Digital Twins**

## Scope

This repository contains the code and data used to reproduce the paper's evaluation:

- mixed-validity Monte Carlo simulation;
- replay-filtering Monte Carlo simulation;
- hierarchy-wide cryptographic operation counts;
- reporting-window / DT HECM sensitivity analysis;
- idealized DT multi-worker processing-capacity analysis;
- limited pond-collector parallelism analysis.

## Important methodological note

HiBaF-Twin was **not implemented on physical ESP32, Raspberry Pi, or other hardware** in this study. Results in this repository are analytical, Monte Carlo, or platform-independent sensitivity results.

Where the literature-reported `2.20 ms` HEC scalar-multiplication value is used, it is explicitly treated as the **Taji--Ghanimi reference-platform HECM-only lower-bound scenario**. It is not a HiBaF-Twin hardware measurement and is not a security-normalized benchmark.

## Repository layout

```text
.
├── monte_carlo/   # Monte Carlo and hierarchy-wide analytical framework
└── scalability/   # Experiments H, I, J (closed-form / deterministic)
```

## Monte Carlo experiments

```bash
cd monte_carlo
python -m pip install -r requirements.txt
python -m pytest -q
python -m hibaf_sim.run_all --config config/simulation_config.yaml --out results
```

The reported Monte Carlo experiments use **10,000 reporting windows per configuration** and master seed **20260603**.

The repository tracks source code and selected summary outputs. Large window-level raw CSV files are intentionally excluded because they are reproducible from the code, configuration, and seed.

## Scalability experiments H/I/J

Experiments H, I and J are deterministic closed-form/enumerative analyses and therefore use no random seed.

```bash
cd scalability
sh run_all.sh
```

They cover:

- **H** — platform-independent HECM sensitivity;
- **I** — idealized DT parallel-processing capacity;
- **J** — limited pond-collector parallelism.

## Reproducibility boundaries

The repository does not claim:

- physical testbed measurements;
- ESP32 or Raspberry Pi benchmarks;
- measured device energy;
- measured end-to-end real-time latency.

The simulations and analytical models quantify processing requirements under the assumptions documented in each subdirectory README.

## Paper

Citation details will be updated after publication.
