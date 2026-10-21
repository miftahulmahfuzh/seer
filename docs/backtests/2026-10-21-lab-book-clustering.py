"""Pairwise residual correlation across every recorded dev curve in the lab.

Reuses hardgate's own definitions verbatim -- no second definition of anything:
  hardgate.geometry        the benchmark curve + its trials.n   (the same bench D14 uses)
  hardgate.mismatches      the D10 price-fingerprint comparability rule
  hardgate.trial_deposits  a funded trial's deposits in curve units
  hardgate.monthly_returns de-funded month-on-month returns
  hardgate.residual        monthly returns less their own OLS fit on SPY's (market share removed)
  hardgate.correlation     Pearson over shared months, with MIN_KIN_MONTHS and the flat guard
  hardgate.KIN_CORRELATION the lab's own 0.85 bar
"""
import json, sqlite3, sys, pickle
from datetime import date
import numpy as np
sys.path.insert(0, "/home/miftah/seer/engine/src")
from seer_engine.lab import hardgate, store

DB = sys.argv[1]
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

geo = hardgate.geometry(conn)
print(f"benchmark: {hardgate.regime.BENCH_CANDIDATE} trial #{geo.bench_n}, "
      f"{len(geo.bench)} points, {len(geo.folds)} folds")

rows = conn.execute(
    'SELECT n, method_id, candidate_id, start, "end", curve_json, mar, eligible, total_return '
    "FROM trials WHERE window='dev' AND curve_json IS NOT NULL ORDER BY n"
).fetchall()
rows = [r for r in rows if json.loads(r["curve_json"])]
print(f"dev trials carrying a curve: {len(rows)} over "
      f"{len({r['method_id'] for r in rows})} methods")

# --- (D10) comparability, hardgate's own rule, applied to every row ------------------
problems = hardgate.mismatches(conn, geo.bench_n, rows)
bad_n = set()
for p in problems:
    bad_n.add(int(p.split("trial #")[1].split(")")[0]))
print(f"(D10) rows refused as incomparable: {len(problems)}")
rows = [r for r in rows if int(r["n"]) not in bad_n]

bench = hardgate.monthly_returns(list(geo.bench))
print(f"benchmark monthly returns: {len(bench)} months")

series = {}
not_measured = []
for r in rows:
    curve = hardgate._curve_of(r)
    res = hardgate.residual(
        hardgate.monthly_returns(curve, hardgate.trial_deposits(conn, r, curve)), bench
    )
    if res is None:
        not_measured.append((int(r["n"]), str(r["candidate_id"]), str(r["method_id"])))
    else:
        series[int(r["n"])] = res
print(f"residual series computed: {len(series)}; not measured (short/flat): {len(not_measured)}")
for n, c, m in not_measured[:20]:
    print(f"   not measured: {m} {c} (#{n})")

meta = {int(r["n"]): dict(method=str(r["method_id"]), cand=str(r["candidate_id"]),
                          mar=r["mar"], elig=int(r["eligible"]), ret=r["total_return"])
        for r in rows if int(r["n"]) in series}

ns = sorted(series)
print(f"pairs to compute: {len(ns)*(len(ns)-1)//2}")

# vectorised Pearson over the common month grid -- identical arithmetic to
# hardgate.correlation, which every pair below is also spot-checked against.
months = sorted({m for s in series.values() for m in s})
idx = {m: i for i, m in enumerate(months)}
M = np.full((len(ns), len(months)), np.nan)
for i, n in enumerate(ns):
    for m, v in series[n].items():
        M[i, idx[m]] = v
mask = ~np.isnan(M)
X = np.nan_to_num(M)
cnt = mask.astype(float) @ mask.astype(float).T
s1 = X @ mask.astype(float).T          # sum of x over shared months
s2 = mask.astype(float) @ X.T          # sum of y over shared months
sxy = X @ X.T
sxx = (X**2) @ mask.astype(float).T
syy = mask.astype(float) @ (X**2).T
with np.errstate(invalid="ignore", divide="ignore"):
    num = sxy - s1 * s2 / cnt
    den = np.sqrt((sxx - s1**2 / cnt) * (syy - s2**2 / cnt))
    R = num / den
R[cnt < hardgate.MIN_KIN_MONTHS] = np.nan
np.fill_diagonal(R, 1.0)

# spot-check the vectorised matrix against hardgate.correlation on 400 random pairs
rng = np.random.default_rng(7)
worst = 0.0
for _ in range(400):
    i, j = rng.integers(0, len(ns), 2)
    if i == j: continue
    a = hardgate.correlation(series[ns[i]], series[ns[j]])
    b = R[i, j]
    if a is None:
        assert np.isnan(b), (ns[i], ns[j], a, b)
    else:
        worst = max(worst, abs(a - b))
print(f"spot-check vs hardgate.correlation on 400 pairs: max abs diff {worst:.3e}")
print(f"pairs below MIN_KIN_MONTHS ({hardgate.MIN_KIN_MONTHS}): "
      f"{int(np.isnan(R).sum() - np.isnan(np.diag(R)).sum())//2}")

with open(sys.argv[2], "wb") as f:
    pickle.dump(dict(ns=ns, R=R, cnt=cnt, meta=meta, months=months), f)
print("saved")
