"""M0558 — Index addition drift: hold newly admitted members, not just rebound deletions.

Source: Chen, Noronha & Singal, The Price Response to S&P 500 Index Additions and Deletions:
Evidence of Asymmetry and a New Explanation, Journal of Finance 59(4), 2004.
Idea: M0495 took the rebound side of the Chen-Noronha-Singal asymmetry (deletions that keep
trading). This method takes the addition side of the same union-of-index demand shock: when a
company joins the S&P 500 or Nasdaq-100, every index fund tracking it must buy on the effective
date regardless of merit. The open question is whether the resulting lift persists (a drift this
book could ride) or reverses once the forced flow stops (a pop this book would only catch the
tail of).

M0117 asked a related but different question with a different design. M0117 is a *dilution*
overlay: it holds the 50 most heavily traded index members, equal weight, and only *subtracts*
the ones whose membership began recently, letting the freed money fall through to the next most
traded name. Measured there, a 12-month exclusion changed the book's composition in 76% of
months but removed only 1.3 names of 50 on average (2.6% of the book), so even if tenure carries
a real -2 pt/yr penalty the overlay could move the book by well under a tenth of a point a year --
below what any DSR at the lab's N would ever call real, and M0117 was rejected on exactly that
basis (its own closing recommendation was to try a market-cap-weighted base book instead, not to
pursue the exclusion further). This method inverts the design instead of refining the overlay:
it holds *only* the newly admitted names (nothing else from the broad index), up to ``floor(1/
slot)`` of them, and parks the rest of the money in SPY. At a 10% slot the admission pool
(measured below) averages 4.1 live, liquid names a month, so the position concentrates into
roughly 40% of the book on average rather than 2.6% of it -- the same underlying tenure signal
M0117 could not move the needle with, but undiluted.

On data date d:

  * **the pool**: each symbol's membership spells in the S&P 500 union Nasdaq-100 union are
    merged (M0117's ``merge_spells``); a spell's start is an admission. Names whose *current*
    spell (the one covering d) began inside ``(d - window_months, d]`` are candidates, unless
    that start date is a snapshot epoch (M0117's left-censoring guard: a start shared by
    ``epoch_min`` or more symbols is the data's first sight, not a real addition, and is never
    counted). A candidate must still trade liquidly: a bar dated d, close >= ``min_price``,
    20-day mean dollar volume >= ``min_dollar_volume``, and no gap longer than ``max_gap_days``
    calendar days between bars from ``continuity_days`` before the admission through d.
  * **the book**: up to ``floor(1 / slot)`` of the pool, most recent admission first (ties by
    symbol), ``slot`` each, the rest of the money in SPY. A name ages out of the book
    ``window_months`` after its admission, so the window is both the recency filter and the
    holding period.
  * **the matched control** (``control="winners"``): the same count the addition book would hold
    on d, filled with liquid current members with the *best* raw return over the last
    ``winner_n`` bars, same slot, rest in SPY, invested on exactly the same days. Newly admitted
    names are usually recent winners already (that is why the index added them), so this asks
    whether being *admitted* earns anything beyond having simply *risen* -- the same logic as
    M0495's "losers" control asked of deletions, mirrored to the winning side.

Measured before the run with this session's own script against the dev store (1996-01 to
2015-10-16, monthly snapshots): 546 non-epoch union admissions occur in the dev window, about
27/year, but the store only carries a priced, liquid bar for roughly 234 of them (the store
serves 539 of ~1,061 requested members, and names never served cannot be "held" at all). At a
6-month window the live pool across 238 monthly snapshots averages 4.34 names (median 4, zero in
74 months, i.e. 31% of the time), so at a 10% slot the book averages 4.13 names held and 58.7%
in SPY; at 1 month the pool averages 0.79 (92% SPY, zero in 60% of months -- too thin to read);
at 3 months, 2.25 (78% SPY); at 12 months, 8.54 pre-cap, 6.19 held after the 10-slot cap (38%
SPY). The pool is richer in 2009-2015 (5.05 average) than before 2009 (3.97 average), the
opposite direction from most of this lab's stock-picking books, because dev-store coverage of
recently added, large, liquid names improves over time even though overall membership coverage
does not.

Fractional shares at Gotrade's real fees: slots of 10-20% of a 20M IDR book are $130-270 a name,
and every trade pays the fee minimum, same as M0495.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0117_index_tenure_exclusion import merge_spells, months_before
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day

ADDED = date(2026, 11, 12)

IDLE = "SPY"
DV_N = 20
CONTROLS = ("none", "winners")


@dataclass(frozen=True, slots=True)
class AdditionParams:
    """How long after an admission a name stays in the book, how big a slot is, and the control."""

    window_months: int = 6
    slot: float = 0.10
    control: str = "none"  # "winners": the matched best-raw-return twin
    winner_n: int = 126
    min_price: float = 1.0
    min_dollar_volume: float = 2_000_000.0
    max_gap_days: int = 7
    continuity_days: int = 30
    epoch_min: int = 20  # a start shared by this many symbols is a snapshot, not an admission

    def __post_init__(self) -> None:
        for name, lo in (
            ("window_months", 1),
            ("winner_n", 1),
            ("max_gap_days", 1),
            ("continuity_days", 1),
            ("epoch_min", 2),
        ):
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool) or v < lo:
                raise ValueError(f"{name} must be an int >= {lo}, got {v!r}")
        if not (0.0 < float(self.slot) <= 1.0):
            raise ValueError(f"slot must be in (0, 1], got {self.slot!r}")
        if self.control not in CONTROLS:
            raise ValueError(f"control must be one of {CONTROLS}, got {self.control!r}")
        if not (self.min_price > 0 and self.min_dollar_volume >= 0):
            raise ValueError("min_price must be > 0 and min_dollar_volume >= 0")

    @property
    def slots(self) -> int:
        return max(1, math.floor(1.0 / self.slot + 1e-9))

    def as_dict(self) -> dict[str, str]:
        return {
            "window_months": str(self.window_months),
            "slot": f"{self.slot:.4f}",
            "control": self.control,
            "winner_n": str(self.winner_n),
            "min_price": f"{self.min_price:.2f}",
            "min_dollar_volume": f"{self.min_dollar_volume:.0f}",
            "max_gap_days": str(self.max_gap_days),
            "continuity_days": str(self.continuity_days),
            "epoch_min": str(self.epoch_min),
        }


def _check(params: object) -> AdditionParams:
    if not isinstance(params, AdditionParams):
        raise TypeError(f"params must be AdditionParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, eq=False)
class AdditionPrepared:
    """The price history, and each symbol's union spells when a membership calendar exists."""

    history: Mapping[str, History] = field(repr=False)
    spells: Mapping[str, tuple[tuple[date, date | None], ...]] | None = None
    counts: Mapping[date, int] = field(default_factory=dict, repr=False)


