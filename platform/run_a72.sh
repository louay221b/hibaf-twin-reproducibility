#!/bin/bash
QA=/home/claude/qemu/qemu/build/qemu-aarch64; PL=/home/claude/qemu/qemu/build/tests/tcg/plugins/libinsn.so
run(){ out=$($QA -plugin $PL -d plugin ./bench_a72 "$@" 2>&1); r=$(echo "$out" | grep RESULT); i=$(echo "$out" | grep "total insns" | awk '{print $3}'); echo "$r insns=$i"; }
run none
for m in fmul fadd finv gadd gdbl hecm indiv; do run $m; done
for n in 1 5 10 25 50 100 250 500; do run straus $n; [ $((2*n+1)) -ge 21 ] && run pipp $n; done
