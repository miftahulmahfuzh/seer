"""M0202 — Bond-like stocks with a gentler crash guard: half the book stays invested below SPY's
200-day average instead of all of it going to cash.

Source: variation of M0197 (Treasury beta; D.E. Shaw research note, caia.org/node/6853; Maio &
Santa-Clara; Driessen, Kuiper & Beilo), reserved by Sera 20261017-1835 from the 20261017-1808
synthesis. The ranking, the screen, the band and the SPY slots are M0197's, imported unchanged;
only the switch is new.

Why. M0197's bond-like book (the 20 members whose weekly returns rise most when the 10-year yield
falls, net of the market) beat every placebo seed and its own opposite with no switch (+12.5% a
year on the deposits against +8.8% to +11.9% and +7.7%), but fell 62% in 2008. Behind the
all-or-nothing SPY 200-day switch it fell only 22%, yet trailed SPY by 3.3 points a year in
2009-2015 (the switch sold the 2010 and 2011 dips) and led the switched placebo by under a point:
the switch did the work and erased the ranking's gap. A half-size guard keeps half the bet on
through the dips the switch sold, so it should keep more of the ranking's lead (and its 2009-2015
edge) while still cutting the 2008 fall roughly in half.

The guard, one of two, always explicit (``FactorParams.trend`` is None in every variant, so F4's
default 200-day gate can never sneak in and empty the book):

    * ``"half"``: full size while SPY closes above its 200-day average; otherwise every target
      (stock slots and the SPY filler alike) at half weight, the rest in cash.
    * ``"half-fast"``: full size while SPY closes above its 200-day OR its 50-day average (M0195's
      stateless "back in on a close over the 50-day"); half size only under both.

Under half size the holdings do not change: a quarter's picks are kept, only resized, so the guard
costs a trim and a top-up, not a full round trip. A re-pick in a half-size month picks as usual
and buys at half weight. With too few SPY bars to read the guard the book is at half size.

Controls on the same frame and the same guard: ``side="neutral"`` (M0197's rate-neutral ranking,
smallest absolute loading; M0197 showed it carries no information) and ``side="placebo"``, which
orders exactly the names M0197's loadings could score by M0187's hash of (seed, symbol, month) --
the frame with no idea in it. Two placebo seeds under "half" and one under "half-fast", so the
idea's lead is read against a spread and not a single draw.

Amendment 1 (2026-10-19), the shape-matched placebo. Those three arms trade about 2.25x the book
each controls and turn over 1.99x to 2.20x it, so every gap quoted against them was read against an
opponent paying twice the fees, and D17 refuses the method on it. The cause is the re-key period,
chosen by hand: M0187's hash is keyed on the month, so the whole book is re-drawn at every
quarterly re-pick, while M0197's 40% keep band holds a name unless it slips out of the top 40% of
the pool. ``Y20-HALF-PLC1``, ``Y20-HALF-PLC2`` and ``Y20-HALF-FAST-PLC1`` keep the frame, the
guard and the seeds and derive the re-key from the bond book's own calendar: at each re-pick the
allocator re-reads M0197's bond ranking at this date and at the previous quarter's re-pick, counts
how many of that quarter's twenty are still under the band, and lets the blind draw replace exactly
the rest. Measured over the dev window's 79 re-picks before any of this ran: 423 entries against
the real book's 443, a ratio of 0.955, where the recorded arms sit at 2.24. The names also change:
``PLC1-HALF-FAST`` is resolved by ``lab control`` against ``Y20-HALF`` rather than its real target
``Y20-HALF-FAST``, because its stem is itself a placebo and the ladder steps past it;
``Y20-HALF-FAST-PLC1`` puts the target's whole name in the control's, so the strongest rung reaches
the right arm. The cost is the lookback -- 331 bars instead of 253 -- which moves no window.

Market-aware (``market_fields = ("series",)``): the history-only path has no yield, so by the
contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``, as M0197: fractional shares,
Gotrade's real fees, the owner's monthly deposits, resized when a slot is off by 1% of the account
(halving a 5% slot always clears it).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.control_draw import matched_partition
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.lab.methods.m0197_treasury_yield_beta import (
    REPICK_MONTHS,
    STEP,
    WEEKS,
    YieldBetaParams,
    YieldBetaPrepared,
    choose,
    loadings,
)
from seer_engine.lab.methods.m0197_treasury_yield_beta import scored as yb_scored
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
)
from seer_engine.strategies.indicators import sma_window

ADDED = date(2026, 10, 17)
SLOW_N = 200
FAST_N = 50
HALF = Decimal("0.5")
GUARDS = ("half", "half-fast")
SIDES = ("bond", "neutral", "placebo")


@dataclass(frozen=True, slots=True)
class HalfGuardParams:
    """``yb`` is M0197's params (screen, book size, band, market; its ``side`` is ignored and its
    ``inner.trend`` must be None); ``side`` which order fills the book; ``guard`` the half-size
    rule; ``seed`` the placebo's hash seed (0 and unused for the real rankings)."""

    yb: YieldBetaParams
    side: str = "bond"
    guard: str = "half"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.yb, YieldBetaParams):
            raise TypeError(f"yb must be YieldBetaParams, got {type(self.yb).__name__}")
        if self.yb.inner.trend is not None:
            raise ValueError("yb.inner.trend must be None: the guard here replaces F4's switch")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if self.guard not in GUARDS:
            raise ValueError(f"guard must be one of {GUARDS}, got {self.guard!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if (self.side == "placebo") != (self.seed > 0):
            raise ValueError("a placebo needs a seed >= 1, and only a placebo takes one")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "guard": self.guard, "seed": str(self.seed),
               "slow_n": str(SLOW_N), "fast_n": str(FAST_N), "half": str(HALF)}
        for k, v in self.yb.as_dict().items():
            if k != "side":
                out[f"yb.{k}"] = v
        return out


