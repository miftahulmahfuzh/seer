"""Re-derive M0356's frozen COEF from the dev store. Provenance for the constants, nothing else.

M0356 scores stocks with 42 elastic-net coefficients that were fitted once, offline, and written
into ``lab/methods/m0356_frozen_daily_return_weights.py`` as constants. A frozen number nobody
can re-derive is a number the lab has to take on trust, so this is the recipe as a script. It is
not part of the engine, nothing imports it, and it records nothing: run it and compare its output
with ``COEF``.

Training data is 1993-01-29 .. 1995-12-29 only. The scored dev window for a member-reading method
opens at ``MEMBERSHIP_START`` = 1996-01-02, so nothing here is inside the window M0356 is judged
on. The single exception, stated in the method's docstring too: the training universe is the
membership snapshot of 1996-01-02, because no point-in-time membership exists before that date.

    engine/.venv/bin/python engine/scripts/fit_m0356_frozen_weights.py [--store PATH]
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.linear_model import ElasticNet
from sklearn.model_selection import GroupKFold

from seer_engine import research

CLIP = 0.5  # m0353._features clips each daily return to +/- this
W = 21  # one trading month of daily returns
TRAIN_END = date(1995, 12, 31)
UNIVERSE_ON = date(1996, 1, 2)  # MEMBERSHIP_START: the first membership row there is
MIN_PRICE = 5.0
ALPHA, L1 = 1e-4, 0.5  # the forced, least-shrunk fit; honest CV picks the empty model


def sample(store: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The 42 features, the cross-section-demeaned next-month return, and a month group id."""
    data = research.load_store(store)
    market = data.market
    members = sorted(market.membership.members_on(UNIVERSE_ON))
    sessions = [d.astype("datetime64[D]").astype(object) for d in market.history["SPY"].dates]
    month_end: dict[tuple[int, int], date] = {}
    for s in sessions:
        if s <= TRAIN_END:
            month_end[(s.year, s.month)] = s
    obs = [month_end[k] for k in sorted(month_end)]

    rows: list[np.ndarray] = []
    target: list[float] = []
    group: list[int] = []
    for oi in range(len(obs) - 1):
        t, nxt = obs[oi], obs[oi + 1]
        x_m: list[np.ndarray] = []
        y_m: list[float] = []
        for symbol in members:
            h = market.history.get(symbol)
            if h is None:
                continue
            i, j = h.index_of(t), h.index_of(nxt)
            if i is None or j is None or i < W:
                continue
            close = h.close[i - W : i + 1].astype(float)
            if not (np.all(np.isfinite(close)) and np.all(close > 0.0)):
                continue
            if float(h.close[i]) < MIN_PRICE or not np.isfinite(h.close[j]) or h.close[j] <= 0:
                continue
            r = np.clip(close[1:] / close[:-1] - 1.0, -CLIP, CLIP)
            x_m.append(np.concatenate([r, np.sort(r)]))
            y_m.append(float(h.close[j]) / float(h.close[i]) - 1.0)
        if len(y_m) < 30:  # too thin a cross-section to demean meaningfully
            continue
        y_arr = np.asarray(y_m) - float(np.mean(y_m))
        rows.extend(x_m)
        target.extend(y_arr.tolist())
        group.extend([oi] * len(y_m))
    return np.asarray(rows), np.asarray(target), np.asarray(group)


def main() -> None:
    ap = argparse.ArgumentParser(description="Re-derive M0356's frozen coefficients.")
    ap.add_argument("--store", type=Path, default=Path("engine/.research"))
    args = ap.parse_args()

    x, y, g = sample(args.store)
    print(f"training rows {x.shape[0]}, features {x.shape[1]}, monthly cross-sections {len(set(g))}")
    sd = np.where(x.std(0) > 0, x.std(0), 1.0)
    z = (x - x.mean(0)) / sd

    cv = GroupKFold(n_splits=5)
    errs = []
    for tr, te in cv.split(z, y, g):
        m = ElasticNet(alpha=ALPHA, l1_ratio=L1, max_iter=500_000, tol=1e-10).fit(z[tr], y[tr])
        errs.append(float(np.mean((y[te] - m.predict(z[te])) ** 2)))
    print(f"grouped-CV R2 at alpha={ALPHA} l1_ratio={L1}: "
          f"{1.0 - float(np.mean(errs)) / float(np.mean(y**2)):+.5f}")

    model = ElasticNet(alpha=ALPHA, l1_ratio=L1, max_iter=500_000, tol=1e-10).fit(z, y)
    coef = model.coef_ / sd
    print(f"non-zero coefficients {int(np.sum(coef != 0))}/42")
    print("COEF = (")
    for i in range(0, 42, 6):
        print("    " + " ".join(f"{c:+.8f}," for c in coef[i : i + 6]))
    print(")")


if __name__ == "__main__":
    main()
