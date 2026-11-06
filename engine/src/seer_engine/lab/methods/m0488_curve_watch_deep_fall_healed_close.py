"""M0488 — A curve watch that ends only after a deep fall has healed.

Source: general knowledge, a variation on M0447 (reserved as an idea row by Sera 20261106-1411).
The inverted-curve signal (Estrella & Mishkin 1996) and SPY's 200-day trend rule are both public
and old (published long before 2015), so no edge is claimed from being early.

M0447's recovery close fired within days of opening: the curve inverts while SPY is still near its
highs, so the "dip under the 200-day average, then back over it" happened in ordinary chop and no
monthly rebalance ever landed inside a watch. Here the watch opens the same way (the first armed
day the 10-year yield is under the 13-week bill) but recovery only starts to count once the market
has actually fallen: SPY's close at least ``fall`` below its own 252-day closing high while the
watch is open. After that, the watch closes on the day SPY has closed above its 200-day average
for ``heal_days`` sessions in a row. Host: M0125's fifty most heavily traded index members sized by
trading value with a 10% ceiling, monthly, fractional, real Gotrade fees.

Episodes re-arm as in M0447 (no inverted day in the previous 365 days). Everything is walked
forward over SPY's bars, so each day's reading depends only on bars dated on or before it.

Variants (NEVER is the no-opinion control, FIXED730 is M0442's clock):

    * ``DVC10-NEVER`` / ``DVC10-FIXED730``: never aside / the two-year clock.
    * ``DVC10-DEEP15``: the treatment: a 15% fall, then 21 sessions over the 200-day average.
    * ``DVC10-DEEP15-NOFALL730``: the same, but a watch that sees no 15% fall within 730 days of
      opening closes then (the backstop for a warning the market never acts on).
    * ``DVC10-DEEP10`` / ``DVC10-DEEP20``: the fall threshold at 10% and 20%, as sensitivity.

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

ADDED = date(2026, 11, 6)

MODES = ("never", "fixed", "deep", "deep_nofall")
TREND_N = 200  # SPY's 200-day average, as every lab book uses
HIGH_N = 252  # the fall is measured from SPY's 252-session closing high
REARM_DAYS = 365  # curve un-inverted this long before a new watch can open


@dataclass(frozen=True, slots=True)
class DeepWatchParams:
    """M0125's book (``host``) in cash while the ``T10Y - T13W`` watch is open.

    ``fixed``: closes ``watch_days`` after the last inverted day (M0442). ``deep``: closes once SPY
    has fallen ``fall`` below its 252-session high during the watch and then closed over its 200-day
    average ``heal_days`` sessions in a row. ``deep_nofall``: that, or ``watch_days`` after opening
    if no such fall has happened by then.
    """

    host: WeightParams
    mode: str
    fall: float = 0.15
    heal_days: int = 21
    watch_days: int = 730

    def __post_init__(self) -> None:
        if not isinstance(self.host, WeightParams):
            raise TypeError(f"host must be WeightParams, got {type(self.host).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if not isinstance(self.fall, float) or not 0.0 < self.fall < 1.0:
            raise ValueError(f"fall must be a float in (0, 1), got {self.fall!r}")
        for name in ("heal_days", "watch_days"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{name} must be an int >= 1, got {v!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "fall": str(self.fall), "heal_days": str(self.heal_days),
               "watch_days": str(self.watch_days)}
        for k, v in self.host.as_dict().items():
            out[f"host.{k}"] = v
        return out


def _check(params: object) -> DeepWatchParams:
    if not isinstance(params, DeepWatchParams):
        raise TypeError(f"params must be DeepWatchParams, got {type(params).__name__}")
    return params


Episode = tuple[date, date | None, date | None]  # (opened, deep fall seen, healed)


@dataclass(frozen=True, slots=True, eq=False)
class DeepPrepared:
    host: Any  # M0125's FactorPrepared
    inverted: tuple[date, ...]  # dates T10Y < T13W, ascending; empty without series
    has_series: bool
    spy: Any = None  # SPY's History, for the per-variant episode walk


def deep_episodes(inverted: tuple[date, ...], spy: Any, fall: float, heal_days: int) -> tuple[Episode, ...]:
    """Each watch's (opened, fell, healed) dates, walked forward over SPY's bars only.

    A watch opens on an inverted day when armed (no inverted day in the previous ``REARM_DAYS``). It
    records ``fell`` on the first later close at least ``fall`` under the highest close of the last
    ``HIGH_N`` sessions, and ``healed`` on the first close after that which completes ``heal_days``
    consecutive closes over the 200-day average (the run may start before the fall day only if it is
    unbroken through it; counting starts fresh at the fall).
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
    run = 0
    for i, d in enumerate(dates):
        if d in inv:
            armed = last_inv is None or d - last_inv >= timedelta(days=REARM_DAYS)
            if armed and cur is None:
                cur = [d, None, None]
                out.append(cur)
            last_inv = d
        if cur is None or d == cur[0] or i + 1 < TREND_N:
            continue
        if cur[1] is None:
            high = float(close[max(0, i + 1 - HIGH_N): i + 1].max())
            if close[i] <= high * (1.0 - fall):
                cur[1] = d
                run = 0
            continue
        sma = (csum[i + 1] - csum[i + 1 - TREND_N]) / TREND_N
        run = run + 1 if close[i] > sma else 0
        if run >= heal_days:
            cur[2] = d
            cur = None
    return tuple((o, f, h) for o, f, h in out)  # type: ignore[misc]


