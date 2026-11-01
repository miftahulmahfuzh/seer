"""M0442 — The two-year curve watch on a book that did not lag SPY after 2009.

Source: general knowledge, a variation on M0339 (whose analysis queued "run the same watch on a
host that held up after 2009"). Reserved as an idea row by Sera 20261101-1447. The inverted-curve
signal (Estrella & Mishkin 1996) and size weighting are both public through the whole dev window.

M0339 showed that paying the watch's cash interest changes nothing in 2009-2015, so that era's
shortfall comes from the picks and the rebound the watch sits out. Every curve-watch book so far
sat on the big-dividend-raise picks, which lagged SPY after 2009. Here the same watch (M0038's
two-year clock on the first day T10Y < T13W) wraps M0125's book of the fifty most heavily traded
index members, sized by trading value. Measured with ``lab timing`` on M0125's recorded trials
(deposits removed), the host's lead in 2009-2015 was +1.93 pts/yr for the 10%-ceiling version and
+0.46 for the square-root version, while the equal-weight one lagged -0.45. The 10%-ceiling host
also fell 72% through 2000-02 and 2008, which is what a watch is supposed to cut.

Variants (host x habit, so the cost of acting is priced, as the 2x2 rule asks):

    * ``DVC10-NEVER`` / ``DVC10-FIXED730``: the 10%-ceiling trading-value book, never aside / watched.
    * ``SQRT-NEVER`` / ``SQRT-FIXED730``: the square-root book, never aside / watched.

The NEVER arms are M0125's own books under a new allocator id, the no-opinion controls. The watch
is read at the host's monthly rebalance only (the preset has no weekly resize), so it can lag a
new inversion by up to a month; cash earns nothing, as in M0336.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0038_yield_curve_watch_gate import inverted_dates, watch_open
from seer_engine.lab.methods.m0125_index_book_volume_weight import VOLWEIGHT, WeightParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 1)

MODES = ("never", "fixed")


@dataclass(frozen=True, slots=True)
class WatchHostParams:
    """M0125's book (``host``) in cash while the ``T10Y - T13W`` watch is open (mode ``fixed``)."""

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


class WatchedVolumeBookAllocator:
    """M0125's trading-value-weighted fifty, held unless the curve watch is open."""

    id = "M0442"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        return VOLWEIGHT.lookback(_check(params).host)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return VOLWEIGHT.symbols(_check(params).host)

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
        return WatchPrepared(VOLWEIGHT.prepare(market.history), inv, has)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, WatchPrepared):
            raise TypeError(f"prepared must be WatchPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


WATCHED = WatchedVolumeBookAllocator()

DVC10 = WeightParams(weighting="dv", cap=0.10)
SQRT = WeightParams(weighting="sqrt")


def _v(suffix: str, host: WeightParams, mode: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0442-{suffix}", family="M0442", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=WATCHED, params=WatchHostParams(host, mode), rationale=rationale,
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0442",
    name="Curve watch on a book that holds up after 2009",
    family="macro-regime-gate",
    source_kind="variation",
    source_ref="M0339",
    parent_id="M0339",
    hypothesis=(
        "M0339 showed that interest on the watch's cash fixes nothing in 2009-2015, so that era's "
        "shortfall to SPY comes from the picks and the rebound the watch sits out. Every curve-watch "
        "book so far held the big-dividend-raise picks, which lagged SPY after 2009. Run the same "
        "two-year curve watch (M0038's clock: the first day the 10-year yield is under the 13-week "
        "bill opens it, 730 days after the last inverted day closes it) on M0125's fifty most heavily "
        "traded index members sized by trading value, at fractional Gotrade fees, monthly. Two hosts: "
        "the 10%-ceiling trading-value book (+1.93 pts a year over SPY in 2009-2015, deposits removed, "
        "by lab timing on M0125-DV-C10, but a 72% fall) and the square-root book (+0.46). Each has its "
        "never-steps-aside twin beside it so the cost of acting is priced. Both the inverted-curve "
        "signal (1996) and size weighting are public and old, so no edge is claimed from being early. "
        "Assumed: cash earns nothing; the watch is read at the monthly rebalance, so it can lag a new "
        "inversion by up to a month; the dev window holds only two inversion-led falls (2000-02, "
        "2008). Success: a watch book that beats SPY in 2009-2015 as well as in the 2001 and 2008 "
        "falls, with a worst fall under the screen."
    ),
    expected_failure=(
        "The host books that held up after 2009 are themselves close to SPY, so the watch adds a "
        "premium in the two falls and costs the same 2009 rebound it cost every earlier host: the "
        "watched book lands between its never-aside twin and cash in 2009-2015 and loses the lead "
        "that made the host attractive. With two warnings in twenty years the fold record is about "
        "2-3 of 4, and the luck bar of 0.90 at this N is not cleared."
    ),
    candidates=(
        _v("DVC10-NEVER", DVC10, "never",
           "Control: the 10%-ceiling trading-value book, never stepping aside"),
        _v("DVC10-FIXED730", DVC10, "fixed",
           "Treatment: the same book in cash while the two-year curve watch is open"),
        _v("SQRT-NEVER", SQRT, "never",
           "Control: the square-root trading-value book, never stepping aside"),
        _v("SQRT-FIXED730", SQRT, "fixed",
           "Treatment: the square-root book in cash while the two-year curve watch is open"),
    ),
    seen_keys=(
        "concept:yield-curve-watch-size-weighted-host",
        "concept:yield-curve-gate",
        "concept:size-weighted-index-book",
        "concept:macro-regime-gate",
    ),
)
