"""Vectorized bracket-order labels: Strategy B's training target (P6a, handover §3 "Label").

``label_orders`` answers, for many candidate rows at once, "what would ONE bracket order placed
for this row have returned, net of cost, had it traded alone?" It follows design §5 exactly as
``sim.step`` and ``backtest.runner.run_backtest`` apply it, on NYSE sessions:

- the order session is ``S1 = next_session(data_date)``; the order fills only on S1, only when
  S1 has a bar with ``low < limit`` (strict), at ``min(open, limit)``; otherwise it expires;
- a filled order is not checked for exits on S1; ``days_held`` is 1 on S1 and grows by one on
  every later session, with or without a bar;
- on each later session with a bar, in order: ``days_held >= TIME_STOP_DAYS`` exits at the
  open ("time"); ``open <= sl`` at the open ("gap"); ``open >= tp`` at the open ("tp");
  ``low <= sl`` at sl ("sl"); ``high > tp`` at tp ("tp");
- after a session's checks, an order still open whose symbol's last bar is before that
  session is force-closed at the last close (the runner's ``close_unpriced``: sim reason
  "time" with ``forced=True``; here "forced"), resolved on that session.

Only bars dated ``<= end`` are read, and "the symbol's last bar" means its last bar dated
``<= end``: the labels are what a run whose data ends at ``end`` would see. An order not
resolved by ``end`` is unresolved (label NaN, resolved NaT, reason -1).

The label is ``exit * (1 - COST) / (fill * (1 + COST)) - 1``: the net return per dollar of the
one order, 0.1% per side. An expired order's label is 0.0. Labels are training targets, not
money, so this is float arithmetic on the float bars; the brackets are ``float()`` of the
4-dp Decimal prices ``sim`` would get, so every comparison agrees with the Decimal one.

Vectorized: the bars of the symbols present are laid out as session-aligned dense float
matrices (NaN = no bar), then one numpy pass per session offset after S1 runs over the rows
still open, until none is left or the sessions run out.

Pure: no database, clock, randomness, logging or files.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np

from seer_engine import dates
from seer_engine.sim.model import TIME_STOP_DAYS
from seer_engine.strategies.base import History

REASONS: tuple[str, ...] = ("expire", "tp", "sl", "gap", "time", "forced")
COST = 0.001

_EXPIRE = 0
_TP = 1
_SL = 2
_GAP = 3
_TIME = 4
_FORCED = 5
_UNRESOLVED = -1


@dataclass(frozen=True, eq=False)
class Labels:
    """One entry per input row, in input order. Every array is read-only.

    - ``label``: float64, ``exit * (1 - COST) / (fill * (1 + COST)) - 1``; 0.0 for "expire";
      NaN when unresolved.
    - ``resolved``: datetime64[D], the exit session (for "expire": the order session S1);
      NaT when unresolved.
    - ``reason``: int8 index into ``REASONS``; -1 when unresolved.
    - ``fill``: float64 fill price; NaN when the order never filled (expired, or S1 > end).
    - ``exit``: float64 exit price; NaN when not filled or unresolved.
    """

    label: np.ndarray
    resolved: np.ndarray
    reason: np.ndarray
    fill: np.ndarray
    exit: np.ndarray


def _readonly(arr: np.ndarray) -> np.ndarray:
    arr.setflags(write=False)
    return arr


def _prices(name: str, x: object, n: int) -> np.ndarray:
    if not isinstance(x, np.ndarray) or x.dtype != np.float64:
        raise TypeError(f"{name} must be a float64 numpy array")
    if x.shape != (n,):
        raise ValueError(f"{name} has shape {x.shape}, expected ({n},)")
    if not bool(np.all(np.isfinite(x))):
        raise ValueError(f"{name} must be finite on every row")
    return x


def _symbol_index(symbols: Sequence[str], n: int) -> tuple[list[str], np.ndarray]:
    """(sorted distinct symbols, int64 index of each row's symbol into that list)."""
    if isinstance(symbols, (str, bytes)) or not isinstance(symbols, Sequence):
        raise TypeError("symbols must be a sequence of str")
    if len(symbols) != n:
        raise ValueError(f"symbols has {len(symbols)} entries, data_dates has {n}")
    names = sorted(set(symbols))
    for s in names:
        if not isinstance(s, str) or not s:
            raise TypeError(f"every symbol must be a non-empty str, got {s!r}")
    code = {s: i for i, s in enumerate(names)}
    return names, np.fromiter((code[s] for s in symbols), dtype=np.int64, count=n)


def _layout(
    history: Mapping[str, History], names: list[str], sess: np.ndarray, end64: np.datetime64
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Session-aligned bars of ``names`` over ``sess`` (all dated <= end).

    Returns (open, high, low) as (symbols, sessions) float64 matrices with NaN where the
    symbol has no bar, ``gone_from`` (int64: the index of the first session after the symbol's
    last bar dated <= end; 0 when it has none) and ``last_close`` (float64: the close of its
    last bar on a session in ``sess``; NaN when none).
    """
    k, m = len(names), sess.shape[0]
    o = np.full((k, m), np.nan)
    hi = np.full((k, m), np.nan)
    lo = np.full((k, m), np.nan)
    c = np.full((k, m), np.nan)
    gone_from = np.zeros(k, dtype=np.int64)
    for i, s in enumerate(names):
        h = history.get(s)
        if h is None:
            continue
        if not isinstance(h, History):
            raise TypeError(f"history[{s!r}] must be a History, got {type(h).__name__}")
        stop = int(np.searchsorted(h.dates, end64, side="right"))
        if stop == 0:
            continue
        gone_from[i] = int(np.searchsorted(sess, h.dates[stop - 1], side="right"))
        start = int(np.searchsorted(h.dates, sess[0], side="left"))
        if start >= stop:
            continue
        d = h.dates[start:stop]
        pos = np.searchsorted(sess, d, side="left")
        on = (pos < m) & (sess[np.minimum(pos, m - 1)] == d)
        cols = pos[on]
        o[i, cols] = h.open[start:stop][on]
        hi[i, cols] = h.high[start:stop][on]
        lo[i, cols] = h.low[start:stop][on]
        c[i, cols] = h.close[start:stop][on]
    has = ~np.isnan(c)
    any_bar = has.any(axis=1)
    last_col = np.where(any_bar, m - 1 - np.argmax(has[:, ::-1], axis=1), 0)
    last_close = np.where(any_bar, c[np.arange(k), last_col], np.nan)
    return o, hi, lo, gone_from, last_close


def label_orders(
    history: Mapping[str, History],
    symbols: Sequence[str],
    data_dates: np.ndarray,
    limit: np.ndarray,
    tp: np.ndarray,
    sl: np.ndarray,
    end: date,
) -> Labels:
    """Label one bracket order per row, each simulated alone (see the module docstring).

    Row i is the order ``(symbols[i], limit[i], tp[i], sl[i])`` placed after the close of
    ``data_dates[i]`` for the next NYSE session. ``data_dates`` is datetime64[D] without NaT;
    ``limit``, ``tp`` and ``sl`` are finite float64 with ``0 < sl < limit < tp`` on every row
    (``float()`` of a valid 4-dp bracket). A symbol missing from ``history`` has no bars, so
    its orders expire. Raises TypeError / ValueError on malformed input.
    """
    if not isinstance(history, Mapping):
        raise TypeError(f"history must be a Mapping, got {type(history).__name__}")
    if isinstance(end, datetime) or not isinstance(end, date):
        raise TypeError(f"end must be a date, got {type(end).__name__}")
    if not isinstance(data_dates, np.ndarray) or data_dates.dtype != np.dtype("datetime64[D]"):
        raise TypeError("data_dates must be a datetime64[D] numpy array")
    if data_dates.ndim != 1:
        raise ValueError("data_dates must be 1-D")
    n = int(data_dates.shape[0])
    if bool(np.any(np.isnat(data_dates))):
        raise ValueError("data_dates must not hold NaT")
    lim = _prices("limit", limit, n)
    take = _prices("tp", tp, n)
    stop = _prices("sl", sl, n)
    if not bool(np.all((stop > 0.0) & (stop < lim) & (lim < take))):
        raise ValueError("every row needs 0 < sl < limit < tp")
    names, sym = _symbol_index(symbols, n)

    label = np.full(n, np.nan)
    resolved = np.full(n, np.datetime64("NaT"), dtype="datetime64[D]")
    reason = np.full(n, _UNRESOLVED, dtype=np.int8)
    fill = np.full(n, np.nan)
    exit_ = np.full(n, np.nan)

    end64 = np.datetime64(end, "D")
    sess = (
        np.array(dates.sessions(data_dates.min().item(), end), dtype="datetime64[D]")
        if n
        else np.array([], dtype="datetime64[D]")
    )
    m = int(sess.shape[0])
    if n and m:
        o, hi, lo, gone_from, last_close = _layout(history, names, sess, end64)

        # S1 = next_session(data_date): the first session in sess after data_date; none -> S1 > end.
        j1 = np.searchsorted(sess, data_dates, side="right")
        rows = np.flatnonzero(j1 < m)
        k1, c1 = sym[rows], j1[rows]
        filled = lo[k1, c1] < lim[rows]  # strict; NaN (no bar on S1) compares False
        gone = rows[~filled]
        reason[gone] = _EXPIRE
        label[gone] = 0.0
        resolved[gone] = sess[j1[gone]]
        act = rows[filled]
        open1 = o[sym[act], j1[act]]
        fill[act] = np.where(open1 < lim[act], open1, lim[act])

        t = 1  # session offset after S1; days_held on entering session S1 + t is t
        while act.size:
            col = j1[act] + t
            inside = col < m
            act, col = act[inside], col[inside]
            if not act.size:
                break
            k = sym[act]
            bo, bh, bl = o[k, col], hi[k, col], lo[k, col]
            bar = ~np.isnan(bo)
            s_, t_ = stop[act], take[act]
            price = np.full(act.size, np.nan)
            why = np.full(act.size, _UNRESOLVED, dtype=np.int8)
            for hit, at, code in (
                (bar & (t >= TIME_STOP_DAYS), bo, _TIME),
                (bar & (bo <= s_), bo, _GAP),
                (bar & (bo >= t_), bo, _TP),
                (bar & (bl <= s_), s_, _SL),
                (bar & (bh > t_), t_, _TP),
            ):
                now = hit & (why == _UNRESOLVED)
                price[now] = at[now]
                why[now] = code
            forced = (why == _UNRESOLVED) & (col >= gone_from[k])
            price[forced] = last_close[k][forced]
            why[forced] = _FORCED
            done = why != _UNRESOLVED
            out = act[done]
            reason[out] = why[done]
            exit_[out] = price[done]
            resolved[out] = sess[col[done]]
            act = act[~done]
            t += 1

        traded = reason > _EXPIRE
        label[traded] = exit_[traded] * (1.0 - COST) / (fill[traded] * (1.0 + COST)) - 1.0

    return Labels(
        label=_readonly(label),
        resolved=_readonly(resolved),
        reason=_readonly(reason),
        fill=_readonly(fill),
        exit=_readonly(exit_),
    )
