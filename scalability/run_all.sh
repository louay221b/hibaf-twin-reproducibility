#!/bin/sh
# Deterministic: no random numbers are used (Experiments H, I, J are closed-form / enumerative), so no seed is needed.
# Usage (from anywhere): sh run_all.sh      Requires: python3 with numpy and matplotlib.
set -e
cd "$(dirname "$0")/scripts"
python3 expH_hecm_sensitivity.py
python3 expI_dt_workers.py
python3 expJ_collector_parallelism.py
python3 verify_all.py
python3 plot_all.py
python3 make_tables.py > /dev/null
echo "run_all.sh: OK"
