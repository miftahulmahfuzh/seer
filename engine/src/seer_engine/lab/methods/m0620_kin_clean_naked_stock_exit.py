"""M0620 -- Find a kin-clean stock ranker whose naked picks beat SPY, then give it the per-stock
200-day exit.

Source: variation of M0107 (the per-stock trend exit) and George & Hwang (2004), "The 52-week
high and momentum investing", J. Finance 59(5), doi:10.1111/j.1540-6261.2004.00695.x.

Idea. M0112 wanted to put M0107's per-stock 200-day exit -- the lab's best drawdown brake, cutting
M0107's own book from a 26.3% worst fall to 13.1% for about 0.9 points a year -- on the lab's
best-earning engine, residual momentum. The coordinator ruled it out before it ran: residual
momentum is M0022, a test-failed method, by family and by `parent_id`, and a braked copy of the
same picks would almost certainly also fail the hard gate's behavioural kin test (D14), since
M0007-N20-RAW already moves with M0022's tested variant at 0.98 residual correlation. The brake
needs a kin-clean host: a book whose picks beat SPY naked (no parked SPY, no market-wide switch)
and whose family, ancestors and behaviour carry no test-failed kin.

The reserved hypothesis named three open candidates: short-term reversal, 52-week-high, and
low-volatility, each held naked. Reading back what this lab has already measured about each,
at today's convention (fractional shares, Gotrade's real fees, the owner's monthly top-up):

    * Low-volatility is dead. Every recent calm-stock book -- M0417 (low residual volatility),
      M0419 (the same with a rank buffer), M0468 (volatility-of-volatility) -- loses to its own
      same-size random control once drawn at a matching trade count: the ranked idea arm never
      clears the luck bar, only its blind twin does. Three independent tries, three losses.
    * Short-term reversal is dead too. M0158, M0161, M0391, M0490, M0537, M0538 are all rejected,
      and M0028 (calm, uptrend-filtered reversal, the closest to this lab's conventions) only ties
      SPY on the owner's deposits (+7.5% vs +7.2%) and correlates 0.65 month-by-month with
      residual momentum -- a quality tilt, not an opposite number.
    * 52-week-high is the one gap. M0015 found the *naked* "nearness to the yearly high" book
      (close / 252-day max close, no blend) barely beat SPY in the dev window (+8.0-8.3% a year
      against SPY's +7.9%) with a shallower fall (17.3-18.0% against the reference book's
      22.2%) -- but that trial ran on `monthly_hold`, the old whole-share book at the flat 0.1%
      fee, years before Gotrade's real fee schedule or the fractional presets existed. Every
      later 52-week-high method blended it with residual momentum (M0017, M0516) or conditioned
      it on volatility (M0232), which reintroduces the exact kin risk this idea exists to avoid.
      The plain, unblended nearness ranker has never been priced at the fees paper actually pays.

This file re-runs M0015's plain "near" ranking fresh: the standard F4 screen (index member, bar on
`data_date`, 20-day mean dollar volume above $20M, close at least $5), ranked by close / 252-day
max close descending (ties by 12-1 momentum descending, then symbol), the top 20 held equal
weight, monthly, fractional at Gotrade's real fees (`monthly-hold-frac-gotrade`), with **no** trend
gate and **no** parked SPY -- naked, as the idea demands. M0107's per-stock exit
(`m0107_stock_trend_exit_raisers.above_own_trend`) is applied on top as the same cash/spread pair
M0107 itself used, so the 20-name slot set a holding drops out of goes to cash (STOCK200) or is
redistributed to the names that stayed in (STOCK200-SPREAD). A fourth arm, built from
`lab.control_draw`'s frame-matched blind draw, holds the same pool at the naked book's own size,
entry count and turnover -- the "same-size random control" the reservation asks for, priced
separately from the lab's automatic 200-random-twin yardstick (which judges each arm's own luck,
not whether this book's trading habit is worth anything over a coin flip).

Success, written now: NEAR20 beats SPY in 2009-2015 and a majority of its walk-forward folds,
and beats RANDOM20 by more than a blind draw's own spread. If NEAR20 clears that, the exit should
cut its worst fall toward the 15% real-money comfort zone for under 3 points a year -- the same
trade M0107 found on the calm-raiser book.

Expected failure: M0015's old edge (+0.1 to +0.4 points a year over SPY) is thin enough that it
reads as pure noise once real fees replace the flat 0.1% the 2015-era trial paid, and once a
same-size random control stands beside it rather than only SPY. If NEAR20 does not clearly beat
RANDOM20, the idea's premise -- that an open, kin-clean family has a naked edge at all -- fails,
which would mean the lab's only working stock-picking engine is the one kin-blocked family the
brake cannot be put on, exactly the finding M0112 was stopped short of confirming.

Pure: reads only bars dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0015_52week_high import nearness
from seer_engine.lab.methods.m0107_stock_trend_exit_raisers import above_own_trend
from seer_engine.sim.book import Target, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
)

ADDED = date(2026, 11, 13)

HIGH_N = 252  # sessions in the 52-week high, M0015's own window


@dataclass(frozen=True, slots=True)
class NearExitParams:
    """``inner`` is F4's screen and book size, naked (``trend=None``); ``high_n`` the 52-week-high
    window; ``stock_n`` the per-stock exit window (None turns it off); ``spread`` the dropped
    slots' weight (cash when False, redistributed to survivors when True); ``seed`` the control
    draw's seed, read only by the matched-draw arm."""

    inner: FactorParams
    high_n: int = HIGH_N
    stock_n: int | None = None
    spread: bool = False
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.inner.trend is not None:
            raise ValueError("this method is naked: inner.trend must be None")
        if isinstance(self.high_n, bool) or not isinstance(self.high_n, int) or self.high_n < 20:
            raise ValueError(f"high_n must be an int >= 20, got {self.high_n!r}")
        if self.stock_n is not None:
            if isinstance(self.stock_n, bool) or not isinstance(self.stock_n, int):
                raise TypeError(f"stock_n must be None or an int, got {type(self.stock_n).__name__}")
            if self.stock_n < 2:
                raise ValueError(f"stock_n must be >= 2, got {self.stock_n}")
        if not isinstance(self.spread, bool):
            raise TypeError(f"spread must be a bool, got {type(self.spread).__name__}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "high_n": str(self.high_n),
            "stock_n": "none" if self.stock_n is None else str(self.stock_n),
            "spread": str(self.spread).lower(),
            "seed": str(self.seed),
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> NearExitParams:
    if not isinstance(params, NearExitParams):
        raise TypeError(f"params must be NearExitParams, got {type(params).__name__}")
    return params


def choose(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           p: NearExitParams) -> tuple[Target, ...]:
    """The naked nearness-to-high book, M0107's per-stock exit, then the weighting ``spread`` asks
    for. No market gate, no parked slack: a dropped slot is cash unless ``spread`` says otherwise."""
    pool = [r for r in rows if r.symbol not in EXCLUDED]
    scored: list[tuple[float, float, str, FactorRow]] = []
    for r in pool:
        near = nearness(history, r.symbol, data_date, p.high_n)
        if near is not None:
            scored.append((-near, -r.momentum, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    chosen = scored[: p.inner.top]  # the slot set the unfiltered book would hold
    slot = equal_weight(p.inner.top)
    if p.stock_n is None:
        kept = chosen
    else:
        kept = [t for t in chosen if above_own_trend(history.get(t[2]), data_date, p.stock_n)]
    w = slot
    if p.spread and kept and len(kept) < len(chosen):
        w = to_weight(slot * Decimal(len(chosen)) / Decimal(len(kept)))
    out: list[Target] = []
    for _, _, _, r in kept:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    return tuple(out)


class NearHighExitAllocator:
    """The naked 52-week-high nearness book with M0107's per-stock trend exit on top."""

    id = "M0620"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        need = [factor_lookback(p.inner), p.high_n]
        if p.stock_n is not None:
            need.append(p.stock_n)
        return max(need)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()  # naked: no fixed trend symbol, no SPY park

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = factor_rows(history, members, data_date, p.inner)
        if not rows:
            return ()
        return choose(history, rows, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return (dict(history), prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        history, factor = prepared
        p = _check(params)
        rows = factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        return choose(history, rows, data_date, p)


ALLOC = NearHighExitAllocator()


class MatchedDrawAllocator:
    """NEAR20's shape with none of its opinion: ``lab.control_draw``'s frame-matched draw from the
    same F4-screened pool, matched to NEAR20's own size, entry count and turnover (not the exited
    book's -- the control prices the ranking habit, not the exit)."""

    id = "M0620-A1"

    def lookback(self, params: Any) -> int:
        p = _check_control(params)
        inner = max(factor_lookback(p.inner), p.high_n)
        return control_draw.lookback_for(inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check_control(params)
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_control(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_control(params)
        return True

    def _select(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                p: NearExitParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        rows = factor_rows(history, members, data_date, p.inner)
        pool = tuple(sorted(r.symbol for r in rows))
        if not pool:
            return (), ()
        naked = replace(p, stock_n=None, spread=False)
        book = tuple(t.symbol for t in choose(history, rows, data_date, naked))
        return pool, book

    def _run(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: NearExitParams) -> tuple[Target, ...]:
        names = control_draw.matched_book(
            lambda d: self._select(history, members, d, p),
            data_date, held, tag="M0620", seed=p.seed,
        )
        w = equal_weight(p.inner.top)
        out: list[Target] = []
        for s in names:
            h = history.get(s)
            if h is None:
                continue
            t = target_from_close(s, last_close(h, data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, members, data_date, held, _check_control(params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(prepared, members, data_date, held, _check_control(params))


def _check_control(params: object) -> NearExitParams:
    """``NearExitParams``, plus the control's own rule: it holds a blind draw, so it may not
    declare an exit of its own -- the exit's cost is read from NEAR20-STOCK200 directly."""
    p = _check(params)
    if p.stock_n is not None:
        raise ValueError("the matched draw is a control: stock_n must be None")
    return p


DRAW = MatchedDrawAllocator()

SCREEN = FactorParams(rank="momentum", top=20, trend=None)  # F4's screen, naked, M0015's book size


def _v(suffix: str, params: NearExitParams, rationale: str, allocator: Any = ALLOC) -> Candidate:
    return Candidate(id=f"M0620-{suffix}", family="M0620", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0620",
    name="Find a kin-clean stock ranker whose naked picks beat SPY, then give it the per-stock 200-day exit",
    family="per-stock-trend-exit",
    source_kind="variation",
    source_ref="M0107 (the per-stock exit); George & Hwang (2004), J. Finance 59(5), the 52-week high",
    parent_id="M0107",
    hypothesis=(
        "M0112 wanted M0107's per-stock 200-day exit on residual momentum, the lab's best-earning "
        "engine, but the coordinator stopped it before it ran: M0022/M0007 are test-failed and any "
        "braked copy of their picks would fail the hard gate on family, ancestry and behaviour "
        "(0.98 residual correlation already measured). The exit needs a kin-clean host. Of the "
        "three open families the reservation named, low-volatility (M0417, M0419, M0468, three "
        "tries) and short-term reversal (M0158, M0161, M0391, M0490, M0537, M0538, M0028) have all "
        "lost to their own random controls or merely tied SPY under today's conventions. "
        "52-week-high is the gap: M0015 found the plain, unblended nearness-to-the-high book "
        "(close / 252-day max close, no residual-momentum blend) beat SPY by a thin margin "
        "(+8.0-8.3%/yr vs SPY's +7.9%) with a shallower fall, but only on the old whole-share book "
        "at the flat 0.1% fee, never at Gotrade's real fees in fractional shares, and never "
        "against a same-size random control. This file re-runs that exact ranking naked (no "
        "trend gate, no parked SPY) on monthly-hold-frac-gotrade: NEAR20 is the idea, RANDOM20 is "
        "a frame-matched blind draw from the same pool (lab.control_draw, matched to NEAR20's own "
        "size, entries and turnover), and NEAR20-STOCK200 / NEAR20-STOCK200-SPREAD put M0107's "
        "per-stock exit on top (cash slack vs spread-to-survivors), mirroring M0107's own 2x2. "
        "Success: NEAR20 beats SPY in 2009-2015 and a majority of walk-forward folds, and beats "
        "RANDOM20 by more than a blind draw's own spread; then the exit should push the worst fall "
        "toward 15% for under 3 points a year, the same trade M0107 found on the calm-raiser book."
    ),
    expected_failure=(
        "M0015's old edge was thin enough (0.1-0.4 points a year) to be pure noise once real fees "
        "replace the flat 0.1% that trial paid and once a same-size random control stands beside "
        "it. NEAR20 does not clearly beat RANDOM20; the naked book is, like every calm-stock and "
        "reversal book tried recently, indistinguishable from a blind draw of the same pool. That "
        "would confirm the lab's working edge lives only in the kin-blocked momentum family, and "
        "the per-stock exit -- proven useful only as a brake, never as a picker (M0107) -- has no "
        "kin-clean book left to be put on."
    ),
    candidates=(
        _v("NEAR20", NearExitParams(SCREEN),
           "The naked nearness-to-high book: no exit, no gate, no parked SPY. The idea."),
        _v("NEAR20-STOCK200", NearExitParams(SCREEN, stock_n=200, spread=False),
           "NEAR20 plus M0107's per-stock 200-day exit, dropped slots in cash."),
        _v("NEAR20-STOCK200-SPREAD", NearExitParams(SCREEN, stock_n=200, spread=True),
           "NEAR20 plus the same exit, dropped slots' weight spread to the survivors."),
        _v("RANDOM20", NearExitParams(SCREEN, seed=620),
           "Control: lab.control_draw's frame-matched blind draw from NEAR20's own pool, matched "
           "to NEAR20's size, entries and turnover -- the same-size random control the "
           "reservation asks for, never a strategy.", allocator=DRAW),
    ),
    seen_keys=(
        "concept:52-week-high-naked",
        "concept:nearness-to-high",
        "concept:per-stock-trend-exit-on-kin-clean-host",
    ),
)
