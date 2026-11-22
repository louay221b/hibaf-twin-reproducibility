# HiBaF-Twin hardware timing harness

Both programs first run a self-test on the target (fast formulas vs generic Cantor, q·L = O,
a reference vector shared with the Python implementation) and then time each operation
7 times, printing the median, min and max per operation:

    HW,<platform>,<operation>,<n>,<median_ms>,<min_ms>,<max_ms>,<repeats>,<ops_per_repeat>

Send back the complete output files (`pi_results.csv`, `esp32_results.txt`); the paper and the
ns-3 recalibration are updated from them directly.

## Raspberry Pi 4
```bash
sudo sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'   # recommended
./raspberry_pi/run_pi.sh          # builds natively and writes raspberry_pi/pi_results.csv (~10 s)
```
Use a heatsink/fan; the script records throttling state before and after.

## ESP32 (240 MHz)
Prebuilt (ESP-IDF v5.4.1, 2 MB flash, DIO 40 MHz), flash with esptool and capture the serial output (115200 baud):
```bash
python -m esptool --chip esp32 -b 460800 write_flash --flash_mode dio --flash_size 2MB --flash_freq 40m \
    0x1000 esp32_idf/prebuilt/bootloader.bin 0x8000 esp32_idf/prebuilt/partition-table.bin 0x10000 esp32_idf/prebuilt/hibaf_hw_bench.bin
python -m serial.tools.miniterm /dev/ttyUSB0 115200 | tee esp32_results.txt     # press EN/RESET; wait for "DONE" (~15 s)
```
Or rebuild from source: `cd esp32_idf && idf.py set-target esp32 build flash monitor | tee esp32_results.txt`.

`QEMU_SMOKE_TEST_NOT_HARDWARE.log` shows the firmware running in Espressif's QEMU. It only
validates the program; its timings are emulator wall-clock and are NOT hardware measurements.
