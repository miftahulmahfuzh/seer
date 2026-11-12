"""M0497 — Big index members ranked by share turnover behind the switch: lightly traded vs heavily.

Source: variation of M0491 (family stock-liquid-leaders-switch); reserved by Sera batch
20261112-1535. Lee and Swaminathan (2000, published, so expect fading after it) found heavily
turned-over "glamour" stocks lag and lightly turned-over ones lead. M0491 found the 20 most
traded big members (ranked by raw dollar volume) lagged all three blind draws and SPY behind the
switch; share turnover is a different ranking of the same screened pool -- volume scaled by the
company's own share count, not by its dollar size -- and was never tested there.

Why it exists. "Most traded" in M0491 says nothing about how much of a company changes hands: a
giant with $50M of daily volume on five billion shares turns over far slower than a mid-cap with
$25M of volume on two hundred million shares. Share turnover (60-day mean volume divided by
point-in-time shares outstanding) is the ratio the published anomaly is actually about. This
method ranks the same F4-screened pool on that ratio instead of on raw dollar volume, holds the
twenty least turned-over names and, as the mirror, the twenty most turned-over, both equal
weight, monthly, behind the same SPY 200-day switch.

The arms, all on ``monthly-hold-frac-gotrade`` (fractional shares, Gotrade's real fees, asked
monthly), all behind ``trend=("SPY", 200)``:

* ``LOW-SW``: F4's screen (20-day mean close x volume over $20M, close at least $5, 253 bars of
  history), ranked by 60-day mean volume / point-in-time shares outstanding ascending (least
  turned over first), the 20 lowest, equal slots. Unsized names (no filed share count on the
  decision date) are skipped, same as M0491's cap arm.
* ``HIGH-SW``: the mirror -- the same screen and ratio, the 20 **most** turned-over names, equal
  slots. Lee and Swaminathan's "glamour" side.
* ``DRAW1-SW``, ``DRAW2-SW``, ``DRAW3-SW``: the blind control, matched against ``LOW-SW``'s own
  churn (``control_draw.matched_book``, rule matched-draw-v1): each month it counts how many names
  ``LOW-SW``'s ranking enters, keeps all but that many of its own names in a date-free hash order
  and draws the rest in a month-keyed hash order, from the same F4-screened pool (unsized names
  included -- the draw does not need a share count to be drawn). Equal slots. Three seeds because
  one draw is not a control (insight on M0440: nineteen draws span 7.5 pts/yr).
* ``SPY-SW``: Control: SPY itself, 100%, behind the SPY 200-day switch -- the same book as
  M0491-SPY-SW, repeated verbatim because it is the cleanest "is it the ranking or the switch"
  yardstick and the lab already recorded it. Not a new result; its money is M0491-SPY-SW's.

Assumptions written before any result. Six arms is the pre-registration cap (``MAX_VARIANTS``), so
the always-invested twin of ``LOW-SW`` (``trend=None``, to separate the ranking from the switch
the way M0490's control did for M0491) is not registered here; it is queued as this method's own
follow-up idea instead. The draw arms are matched to ``LOW-SW`` specifically, not to ``HIGH-SW``:
both share the same F4-screened pool and the same switch, so one matched control prices the cost
of acting on either ranking. GOOG/GOOGL before 2014 can appear in both ``LOW-SW`` and ``HIGH-SW``
and the draws (no one-class-per-company dedupe), exactly as M0491's equal-weight arm: only a
size-weighted book needs that dedupe, and this method holds no size-weighted arm.

Market-aware (``market_fields = ("shares",)``): ``lab run`` refuses it on a store without share
counts, and by the lab's contract for market-aware allocators every arm targets nothing on the
history-only path, so all six arms always run on the same store and the same code path.
Pure: reads only bars and share counts dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Amendment, Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 12)
ARMS = ("low", "high", "draw", "spy")
DRAW_TAG = "M0497"
TURNOVER_N = 60  # bars of volume averaged for the turnover ratio


@dataclass(frozen=True, slots=True)
class TurnoverParams:
    """``arm`` low / high / draw / spy; ``top`` names held; ``seed`` the draw's hash seed (draw
    arm only); ``trend`` the switch, set by every arm."""

    arm: str
    top: int = 20
    seed: int = 0
    trend: tuple[str, int] | None = ("SPY", 200)

    def __post_init__(self) -> None:
        if self.arm not in ARMS:
            raise ValueError(f"arm must be one of {ARMS}, got {self.arm!r}")
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 100:
            raise ValueError(f"top must be an int in [1, 100], got {self.top!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if (self.seed != 0) != (self.arm == "draw"):
            raise ValueError("seed is set on the draw arm and only there")
        self.inner  # validates the switch

    @property
    def inner(self) -> FactorParams:
        """F4's screen and switch; the ranking that follows uses share turnover, not this rank."""
        return FactorParams(rank="momentum", top=self.top, trend=self.trend)

    def as_dict(self) -> dict[str, str]:
        return {"arm": self.arm, "top": str(self.top), "seed": str(self.seed),
                "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
                "rank": f"share-turnover-{TURNOVER_N}d"}


