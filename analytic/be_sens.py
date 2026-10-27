import sys, time
from multiprocessing import Pool
import campaign as C0
J=[]
for v in ["msm","ind"]:
    for r in C0.SEEDS:
        J.append(dict(tag="BEsens", variant=v, run=r, nSensors=500, reportInterval=10, simTime=330, tHecmBe=1.19))
with Pool(2) as p:
    for i,_ in enumerate(p.imap_unordered(C0.run, J)):
        if (i+1)%20==0: print(i+1, flush=True)
print("ALL DONE", flush=True)
