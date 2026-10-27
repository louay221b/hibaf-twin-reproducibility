#!/bin/bash
# HiBaF-Twin hardware timing on a Raspberry Pi 4 (64-bit Raspberry Pi OS). Output: pi_results.csv
set -e
cd "$(dirname "$0")"
gcc -O2 -mcpu=cortex-a72 -o hw_bench hw_bench.c
{
  echo "# date: $(date -Iseconds)"
  echo "# model: $( (tr -d '\0' < /proc/device-tree/model) 2>/dev/null || echo unknown)"
  echo "# kernel: $(uname -r)  gcc: $(gcc -dumpfullversion)"
  echo "# cpu max freq kHz: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null)"
  echo "# governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)"
  echo "# throttled: $(vcgencmd get_throttled 2>/dev/null || echo n/a)  temp: $(vcgencmd measure_temp 2>/dev/null || echo n/a)"
  if [ "$(nproc)" -ge 4 ] && command -v taskset >/dev/null; then taskset -c 3 ./hw_bench 500; else ./hw_bench 500; fi
  echo "# throttled after: $(vcgencmd get_throttled 2>/dev/null || echo n/a)  temp: $(vcgencmd measure_temp 2>/dev/null || echo n/a)"
} | tee pi_results.csv
