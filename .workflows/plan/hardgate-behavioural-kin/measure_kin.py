import sqlite3, sys, numpy as np
from seer_engine.lab import hardgate, store
from seer_engine.backtest import regime
conn = sqlite3.connect(sys.argv[1]); conn.row_factory = sqlite3.Row
geo = hardgate.geometry(conn); bench=list(geo.bench)
def monthly(curve):
    m={}
    for d,v in curve: m[(d.year,d.month)]=v
    k=sorted(m); return {k[i]:m[k[i]]/m[k[i-1]]-1 for i in range(1,len(k))}
bm=monthly(bench)
def resid(a):
    ks=sorted(set(a)&set(bm)); x=np.array([bm[k] for k in ks]); y=np.array([a[k] for k in ks])
    b=np.polyfit(x,y,1); return dict(zip(ks,y-np.polyval(b,x)))
def rc(a,b):
    ks=sorted(set(a)&set(b))
    if len(ks)<36: return float('nan')
    return float(np.corrcoef([a[k] for k in ks],[b[k] for k in ks])[0,1])
status={r[0]:r[1] for r in conn.execute("select id,status from methods")}
fam={r[0]:r[1] for r in conn.execute("select id,family from methods")}
V={}  # method -> {cand: resid series}
for (mid,) in conn.execute("select id from methods order by id"):
    rows=hardgate._dev_curves(conn,mid)
    if not rows: continue
    if hardgate.mismatches(conn, geo.bench_n, rows): print('mismatch',mid); continue
    V[mid]={}
    for r in rows:
        c=hardgate._curve_of(r); V[mid][r['candidate_id']]=resid(monthly(regime.defunded(c,hardgate.trial_deposits(conn,r,c))))
failed=[m for m in V if status[m]=='test-failed']
tested={m: conn.execute("select candidate_id from trials where method_id=? and window='test' order by n limit 1",(m,)).fetchone()[0] for m in failed}
print('tested',tested)
F={m:V[m][tested[m]] for m in failed}
print('failed x failed'); 
for a in failed: print(a,[f"{rc(F[a],F[b]):.2f}" for b in failed])
def promo(m):
    try: return hardgate.promoted_variant(conn,m)
    except Exception: return None
res=[]
for m in V:
    p=promo(m)
    pv = max((rc(V[m][p],F[f]),f) for f in failed if f!=m) if p in V[m] else None
    anyv = max((rc(s,F[f]),f,c) for c,s in V[m].items() for f in failed if f!=m)
    res.append((m,p,pv,anyv))
for m,p,pv,anyv in sorted(res,key=lambda r:-(r[3][0] if r[3][0]==r[3][0] else -1)):
    print(f"{m:10s} {status[m]:12s} {fam[m][:30]:30s} promo={'%.2f'%pv[0] if pv else '  - '} any={anyv[0]:.2f} {anyv[1]} via {anyv[2]} K={','.join(hardgate.failed_kin(conn,m)) or '-'}")
