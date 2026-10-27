#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QA="${HIBAF_QEMU_AARCH64:-qemu-aarch64}"
PL="${HIBAF_QEMU_INSN_PLUGIN:-}"
if [[ -z "$PL" || ! -f "$PL" ]]; then
  echo "Set HIBAF_QEMU_INSN_PLUGIN to the compiled QEMU libinsn.so plugin." >&2
  exit 2
fi
if [[ ! -f "$HERE/bench_a72" ]]; then
  echo "Missing $HERE/bench_a72; cross-compile platform/bench.c for Cortex-A72 first." >&2
  exit 2
fi
run(){
  out=$("$QA" -plugin "$PL" -d plugin "$HERE/bench_a72" "$@" 2>&1)
  r=$(echo "$out" | grep RESULT)
  i=$(echo "$out" | grep "total insns" | awk '{print $3}')
  echo "$r insns=$i"
}
run none
for m in fmul fadd finv gadd gdbl hecm indiv; do run "$m"; done
for n in 1 5 10 25 50 100 250 500; do run straus "$n"; [ $((2*n+1)) -ge 21 ] && run pipp "$n"; done
