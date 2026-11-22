import glob,re,csv,collections,statistics as st
def load(pat):
    D=collections.defaultdict(list)
    for f in glob.glob(pat):
        r=list(csv.DictReader(open(f)))[0]
        D[(r['tag'],r['variant'])].append(r)
    return D
new=load('runs/*/summary.csv')
old=load('/home/claude/sim/runs_beaconfix/*/summary.csv')
oldall=load('/home/claude/sim/runs_hwall/*/summary.csv')
cols=['pdr','syncSuccess','e2eMean','e2eP95','colCpuUtil','hecmPerVerified']
def m(rows,c):
    v=[float(r[c]) for r in rows if r[c] not in('nan','')]
    n=len(v); mu=sum(v)/n; sd=st.stdev(v) if n>1 else 0
    return mu,2.045*sd/n**.5,n
def line(lab,rows):
    s=[]
    for c in cols:
        mu,ci,n=m(rows,c); s.append(f"{c}={mu:.4g}±{ci:.2g}")
    print(f"{lab:34s} n={len(rows)} "+" ".join(s))
def pick(D,tag,var,att=None):
    rows=D.get((tag,var),[])
    if att is not None: rows=[r for r in rows if r['attackers']==str(att)]
    return rows
for sc,oldtag,att in(('A2','H_A2_hwPi',None),('E','H_E_hwPi',10)):
    print('==',sc)
    for v in('msm','base','ind'):
        line(f'{v} BE=0.10 (published)',pick(old,oldtag,v,att))
        for be in('1.19','0.86'):
            line(f'{v} BE={be} (new)',pick(new,f'S1_{sc}_be{be}',v))
print('== B1 theta')
for lab,tag,otag,ok in(('A100','S2_A100_th025','H_A_hwPi',lambda r:r['nSensors']=='100'),('A500','S2_A500_th025','H_A_hwPi',lambda r:r['nSensors']=='500'),('A2','S2_A2_th025','H_A2_hwPi',lambda r:True),('E','S2_E_th025','H_E_hwPi',lambda r:r['attackers']=='10')):
    line(f'{lab} ind theta=1 (published)',[r for r in old.get((otag,'ind'),[]) if ok(r)])
    line(f'{lab} ind theta=0.25 (new)',new.get((tag,'ind'),[]))
    line(f'{lab} msm theta=0.25 (published)',[r for r in old.get((otag,'msm'),[]) if ok(r)])