def _check(params: object) -> TurnoverParams:
    if not isinstance(params, TurnoverParams):
        raise TypeError(f"params must be TurnoverParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class TurnoverPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared | None  # None on the plain history path: rows are computed directly
    market: Any  # the Market (share counts), or None when there is none


def _rows(prep: TurnoverPrepared, members: AbstractSet[str], d: date, p: TurnoverParams) -> list[FactorRow]:
    if prep.factor is not None:
        return prep.factor.rows_on(members, d, p.inner)
    return factor_rows(prep.history, members, d, p.inner)


def _turnover(prep: TurnoverPrepared, rows: list[FactorRow], d: date) -> list[tuple[str, float, float]]:
    """``(symbol, close, turnover)`` for every row with a known share count: 60-day mean volume /
    point-in-time shares outstanding. Skips a row with no filed share count on ``d``."""
    mk = prep.market
    if mk is None:
        return []
    out: list[tuple[str, float, float]] = []
    for r in rows:
        h = prep.history.get(r.symbol)
        if h is None:
            continue
        i = h.index_of(d)
        if i is None or i + 1 < TURNOVER_N:
            continue
        shares = mk.shares_on(r.symbol, d)
        if shares is None or not (np.isfinite(shares) and shares > 0.0):
            continue
        vol60 = float(np.mean(h.volume[i + 1 - TURNOVER_N : i + 1]))
        if not np.isfinite(vol60) or vol60 < 0.0:
            continue
        out.append((r.symbol, r.close, vol60 / float(shares)))
    return out


def least_turned(rows: list[tuple[str, float, float]], top: int) -> list[tuple[str, float, float]]:
    """Lightly traded first, ties by symbol."""
    return sorted(rows, key=lambda x: (x[2], x[0]))[:top]


def most_turned(rows: list[tuple[str, float, float]], top: int) -> list[tuple[str, float, float]]:
    """Heavily traded first (the mirror), ties by symbol."""
    return sorted(rows, key=lambda x: (-x[2], x[0]))[:top]


def _run(prep: TurnoverPrepared, members: AbstractSet[str], d: date, held: frozenset[str],
         p: TurnoverParams) -> tuple[Target, ...]:
    if prep.market is None:  # the lab's market-aware contract: no panel, no targets, on every arm
        return ()
    if not trend_on(prep.history, d, p.inner):
        return ()
    if p.arm == "spy":
        t = target_from_close("SPY", last_close(prep.history.get("SPY"), d), equal_weight(1))
        return () if t is None else (t,)
    rows = _rows(prep, members, d, p)
    if not rows:
        return ()
    w = equal_weight(p.top)
    picks: list[tuple[str, float]]
    if p.arm == "low":
        picks = [(s, c) for s, c, _ in least_turned(_turnover(prep, rows, d), p.top)]
    elif p.arm == "high":
        picks = [(s, c) for s, c, _ in most_turned(_turnover(prep, rows, d), p.top)]
    else:
        close = {r.symbol: r.close for r in rows}

        def select(at: date) -> tuple[list[str], list[str]]:
            pool = rows if at == d else _rows(prep, members, at, p)
            turnover = _turnover(prep, pool, at)
            return [r.symbol for r in pool], [s for s, _, _ in least_turned(turnover, p.top)]

        names = control_draw.matched_book(select, d, held, tag=DRAW_TAG, seed=p.seed)
        picks = [(s, close[s]) for s in names if s in close]
    out: list[Target] = []
    for s, c in picks:
        t = target_from_close(s, c, w)
        if t is not None:
            out.append(t)
    return tuple(out)


class ShareTurnoverAllocator:
    """Big index members ranked by 60-day volume / point-in-time shares outstanding: the 20 least
    turned-over, the 20 most (mirror), a matched blind draw against the low-turnover ranking, or
    SPY itself; all cash while SPY closes at or below its 200-day average. Held names are not
    consulted except by the draw, which keeps its own names."""

    id = "M0497"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        inner = max(factor_lookback(p.inner), TURNOVER_N)
        return control_draw.lookback_for(inner) if p.arm == "draw" else inner

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return ("SPY",) if _check(params).arm == "spy" else ()

    def uses_members(self, params: Any) -> bool:
        return _check(params).arm != "spy"

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no arm targets anything (the contract)."""
        return _run(TurnoverPrepared(history, None, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> TurnoverPrepared:
        return TurnoverPrepared(history, None, None)

    def prepare_market(self, market: Any) -> TurnoverPrepared:
        sized = len(market.shares) > 0
        return TurnoverPrepared(market.history, prepare_factor(market.history), market if sized else None)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TurnoverPrepared):
            raise TypeError(f"prepared must be TurnoverPrepared, got {type(prepared).__name__}")
        return _run(prepared, members, data_date, held, _check(params))


TURNOVER = ShareTurnoverAllocator()


def _v(suffix: str, params: TurnoverParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0497-{suffix}", family="M0497", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=TURNOVER, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0497",
    name="Big index members ranked by share turnover behind the switch: least turned-over vs most",
    family="stock-share-turnover",
    source_kind="variation",
    source_ref="M0491 (same F4-screened pool, a different ranking); Lee and Swaminathan 2000",
    parent_id="M0491",
    hypothesis=(
        "Lee and Swaminathan (2000, published, so expect fading after it) found heavily "
        "turned-over 'glamour' stocks lag and lightly turned-over ones lead. M0491 found the 20 "
        "most traded big members, ranked by raw dollar volume, lagged all three blind draws and "
        "SPY behind the switch; share turnover -- 60-day mean volume divided by point-in-time "
        "shares outstanding -- is a different ranking of the same F4-screened pool and was never "
        "tested there. If the ratio carries a real signal, the 20 least turned-over names beat "
        "all three matched blind draws of the same pool and SPY-behind-the-switch (M0491-SPY-SW's "
        "book, repeated here as a yardstick and not a new result), the 20 most turned-over names "
        "do worse than the draws (the mirror), and the gap survives in 2009-2015, judged first. "
        "Six arms is the pre-registration cap, so the always-invested twin that would separate "
        "the ranking from the switch is queued as a follow-up rather than run here."
    ),
    expected_failure=(
        "Low turnover is a low-beta/value tilt that lags in the 2009-2015 rally: LOW-SW lands "
        "inside the blind draws' spread or behind them in 2009-2015 even if it leads on the whole "
        "window, the same way M0491's most-traded ranking earned its whole edge in 2008 and lost "
        "money in 1 of 4 walk-forward folds alone. The mirror then fails to mirror -- HIGH-SW does "
        "not clearly trail the draws either -- which would say the ratio is noise dressed as a "
        "signal rather than two ends of one anomaly."
    ),
    candidates=(
        _v("LOW-SW", TurnoverParams("low"),
           "The 20 least turned-over screened members (60-day volume / shares outstanding), behind the switch"),
        _v("HIGH-SW", TurnoverParams("high"),
           "Mirror: the 20 most turned-over screened members, same screen and switch"),
        _v("DRAW1-SW", TurnoverParams("draw", seed=1),
           "Control: 20 names drawn blind from the same screened pool at LOW-SW's churn, seed 1"),
        _v("DRAW2-SW", TurnoverParams("draw", seed=2),
           "Control: 20 names drawn blind from the same screened pool at LOW-SW's churn, seed 2"),
        _v("DRAW3-SW", TurnoverParams("draw", seed=3),
           "Control: 20 names drawn blind from the same screened pool at LOW-SW's churn, seed 3"),
        _v("SPY-SW", TurnoverParams("spy"),
           "Control: SPY itself behind the same switch, repeats M0491-SPY-SW's book verbatim"),
    ),
    seen_keys=(
        "concept:share-turnover-rank-behind-switch",
        "concept:glamour-vs-value-turnover-mirror",
    ),
    amendments=(
        Amendment(
            added=date(2026, 11, 12),
            why=(
                "The run reversed the hypothesis: HIGH-SW (most turned-over) cleared DSR and beat "
                "every draw and SPY-SW, LOW-SW (least turned-over, the predicted winner) failed "
                "both bars, and `lab dressing M0497` confirms it structurally (BACKWARDS, -7.25 "
                "pts on the prices whole-window). No always-invested arm was recorded for this "
                "ranking, so what the 200-day switch costs on top of the ranking that actually won "
                "could not be priced. This arm answers that for HIGH-SW specifically, since it is "
                "the arm a promotion would be about."
            ),
            hypothesis=(
                "HIGH-SW's edge is mostly the ranking, not the switch: an always-invested twin of "
                "HIGH-SW (same screen, same most-turned-over ranking, trend=None) still beats "
                "SPY TR and the draws, even without the 2008 exit the switch would have given it."
            ),
            expected_failure=(
                "The edge was the switch wearing the ranking's name: HIGH-ALWAYS gives back most "
                "of HIGH-SW's lead once it rides 2008 and 2015-2016 uncushioned, the same way "
                "M0491's most-traded ranking turned out to be the switch's record and not the "
                "stocks'."
            ),
            candidates=(
                _v("HIGH-ALWAYS", TurnoverParams("high", trend=None),
                   "HIGH-SW's own always-invested twin: same ranking, never stepping aside, "
                   "to separate the ranking from the switch for the arm that cleared DSR"),
            ),
        ),
    ),
)
