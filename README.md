# HiBaF-Twin v2 — reproducibility package

Everything in this package was executed. Each item is labelled by the kind of evidence it produces.

| Folder | Content | Evidence type |
|---|---|---|
| `ns3/hibaf-sim.cc` | ns-3.49 simulator of the full protocol (802.15.4/6LoWPAN ponds, CSMA LAN, P2P WAN, TCP, beacons, caches, quota, MSM controller, revocation) | simulated |
| `campaign/campaign.py` | Scenarios A–F, 30 RNG runs per configuration (3,510 runs) | simulated |
| `campaign/analyze.py` | Merge, mean/SD/95% CI, Welch t-test, Hedges' g, figures | — |
| `results/tables/all_runs.csv` | One row per run (all metrics) — the source of every number in the paper | simulated |
| `results/tables/*.csv` | Per-scenario summaries and `significance.csv` | simulated |
| `results/figures/` | Figs. 6–12 (PNG + PDF) | simulated |
| `crypto_level1/` | Genus-2 Cantor arithmetic over F_(2^127−1), wNAF, Straus, Pippenger; `bench_g2_127_calibration.json` (ratios used in ns-3); `bench_repeat.json` (3 repeats); operation-count and isolation-strategy models; the fixed version of the original Monte Carlo script | measured (ratios) / analytical |
| `curve/` | **Certified curve** y² = x⁵ + 8 over F_p, p = 2¹²⁷ − 2437; prime order q (254 bits). `find_curve.py` (CM search), `validate_curve.py` (order certificate, embedding degree, rho bits, twists, generator), `real_curve_test.py` (Schnorr, MSM batch, 64-byte canonical encoding on the real curve), 5-repeat benchmark on this curve | certified / executable / measured |
| `reference_model/` | Executable HiBaF v2 on a prime-order toy Jacobian, with real AES-128-GCM and BLAKE2s; `test_hibaf_v2.py` passes 35/35 correctness and attack checks (`test_output.txt`) | executable |
| `tamarin/` | Tamarin 1.10.0 models and proof logs: enrolment (unbounded), core (unbounded and 3-epoch), forward secrecy (3-epoch; unbounded attempt) | symbolic |
| `REVIEW_ASSESSMENT.md` | Three-reviewer assessment and the remaining checklist | — |

## Reproduce

```bash
# ns-3
git clone --depth 1 --branch ns-3.49 https://github.com/nsnam/ns-3-dev-git ns-3.49
mkdir -p ns-3.49/scratch/hibaf && cp ns3/hibaf-sim.cc ns-3.49/scratch/hibaf/
cd ns-3.49 && ./ns3 configure --build-profile=optimized \
  --enable-modules="lr-wpan;sixlowpan;internet;csma;point-to-point;applications;energy" \
  --disable-examples --disable-tests --disable-python && ./ns3 build hibaf-sim
# single run
./build/scratch/hibaf/ns3.49-hibaf-sim-optimized --variant=msm --nSensors=100 --out=/tmp/r
# Return to the repository root before starting the campaign:
cd ..
# Campaign defaults: binary under ns-3.49/build/..., run summaries under runs/.
# Override with HIBAF_NS3_BIN and HIBAF_RUNS_DIR when needed.
python3 campaign/campaign.py 2 && python3 campaign/analyze.py

# Level 1 and reference model (Python 3, numpy, pandas, matplotlib, scipy, cryptography)
python3 crypto_level1/bench_g2_127.py
python3 crypto_level1/check_equations.py
cd reference_model && python3 test_hibaf_v2.py

# Tamarin 1.10.0 + Maude 3.5
tamarin-prover --prove tamarin/hibaf_v2_enrol.spthy
tamarin-prover --prove tamarin/hibaf_v2_core3.spthy
tamarin-prover --prove tamarin/hibaf_v2_fsmin3.spthy
tamarin-prover --prove tamarin/hibaf_v3_fs_grace.spthy
```

## Calibration and limitations (also stated in the paper)

- Cryptography is a calibrated CPU delay in ns-3, not executed. The scalar-multiplication times are the authors' earlier values (ESP32 28.62 ms, RPi4 4.20 ms). The back-end value (0.10 ms) is an assumption. MSM and individual-verification costs are measured *ratios* (`bench_g2_127_calibration.json`). To recalibrate, change `tHecm*` on the command line, or the `MSM_PTS` table in `hibaf-sim.cc`, and rerun the campaign.
- The ns-3 calibration ratios were measured on a random curve under CPU contention. Repeated on the certified curve with the CPU idle (`curve/bench_certified_curve_summary.json`), MSM costs 0.25–0.28 HECM per report for n ≥ 50, versus 0.32–0.34 in the calibration, so the simulated MSM gains are conservative.
- Reproduce the curve: `python3 curve/find_curve.py && python3 curve/validate_curve.py && python3 curve/real_curve_test.py` (needs sympy).
- The shipped `01_adversarial_bisection.py` of the previous package omitted the cost of failed parent tests. `crypto_level1/01_adversarial_bisection_FIXED.py` reproduces the earlier manuscript's Fig. 5 exactly.

