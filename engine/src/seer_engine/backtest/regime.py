"""Market breadth as a regime label, and a recorded result split by it.

**Why this exists.** Every lab method is chosen on one twenty-year average, and an average hides a
regime. M0007's own dev analysis measured the hole and filed it as a virtue: residual momentum
"deliberately refuses" to ride the high-beta names that lead a narrow melt-up, which cost it
1999-2000 and nothing else across 1996-2015 -- two years in twenty, easy to average away. In the
2015-2026 test window that regime was three years in eight, and it took 91% of the shortfall
against SPY. Four of four test-window looks have now failed on ``beats SPY TR``.

So the question an average cannot answer is: *in which market does this method work, and how often
is that market?* This module answers it.

**Breadth, defined.** For each calendar month: the cap-weighted index's return minus the
equal-weighted mean return of the index's own members that month. Positive means the index beat
the typical member -- a few large names carried it, which is a **narrow** month. Negative or zero
means the typical member kept up or did better: a **broad** month. Nothing is fitted and there is
no parameter to tune; it is one subtraction, and both halves come from bars the store already has.

**Point in time.** Members come from ``Membership.members_on`` at the month's start, so a month is
scored on the index as it stood then, never on who turned out to be in it later.

**It re-runs nothing.** A recorded trial carries its monthly equity curve (``trials.curve_json``),
so every method the lab has ever run can be split by regime from the database alone. No backtest,
no trial row, no look. This is a report in the sense ``lab costs`` is a report.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from seer_engine.backtest.market import Market

NARROW = "narrow"
BROAD = "broad"
REGIMES: tuple[str, ...] = (NARROW, BROAD)
SPY = "SPY"
MIN_MEMBERS = 30  # below this an equal-weighted mean is noise, and the month is not labelled
BENCH_CANDIDATE = "REF-SPY-HOLD"  # the lab's recorded SPY buy-and-hold curve, the panel's yardstick


def read(gaps: Mapping[str, float]) -> str:
    """The two gaps in plain words, because the shape matters more than either number.

    The dangerous shape is "pays only in broad": it looks like skill on a window where broad
    months happened to dominate, and it is a bet on breadth that nobody wrote down.
    """
    n, b = gaps.get(NARROW), gaps.get(BROAD)
    if n is None or b is None:
        return "not enough months"
    if n > 0 and b > 0:
        return "pays in both"
    if n <= 0 and b <= 0:
        return "pays in neither"
    if b > 0:
        return "pays only in broad"
    return "pays only in narrow"



@dataclass(frozen=True, slots=True)
class Span:
    """One regime's slice of a monthly curve."""

    regime: str
    months: int
    total_return: float | None  # compounded across this regime's months only
    annualised: float | None  # the same, raised to 12/months

    @property
    def years(self) -> float:
        return self.months / 12.0


def _closes_at(market: Market, symbol: str, when: Sequence[date]) -> np.ndarray:
    """``symbol``'s last close on or before each date in ``when``; NaN where it has no bar yet."""
    h = market.history.get(symbol)
    out = np.full(len(when), np.nan)
    if h is None or len(h) == 0:
        return out
    idx = np.searchsorted(h.dates, np.array(when, dtype="datetime64[D]"), side="right") - 1
    ok = idx >= 0
    out[ok] = h.close[idx[ok]]
    return out


def month_ends(curve: Sequence[tuple[date, float]]) -> tuple[date, ...]:
    """The dates of ``curve``, which a recorded lab curve already samples one per month."""
    return tuple(d for d, _v in curve)


def breadth(market: Market, when: Sequence[date]) -> dict[date, float]:
    """Index return minus the equal-weighted mean member return, for each step of ``when``.

    ``when`` are consecutive month-end dates; the value at ``when[i]`` describes the move from
    ``when[i-1]`` to ``when[i]``, so ``when[0]`` is never labelled. A month with fewer than
    ``MIN_MEMBERS`` priced members is left out rather than guessed at.
    """
    when = list(when)
    if len(when) < 2:
        return {}
    spy = _closes_at(market, SPY, when)
    symbols = sorted(s for s in market.history if s != SPY)
    closes = {s: _closes_at(market, s, when) for s in symbols}
    out: dict[date, float] = {}
    for i in range(1, len(when)):
        if not (np.isfinite(spy[i]) and np.isfinite(spy[i - 1]) and spy[i - 1] > 0):
            continue
        members = market.membership.members_on(when[i - 1])
        rs = [
            closes[s][i] / closes[s][i - 1] - 1.0
            for s in symbols
            if s in members
            and np.isfinite(closes[s][i])
            and np.isfinite(closes[s][i - 1])
            and closes[s][i - 1] > 0
        ]
        if len(rs) < MIN_MEMBERS:
            continue
        out[when[i]] = float(spy[i] / spy[i - 1] - 1.0) - float(np.mean(rs))
    return out


PERSIST_MONTHS = 36  # three years: long enough that one melt-up month cannot set the label


