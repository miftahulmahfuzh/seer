"""M0047 — Weight the residual-momentum picks by real company size, with a ceiling on any one name.

Source: variation of M0034 (the size tilt that could only read trading volume), reserved by Sera
20261018-0517 for the owner's theme "books shaped like the market". Unblocked 2026-10-17, when
the research stores gained point-in-time shares outstanding from 1996 (EDGAR cover pages, then
XBRL, each usable from its filing day) and ``Market.market_value`` stopped multiplying an
unadjusted count by a split-adjusted close.

Why. Every strategy the owner ran from 2018 lost to SPY by a similar margin (insight 91), and
SPY is weighted by company size while these books give each of their twenty names an equal
slot. M0034 asked whether leaning the slots toward the bigger names pays, but it could only read
trading volume, which ranks companies like market value at a Spearman 0.69 and puts 35-40% of the
money on different names. This method asks the question with the real number: does sizing the
same residual-momentum picks the way the index sizes companies earn its concentration at any
ceiling, and does it close any of the gap a market-shaped yardstick opens.

What is the same as M0032-N20-RAW-FRAC-GT (and M0034-EQ): the SPY 200-day trend gate, F4's
screen, top-20 raw cumulative residual momentum, monthly, fractional shares at Gotrade's real
fees on the owner's monthly top-up. What this method adds:

    * ONE SHARE CLASS PER COMPANY. ``market_value`` answers each listed class with the whole
      company's count times that class's price, so GOOG and GOOGL would count Alphabet twice.
      The picks are walked in rank order and a second class of a company already chosen is
      skipped; the next name fills its slot. Applied to every arm, the equal one included, so
      the arms differ only in weighting.
    * SIZE WEIGHTS. Each pick's weight is proportional to ``market.market_value(symbol,
      data_date)``. The stock weights sum to picks / 20 (the equal book's exposure), so sizing
      moves money between names and never changes how much is invested. A pick whose size is
      unknown that day (no usable filing yet) is given the median known size among the picks:
      neutral, neither leaned on nor dropped. If no pick has a known size the book is equal
      weight. Assumption, written before any result.
    * A CEILING. No name above 10% (twice the equal slot) or 20% (four times), the excess spread
      over the names still under it (M0034's water-filling). One arm runs with no ceiling, to
      show what the ceiling is buying.
    * THE MEANINGLESS CONTROL. The same gate, screen, count, one-class rule and size weights,
      but the names are drawn in a fixed hash order (M0187's ``draw``) over exactly the names the
      residual ranking could score that day, re-drawn each quarter (March, June, September,
      December) and otherwise kept while still in the screen, with M0187's 40% keep band at a
      re-draw; a slot a holding leaves between re-draws is filled from the same hash order. If
      the size-weighted placebo matches the size-weighted momentum book, the lead is
      the size weighting's and not the ranking's.

Market-aware (``market_fields = ("shares",)``): the history-only path, and a market with no share
counts, target nothing, so ``lab run`` refuses this on a store without company size and the
contract kit sees an empty book. Pure: the hash is a function of its inputs and every read is of
bars and filings dated <= ``data_date``.

Amendment 1 (2026-10-19). The two size-weighted placebos above were re-drawn only in March, June,
September and December and otherwise kept whatever was still in the screen, so they traded 881
and 876 times against the 1600 and 1591 of the books they were quoted against -- 0.55x, with half
the fee bill, which is not the same book. MV10-PLC and MV20-PLC replace a re-draw period chosen by
hand with the churn of the arm each one controls: at every monthly decision the control recomputes
the real book at this session and at the previous one, counts the names it would have entered, and
replaces exactly that many of its own. Their names also repair a second thing. The stem
"M0047-PLC1" names no arm, so the control-shape ladder fell through to its weakest rung and read
both placebos against M0047-EQ -- the equal-weight arm -- when these are size-weighted books whose
opponents are MV10 and MV20. Against EQ the quoted lead was +3.80 points a year; against the true
target it is +1.28. Both numbers belong in any sentence written about this method. The originals
stay recorded and are not withdrawn: a trial is a measurement and the lab keeps its measurements.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market
from seer_engine.lab import control_draw
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    FACTOR_SYMBOLS,
    N20,
    ResidParams,
    ResidPrepared,
    resid_lookback,
    residual_scores,
)
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorRow, prepare_factor, trend_on

ADDED = date(2026, 10, 18)
AMEND_1 = date(2026, 10, 19)

PICKS = ("residual", "placebo")
WEIGHTINGS = ("equal", "size")
REPICK_MONTHS = (3, 6, 9, 12)
KEEP_PCT = 40

#: Second listed classes of one filer, mapped to the class that names the company. Only the first
#: pick of a company is kept.
COMPANY: Mapping[str, str] = {
    "GOOGL": "GOOG", "FOXA": "FOX", "NWSA": "NWS", "UAA": "UA", "CMCSK": "CMCSA",
    "BATRK": "BATRA", "DISCK": "DISCA", "LBTYK": "LBTYA", "VIAB": "VIA", "LSXMK": "LSXMA",
    "FWONK": "FWONA",
}


def company(symbol: str) -> str:
    return COMPANY.get(symbol, symbol)


@dataclass(frozen=True, slots=True)
class SizeParams:
    """M0032's ranking (``inner``), how the twenty are picked, how they are sized, and the
    ceiling as an absolute weight (None = none)."""

    inner: ResidParams
    picks: str = "residual"
    weighting: str = "size"
    cap: float | None = None
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if self.picks not in PICKS:
            raise ValueError(f"picks must be one of {PICKS}, got {self.picks!r}")
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if self.cap is not None:
            if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
                raise TypeError(f"cap must be a number or None, got {type(self.cap).__name__}")
            if not 1.0 / self.inner.inner.top <= self.cap <= 1.0:
                raise ValueError(f"cap must lie between the equal slot and 1, got {self.cap}")
            if self.weighting == "equal":
                raise ValueError("cap is meaningless on equal weights")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if self.picks == "residual" and self.seed != 0:
            raise ValueError("seed is for the placebo picks only")

    def as_dict(self) -> dict[str, str]:
        out = {"picks": self.picks, "weighting": self.weighting,
               "cap": "none" if self.cap is None else repr(float(self.cap)),
               "seed": str(self.seed), "size": "market_value", "unknown_size": "median-of-picks",
               "one_class_per_company": ",".join(f"{k}>{v}" for k, v in sorted(COMPANY.items()))}
        if self.picks == "placebo":
            out["hash"] = "blake2b-8"
            out["repick_months"] = ",".join(str(m) for m in REPICK_MONTHS)
            out["keep_pct"] = str(KEEP_PCT)
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SizeParams:
    if not isinstance(params, SizeParams):
        raise TypeError(f"params must be SizeParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True)
class SizePrepared:
    """M0007's prepared ranking inputs plus the market whose share counts size the picks."""

    resid: ResidPrepared
    market: Market | None