def _liquid_close(h: History, i: int, p: AdditionParams) -> float | None:
    """The close on bar ``i`` when it clears the price and dollar-volume floors, else None."""
    if i + 1 < DV_N:
        return None
    close = float(h.close[i])
    if not math.isfinite(close) or close < p.min_price:
        return None
    window = slice(i + 1 - DV_N, i + 1)
    dv = float(np.mean(h.close[window] * h.volume[window]))
    if not math.isfinite(dv) or dv <= p.min_dollar_volume:
        return None
    return close


def _current_spell_start(
    spells: Mapping[str, tuple[tuple[date, date | None], ...]], symbol: str, data_date: date
) -> date | None:
    """The start of the spell covering ``data_date``, or None when the symbol is not a member."""
    for start, end in spells.get(symbol, ()):
        if start <= data_date and (end is None or data_date < end):
            return start
    return None


def addition_pool(
    prepared: AdditionPrepared, members: AbstractSet[str], data_date: date, p: AdditionParams
) -> list[tuple[date, str, float]]:
    """``(admission, symbol, close)`` for every recent admission still a member on d, newest first."""
    assert prepared.spells is not None
    cut = months_before(data_date, p.window_months)
    day = as_day(data_date)
    out: list[tuple[date, str, float]] = []
    for symbol in sorted(members):
        if symbol == IDLE:
            continue
        start = _current_spell_start(prepared.spells, symbol, data_date)
        if start is None or not (cut < start <= data_date):
            continue
        if prepared.counts.get(start, 0) >= p.epoch_min:
            continue  # a snapshot epoch: tenure unknown, not a real admission
        h = prepared.history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None:
            continue
        close = _liquid_close(h, i, p)
        if close is None:
            continue
        lo = int(np.searchsorted(h.dates, as_day(start - timedelta(days=p.continuity_days))))
        span = h.dates[lo : i + 1]
        if len(span) < 2 or span[0] > as_day(start) or span[-1] != day:
            continue
        gaps = np.diff(span).astype("timedelta64[D]").astype(int)
        if int(gaps.max()) > p.max_gap_days:
            continue
        out.append((start, symbol, close))
    out.sort(key=lambda r: (-r[0].toordinal(), r[1]))
    return out