def _check(params: object) -> HalfGuardParams:
    if not isinstance(params, HalfGuardParams):
        raise TypeError(f"params must be HalfGuardParams, got {type(params).__name__}")
    return params


def _sma(h: History, i: int, n: int) -> float | None:
    if i + 1 < n:
        return None
    return float(sma_window(h.close[i + 1 - n : i + 1].reshape(1, n), n)[0])


def full_size(history: Mapping[str, History], data_date: date, p: HalfGuardParams) -> bool:
    """True when the guard allows the full book on ``data_date``; False (half size) otherwise,
    including when SPY has no bar dated d or too few bars for the 200-day average."""
    h = history.get(p.yb.market)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None:
        return False
    close = float(h.close[i])
    slow = _sma(h, i, SLOW_N)
    if slow is None:
        return False
    if close > slow:
        return True
    if p.guard == "half":
        return False
    fast = _sma(h, i, FAST_N)
    return fast is not None and close > fast


def ranked(history: Mapping[str, History], series: MarketSeries, rows: list[FactorRow],
           data_date: date, p: HalfGuardParams) -> dict[str, float]:
    """Rank fractions in [0, 1), 0 first: M0197's for bond and neutral, the hash for the placebo
    over exactly the names M0197's loadings could score that day."""
    if p.side != "placebo":
        return yb_scored(history, series, rows, data_date, replace(p.yb, side=p.side))
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.yb.market)
    lv = loadings(history, series, pool, data_date, p.yb.market)
    order = sorted(lv, key=lambda s: (draw(p.seed, s, data_date), s))
    return {s: k / len(order) for k, s in enumerate(order)}


def halved(targets: tuple[Target, ...]) -> tuple[Target, ...]:
    """Every target at half its weight, the rest left in cash."""
    out = []
    for t in targets:
        w = (t.weight * HALF).quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)
        if w > 0:
            out.append(replace(t, weight=w))
    return tuple(out)


