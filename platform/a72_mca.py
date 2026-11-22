"""Cycle estimate for Cortex-A72: sum over executed translation blocks of
exec_count x steady-state cycles per block (llvm-mca, -mcpu=cortex-a72).
Assumes warm caches and predicted branches (optimistic); see report."""
import subprocess, sys, re, json, functools, os
BIN = "./bench_a72"; QA = "/home/claude/qemu/qemu/build/qemu-aarch64"
PL = "/home/claude/qemu/qemu/build/contrib/plugins/libhotblocks.so"
dis = {}
for line in subprocess.run(["llvm-objdump", "-d", "--no-show-raw-insn", BIN], capture_output=True, text=True).stdout.splitlines():
    m = re.match(r"\s*([0-9a-f]+):\s+(.*)$", line)
    if m: dis[int(m.group(1), 16)] = m.group(2).split("//")[0].strip()
@functools.lru_cache(None)
def block_cycles(pc, n):
    ins = [dis.get(pc + 4*i) for i in range(n)]
    if any(i is None for i in ins): return float(n)
    # branches/labels: llvm-mca needs no symbolic targets -> replace branch targets by a local label
    asm = []
    for i in ins:
        i = re.sub(r"\s+<[^>]*>", "", i)
        i = re.sub(r"^(b\.\w+|b|bl|cbz|cbnz|tbz|tbnz)(\s+)(.*?)(0x)?[0-9a-f]+$", lambda m: m.group(1) + m.group(2) + m.group(3) + "L0", i)
        asm.append(i)
    src = "L0:\n" + "\n".join(asm) + "\n"
    r = subprocess.run(["llvm-mca", "-mtriple=aarch64", "-mcpu=cortex-a72", "-iterations=200"], input=src, capture_output=True, text=True)
    m = re.search(r"Total Cycles:\s+(\d+)", r.stdout)
    if not m: return float(n)          # fallback: 1 cycle per instruction
    return int(m.group(1)) / 200.0
def estimate(args):
    out = "hb_tmp.txt"
    subprocess.run([QA, "-plugin", PL, "-d", "plugin", "-D", out, BIN] + args, capture_output=True)
    cyc = ins = 0.0; fails = 0
    for line in open(out).read().splitlines()[2:]:
        p = [x.strip() for x in line.split(",")]
        if len(p) < 4: continue
        pc, n, e = int(p[0], 16), int(p[2]), int(p[3])
        c = block_cycles(pc, n); cyc += e * c; ins += e * n
    return cyc, ins
if __name__ == "__main__":
    modes = [["none"], ["fmul"], ["fadd"], ["finv"], ["gadd"], ["gdbl"], ["hecm"], ["indiv"]] + \
            [["straus", str(n)] for n in [1, 5, 10, 25, 50, 100, 250, 500]] + [["pipp", str(n)] for n in [10, 25, 50, 100, 250, 500]]
    res = {}
    for m in modes:
        c, i = estimate(m); res[" ".join(m)] = {"cycles": c, "insns": i}
        print(" ".join(m), f"cycles={c:.0f} insns={i:.0f}", flush=True)
    json.dump(res, open("a72_mca_raw.json", "w"), indent=1)
