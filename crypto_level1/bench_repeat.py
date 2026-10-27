"""Repeat the Level-1 ratio measurement R times (fresh points/scalars each time) to report variability."""
import json, sys, subprocess, statistics as st, os
R = int(sys.argv[1]) if len(sys.argv) > 1 else 3
res = []
for r in range(R):
    subprocess.run([sys.executable, "bench_g2_127.py"], check=True, capture_output=True,
                   env=dict(os.environ, BENCH_SEED=str(1000 + r)))
    res.append(json.load(open("bench_g2_127.json")))
os.replace("bench_g2_127.json", "bench_g2_127_last_repeat.json")
out = {"repeats": R, "ratio_indiv": [x["T_indiv_shamir_ms"]/x["T_hecm_ms"] for x in res], "rows": {}}
for i, row in enumerate(res[0]["rows"]):
    vals = [x["rows"][i]["rho_best_over_hecm"] for x in res]
    out["rows"][row["n"]] = dict(mean=st.mean(vals), sd=st.stdev(vals) if R > 1 else 0, values=vals)
json.dump(out, open("bench_repeat.json", "w"), indent=1)
print(json.dumps(out, indent=1))
