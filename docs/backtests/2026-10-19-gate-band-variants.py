"""Can the gate's insurance be kept without its calm-decade premium? Measured on SPY alone.

Every variant is scored on BOTH axes at once, because the standing result is that every
gate-off arm was worse on return AND drawdown together. A variant only counts if it cuts the
2009-2015 premium while still sitting out the two crashes. Signals read bars through day i and
are acted on at i+1, so nothing here trades on a close it has not seen.
"""
import csv, numpy as np
from datetime import date

rows = [r for r in csv.DictReader(open('engine/.research/bars.csv')) if r['symbol'] == 'SPY']
rows.sort(key=lambda r: r['date'])
d = np.array([date.fromisoformat(r['date']) for r in rows])
c = np.array([float(r['close']) for r in rows])
n = len(c)

vix = {}
for r in csv.DictReader(open('engine/.research/market_series.csv')):
    if r['series'] == 'VIX':
        vix[date.fromisoformat(r['date'])] = float(r['value'])
V = np.array([vix.get(x, np.nan) for x in d])

def sma(a, w):
    out = np.full(len(a), np.nan)
    cs = np.cumsum(np.insert(a, 0, 0.0))
    out[w-1:] = (cs[w:] - cs[:-w]) / w
    return out

S200, S50 = sma(c, 200), sma(c, 50)
ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
WARM = 200

def run(weight):
    """weight[i] = fraction of the book in the market on day i, already lagged."""
    w = np.zeros(n); w[1:] = weight[:-1]
    w[:WARM] = 0.0
    eq = np.cumprod(1.0 + ret * w)
    return eq, w

def stats(eq, w, lo, hi):
    m = (d >= lo) & (d <= hi)
    i = np.where(m)[0]
    if len(i) < 2: return None
    yrs = (d[i[-1]] - d[i[0]]).days / 365.25
    e = eq[i] / eq[i[0]]
    cagr = e[-1] ** (1 / yrs) - 1.0
    dd = (e / np.maximum.accumulate(e) - 1.0).min()
    return dict(cagr=cagr, dd=dd, inv=w[i].mean())

def spy_stats(lo, hi):
    m = (d >= lo) & (d <= hi); i = np.where(m)[0]
    yrs = (d[i[-1]] - d[i[0]]).days / 365.25
    e = c[i] / c[i[0]]
    return (e[-1] ** (1/yrs) - 1.0), (e / np.maximum.accumulate(e) - 1.0).min()

ERAS = [("whole", date(1994,1,1), date(2015,10,16)),
        ("dotcom", date(2000,3,1), date(2002,10,31)),
        ("gfc", date(2007,10,1), date(2009,3,31)),
        ("2009-2015", date(2009,1,1), date(2015,10,16))]

# ---------------------------------------------------------------- the variants
def baseline():
    return (c > S200).astype(float)

def band(b):
    """Exit only b% BELOW the average, re-enter only b% above: a price band, not a time lock."""
    on = np.zeros(n); cur = 0.0
    for i in range(n):
        if np.isnan(S200[i]): on[i] = 0.0; continue
        if cur == 0.0 and c[i] > S200[i] * (1 + b): cur = 1.0
        elif cur == 1.0 and c[i] < S200[i] * (1 - b): cur = 0.0
        on[i] = cur
    return on

def exit_buffer(b):
    """Asymmetric: hard to leave (b% below), easy to come back (any cross above)."""
    on = np.zeros(n); cur = 0.0
    for i in range(n):
        if np.isnan(S200[i]): on[i] = 0.0; continue
        if cur == 0.0 and c[i] > S200[i]: cur = 1.0
        elif cur == 1.0 and c[i] < S200[i] * (1 - b): cur = 0.0
        on[i] = cur
    return on

def confirm(k):
    """Exit only after k consecutive closes below the average."""
    below = (c < S200)
    run_ = np.zeros(n, int)
    for i in range(1, n):
        run_[i] = run_[i-1] + 1 if below[i] else 0
    on = np.zeros(n); cur = 0.0
    for i in range(n):
        if np.isnan(S200[i]): on[i] = 0.0; continue
        if cur == 0.0 and c[i] > S200[i]: cur = 1.0
        elif cur == 1.0 and run_[i] >= k: cur = 0.0
        on[i] = cur
    return on

def partial(wout):
    return np.where(np.isnan(S200), 0.0, np.where(c > S200, 1.0, wout))

def fast_reentry():
    """Out on the 200-day, back in on the 50-day: slow to leave, quick to return."""
    on = np.zeros(n); cur = 0.0
    for i in range(n):
        if np.isnan(S200[i]) or np.isnan(S50[i]): on[i] = 0.0; continue
        if cur == 0.0 and (c[i] > S50[i] or c[i] > S200[i]): cur = 1.0
        elif cur == 1.0 and c[i] < S200[i]: cur = 0.0
        on[i] = cur
    return on

def vix_confirm(th):
    """Honour the exit only when fear is actually elevated."""
    on = np.zeros(n); cur = 0.0
    for i in range(n):
        if np.isnan(S200[i]): on[i] = 0.0; continue
        v = V[i] if not np.isnan(V[i]) else 0.0
        if cur == 0.0 and c[i] > S200[i]: cur = 1.0
        elif cur == 1.0 and c[i] < S200[i] and v >= th: cur = 0.0
        on[i] = cur
    return on

VARIANTS = [("baseline gate", baseline())]
for b in (0.01, 0.02, 0.03, 0.05): VARIANTS.append((f"band {b*100:.0f}%", band(b)))
for b in (0.02, 0.03, 0.05):       VARIANTS.append((f"exit-buffer {b*100:.0f}%", exit_buffer(b)))
for k in (3, 5, 10):               VARIANTS.append((f"confirm {k}d", confirm(k)))
for wv in (0.25, 0.5):             VARIANTS.append((f"partial {wv*100:.0f}% out", partial(wv)))
VARIANTS.append(("fast re-entry (50d)", fast_reentry()))
for th in (20, 25, 30):            VARIANTS.append((f"VIX>={th} confirm", vix_confirm(th)))

sc, sdd = spy_stats(date(1994,1,1), date(2015,10,16))
s09, s09dd = spy_stats(date(2009,1,1), date(2015,10,16))
print(f"SPY buy-and-hold:  whole {sc*100:.2f}%/yr dd {sdd*100:.1f}%   |  2009-2015 {s09*100:.2f}%/yr dd {s09dd*100:.1f}%\n")
hdr = f"{'variant':22s} {'whole':>7} {'wDD':>7} {'dotDD':>7} {'gfcDD':>7} {'09-15':>7} {'prem':>7} {'inv09':>6}"
print(hdr); print("-" * len(hdr))
for name, sig in VARIANTS:
    eq, w = run(sig)
    r = {k: stats(eq, w, lo, hi) for k, lo, hi in ERAS}
    prem = r["2009-2015"]["cagr"] - s09
    print(f"{name:22s} {r['whole']['cagr']*100:6.2f}% {r['whole']['dd']*100:6.1f}% "
          f"{r['dotcom']['dd']*100:6.1f}% {r['gfc']['dd']*100:6.1f}% "
          f"{r['2009-2015']['cagr']*100:6.2f}% {prem*100:+6.2f} {r['2009-2015']['inv']*100:5.1f}%")