def _aside(episodes: tuple[Episode, ...], data_date: date, p: DeepWatchParams) -> bool:
    for opened, fell, healed in episodes:
        if opened > data_date:
            break
        end = healed
        if p.mode == "deep_nofall":
            cap = opened + timedelta(days=p.watch_days)
            if fell is None or fell >= cap:
                end = cap
        if end is None or data_date < end:
            return True
    return False


class DeepWatchAllocator:
    """M0125's trading-value-weighted fifty, held unless the deep-fall curve watch is open."""

    id = "M0488"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        return max(VOLWEIGHT.lookback(_check(params).host), HIGH_N)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({"SPY", *VOLWEIGHT.symbols(_check(params).host)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return VOLWEIGHT.holds(_check(params).host)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prep: DeepPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: DeepWatchParams) -> tuple[Target, ...]:
        if not prep.has_series:  # no series: target nothing (market-aware contract)
            return ()
        if p.mode == "fixed" and watch_open(prep.inverted, data_date, p.watch_days):
            return ()
        if p.mode in ("deep", "deep_nofall"):
            eps = deep_episodes(prep.inverted, prep.spy, p.fall, p.heal_days)
            if _aside(eps, data_date, p):
                return ()
        return VOLWEIGHT.targets_prepared(prep.host, members, data_date, held, p.host)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no gate reading and no target."""
        return self._run(DeepPrepared(VOLWEIGHT.prepare(history), (), False), members, data_date,
                         held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> DeepPrepared:
        return DeepPrepared(VOLWEIGHT.prepare(history), (), False)

    def prepare_market(self, market: Any) -> DeepPrepared:
        series = market.series
        has = isinstance(series, MarketSeries) and len(series) > 0
        inv = inverted_dates(series, "T13W") if has else ()
        return DeepPrepared(VOLWEIGHT.prepare(market.history), inv, has, market.history.get("SPY"))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, DeepPrepared):
            raise TypeError(f"prepared must be DeepPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


DEEP_WATCH = DeepWatchAllocator()

DVC10 = WeightParams(weighting="dv", cap=0.10)


def _v(suffix: str, params: DeepWatchParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0488-{suffix}", family="M0488", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DEEP_WATCH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0488",
    name="Curve watch that ends only after a deep fall has healed",
    family="macro-regime-gate",
    source_kind="variation",
    source_ref="M0447",
    parent_id="M0447",
    hypothesis=(
        "M0447's recovery close fired within days because yield curves invert while SPY is still "
        "near its highs, so the book never left the market. Keep the same watch opening (10-year "
        "yield under the 13-week bill, published 1996; re-arm after 365 un-inverted days) on the "
        "trading-value fifty with a 10% ceiling (M0125's book, fractional shares, Gotrade fees, "
        "monthly), but count recovery only after SPY has closed at least 15% below its 252-session "
        "closing high while the watch is open, then close the watch once SPY has closed above its "
        "200-day average 21 sessions in a row. Arms: never aside (the no-opinion control), M0442's "
        "two-year clock (the clock control), the 15% treatment, the 15% treatment with a backstop "
        "that closes a watch which saw no 15% fall within 730 days of opening, and the fall "
        "threshold at 10% and 20% as sensitivity. Screens as the lab applies them: the dev max "
        "drawdown screen, profit factor >= 1.3, >= 100 trades, DSR >= 0.90 at the lab's N, a "
        "majority of 4 walk-forward folds. Both signals are old and public, so no edge from being "
        "early is claimed. Assumed: cash earns nothing; the watch is read at the monthly rebalance "
        "only; the dev window holds only a few inversions (around 1998, 2000 and 2006-07), so "
        "every arm's record rests on two or three episodes. Success: a 2009-2015 lead over SPY "
        "with the 2000-02 and 2008 saves kept and a majority of folds."
    ),
    expected_failure=(
        "The deep-fall trigger needs a fall the 2009-2015 window never had, so that era is decided "
        "by when the 2008 watch healed: if the 21-session heal lands in mid-2009 the book behaves "
        "like the two-year clock (and inherits its 2 of 4 folds), and a heal any later loses more "
        "of the rebound. A watch that never sees its fall (1998 if it opened, or a 20% threshold) "
        "stays in cash indefinitely without the backstop. Bear-market rallies (2001, 2002) can "
        "complete a 21-session heal and re-expose the book early. With so few episodes the fold "
        "record is thin and the 0.90 luck bar may not be cleared."
    ),
    candidates=(
        _v("DVC10-NEVER", DeepWatchParams(DVC10, "never"),
           "Control: the 10%-ceiling trading-value book, never stepping aside"),
        _v("DVC10-FIXED730", DeepWatchParams(DVC10, "fixed"),
           "Clock control: M0442's two-year curve watch"),
        _v("DVC10-DEEP15", DeepWatchParams(DVC10, "deep"),
           "Treatment: in cash from the inverted day until a 15% fall has healed for 21 sessions"),
        _v("DVC10-DEEP15-NOFALL730", DeepWatchParams(DVC10, "deep_nofall"),
           "Treatment with a backstop: closes at 730 days if the 15% fall never came"),
        _v("DVC10-DEEP10", DeepWatchParams(DVC10, "deep", fall=0.10),
           "Sensitivity: a 10% fall is enough to start counting recovery"),
        _v("DVC10-DEEP20", DeepWatchParams(DVC10, "deep", fall=0.20),
           "Sensitivity: only a 20% fall (a bear market) starts the recovery count"),
    ),
    seen_keys=(
        "concept:yield-curve-watch-deep-fall-healed-close",
        "concept:yield-curve-watch-price-recovery-close",
        "concept:yield-curve-gate",
    ),
)