def winner_pool(
    history: Mapping[str, History], members: AbstractSet[str], data_date: date, p: AdditionParams
) -> list[tuple[float, str, float]]:
    """``(return over winner_n bars, symbol, close)`` for liquid current members, best first."""
    out: list[tuple[float, str, float]] = []
    for symbol in sorted(members):
        if symbol == IDLE:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < p.winner_n:
            continue
        close = _liquid_close(h, i, p)
        if close is None:
            continue
        past = float(h.close[i - p.winner_n])
        if not (math.isfinite(past) and past > 0):
            continue
        out.append((close / past - 1.0, symbol, close))
    out.sort(key=lambda r: (-r[0], r[1]))
    return out


class IndexAdditionAllocator:
    """Recent index admissions that still trade, a fixed slot each, the rest in SPY."""

    id = "M0558"
    market_fields = ()  # reads Market.membership, which every store carries

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(p.winner_n + 1, DV_N, 31 * p.window_months + p.continuity_days)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (IDLE,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (IDLE,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(
        self, prepared: AdditionPrepared, members: AbstractSet[str], data_date: date, p: AdditionParams
    ) -> tuple[Target, ...]:
        if prepared.spells is None:  # no membership calendar (market-aware contract)
            return ()
        picks = addition_pool(prepared, members, data_date, p)[: p.slots]
        if p.control == "winners":
            n = len(picks)
            picks_c = [(s, c) for _, s, c in winner_pool(prepared.history, members, data_date, p)[:n]]
        else:
            picks_c = [(s, c) for _, s, c in picks]
        slot = Decimal(f"{p.slot:.4f}")
        out: list[Target] = []
        for symbol, close in picks_c:
            t = target_from_close(symbol, close, slot)
            if t is not None:
                out.append(t)
        rest = Decimal(1) - slot * len(out)
        if rest > 0:
            h = prepared.history.get(IDLE)
            i = h.index_of(data_date) if h is not None else None
            if i is not None:
                t = target_from_close(IDLE, float(h.close[i]), rest)
                if t is not None:
                    out.append(t)
        return tuple(out)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        """The history-only path: no membership calendar, so no book."""
        return self._run(AdditionPrepared(dict(history)), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> AdditionPrepared:
        return AdditionPrepared(dict(history))

    def prepare_market(self, market: Any) -> AdditionPrepared:
        spells, counts = merge_spells(tuple(market.membership.intervals))
        return AdditionPrepared({s: h for s, h in market.history.items()}, spells, counts)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, AdditionPrepared):
            raise TypeError(f"prepared must be AdditionPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


ADDITION = IndexAdditionAllocator()


def _v(suffix: str, params: AdditionParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0558-{suffix}",
        family="M0558",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=ADDITION,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0558",
    name="Index addition drift: hold newly admitted members, not just rebound deletions",
    family="stock-index-addition-drift",
    source_kind="paper",
    source_ref=(
        "Chen, Noronha & Singal (2004, Journal of Finance) asymmetric add/delete response; "
        "cf. M0117 (Greenwood & Sammon 2023; Vijh & Wang 2022), the lab's prior, rejected "
        "look at index tenure, which diluted the same signal into a 50-name overlay instead "
        "of holding it directly"
    ),
    parent_id="M0495",
    hypothesis=(
        "M0495 took the rebound side of the Chen-Noronha-Singal deletion/addition asymmetry "
        "(deletions that keep trading); this method takes the addition side of the same "
        "union-of-index demand shock. When a company joins the S&P 500 or Nasdaq-100, every "
        "index fund tracking it must buy on the effective date regardless of merit, and the open "
        "question is whether the resulting lift persists (a drift this book could ride) or "
        "reverses once the forced flow stops (a pop this book only catches the tail of). On each "
        "monthly re-pick: merge each symbol's membership spells in the S&P 500 / Nasdaq-100 union "
        "(M0117's merge_spells) and find names whose current spell began within the last 1, 3 or "
        "6 months, are still a member, and trade liquidly (a bar on the day, price at least $1, "
        "20-day dollar volume over $2M, no gap longer than a week from a month before the "
        "admission through the pick date; a spell start shared by 20+ symbols is a snapshot epoch "
        "and is never counted as an admission, M0117's left-censoring guard). Hold up to "
        "floor(1/slot) of that pool, newest admission first, a fixed 10% slot each (20% in one "
        "arm), the rest in SPY; a name ages out of the book that many months after its admission. "
        "This differs from M0117 in shape, not in source: M0117 held a broad 50-name book and "
        "only subtracted recent joiners as an overlay, which measured there moved only 1.3 of 50 "
        "names (2.6% of the book) on average -- too diluted for any real tenure effect to clear "
        "the lab's DSR bar, and M0117 was rejected on exactly that arithmetic, with its own "
        "closing note recommending a market-cap-weighted base book rather than a bigger "
        "exclusion. This method instead holds nothing but the admissions, undiluted: measured "
        "before the run with this session's own script against the dev store (238 monthly "
        "snapshots, 1996-01 to 2015-10-16), a 6-month window's live, liquid pool averages 4.34 "
        "names (median 4, empty 31% of the time), so at a 10% slot the book averages 4.13 names "
        "held and 58.7% in SPY -- the same signal M0117 could not move the needle with, now "
        "concentrated into roughly 40% of the book instead of 2.6% of it. The matched control W6 "
        "holds, on each re-pick, exactly as many names as A6 would, at the same slot, but chooses "
        "liquid current members with the best 126-day raw return -- newly admitted names are "
        "usually recent winners already, so the gap A6 minus W6 is what being admitted adds to "
        "having simply risen. SPY is the always-invested no-opinion arm, since every variant's "
        "residual is SPY. Success: A6 or A3 beats total-return SPY and W6 on dev with a worst fall "
        "under the bar, and is still ahead of SPY in 2009-2015, where the pool is in fact richer "
        "(5.05 average names vs 3.97 before 2009) because dev-store coverage of large, liquid, "
        "newly added names improves over time even though overall membership coverage does not. "
        "Fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade and the owner's "
        "monthly deposits. Read 2009-2015 first; lab survivorship is mandatory before any verdict, "
        "since large recent joiners are close to the opposite of the companies the dev store fails "
        "to price, so this book's survivorship exposure should run the other way from most of the "
        "lab's stock-picking books and that needs checking, not assuming."
    ),
    expected_failure=(
        "The point-in-time membership calendar marks a name's spell start on the effective date, "
        "which is public on the day -- but the academic literature finds the price response is "
        "centred on the *announcement* date, about a week earlier, and partly reverses afterward. "
        "A book that can only buy once the admission is in a public snapshot therefore buys after "
        "the move is substantially earned and is left holding whatever comes next, which on the "
        "deletion side (M0495, the same asymmetry's other half) the lab already measured as a "
        "real but thin and drawdown-heavy rebound. The addition side's own literature (Chen, "
        "Noronha & Singal 2004) is explicitly about a reversal, so the more likely outcome here is "
        "the mirror image: a drift that gives back rather than continues, with W6 (which captures "
        "the recent-winner correlation without the admission timing) doing at least as well as A6 "
        "once that give-back is netted out. The anomaly is also twenty years old by the dev "
        "window's end, so any real edge should be visibly weaker in 2009-2015 than before 2009 -- "
        "which would cut against the richer-pool finding above, since a richer pool with a faded "
        "edge is worse than a thin pool with a real one. A second, more mechanical failure: the "
        "pool is thin enough (31% of months empty at 6 months, 60% at 1 month) that most of the "
        "book is SPY most of the time, so whatever edge exists is diluted by sitting in cash-like "
        "SPY exposure even though it is no longer diluted across 50 names -- the 1-month arm in "
        "particular may be unreadable rather than merely negative."
    ),
    candidates=(
        _v("A1", AdditionParams(window_months=1), "admissions in the last month, 10% each, rest SPY"),
        _v("A3", AdditionParams(window_months=3), "admissions in the last 3 months, 10% each, rest SPY"),
        _v("A6", AdditionParams(window_months=6), "admissions in the last 6 months, 10% each, rest SPY"),
        _v(
            "A6S20",
            AdditionParams(window_months=6, slot=0.20),
            "admissions in the last 6 months, 20% each (at most five), rest SPY",
        ),
        _v(
            "W6",
            AdditionParams(window_months=6, control="winners"),
            "control: as many as A6 holds, but current members with the best 126-day return",
        ),
    ),
    seen_keys=(
        "concept:index-addition-drift",
        "concept:index-addition-effect",
        "concept:forced-index-buying",
    ),
)
