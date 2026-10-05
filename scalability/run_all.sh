#!/bin/sh
# Deterministic: Experiments H, I and J are closed-form / enumerative.
set -e
cd "$(dirname "$0")/scripts"
python3 expH_hecm_sensitivity.py
python3 expI_dt_workers.py
python3 expJ_collector_parallelism.py
python3 verify_all.py
echo "run_all.sh: OK"