def persistence(spread: Mapping[date, float], months: int = PERSIST_MONTHS) -> list[tuple[date, float]]:
    """The trailing mean spread over ``months``, per month end. The measure that actually works.

    **Why not the month-by-month label.** ``labels`` splits months by the sign of the spread, and
    measured that way the dev window is 41% narrow and the 2023-2026 stretch 54% -- close enough
    that every recorded method reads "pays in both" and nothing is flagged. The month labels do
    not discriminate, and a panel built only on them would have cleared M0007 exactly as the old
    gate did.

    What separates the two eras is not how narrow a month gets but how long narrowness *lasts*.
    The extremes are the same: the twelve narrowest dev months run +2.1% to +5.2%, the twelve
    narrowest of 2023-2026 run +2.0% to +4.5%. The mean is what moved -- dev -0.66% a month,
    2023-2026 +0.60% -- because the broad months that used to pay the equal-weighted book back
    stopped coming.

    Measured on one store so the member coverage is constant (the test store, 1993-2026), the
    trailing three-year mean peaked at +0.68% a month in December 2025, above the dot-com peak of
    +0.53%, and stayed positive essentially unbroken from late 2023. Over the dev window it cleared
    +0.17% once, around 2008, in 6 of 202 windows.

    A sustained positive value is a standing headwind for any equal-weighted or beta-stripped
    book: at +0.5% a month it is six points a year, every year, with no broad spell to recover in.
    """
    if months < 2:
        raise ValueError(f"months must be at least 2, got {months}")
    days = sorted(spread)
    out: list[tuple[date, float]] = []
    for i in range(months - 1, len(days)):
        window = [spread[d] for d in days[i - months + 1 : i + 1]]
        out.append((days[i], float(np.mean(window))))
    return out


def headwind(spread: Mapping[date, float], months: int = PERSIST_MONTHS) -> float | None:
    """The most recent trailing mean spread, or None when there is not enough history."""
    runs = persistence(spread, months)
    return runs[-1][1] if runs else None


def labels(spread: Mapping[date, float]) -> dict[date, str]:
    """``NARROW`` where the index beat the typical member that month, ``BROAD`` otherwise."""
    return {d: (NARROW if v > 0 else BROAD) for d, v in spread.items()}


def bucket(curve: Sequence[tuple[date, float]], credited: Mapping[date, float]) -> dict[date, float]:
    """Deposits credited inside each curve step, keyed by the step's end date.

    A deposit landing in ``(curve[i-1].date, curve[i].date]`` belongs to step ``i``; a deposit on
    or before the first point belongs to the opening balance and is dropped, because it is already
    in ``curve[0]`` rather than being growth over it.
    """
    out: dict[date, float] = {}
    for i in range(1, len(curve)):
        lo, hi = curve[i - 1][0], curve[i][0]
        got = sum(a for d, a in credited.items() if lo < d <= hi)
        if got:
            out[hi] = float(got)
    return out


def split(
    curve: Sequence[tuple[date, float]],
    label: Mapping[date, str],
    deposits: Mapping[date, float] | None = None,
) -> dict[str, Span]:
    """``curve``'s compounded return inside each regime's months.

    The months of one regime are chained as if the other months had not happened, which is the
    only honest way to ask "what does this method do in this weather": it is not a tradable
    result, it is a description of where the return came from.

    ``deposits`` is what a funded run received inside each step (``bucket``), and it is **not
    optional for a funded trial**. A funded curve rises because money arrived as well as because
    the book earned, so slicing it raw counts the owner's own deposits as growth -- and then
    compares that against a benchmark curve which received none. Measured on the lab's own record
    that is not a rounding error: a funded dev trial records ``cagr`` 0.376 beside an ``mwr`` of
    0.137, and the batch of 2026-10-09 read as beating the market by seventy to eighty points a
    year in the early era, which was 148,000 dollars of the owner's money counted as profit on one
    side of a comparison and not the other. With ``deposits`` each step's return is measured on
    what the book did with the money it already had: ``(value - deposit) / previous``.
    """
    dep = deposits or {}
    by: dict[str, list[float]] = {r: [] for r in REGIMES}
    for i in range(1, len(curve)):
        d, v = curve[i]
        prev = curve[i - 1][1]
        r = label.get(d)
        if r is None or prev <= 0:
            continue
        by[r].append((v - dep.get(d, 0.0)) / prev - 1.0)
    out: dict[str, Span] = {}
    for r, rs in by.items():
        if not rs:
            out[r] = Span(r, 0, None, None)
            continue
        total = float(np.prod([1.0 + x for x in rs]) - 1.0)
        ann = float((1.0 + total) ** (12.0 / len(rs)) - 1.0) if len(rs) else None
        out[r] = Span(r, len(rs), total, ann)
    return out


def panel(
    curve: Sequence[tuple[date, float]],
    bench: Sequence[tuple[date, float]],
    label: Mapping[date, str],
    deposits: Mapping[date, float] | None = None,
) -> dict[str, tuple[Span, Span, float | None]]:
    """Per regime: ``(the method's span, the benchmark's span, the method minus the benchmark)``.

    The third element is what the panel exists for. A method that beats the benchmark in broad
    months and loses in narrow ones is not a good method with bad luck; it is a bet on breadth,
    and the only question left is how often each weather comes.
    """
    mine, theirs = split(curve, label, deposits), split(bench, label)
    out: dict[str, tuple[Span, Span, float | None]] = {}
    for r in REGIMES:
        a, b = mine[r], theirs[r]
        gap = None if a.annualised is None or b.annualised is None else a.annualised - b.annualised
        out[r] = (a, b, gap)
    return out