def one_per_company(order: Sequence[str], top: int) -> list[str]:
    """The first ``top`` symbols of ``order`` with at most one class of each company."""
    out: list[str] = []
    seen: set[str] = set()
    for s in order:
        if len(out) >= top:
            break
        c = company(s)
        if c in seen:
            continue
        seen.add(c)
        out.append(s)
    return out


def size_weights(sizes: Sequence[float | None], top: int, p: SizeParams) -> list[Decimal | None]:
    """One weight per pick, summing to len(sizes) / top. Unknown sizes take the median known."""
    if not sizes:
        return []
    eq = equal_weight(top)
    known = [s for s in sizes if s is not None and np.isfinite(s) and s > 0.0]
    if p.weighting == "equal" or not known:
        return [eq for _ in sizes]
    fill = float(np.median(known))
    raw = np.array([s if s is not None and np.isfinite(s) and s > 0.0 else fill for s in sizes],
                   dtype=np.float64)
    w = raw / float(raw.sum()) * (len(sizes) / top)
    if p.cap is not None:
        w = _apply_ceiling(w, float(p.cap))
    return [_floor_weight(float(x)) for x in w]


def placebo_order(scores: Mapping[str, float], data_date: date, held: frozenset[str],
                  rows: Mapping[str, FactorRow], p: SizeParams) -> list[str]:
    """The placebo's names in slot order. At a re-draw: held names under the keep band, then the
    hash order over the scorable names. Between re-draws: the holdings still in the screen, then
    the hash order to fill any slot a holding left."""
    stocks = sorted(s for s in held if s in rows and s not in EXCLUDED)
    order = sorted((s for s in scores if s not in EXCLUDED), key=lambda s: (draw(p.seed, s, data_date), s))
    if stocks and data_date.month not in REPICK_MONTHS:
        first = stocks
    else:
        frac = {s: k / len(order) for k, s in enumerate(order)}
        first = sorted((s for s in stocks if frac.get(s, 1.0) < KEEP_PCT / 100.0), key=lambda s: (frac[s], s))
    taken = set(first)
    return first + [s for s in order if s not in taken]


