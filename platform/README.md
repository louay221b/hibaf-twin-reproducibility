# Cortex-A72 and ESP32 emulation

The programs in this directory produce **emulated cost estimates**, not physical-device measurements. The physical ESP32 and Raspberry Pi benchmarks, including their raw logs, are under `hardware_harness/`.

## Cortex-A72 execution under QEMU (Linux / WSL)

Cross-compile from the repository root (the toolchain must be installed separately):

```bash
aarch64-linux-gnu-gcc -O2 -static -mcpu=cortex-a72 platform/bench.c -o platform/bench_a72
```

The instruction-count and hot-block scripts use QEMU plugins that must be built or supplied separately. Their paths are **not part of this repository**. Configure them with environment variables rather than developer-specific locations:

```bash
export HIBAF_QEMU_AARCH64=qemu-aarch64
export HIBAF_QEMU_INSN_PLUGIN=/path/to/libinsn.so
bash platform/run_a72.sh

export HIBAF_QEMU_HOTBLOCKS=/path/to/libhotblocks.so
python3 platform/a72_mca.py
```

`a72_mca.py` additionally requires `llvm-objdump` and `llvm-mca`. Its estimate assumes warm caches and predicted branches, as documented in its source. The raw modelled results are archived as `a72_mca_raw.json`.

## ESP32 emulation

The `bench.c` benchmark also supports an ESP32 QEMU build with the Xtensa toolchain; see the top-level README for the exact compile and emulator command. Results in `esp32_run.txt` were measured using emulation, and **must not be presented as physical ESP32 timings**.

Hardware sources and measured timings are available separately in `hardware_harness/esp32_idf/`, `hardware_harness/raspberry_pi/`, and `hardware_harness/results/`.