## Revision after external review (2026-10-15)

| Path | What | Status |
|---|---|---|
| `curve/cert/` | Deterministic proof that #J = q: ECPP certificates for q and p (PARI/GP `primecert`, Primo format), qL = O, exact Hasse–Weil check. `python3 certify_order.py` | proved |
| `tamarin/hibaf_v3_enrol.spthy` | Three-message (SIGMA-I style) enrolment with key confirmation; 5 lemmas verified, unbounded (`v3_enrol.log`) | symbolic |
| `tamarin/hibaf_v3_fs_grace.spthy` | Three-epoch ratchet with the back end's grace-period retention of the last window's keys: forward secrecy with the grace exception, other windows secret, secret after the grace period, and reachability of the grace exposure; 4 lemmas verified (`fs_grace.log`) | symbolic |
| `tamarin/hibaf_v2_enrol_flaw.spthy` | Old two-message enrolment: Tamarin falsifies "BE installs only keys the sensor derived" (replayed message 1 overwrites the key) | symbolic (attack) |
| `reference_model/` | Updated model (3-message enrolment, evidence-based revocation); 35/35 checks (`test_output.txt`) | executable |
| `platform/` | Portable C implementation (`g2.c`, `bench.c`) of the certified curve; ESP32 run under Espressif QEMU (`esp32_run.txt`, CCOUNT with `-icount shift=5`, 1.28 ticks/instruction); Cortex-A72 build under QEMU 9.2.2 with insn/hotblocks plugins (`a72_run.txt`) and llvm-mca cycle model (`a72_mca.py`); summary `platform_estimates.json` | **emulated estimates, not hardware measurements** |
| `ns3/hibaf-sim.cc` | Adds `--evidence` (revocation on back-end-validated evidence, default 1), `--byzNoticeRate`, `--sharedChannel`, `--pondSpacing`, `--beaconStagger` | simulated |
| `campaign/campaign_rev.py`, `analyze_rev.py` | 1,800 runs: Dev (scenario D with evidence), Dz (Byzantine collector), G (shared channel), H_* (recalibration with emulated platform costs) | simulated |
| `results/tables/all_runs_rev.csv` | One row per revision run | simulated |