class HalfGuardAllocator:
    """M0197's screened, banded, quarterly book (bond-like, rate-neutral or a hash placebo),
    always invested, at half size while SPY is under its guard. No yield: no targets."""

    id = "M0202"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).yb.inner), SLOW_N + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return (_check(params).yb.market,)

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).yb.market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: HalfGuardParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        inner = p.yb.inner
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        stocks = [s for s in held if s != p.yb.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = ranked(prepared.history, prepared.series, rows, data_date, p) if repick else {}
        out = choose(prepared.history, members, frac, data_date, held, p.yb)
        return out if full_size(prepared.history, data_date, p) else halved(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no yield, so no ranking and no target."""
        return self._run(YieldBetaPrepared(history, EMPTY_SERIES, None), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> YieldBetaPrepared:
        return YieldBetaPrepared(history, EMPTY_SERIES, prepare_factor(history))

    def prepare_market(self, market: Any) -> YieldBetaPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return YieldBetaPrepared(market.history, series, prepare_factor(market.history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, YieldBetaPrepared):
            raise TypeError(f"prepared must be YieldBetaPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


HALFGUARD = HalfGuardAllocator()


def _p(side: str, guard: str, seed: int = 0) -> HalfGuardParams:
    # trend=None, always: FactorParams' default is the SPY 200-day switch (M0188's slip), and here
    # the guard replaces it. The rank is unused: only the screen.
    yb = YieldBetaParams(FactorParams(rank="momentum", top=20, trend=None))
    return HalfGuardParams(yb, side=side, guard=guard, seed=seed)


def _v(suffix: str, params: HalfGuardParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0202-{suffix}", family="M0202", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=HALFGUARD, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


# ------------------------------------------------------------------ amendment 1 (2026-10-19)
#
# The shape-matched placebo. See the module docstring for why the recorded arms trade 2.25x the
# book each controls; what follows is the repair. Nothing above this line changes: a new allocator
# id is the only safe way to add an arm, because `registry._canon` renders a params dataclass by
# `dataclasses.fields()` and a field added to `HalfGuardParams` -- even a defaulted one -- would
# move every recorded config_digest that used it.

AMENDED = date(2026, 10, 19)
PREV_SPAN = 70  # sessions in a quarter, with room for the longest one in the dev window
MATCHED_LOOKBACK = WEEKS * STEP + PREV_SPAN + 1  # 331: a year of weekly marks before the previous
                                                 # re-pick, which the matched draw re-reads
REAL_SIDE = "bond"  # the side of the book these three arms are the controls for


def _check_control(params: object) -> HalfGuardParams:
    """``HalfGuardParams``, plus the one thing a control's params may not say.

    The matched draw differs from the three recorded placebo arms in its allocator id and in
    nothing else, so the params must still read ``side="placebo"``. Saying ``"bond"`` would record
    a configuration whose text claims a yield ranking this allocator never performs -- the config
    text is the public record of what an arm did, and a blind book must not describe itself as a
    ranked one.
    """
    p = _check(params)
    if p.side != "placebo":
        raise ValueError(
            f"the matched draw is a control: side must be 'placebo', got {p.side!r}"
        )
    return p


def prev_repick_session(history: Mapping[str, History], data_date: date,
                        market: str) -> date | None:
    """The session this chassis last re-picked on, or None when the history does not reach it.

    Derived from the calendar, never carried in state: an allocator is called once per session and
    holds nothing between calls. The rules are ``monthly-hold-frac-gotrade``, so a decision session
    is the first session of a month and the ``data_date`` the allocator is handed is the last
    session of the month before it; a re-pick month is one of ``REPICK_MONTHS``, three apart. So
    the previous re-pick's data date is the last session ``market`` printed in the month three
    calendar months back. The search is bounded by ``data_date``'s own index, so it can see no bar
    the session cannot.

    This chassis does NOT call ``control_draw.previous_decision_date``, and must not: that helper
    answers the previous *monthly* decision, which is the right question wherever a basket moves
    every month. Here ``_run`` passes an empty ``frac`` on every non-``REPICK_MONTHS`` month, so
    the allocator is called monthly but the basket only moves quarterly, behind M0197's 40% keep
    band, and there is no monthly entry count to match. Written out here rather than imported from
    M0201 on purpose: importing it would make M0202's recorded trials depend on M0201's file while
    only M0201's ``method_amendments.source_sha`` moved.
    """
    h = history.get(market)
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None:
        return None
    year, month = data_date.year, data_date.month - 3
    if month <= 0:
        year, month = year - 1, month + 12
    after = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    k = int(np.searchsorted(h.dates[: i + 1], np.datetime64(after, "D"), side="left")) - 1
    if k < 0:
        return None
    out = h.dates[k].item()
    return out if (out.year, out.month) == (year, month) else None


def real_frac_at(prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
                 p: HalfGuardParams) -> dict[str, float]:
    """M0197's own bond-side rank fractions on ``data_date``, over ``members``.

    ``members`` is the set the allocator was handed for its own session and is used unchanged at
    the previous quarter: a control is never given the membership of a past date, and reading
    today's set backwards uses no data the session does not already have. ``YieldBetaPrepared``
    carries no Market and so could not reach a past membership even if that were wanted, and M0201
    runs the identical rule on purpose, so the two amendments are one rule and not two.
    """
    inner = p.yb.inner
    if prepared.factor is None:
        rows = factor_rows(prepared.history, members, data_date, inner)
    else:
        rows = prepared.factor.rows_on(members, data_date, inner)
    return yb_scored(prepared.history, prepared.series, rows, data_date,
                     replace(p.yb, side=REAL_SIDE))


def matched_entries(prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
                    now: Mapping[str, float], p: HalfGuardParams) -> int:
    """How many names the bond book itself takes in on ``data_date``.

    Its own keep band, applied to the book it would have held at the previous quarter's re-pick:
    every name of that book still under ``keep_pct`` stays, and the rest of the twenty slots are
    entries. The band and not a symmetric difference, because a name that slips from rank 18 to
    rank 40 is kept by this chassis and is not an entry; counting ``control_draw.churn`` over two
    top-20 lists would over-state it and re-make the error this amendment exists to undo. With no
    previous re-pick in reach the whole book is an entry, which is what the chassis does on its
    first session anyway.
    """
    top = p.yb.inner.top
    before_date = prev_repick_session(prepared.history, data_date, p.yb.market)
    if before_date is None:
        return top
    before = real_frac_at(prepared, members, before_date, p)
    if not before:
        return top
    book = [s for _, s in sorted((v, s) for s, v in before.items())][:top]
    cut = p.yb.keep_pct / 100.0
    kept = min(sum(1 for s in book if now.get(s, 1.0) < cut), top)
    return max(0, top - kept)


def matched_frac(prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
                 held: frozenset[str], p: HalfGuardParams) -> dict[str, float]:
    """Rank fractions that drive M0197's ``choose`` to a blind book of the bond book's own shape.

    ``choose`` keeps a holding whose fraction is under ``keep_pct`` and fills the rest of the
    twenty slots from the top of the order, so a fraction below the band is an instruction to hold
    and one above it an instruction to enter. The names the matched draw keeps are laid out under
    the band in keep order, and every other name above it in the order the control would take it --
    ``matched_partition``'s ``tail``, which guarantees the names the control does not hold come
    before the holdings it is dropping, so a just-dropped name is never taken straight back.
    ``choose`` itself is called unchanged, and so is the guard that halves what it returns, so the
    band, the quarterly calendar, the SPY filler and the half-size rule are byte-identical to the
    arm this controls; the only thing that differs is which names fill the slots.
    """
    now = real_frac_at(prepared, members, data_date, p)
    if not now:
        return {}
    cut = p.yb.keep_pct / 100.0
    top = p.yb.inner.top
    keep, tail = matched_partition(
        pool=sorted(now),
        held=held,
        keep_n=max(0, top - matched_entries(prepared, members, data_date, now, p)),
        tag="M0202",
        seed=p.seed,
        data_date=data_date,
    )
    out: dict[str, float] = {s: cut * (i + 1) / (len(keep) + 1) for i, s in enumerate(keep)}
    for j, s in enumerate(tail):
        out[s] = cut + (1.0 - cut) * (j + 1) / (len(tail) + 1)
    return out


class MatchedHalfGuardPlaceboAllocator(HalfGuardAllocator):
    """M0202's guarded book filled by a blind draw of the bond book's own shape, under its own id.

    Everything but the order is ``HalfGuardAllocator``'s: the screen, the band, the quarterly
    calendar, the SPY filler and the half-size guard in both its speeds. Two things change. The
    order on a re-pick comes from ``matched_frac`` instead of ``ranked``. And the lookback rises to
    ``MATCHED_LOOKBACK``, because this control re-reads the bond ranking at the previous quarter's
    re-pick and ``loadings`` wants a year of weekly marks before whatever date it is given; the
    rise moves no window, since ``candidate_window`` floors at the member index's 1996-01-02 and
    SPY's 331st bar is 1994-05-19.
    """

    id = "M0202-A1"

    def lookback(self, params: Any) -> int:
        return max(super().lookback(params), MATCHED_LOOKBACK)

    def _run(self, prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: HalfGuardParams) -> tuple[Target, ...]:
        p = _check_control(p)
        if len(prepared.series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        stocks = [s for s in held if s != p.yb.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = matched_frac(prepared, members, data_date, held, p) if repick else {}
        out = choose(prepared.history, members, frac, data_date, held, p.yb)
        return out if full_size(prepared.history, data_date, p) else halved(out)


MATCHED = MatchedHalfGuardPlaceboAllocator()


def _vm(suffix: str, params: HalfGuardParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate, with the declaration of which recorded arm it replaces.

    It matters most on the third arm: ``PLC1-HALF-FAST`` resolves to ``Y20-HALF`` while its
    replacement resolves to ``Y20-HALF-FAST``, so a supersession rule that matched targets would
    retire nothing there. D17's rule is a declaration, and this is where it is made."""
    return Candidate(id=f"M0202-{suffix}", family="M0202", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_CONTROL_AMENDMENT = Amendment(
    added=AMENDED,
    why=(
        "The guarded placebo re-drawn to the bond book's own churn, because the recorded three "
        "trade about 2.25x the book each controls and the gaps were quoted against them"
    ),
    hypothesis=(
        "Written before any result. PLC1-HALF, PLC2-HALF and PLC1-HALF-FAST order the same "
        "scoreable names by a hash re-keyed every month, so the whole book is re-drawn at every "
        "quarterly re-pick while the bond book's own 40% keep band holds about fourteen of its "
        "twenty names; measured, they trade 2.25x, 2.25x and 2.25x the arms they control and turn "
        "over 2.01x, 1.99x and 1.91x, outside or at the edge of D17's refuse band. These three "
        "arms keep the frame, the guard and the seeds and change only where the re-key comes "
        "from: at each re-pick the blind draw replaces exactly as many names as the bond book's "
        "own band lets go, counted by re-reading M0197's bond ranking at this date and at the "
        "previous quarter's re-pick. The direction, pre-registered: a control that traded 2.25x "
        "was over-paying Gotrade's fees on about twelve entries a quarter instead of five or six, "
        "so an honestly-shaped replacement pays less and earns MORE, and every lead quoted "
        "against the old three NARROWS or REVERSES. Concretely, on the deposits (SPY TR 7.19% a "
        "year): Y20-HALF's 12.65% against PLC1-HALF's 11.30% is a 1.35 point lead that shrinks "
        "and may cross zero; against PLC2-HALF's 9.56% the 3.09 point lead shrinks; "
        "Y20-HALF-FAST's 12.14% against PLC1-HALF-FAST's 11.38% is a 0.76 point lead that is the "
        "likeliest of the three to reverse. The third arm is also re-aimed: PLC1-HALF-FAST is "
        "resolved today against Y20-HALF rather than Y20-HALF-FAST, and Y20-HALF-FAST-PLC1 puts "
        "the target's whole name in the control's so the margin is read against the arm it "
        "actually controls. Two seeds under the slow guard are kept deliberately, so the lead is "
        "read against a spread and not a single draw. Success for the amendment is only this: all "
        "three new arms land inside 0.80x-1.25x on trades and on turnover against the arm each "
        "resolves to. Whatever the margin then says is the finding and is reported as it comes; "
        "no seed is tuned and no arm is re-drawn for a better one."
    ),
    expected_failure=(
        "The shape may match and the leads may still move the other way, and if they do the cause "
        "is not fees but name identity: a blind book of twenty members drawn with the real book's "
        "churn still holds a different twenty, and over 1996-2015 the dev store's surviving "
        "members earned enough that a random slow-turning book can beat a bond-like book on luck "
        "alone -- PLC1-HALF's 11.30% against PLC2-HALF's 9.56% is already a 1.7 point spread "
        "between two draws of the same rule. Second, the match itself may miss on the fast guard "
        "rather than the slow one: HALF-FAST flips between full and half size far more often than "
        "HALF (2.71 turnover against 2.35 on the same 440 trades), those flips are resize trades "
        "the entry-count derivation does not control, and a blind book's weights sit differently "
        "under a halving than a bond book's. Third, the entry count is derived by re-reading the "
        "bond ranking at the previous quarter with today's member set, which the walk put at "
        "0.955 of the real book's entries rather than 1.00. If any arm lands outside the band the "
        "amendment has failed its own test and the number is recorded as the failure, not "
        "corrected."
    ),
    candidates=(
        _vm("Y20-HALF-PLC1", _p("placebo", "half", seed=1),
            "Placebo, shape-matched: the same scoreable names in a hash order (seed 1), re-drawn "
            "only as often as the bond book's own picks turn over, same half-size guard",
            supersedes=("M0202-PLC1-HALF",)),
        _vm("Y20-HALF-PLC2", _p("placebo", "half", seed=2),
            "Placebo, shape-matched: hash order seed 2, the same matched churn, same half-size "
            "guard",
            supersedes=("M0202-PLC2-HALF",)),
        _vm("Y20-HALF-FAST-PLC1", _p("placebo", "half-fast", seed=1),
            "Placebo, shape-matched: hash order seed 1, the same matched churn, under the fast "
            "guard",
            supersedes=("M0202-PLC1-HALF-FAST",)),
    ),
)


METHOD = Method(
    id="M0202",
    name=(
        "Bond-like stocks with a gentler crash guard: half the book stays invested below SPY's "
        "200-day average instead of all of it going to cash"
    ),
    family="stock-treasury-beta",
    source_kind="variation",
    source_ref="M0197 synthesis (Sera 20261017-1808); Treasury beta, caia.org/node/6853",
    parent_id="M0197",
    hypothesis=(
        "M0197's bond-like picks (the 20 screened members whose weekly returns rise most when the "
        "10-year Treasury yield falls, net of the market, re-picked quarterly with a 40% keep "
        "band, empty slots in SPY) beat every placebo seed and their own opposite without a "
        "switch (+12.5% a year on the deposits vs +8.8% to +11.9%, SPY +7.2%) but fell 62% in "
        "2008; behind the all-or-nothing SPY 200-day switch they fell 22% but trailed SPY by 3.3 "
        "points a year in 2009-2015 and led the switched placebo by under a point. The rate-beta "
        "papers are from the 2010s, so the dev window is before publication and any edge may have "
        "faded since. A gentler guard keeps half the bet on: full size while SPY closes above its "
        "200-day average, every target at half weight (rest cash) below it (HALF); and HALF-FAST, "
        "full size again as soon as SPY closes above its 50-day average. Holdings are kept and "
        "only resized when the guard flips. Controls under the same guard and frame: N20-HALF "
        "(rate-neutral, smallest absolute loading) and a hash-order placebo over the same "
        "scoreable names (two seeds under HALF, one under HALF-FAST). Fractional shares at "
        "Gotrade's real fees (monthly-hold-frac-gotrade) on the owner's monthly top-up. "
        "Success, written now: Y20-HALF or Y20-HALF-FAST beats total-return SPY on dev with a "
        "worst fall under the screen's 50% bar, a positive lead over SPY in 2009-2015, and beats "
        "its own same-guard placebo seeds by at least 2 points a year on the deposits."
    ),
    expected_failure=(
        "Halving exposure halves the switch's protection without restoring the ranking's edge: "
        "the 2008 fall of the bond-like book was led by the financials the 2007-08 fit put on the "
        "bond side (Fannie, Freddie, regional banks), and half of a 62% fall compounded through "
        "a year below the 200-day is still about 35-40%, past design section 1's 25% even if it "
        "clears the screen's 50%. In 2009-2015 the half-size book recovers only half as fast in "
        "the 2009 rebound and the 2010-11 dips, so it lands between Y20 (+7.0 points vs SPY) and "
        "Y20-SW (-3.3), likely near zero, and the placebo under the same guard rises with it, "
        "leaving the gap to the placebo near M0197's one point rather than two. HALF-FAST adds "
        "whipsaw trades at real fees around the 50-day. DSR at N about 130 needs a lead well "
        "above the placebo's; the survivorship check halved M0197's lead and is likely to do the "
        "same here. And from 2016 yields stopped falling and rose sharply in 2022, the regime a "
        "bond-like book suffers in, which dev cannot show."
    ),
    candidates=(
        _v("Y20-HALF", _p("bond", "half"),
           "The 20 members that rise most when the 10-year yield falls, half size below SPY's "
           "200-day average"),
        _v("Y20-HALF-FAST", _p("bond", "half-fast"),
           "The bond-like book, half size only while SPY is under both its 200-day and 50-day "
           "averages"),
        _v("N20-HALF", _p("neutral", "half"),
           "Contrast: the 20 members least moved by yield changes, same half-size guard"),
        _v("PLC1-HALF", _p("placebo", "half", seed=1),
           "Placebo: the same scoreable names in a fixed hash order (seed 1), same guard"),
        _v("PLC2-HALF", _p("placebo", "half", seed=2),
           "Placebo: hash order seed 2, same guard"),
        _v("PLC1-HALF-FAST", _p("placebo", "half-fast", seed=1),
           "Placebo: hash order seed 1 under the fast guard"),
    ),
    seen_keys=(
        "concept:treasury-beta",
        "concept:half-size-trend-guard",
    ),
    amendments=(MATCHED_CONTROL_AMENDMENT,),
)