class MarketValueAllocator:
    """Residual-momentum (or hash-order placebo) picks, one class per company, sized by real
    market value under an optional ceiling. No share counts: no targets."""

    id = "M0047"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return resid_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).inner
        return tuple(sorted({p.market, *FACTOR_SYMBOLS(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: SizePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizeParams) -> tuple[Target, ...]:
        market = prepared.market
        if market is None or len(market.shares) == 0:  # no company size: target nothing
            return ()
        resid = prepared.resid
        if not trend_on(resid.history, data_date, p.inner.inner):
            return ()
        rows = resid.factor.rows_on(members, data_date, p.inner.inner)
        if not rows:
            return ()
        grid = resid.grid(p.inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.inner)
        by_symbol = {r.symbol: r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED}
        top = p.inner.inner.top
        if p.picks == "residual":
            order = sorted(by_symbol, key=lambda s: (-scores[s], s))
        else:
            order = placebo_order({s: scores[s] for s in by_symbol}, data_date, held, by_symbol, p)
        chosen = one_per_company(order, top)
        sizes = [market.market_value(s, data_date) for s in chosen]
        out: list[Target] = []
        for s, w in zip(chosen, size_weights(sizes, top, p), strict=True):
            if w is None:
                continue
            t = target_from_close(s, by_symbol[s].close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no targets."""
        p = _check(params)
        return self._run(self.prepare(history), members, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> SizePrepared:
        return SizePrepared(ResidPrepared(history, prepare_factor(history)), None)

    def prepare_market(self, market: Any) -> SizePrepared:
        if not isinstance(market, Market):
            raise TypeError(f"market must be a Market, got {type(market).__name__}")
        return SizePrepared(ResidPrepared(market.history, prepare_factor(market.history)), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizePrepared):
            raise TypeError(f"prepared must be SizePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


MARKETVALUE = MarketValueAllocator()

#: M0032-N20-RAW-FRAC-GT's ranking, verbatim: top-20 RAW cumulative residual momentum, SPY-200 gate.
RANKING = ResidParams(N20, scaled=False)


def _v(suffix: str, params: SizeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0047-{suffix}", family="M0047", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MARKETVALUE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


# --------------------------------------------------------------------------- amendment 1 (2026-10-19)
#
# The churn-matched placebo. Everything below is new; nothing above it moved, so every recorded
# config_digest of the six originals is byte-identical to the one its trial holds.
#
# The params are the replaced arms' own values, reused: SizeParams already carries inner, picks,
# weighting, cap and seed, which is everything this allocator reads, so a dataclass of its own
# would hold nothing new and would be a second way of saying the same thing in each of nine
# method files. A field added to SizeParams would move all six recorded M0047 digests
# (registry._canon renders a dataclass by dataclasses.fields(), not by as_dict), and a
# compare=False field would make the new arm's configuration identical to the old one's, which
# Method.__post_init__ refuses. The new allocator id is the whole of the difference, and the
# allocator= line of config_text is enough to make it a configuration the lab has not run.
#
# One honest caveat, recorded rather than repaired: SizeParams.as_dict stamps repick_months and
# keep_pct onto every placebo's reported params, and this draw uses neither -- its re-key period
# is read off the book it controls, which is the whole point. as_dict is reporting only
# (registry._canon walks dataclasses.fields(), never as_dict), so it moves no digest, and editing
# it is outside this amendment's reach: the params value is reused byte for byte and the
# allocator id is the whole of the difference (plan invariant 12). The allocator id M0047-A1 in
# the same record is what tells a reader which draw actually ran.


def _checkm(params: object) -> SizeParams:
    """``SizeParams``, plus the one thing a control's params may not say.

    The matched draw differs from ``PLC1-MV10`` in its allocator id and in nothing else, so the
    params must still read ``picks="placebo"``. Saying ``"residual"`` would record a configuration
    whose text claims the residual ranking this allocator never performs on its own names -- it
    recomputes that ranking to count the real book's entries, and then draws blind.
    """
    if not isinstance(params, SizeParams):
        raise TypeError(f"params must be SizeParams, got {type(params).__name__}")
    if params.picks != "placebo":
        raise ValueError(
            f"the matched draw is a control: picks must be 'placebo', got {params.picks!r}"
        )
    if params.seed == 0:
        raise ValueError("seed 0 belongs to the real book; a placebo draws on a non-zero seed")
    return params


class MatchedDrawAllocator:
    """M0047's book with none of its identity: hash-drawn names, the real book's own churn.

    Same SPY 200-day gate, same F4 screen, same scorable pool, same one class per company, same
    point-in-time market-value weights under the same ceiling as ``MarketValueAllocator``. The
    one difference is which names fill the slots, and that is the placebo's whole content.

    **Why the draw it replaces was not honest.** ``placebo_order`` re-drew on the first session of
    March, June, September and December and otherwise kept everything still in the screen. The
    arms it was quoted against re-pick a fresh top twenty every single month. Measured: 881 trades
    against 1600 (0.55x) and 4.415 turnover against 9.345 (0.50x), outside D17's refuse band. Half
    the fee bill is not the same book, so the gap it reported was not evidence. The author of that
    draw chose a re-draw period by hand; M0243's author saw the same failure on another chassis,
    corrected by hand in the other direction, and overshot to 3.01x. Choosing the period by hand
    is the error, in both signs.

    **What this one does instead.** At every decision session it recomputes the controlled arm's
    own selection twice -- at this session and at the previous decision session -- and counts the
    names the real book would have entered. It then keeps exactly ``size - entries`` of its own
    holdings, in a date-free hash order so the keep set is stable, and draws the rest from the
    same scorable pool in a hash order keyed on this month. The entry count matches by
    construction rather than by luck, so the fee bill matches, so the gap is signal.

    **The previous decision session is a calendar fact, not a bar.** ``monthly-hold-frac-gotrade``
    lets the basket move on the first NYSE session of each calendar month
    (``sim.rules.is_rank_session`` -> ``_first_of``), and ``control_draw.previous_decision_date``
    walks the NYSE calendar to it without reading a single price. Nothing about it can look ahead.
    The extra bars the second scoring pass reaches back for cost
    ``control_draw.PREVIOUS_DECISION_BARS`` (26) of lookback.

    **And the monthly clock is the right one for THIS chassis, which the brief got wrong.**
    ``REPICK_MONTHS`` and ``KEEP_PCT`` appear in this file only inside ``placebo_order``
    (:189-202); the residual arms take a fresh ``one_per_company(order, 20)`` at every monthly
    decision (:244-248). The quarterly band is the handicap being removed, not a property to
    reproduce. (M0201's and M0202's shared chassis is genuinely quarterly and derives its own
    previous re-pick in its own files -- that is phase 5's, and it is the only place in the set
    where the monthly helper is the wrong answer.)

    **One assumption, written before the run.** The member set is point-in-time and the allocator
    is handed only *this* session's. Recomputing the real book at the previous session therefore
    screens the previous date's bars against today's members, so a name that joined the index this
    month and would have entered the real book is counted as already present, and the entry count
    comes out at most a name or two low. The bias is one-signed and toward stickiness, so it can
    only push the measured trade ratio **below** 1.00 -- it cannot manufacture a match. If the
    ratio lands inside the match band, the assumption did no harm; if it lands under 0.80, this is
    the first thing to look at. The real arms' own recorded trials used the true point-in-time
    members, so the comparison is honest in the direction that matters.

    Market-aware exactly as ``MarketValueAllocator`` is (``market_fields = ("shares",)``): no
    share counts, no targets, so ``lab run`` refuses this on a store without company size and the
    history-only contract kit sees an empty book.
    """

    id = "M0047-A1"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return control_draw.lookback_for(resid_lookback(_checkm(params).inner))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _checkm(params).inner
        return tuple(sorted({p.market, *FACTOR_SYMBOLS(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _checkm(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _checkm(params)
        return True

    def _real_book(self, prepared: SizePrepared, members: AbstractSet[str], data_date: date,
                   p: SizeParams) -> tuple[tuple[str, ...], dict[str, FactorRow]]:
        """The controlled arm's own names on ``data_date``, and the pool they were picked from.

        Byte-for-byte ``MarketValueAllocator._run``'s residual path up to ``chosen``: the same
        gate, the same screen, the same scores, the same one-class rule. Empty when the gate is
        off, which is how the control sits in cash on exactly the days the real book does.
        """
        resid = prepared.resid
        if not trend_on(resid.history, data_date, p.inner.inner):
            return (), {}
        rows = resid.factor.rows_on(members, data_date, p.inner.inner)
        if not rows:
            return (), {}
        grid = resid.grid(p.inner.market)
        if grid is None:
            return (), {}
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.inner)
        by_symbol = {r.symbol: r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED}
        order = sorted(by_symbol, key=lambda s: (-scores[s], s))
        return tuple(one_per_company(order, p.inner.inner.top)), by_symbol

    def _run(self, prepared: SizePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizeParams) -> tuple[Target, ...]:
        market = prepared.market
        if market is None or len(market.shares) == 0:  # no company size: target nothing
            return ()
        now, by_symbol = self._real_book(prepared, members, data_date, p)
        if not now:
            return ()
        before, _ = self._real_book(
            prepared, members, control_draw.previous_decision_date(data_date), p
        )
        size = len(now)
        keep, tail = control_draw.matched_partition(
            pool=sorted(by_symbol), held=held,
            keep_n=max(size - control_draw.churn(now, before), 0),
            tag="M0047", seed=p.seed, data_date=data_date,
        )
        chosen = one_per_company(keep + tail, size)
        top = p.inner.inner.top
        sizes = [market.market_value(s, data_date) for s in chosen]
        out: list[Target] = []
        for s, w in zip(chosen, size_weights(sizes, top, p), strict=True):
            if w is None:
                continue
            t = target_from_close(s, by_symbol[s].close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no targets."""
        p = _checkm(params)
        return self._run(self.prepare(history), members, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> SizePrepared:
        return SizePrepared(ResidPrepared(history, prepare_factor(history)), None)

    def prepare_market(self, market: Any) -> SizePrepared:
        if not isinstance(market, Market):
            raise TypeError(f"market must be a Market, got {type(market).__name__}")
        return SizePrepared(ResidPrepared(market.history, prepare_factor(market.history)), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizePrepared):
            raise TypeError(f"prepared must be SizePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _checkm(params))


MATCHED = MatchedDrawAllocator()


def _a1(suffix: str, params: SizeParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate, with the declaration of which recorded arm it replaces.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``); it is declared, never
    inferred, and it is outside ``config_digest`` because ``config_text`` names its three
    attributes by hand. It matters more here than anywhere: these two arms are deliberately
    re-pointed at their TRUE targets, so the old arms' ``target_id`` (``M0047-EQ``) and the new
    ones' (``M0047-MV10`` / ``-MV20``) differ, and a rule that matched targets would retire
    nothing at all."""
    return Candidate(id=f"M0047-{suffix}", family="M0047", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=AMEND_1,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_DRAW_AMENDMENT = Amendment(
    added=AMEND_1,
    why=(
        "The two size-weighted placebos traded about half as often as the books they control and "
        "were being read against the wrong arm; re-draw them churn-matched and name them after "
        "their true targets"
    ),
    hypothesis=(
        "Written before any result. Two independent defects sit on the same pair of arms and this "
        "block repairs both. FIRST, SHAPE. PLC1-MV10 and PLC1-MV20 are re-drawn only in March, "
        "June, September and December and otherwise keep whatever is still in the screen, while "
        "MV10 and MV20 re-pick a fresh top twenty every month. Measured: 881 and 876 trades "
        "against 1600 and 1591, 0.55x, and turnover 4.415 and 4.522 against 9.345 and 9.853, "
        "0.50x and 0.51x -- outside the 0.50-2.00 band the lab refuses a control at. MV10-PLC and "
        "MV20-PLC take their entry count each month from the arm they control instead of from a "
        "re-draw month chosen by hand, so they trade about 1.8x as often as the arms they replace "
        "and pay a fee bill the size of MV10's and MV20's. SECOND, RESOLUTION. The stem "
        "'M0047-PLC1' names no arm, so the ladder falls through to its weakest rung and reports "
        "both placebos against M0047-EQ, the equal-weight arm -- but these are size-weighted "
        "books and their true opponents are MV10 and MV20. The names MV10-PLC and MV20-PLC make "
        "the sibling-stem rung resolve each one onto the book it actually controls. "
        "PRE-REGISTERED DIRECTION. A hash order carries no information, so the extra trading buys "
        "nothing and costs Gotrade's fees: each re-drawn control earns LESS than the arm it "
        "replaces (under 9.87% and under 9.88% money-weighted), and each book's lead over its own "
        "honest placebo therefore WIDENS. Against the true targets the standing leads are MV10 "
        "11.15 - 9.87 = +1.28 points a year and MV20 10.42 - 9.88 = +0.54; the prediction is that "
        "both grow, MV10's to somewhere between +1.3 and +3.0 and MV20's to between +0.6 and "
        "+2.5. Both re-drawn arms should land inside 0.80-1.25 on trades and on turnover against "
        "their own targets. The SPY 200-day gate is in both books and is worth a constant 3.6 "
        "points a year to either, so it nets out of every number here. The re-stated verdict on "
        "M0047's own success clause -- 'beats its own size-weighted placebo by at least 2 points "
        "a year' -- is reported against the true target whatever it says: against EQ it looked "
        "like +3.80 and a comfortable pass, against MV10 it is +1.28 and already a failure before "
        "this amendment runs a single session."
    ),
    expected_failure=(
        "The direction can come out backwards and the measurement is what decides. The quarterly "
        "keep band held names that kept passing the screen quarter after quarter, which is a "
        "quiet survivor tilt the honest monthly draw throws away; if that tilt was worth more "
        "than the fees it saved, MV10-PLC and MV20-PLC earn MORE than 9.87% and 9.88%, both leads "
        "narrow instead of widening, and M0047's two-point clause fails by a wider margin. The "
        "lead can even go negative, as M0221's and M0225's blind draws already do on their own "
        "books; that is the finding and it is reported, never re-drawn away. The shape can also "
        "miss: the control is matched on entries, and exits follow entries only while its own "
        "holdings stay inside the screen -- when a drawn name leaves the pool the control must "
        "replace it whether or not the real book entered anyone, which pushes the trade ratio "
        "above 1.00; the opposite push comes from reading the previous session's book against "
        "this session's member set, which can hide an index joiner and pull the ratio under 1.00. "
        "If either arm lands outside 0.80-1.25 the result is recorded and the phase stops; a "
        "second draw is admissible only for a missed shape and never for a disliked margin "
        "(design section 4). Finally, market value is unknown for many picks before about 2000 "
        "and both books fall back to the median known size there, so the early years of the "
        "comparison are close to equal weight on both sides and the real test lives in 2001-2015."
    ),
    candidates=(
        _a1("MV10-PLC",
            SizeParams(RANKING, picks="placebo", weighting="size", cap=0.10, seed=1),
            "Placebo for MV10: names in a hash order over the same scorable set, entering as "
            "often as MV10 itself enters, sized by market value, 10% ceiling",
            supersedes=("M0047-PLC1-MV10",)),
        _a1("MV20-PLC",
            SizeParams(RANKING, picks="placebo", weighting="size", cap=0.20, seed=1),
            "Placebo for MV20: the same hash order and the same matched churn, sized by market "
            "value, 20% ceiling",
            supersedes=("M0047-PLC1-MV20",)),
    ),
)


METHOD = Method(
    id="M0047",
    name="Weight the momentum picks by real company size, with a ceiling on any one name",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref=(
        "variation of M0034 (size tilt by trading volume) with point-in-time market value from "
        "EDGAR share counts (stores of 2026-10-17); Sera 20261018-0517, theme 'books shaped like "
        "the market'; placebo frame of M0187"
    ),
    parent_id="M0034",
    hypothesis=(
        "Equal slots in a twenty-name momentum book lean toward the smaller index members compared "
        "with SPY, which weights by company size, and from 2018 SPY's big-company drift beat every "
        "book the lab tried (insight 91). M0034 tested a lean toward bigger names but could only "
        "read trading volume, which puts 35-40% of the money on different names than market value "
        "would. This method keeps M0032-N20-RAW-FRAC-GT's book exactly (SPY 200-day gate, F4 "
        "screen, top-20 raw residual momentum, monthly, fractional shares at Gotrade's real fees on "
        "the monthly top-up), keeps one share class per company, and sizes the twenty by "
        "point-in-time market value (filed share count times the close as it printed, from 1996), "
        "with no name above 10% (MV10) or 20% (MV20), plus an uncapped arm (MV) and the equal-slot "
        "control (EQ). Unknown sizes take the median known size among the picks. The meaningless "
        "control is the same frame and the same size weights on names drawn in a hash order over "
        "the same scorable names, re-drawn quarterly (PLC1-MV10, PLC1-MV20). Size-weighting is a "
        "very old idea (the cap-weighted index itself) and residual momentum was published in "
        "2011 (Blitz, Huij and Martens), inside the dev window. Success, written now: MV10 or MV20 "
        "beats total-return SPY on dev with a worst fall under the screen bar, beats EQ on return "
        "per unit of worst fall (MAR), keeps or improves EQ's edge over SPY in 2009-2015, and "
        "beats its own size-weighted placebo by at least 2 points a year. The expected direction "
        "on dev is a smaller worst fall and a lower return than EQ: the big names move less."
    ),
    expected_failure=(
        "Sizing by market value pulls the book toward the few biggest names the momentum screen "
        "happens to hold (in the 1990s GE, Microsoft, Cisco; later Exxon, Apple), so the book "
        "becomes a smaller, more concentrated copy of SPY's top end: lower volatility, but its "
        "edge over SPY shrinks with its distance from SPY, and the cap binds most months so MV10 "
        "ends up close to equal weight anyway while MV pays for concentration (one name at 30% or "
        "more, a deeper single-name fall such as Cisco in 2000-02). The size-weighted placebo "
        "probably beats SPY too on dev, because the gate and the screen do most of the work "
        "(M0187, M0198), and the size weighting moves both books together, so the gap to the "
        "placebo stays under 2 points. Coverage: before about 2000 many picks have no filed count "
        "and take the median, so the early years are close to equal weight and the test of the "
        "idea really lives in 2001-2015. The survivorship-check store, which holds the companies "
        "that died, should hurt the equal arm more than the size arms, since dead companies were "
        "mostly small; that is the one place a size tilt could look better than it is. And the "
        "method's ancestry runs through the residual-momentum family, which has a test-failed "
        "method, so the hard gate is expected to refuse promotion whatever dev says."
    ),
    candidates=(
        _v("EQ", SizeParams(RANKING, weighting="equal"),
           "Equal slots, one class per company: M0032's book under this allocator, the control"),
        _v("MV10", SizeParams(RANKING, weighting="size", cap=0.10),
           "Sized by real market value, no name above 10% (twice an equal slot)"),
        _v("MV20", SizeParams(RANKING, weighting="size", cap=0.20),
           "Sized by real market value, no name above 20% (four times an equal slot)"),
        _v("MV", SizeParams(RANKING, weighting="size"),
           "Sized by real market value with no ceiling: what the ceiling is buying"),
        _v("PLC1-MV10", SizeParams(RANKING, picks="placebo", weighting="size", cap=0.10, seed=1),
           "Placebo: hash-order names over the same scorable set, sized by market value, 10% ceiling"),
        _v("PLC1-MV20", SizeParams(RANKING, picks="placebo", weighting="size", cap=0.20, seed=1),
           "Placebo: the same hash-order names, sized by market value, 20% ceiling"),
    ),
    seen_keys=(
        "concept:market-value-weighted-momentum-book",
        "concept:size-weighted-placebo-control",
    ),
    amendments=(MATCHED_DRAW_AMENDMENT,),
)
