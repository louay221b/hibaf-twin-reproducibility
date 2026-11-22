"""Compare invalid-report isolation strategies (analytical group-op cost, 254-bit scalars).
Cost models (textbook estimates, NOT measurements):
  individual verify (Shamir/Straus 2-term)   : 364 ops
  Base batch over m reports (2m+1 indep. wNAF): (2m+1)*309.8 + 2m
  MSM batch over m reports (Straus, short alpha): 254 + m*(128/5+4) + m*(254/5+4) + (254/5+4)"""
import numpy as np
rng = np.random.default_rng(20260603)
IND = 364.0
base = lambda m: (2*m+1)*309.8 + 2*m
msm  = lambda m: 254 + m*(128/5+4) + m*(254/5+4) + (254/5+4)
def bisect(inv, l, r, B, skip):
    m = r-l
    if m == 1: return IND
    c = B(m)
    if inv[l:r].sum() == 0: return c
    mid = l+m//2
    left = bisect_known(inv,l,mid,B,skip) if False else bisect(inv,l,mid,B,skip)
    if skip and inv[l:mid].sum()==0:          # left passed -> right known bad: don't re-test it
        return c + left + split_known_bad(inv,mid,r,B)
    return c + left + bisect(inv,mid,r,B,skip)
def split_known_bad(inv,l,r,B):
    m=r-l
    if m==1: return IND
    mid=l+m//2
    left = bisect(inv,l,mid,B,True)
    if inv[l:mid].sum()==0: return left + split_known_bad(inv,mid,r,B)
    return left + bisect(inv,mid,r,B,True)
def fallback(inv,B): 
    n=len(inv); return B(n) + (0 if inv.sum()==0 else n*IND)
W=3000
print(f"{'n':>4} {'mu%':>5} | {'indiv':>8} | Base: {'bisect':>8} {'bis+skip':>8} {'fallback':>8} | MSM: {'bisect':>8} {'bis+skip':>8} {'fallback':>8}")
for n in [10,100,500]:
    for mu in [0,0.01,0.05,0.25]:
        acc={k:[] for k in ['bb','bs','bf','mb','ms','mf']}
        for _ in range(W):
            inv=(rng.random(n)<mu).astype(int)
            acc['bb'].append(bisect(inv,0,n,base,False)); acc['bs'].append(bisect(inv,0,n,base,True)); acc['bf'].append(fallback(inv,base))
            acc['mb'].append(bisect(inv,0,n,msm,False)); acc['ms'].append(bisect(inv,0,n,msm,True)); acc['mf'].append(fallback(inv,msm))
        a={k:np.mean(v)/(n*IND) for k,v in acc.items()}
        print(f"{n:>4} {mu*100:>5.0f} | {1.0:>8.2f} | Base: {a['bb']:>8.2f} {a['bs']:>8.2f} {a['bf']:>8.2f} | MSM: {a['mb']:>8.2f} {a['ms']:>8.2f} {a['mf']:>8.2f}")
print("(values = cost relative to individual verification of all n reports; <1 is a saving)")