Build the platform benchmarks:
```bash
gcc -O2 bench.c -o bench64 && ./bench64 selftest
aarch64-linux-gnu-gcc -O2 -static -mcpu=cortex-a72 bench.c -o bench_a72   # run under qemu-aarch64 with libinsn.so
xtensa-esp32-elf-gcc -O2 -DESP_ALL -DBKBITS=6 -specs=sim.elf.specs -specs=sys.qemu.specs -Wl,--defsym=entire_dram_seg=1 bench.c -o bench_esp32.elf
qemu-system-xtensa -M esp32 -nographic -semihosting -kernel bench_esp32.elf -icount shift=5
```
The old scenario D results (revocation on the collector's notice alone) remain in `results/tables/all_runs.csv` (tag D) for comparison; the paper uses tag Dev.

## Restructured version (v3): analytical and Monte Carlo evaluation

| Path | What | Status |
|---|---|---|
| `analytic/eval_analytic.py` | Monte Carlo (seed 20260603, 10 000 windows): mixed validity (individual, Base + bisection, MSM + bisection, HiBaF-MSM controller) and replay filtering vs. B4; Base reproduces the earlier manuscript exactly | Monte Carlo |
| `analytic/eval_analytic2.py` | Figures, scalability (back-end admissible T_HECM, workers, site critical path) and energy (E = P·T) | analytical |
| `analytic/eval_tables_v3.py` | Operation-count, scheme-comparison, B2/B3 and energy tables | analytical |
| `hardware_harness/` | Raspberry Pi C sources and native runner (`raspberry_pi/`), ESP-IDF source and prebuilt firmware (`esp32_idf/`), and raw measurement logs (`results/`); original harness ZIP also retained | to be run on hardware |

## Recheck (2026-10-15, evening)
- `H2` (challenge hash to Z_q) is BLAKE2b-512 reduced mod q in the reference model and the real-curve test (a 256-bit hash reduced mod q ≈ 2^254 is at statistical distance ≈ 2^-62.7 from uniform). All 35 reference-model checks and the real-curve test pass.
- Monte Carlo controller candidates are the powers of two b ∈ {2,…,256} with g ∈ {1,2,4,8,16} (40 candidates), identical to Algorithm 3 and the ns-3 controller.
- `analytic/be_sens.py`: 60 runs of scenario A (500 sensors) with the measured x86 back-end cost (1.19 ms per scalar multiplication).
- `analytic/analyze_fig.py`: regenerates the ns-3 figures from the archived `all_runs_original_3510.csv` with generic axis labels (summary tables are byte-identical to the originals).


## ESP32 hardware measurement (October 2026)

- `hardware_harness/results/esp32_results.txt`: raw serial output of `hw_bench.c` on an ESP32-D0WD-V3 (rev. 3.0) at 240 MHz, ESP-IDF v5.4.1, `esp_timer`, 7 repetitions; self-test PASS. One 254-bit scalar multiplication: 102.666 ms median (101.778-103.476). **Hardware measurement.**
- `campaign/campaign_hw.py`, `campaign/analyze_hw.py`, `results/rev_H_hw.csv`: ns-3 recalibration (scenarios A, A2, E; 1,020 runs) with the measured ESP32 cost at the sensors and the emulated Cortex-A72 range (1.12 / 2.78 ms) at collectors and station.

## Raspberry Pi 4 hardware measurement (October 2026)

- `hardware_harness/results/pi_results.csv`: `run_pi.sh` output on a Raspberry Pi 4 Model B Rev 1.5 (1.8 GHz, performance governor, no throttling, 50-52 C, Linux 6.18.50, gcc 14.2.0); self-test PASS. One 254-bit scalar multiplication: 1.706 ms median (1.690-1.720). **Hardware measurement.**
- `campaign/campaign_hw2.py`, `campaign/analyze_pi.py`, `results/rev_H_pi.csv`: final ns-3 recalibration (scenarios A, A2, E; 510 runs) with both measured costs (ESP32 102.666 ms, Pi 4 1.706 ms). The earlier runs with emulated Cortex-A72 costs (`rev_H_hw.csv`) are kept for comparison.

## Browsable ESP32 and Raspberry Pi source

The hardware-harness ZIP is also unpacked in this repository for direct inspection:

- **Raspberry Pi 4:** `hardware_harness/raspberry_pi/hw_bench.c`, `g2.c`, `run_pi.sh`. The script builds with GCC and records native measurements on the board.
- **ESP32:** `hardware_harness/esp32_idf/main/hw_bench.c`, `g2.c`, `main.c`, ESP-IDF CMake files and `sdkconfig.defaults`. Requires ESP-IDF 5.4.1 to rebuild, using `idf.py set-target esp32 build`.
- **Optional prebuilt firmware:** `hardware_harness/esp32_idf/prebuilt/`.
- **Original measurement data:** `hardware_harness/results/`. `QEMU_SMOKE_TEST_NOT_HARDWARE.log` is an emulator check, **not a hardware timing measurement**.

The reference model includes the pending-duplicate regression check: `python reference_model/test_hibaf_v2.py` (requires the Python `cryptography` package), expected `35/35 checks passed`.

## Portable ns-3 campaigns and curve verification

The campaign scripts discover the ns-3.49 executable in `ns-3.49/build/scratch/hibaf/`
relative to the repository root and write raw run summaries under `runs/`.
Use `HIBAF_NS3_BIN` for a custom executable, and `HIBAF_RUNS_DIR`
to choose an alternative location for the run directories. The same run directory
is used by `campaign/analyze.py`, `analyze_rev.py`, `analyze_hw.py`
and `analyze_pi.py`. Python dependencies include `numpy`, `pandas`,
`matplotlib` and `scipy`; compiling ns-3.49 also requires the relevant
ns-3 toolchain and modules.

```bash
python3 curve/validate_curve.py
python3 curve/real_curve_test.py
python3 curve/cert/certify_order.py  # also requires PARI/GP executable 'gp'
```

The curve checks use the included Jacobian model and JSON files, with paths
resolved from the scripts rather than the working directory.

For Cortex-A72 QEMU measurements, first build `platform/bench_a72`
and supply the separately built QEMU plugins. See
[platform/README.md](platform/README.md) for the required environment variables.
Emulated estimates are not hardware measurements.

## Portable analytical evaluation

The analytical scripts now locate inputs relative to this repository rather than using developer-specific absolute paths. See [analytic/README.md](analytic/README.md) for dependencies, commands, generated outputs and evidence boundaries.
