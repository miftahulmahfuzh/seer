"""M0447 — A curve watch that ends when prices recover, not on a clock.

Source: general knowledge, a variation on M0442 (reserved as an idea row by Sera 20261101-2125).
The inverted-curve signal (Estrella & Mishkin 1996) and SPY's 200-day trend rule are both public
and old (published long before 2015), so no edge is claimed from being early.

M0442's two-year watch saved the 2000-02 and 2008 falls but sat out the 2009-2015 rebound on
every host. Here the watch opens the same way (the first day the 10-year yield is under the
13-week bill) but closes when SPY crosses back above its 200-day average after having been at or
under it, so the book returns when the market itself says the fall is over. Host: M0125's fifty
most heavily traded index members sized by trading value, monthly, fractional, real Gotrade fees.

Episodes: one watch opens on the first inverted day; it cannot open again until the curve has
been un-inverted for 365 days (otherwise it would re-open the day after it closed, as the curve
stays inverted for months). Once open it needs two things to close: SPY at or under its 200-day
average on some day (the dip), then SPY back over it (the recovery). The state is walked forward
over SPY's bars, so each day's reading depends only on bars dated on or before it.

Variants (host x habit; NEVER is the no-opinion control, FIXED730 is M0442's clock):

    * ``DVC10-NEVER`` / ``DVC10-FIXED730``: the 10%-ceiling book, never aside / two-year clock.
    * ``DVC10-RECOVER``: aside until SPY recovers (no cap).
    * ``DVC10-RECOVER-CAP730``: the same, but also closed 730 days after opening.
    * ``SQRT-NEVER`` / ``SQRT-RECOVER``: the square-root book control and recovery arm.

Cash earns nothing; the watch is read at the monthly rebalance only.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0038_yield_curve_watch_gate import inverted_dates, watch_open
from seer_engine.lab.methods.m0125_index_book_volume_weight import VOLWEIGHT, WeightParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 1)

MODES = ("never", "fixed", "recover", "recover_cap")
TREND_N = 200  # SPY's 200-day average, as every lab book uses
REARM_DAYS = 365  # curve un-inverted this long before a new watch can open


@dataclass(frozen=True, slots=True)
class WatchHostParams:
    """M0125's book (``host``) in cash while the ``T10Y - T13W`` watch is open.

    ``fixed``: closes ``watch_days`` after the last inverted day (M0442). ``recover``: closes when SPY
    crosses back over its 200-day average after a dip. ``recover_cap``: that, or ``watch_days`` after
    the watch opened, whichever is first.
    """

    host: WeightParams
    mode: str
    watch_days: int = 730

    def __post_init__(self) -> None:
        if not isinstance(self.host, WeightParams):
            raise TypeError(f"host must be WeightParams, got {type(self.host).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.watch_days, bool) or not isinstance(self.watch_days, int) or self.watch_days < 1:
            raise ValueError(f"watch_days must be an int >= 1, got {self.watch_days!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "watch_days": str(self.watch_days)}
        for k, v in self.host.as_dict().items():
            out[f"host.{k}"] = v
        return out


def _check(params: object) -> WatchHostParams:
    if not isinstance(params, WatchHostParams):
        raise TypeError(f"params must be WatchHostParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class WatchPrepared:
    host: Any  # M0125's FactorPrepared
    inverted: tuple[date, ...]  # dates T10Y < T13W, ascending; empty without series
    has_series: bool
    episodes: tuple[tuple[date, date | None, date | None], ...] = ()  # (opened, recovered, capped)


def recovery_episodes(inverted: tuple[date, ...], spy: Any) -> tuple[tuple[date, date | None, date | None], ...]:
    """Each watch's (opened, recovered, capped-at) dates, walked forward over SPY's bars only.

    A watch opens on an inverted day when armed (no inverted day in the previous ``REARM_DAYS``). It
    is recovered on the first SPY close over its 200-day average that follows a close at or under
    it. ``capped`` is 730 days after opening (the cap arm reads it; the plain arm ignores it).
    """
    if spy is None or len(spy) < TREND_N or not inverted:
        return ()
    close = np.asarray(spy.close, dtype=np.float64)
    csum = np.concatenate(([0.0], np.cumsum(close)))
    dates = [d.astype(object) for d in spy.dates]
    inv = set(inverted)
    last_inv: date | None = None
    out: list[list[date | None]] = []
    cur: list[date | None] | None = None
    dipped = False
    for i, d in enumerate(dates):
        if d in inv:
            armed = last_inv is None or d - last_inv >= timedelta(days=REARM_DAYS)
            if armed and cur is None:
                cur = [d, None, d + timedelta(days=730)]
                out.append(cur)
                dipped = False
            last_inv = d
        if cur is not None and i + 1 >= TREND_N and d != cur[0]:
            sma = (csum[i + 1] - csum[i + 1 - TREND_N]) / TREND_N
            if close[i] <= sma:
                dipped = True
            elif dipped:
                cur[1] = d
                cur = None
    return tuple((o, r, c) for o, r, c in out)  # type: ignore[misc]


def _aside(episodes: tuple[tuple[date, date | None, date | None], ...], data_date: date,
           p: WatchHostParams) -> bool:
    for opened, recovered, _ in episodes:
        if opened > data_date:
            break
        end = recovered
        if p.mode == "recover_cap":
            cap = opened + timedelta(days=p.watch_days)
            end = cap if end is None else min(end, cap)
        if end is None or data_date < end:
            return True
    return False


class WatchedVolumeBookAllocator:
    """M0125's trading-value-weighted fifty, held unless the curve watch is open."""

    id = "M0447"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        return max(VOLWEIGHT.lookback(_check(params).host), TREND_N)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({"SPY", *VOLWEIGHT.symbols(_check(params).host)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return VOLWEIGHT.holds(_check(params).host)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prep: WatchPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: WatchHostParams) -> tuple[Target, ...]:
        if not prep.has_series:  # no series: target nothing (market-aware contract)
            return ()
        if p.mode == "fixed" and watch_open(prep.inverted, data_date, p.watch_days):
            return ()
        if p.mode in ("recover", "recover_cap") and _aside(prep.episodes, data_date, p):
            return ()
        return VOLWEIGHT.targets_prepared(prep.host, members, data_date, held, p.host)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no gate reading and no target."""
        return self._run(WatchPrepared(VOLWEIGHT.prepare(history), (), False), members, data_date,
                         held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> WatchPrepared:
        return WatchPrepared(VOLWEIGHT.prepare(history), (), False)

    def prepare_market(self, market: Any) -> WatchPrepared:
        series = market.series
        has = isinstance(series, MarketSeries) and len(series) > 0
        inv = inverted_dates(series, "T13W") if has else ()
        return WatchPrepared(VOLWEIGHT.prepare(market.history), inv, has,
                             recovery_episodes(inv, market.history.get("SPY")) if has else ())

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, WatchPrepared):
            raise TypeError(f"prepared must be WatchPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


WATCHED = WatchedVolumeBookAllocator()

DVC10 = WeightParams(weighting="dv", cap=0.10)
SQRT = WeightParams(weighting="sqrt")


def _v(suffix: str, host: WeightParams, mode: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0447-{suffix}", family="M0447", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=WATCHED, params=WatchHostParams(host, mode), rationale=rationale,
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0447",
    name="Curve watch that ends when prices recover, not on a clock",
    family="macro-regime-gate",
    source_kind="variation",
    source_ref="M0442",
    parent_id="M0442",
    hypothesis=(
        "M0442 showed the two-year curve watch saves the two big falls but sits out the 2009-2015 "
        "rebound on any host. Keep the same watch opening (10-year yield under 13-week bill, "
        "published 1996) on the trading-value-weighted fifty (M0125's book, fractional shares, "
        "Gotrade fees, monthly) but close it when SPY crosses back above its 200-day average after "
        "having dipped to or under it, instead of after 730 days. Episodes re-arm only after 365 "
        "un-inverted days. Arms: the 10%-ceiling host never aside (no-opinion control), on M0442's "
        "fixed 730-day clock (the clock control), aside until recovery, and aside until recovery "
        "with a 730-day cap; plus the square-root host never aside and aside until recovery. The "
        "never-aside twin prices what acting costs; the fixed twin shows whether the recovery rule "
        "beats the clock. Screens: max drawdown <= 15% where the lab applies it, profit factor >= "
        "1.3, >= 100 trades, DSR >= 0.90 at the lab's N, a majority of 4 folds. Both signals are "
        "old and public, so no edge from being early is claimed. Assumed: cash earns nothing; the "
        "watch is read at the monthly rebalance; the dev window holds only a few inversions "
        "(1998, 2000, 2006-07). Success: a 2009-2015 lead over SPY with the 2000-02 and 2008 "
        "saves kept and a majority of folds."
    ),
    expected_failure=(
        "Price recovery signals fire inside bear-market rallies (2001, 2002, late 2008 bounces) "
        "and re-expose the book early, giving back the saves, so the recovery arm lands near the "
        "never-aside book in the falls and near the clock arm in the rebound: no better than "
        "either. With three or four episodes in twenty years the fold record is thin and the luck "
        "bar of 0.90 is not cleared."
    ),
    candidates=(
        _v("DVC10-NEVER", DVC10, "never", "Control: the 10%-ceiling trading-value book, never stepping aside"),
        _v("DVC10-FIXED730", DVC10, "fixed", "Clock control: M0442's two-year curve watch"),
        _v("DVC10-RECOVER", DVC10, "recover",
           "Treatment: in cash from the first inverted day until SPY recovers over its 200-day average"),
        _v("DVC10-RECOVER-CAP730", DVC10, "recover_cap",
           "Treatment with a backstop: recovery close, or 730 days after opening"),
        _v("SQRT-NEVER", SQRT, "never", "Control: the square-root trading-value book, never stepping aside"),
        _v("SQRT-RECOVER", SQRT, "recover",
           "Treatment: the square-root book in cash until SPY recovers over its 200-day average"),
    ),
    seen_keys=(
        "concept:yield-curve-watch-price-recovery-close",
        "concept:yield-curve-watch-size-weighted-host",
        "concept:yield-curve-gate",
        "concept:recovery-based-exit",
    ),
)
