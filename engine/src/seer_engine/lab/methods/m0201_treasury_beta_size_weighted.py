"""M0201 — The bond-like book sized by company size: M0197's 20 picks weighted by real market
value under a 10% ceiling, instead of equal slots.

Source: variation of M0197 (Treasury beta; D.E. Shaw research note, caia.org/node/6853; Maio &
Santa-Clara; Driessen, Kuiper & Beilo). Reserved as an idea weighting by dollar volume; Sera
20261018-0517 sharpened it for the owner's theme "books shaped like the market": weight by real
point-in-time market value, one share class per company, a pre-registered ceiling, a dollar-volume
arm only as the bridge to M0122/M0198, and the meaningless control of the same shape.

Why. M0197's bond-like book beat its rate-rising opposite by about 5 points a year on the deposits
with no switch, but every book in that frame holds 20 equal slots, which leans toward the smaller
index members compared with SPY (insight 91), and SPY's big-company drift is the opponent from
2018. This method keeps M0197's picks byte for byte (its ``scored`` and banded quarterly
``choose``, imported unchanged) and moves money between them by company size, so the question is
whether the ranking's lead survives once the book is shaped like the market.

The sizing. At every monthly check each pick's weight is proportional to its size and the stock
weights sum to what the equal book holds (picks / 20): the dial moves money between names, never
changes how much is invested; unfilled slots stay in SPY as in M0197.

    * ``"mv"``: ``Market.market_value(symbol, data_date)``, shares outstanding as filed by that day
      times the close as it printed (``market_fields`` includes ``"shares"``). One value per
      company: when more than one listed class of one company is held (GOOG/GOOGL, FOX/FOXA,
      NWS/NWSA), each class answers the whole company's count times its own price, so the
      company is sized once (from the first held class that answers), the ceiling applies to the
      company, and its weight is split equally over its held classes.
    * ``"dv"``: mean close times volume over the last ``DV_N`` sessions (M0198's
      ``trading_value``), the old stand-in, kept as the bridge to the dollar-volume yardsticks.

A company whose size is unknown (no filed count, or a zero read) gets the median size of the
picks' companies that have one; with no known size at all they share the exposure equally. Then no name may hold
more than ``cap`` of the account (M0034's water-filling ``_apply_ceiling``: the excess goes to the
names still under it). The ceiling is 10% in every variant, written now: a ranking probe run
before this file was committed (the bond side's picks and their market values on re-pick dates,
no later returns) put up to 52% of an uncapped book in one name (MSFT, 2013-12-31) and the
effective name count at 3.5-15.

Known caveats of the size figure, written before any result: about one pick in ten has no value
(Fannie and Freddie through 2004, DTE, PCG, META in 2014) and takes the median; BRK.B's 2010-11
figure counts class A shares only, so it weighs far too little those years; companies tagging
their count per class in XBRL (Alphabet from 2014) go unknown and take the median.

Controls in the same frame: ``side="opp"`` (M0197's rate-rising side, the paired control) and
``side="placebo"``, M0202's hash order over exactly the names M0197's loadings could score that
day (M0187's ``draw``), sized the same way -- the meaningless book of the same shape.

Amendment 1 (2026-10-19), the shape-matched placebo. The two placebo seeds above trade 2.27x and
2.26x the book they control and turn over 2.13x and 2.12x it, so the gap they were quoted for was
read against an opponent paying twice the fees, and D17 refuses the method on it. The cause is the
re-key period, chosen by hand: M0187's ``draw`` is keyed on the month, so the whole book is re-drawn
at every quarterly re-pick, while the real book's 40% keep band holds a name unless it slips out of
the top 40% of the pool. ``Y20-MV10-PLC1`` and ``Y20-MV10-PLC2`` keep the frame, the sizing, the
ceiling and the seeds and derive the re-key from the bond book's own calendar instead: at each
re-pick the allocator re-reads M0197's bond ranking at this date and at the previous quarter's
re-pick, counts how many of that quarter's twenty are still under the band, and lets the blind draw
replace exactly the rest. Measured over the dev window's 79 re-picks before any of this ran: 423
entries against the real book's 443, a ratio of 0.955, where the recorded pair sits at 2.24. The
cost is the lookback -- 331 bars instead of 253, a year of weekly marks before the previous
re-pick -- which moves no window, because SPY's 331st bar is 1994-05-19 and the member index opens
1996-01-02.

Pure: picks, sizes and weights read only bars and filings dated <= ``data_date``. Every variant
sets ``trend`` explicitly (``FactorParams``' default is the SPY 200-day switch, M0188's slip).
Market-aware (``market_fields = ("series", "shares")``): the history-only path has no yield, so by
the contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at
Gotrade's real fees on the owner's monthly top-up.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.control_draw import matched_partition
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.lab.methods.m0197_treasury_yield_beta import (
    REPICK_MONTHS,
    STEP,
    WEEKS,
    YieldBetaParams,
    choose,
    loadings,
)
from seer_engine.lab.methods.m0197_treasury_yield_beta import scored as yb_scored
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 18)
DV_N = 63  # sessions in the dollar-volume read
SIDES = ("bond", "opp", "placebo")
SIZINGS = ("mv", "dv")

#: Listed classes of one company; each answers the whole company's count times its own price.
CLASS_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"GOOG", "GOOGL"}),
    frozenset({"FOX", "FOXA"}),
    frozenset({"NWS", "NWSA"}),
)


@dataclass(frozen=True, slots=True)
class SizedYieldBetaParams:
    """M0197's book (``yb``; its own ``side`` is unused, ``side`` here decides) plus the sizing.
    ``cap`` is an absolute per-name ceiling (0.10 = 10% of the account); ``seed`` the placebo's
    hash seed (0 and unused for the real rankings)."""

    yb: YieldBetaParams
    side: str = "bond"
    sizing: str = "mv"
    cap: float = 0.10
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.yb, YieldBetaParams):
            raise TypeError(f"yb must be YieldBetaParams, got {type(self.yb).__name__}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if self.sizing not in SIZINGS:
            raise ValueError(f"sizing must be one of {SIZINGS}, got {self.sizing!r}")
        if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
            raise TypeError(f"cap must be a number, got {type(self.cap).__name__}")
        if not (1.0 / self.yb.inner.top <= float(self.cap) <= 1.0):
            raise ValueError(f"cap must lie in [1/top, 1], got {self.cap}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be an int >= 0, got {self.seed!r}")
        if (self.side == "placebo") != (self.seed > 0):
            raise ValueError("a placebo needs a seed >= 1, and only a placebo takes one")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "sizing": self.sizing, "cap": repr(float(self.cap)),
               "seed": str(self.seed), "dv_n": str(DV_N),
               "class_groups": ";".join(",".join(sorted(g)) for g in CLASS_GROUPS)}
        for k, v in self.yb.as_dict().items():
            if k != "side":
                out[f"yb.{k}"] = v
        return out


def _check(params: object) -> SizedYieldBetaParams:
    if not isinstance(params, SizedYieldBetaParams):
        raise TypeError(f"params must be SizedYieldBetaParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class SizedPrepared:
    history: Mapping[str, History]
    series: MarketSeries
    factor: FactorPrepared | None
    market: Any  # the Market, for market_value; None on the history-only path


def ranked(history: Mapping[str, History], series: MarketSeries, rows: list[FactorRow],
           data_date: date, p: SizedYieldBetaParams) -> dict[str, float]:
    """Rank fractions in [0, 1), 0 first: M0197's for bond and opp, M0202's hash placebo over
    exactly the names M0197's loadings could score that day."""
    if p.side != "placebo":
        return yb_scored(history, series, rows, data_date, replace(p.yb, side=p.side))
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.yb.market)
    lv = loadings(history, series, pool, data_date, p.yb.market)
    order = sorted(lv, key=lambda s: (draw(p.seed, s, data_date), s))
    return {s: k / len(order) for k, s in enumerate(order)}


def company(symbol: str) -> str:
    """The key one company's listed classes share (the group's first symbol), else the symbol."""
    group = next((g for g in CLASS_GROUPS if symbol in g), None)
    return symbol if group is None else min(group)


def sizes(prepared: SizedPrepared, picks: list[str], data_date: date,
          p: SizedYieldBetaParams) -> dict[str, float]:
    """One size per company among the picks (0.0 = unknown): market value, read from the first
    held class that answers (every class answers the whole company), or summed trading value."""
    out: dict[str, float] = {}
    for s in picks:
        k = company(s)
        if p.sizing == "dv":
            out[k] = out.get(k, 0.0) + trading_value(prepared.history[s], data_date, DV_N)
            continue
        if out.get(k, 0.0) > 0.0:
            continue
        v = prepared.market.market_value(s, data_date)
        out[k] = float(v) if v is not None and np.isfinite(v) and v > 0.0 else 0.0
    return out


def sized_weights(raw: list[float], exposure: float, cap: float) -> list[Decimal | None]:
    """One weight per company, summing to ``exposure`` (the equal book's), unknown sizes at the
    median known size, then the ceiling. No known size: equal shares of ``exposure``."""
    if not raw:
        return []
    known = [x for x in raw if x > 0.0]
    med = float(np.median(known)) if known else 1.0
    size = np.array([x if x > 0.0 else med for x in raw], dtype=np.float64)
    w = _apply_ceiling(size / float(size.sum()) * exposure, cap)
    return [_floor_weight(float(x)) for x in w]


def resize(prepared: SizedPrepared, equal: tuple[Target, ...], data_date: date,
           p: SizedYieldBetaParams) -> tuple[Target, ...]:
    """M0197's equal-slot targets with the stock slots re-sized by company, the ceiling applied
    to each company, a company's weight split equally over its held classes, the rest in SPY."""
    market = p.yb.market
    picks = [t.symbol for t in equal if t.symbol != market]
    size = sizes(prepared, picks, data_date, p)
    keys = list(size)
    cw = sized_weights([size[k] for k in keys], len(picks) / p.yb.inner.top, float(p.cap))
    weight = dict(zip(keys, cw, strict=True))
    out: list[Target] = []
    for s in picks:
        w = weight[company(s)]
        if w is None:
            continue
        n = sum(1 for x in picks if company(x) == company(s))
        if n > 1:
            w = _floor_weight(float(w) / n)
            if w is None:
                continue
        t = target_from_close(s, last_close(prepared.history[s], data_date), w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - sum((t.weight for t in out), Decimal(0))
    mh = prepared.history.get(market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


class SizedYieldBetaAllocator:
    """M0197's screened, banded, quarterly book (bond-like, its opposite or a hash placebo), the
    picks sized by company size under a ceiling; slots left over in SPY. No yield: no targets."""

    id = "M0201"
    market_fields = ("series", "shares")

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).yb.inner), DV_N)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.yb.market}
        if p.yb.inner.trend is not None:
            fixed.add(p.yb.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).yb.market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizedYieldBetaParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0 or prepared.market is None:  # market-aware contract
            return ()
        inner = p.yb.inner
        if not trend_on(prepared.history, data_date, inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        stocks = [s for s in held if s != p.yb.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = ranked(prepared.history, prepared.series, rows, data_date, p) if repick else {}
        equal = choose(prepared.history, members, frac, data_date, held, p.yb)
        return resize(prepared, equal, data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no yield and no share counts, so no target."""
        return self._run(SizedPrepared(history, EMPTY_SERIES, None, None), members, data_date,
                         held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> SizedPrepared:
        return SizedPrepared(history, EMPTY_SERIES, prepare_factor(history), None)

    def prepare_market(self, market: Any) -> SizedPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return SizedPrepared(market.history, series, prepare_factor(market.history), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizedPrepared):
            raise TypeError(f"prepared must be SizedPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


SIZEDYB = SizedYieldBetaAllocator()

SW = ("SPY", 200)


def _p(side: str, sizing: str = "mv", trend: tuple[str, int] | None = None,
       seed: int = 0) -> SizedYieldBetaParams:
    # trend has no default here: FactorParams' own default is the SPY 200-day switch, and every
    # variant must say which it means (M0188's slip). The rank is unused: only the screen.
    yb = YieldBetaParams(FactorParams(rank="momentum", top=20, trend=trend))
    return SizedYieldBetaParams(yb, side=side, sizing=sizing, cap=0.10, seed=seed)


def _v(suffix: str, params: SizedYieldBetaParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0201-{suffix}", family="M0201", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SIZEDYB, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


# ------------------------------------------------------------------ amendment 1 (2026-10-19)
#
# The shape-matched placebo. See the module docstring for why the recorded pair trades 2.27x the
# book it controls; what follows is the repair. Nothing above this line changes: a new allocator
# id is the only safe way to add an arm, because `registry._canon` renders a params dataclass by
# `dataclasses.fields()` and a field added to `SizedYieldBetaParams` -- even a defaulted one --
# would move every recorded config_digest that used it.

AMENDED = date(2026, 10, 19)
PREV_SPAN = 70  # sessions in a quarter, with room for the longest one in the dev window
MATCHED_LOOKBACK = WEEKS * STEP + PREV_SPAN + 1  # 331: a year of weekly marks before the previous
                                                 # re-pick, which the matched draw re-reads
REAL_SIDE = "bond"  # the side of the book these two arms are the controls for


def _check_control(params: object) -> SizedYieldBetaParams:
    """``SizedYieldBetaParams``, plus the one thing a control's params may not say.

    The matched draw differs from ``PLC1-MV10`` and ``PLC2-MV10`` in its allocator id and in
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
    band, and there is no monthly entry count to match.
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


def real_frac_at(prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
                 p: SizedYieldBetaParams) -> dict[str, float]:
    """M0197's own bond-side rank fractions on ``data_date``, over ``members``.

    ``members`` is the set the allocator was handed for its own session and is used unchanged at
    the previous quarter: a control is never given the membership of a past date, and reading
    today's set backwards uses no data the session does not already have. It costs match quality
    and the cost was measured before this ran -- 0.955 against 1.0045 with the true historical
    sets -- and is paid so that M0201 and M0202, whose ``prepared`` types differ, run the identical
    rule.
    """
    inner = p.yb.inner
    if prepared.factor is None:
        rows = factor_rows(prepared.history, members, data_date, inner)
    else:
        rows = prepared.factor.rows_on(members, data_date, inner)
    return yb_scored(prepared.history, prepared.series, rows, data_date,
                     replace(p.yb, side=REAL_SIDE))


def matched_entries(prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
                    now: Mapping[str, float], p: SizedYieldBetaParams) -> int:
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


def matched_frac(prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
                 held: frozenset[str], p: SizedYieldBetaParams) -> dict[str, float]:
    """Rank fractions that drive M0197's ``choose`` to a blind book of the bond book's own shape.

    ``choose`` keeps a holding whose fraction is under ``keep_pct`` and fills the rest of the
    twenty slots from the top of the order, so a fraction below the band is an instruction to hold
    and one above it an instruction to enter. The names the matched draw keeps are laid out under
    the band in keep order, and every other name above it in the order the control would take it --
    ``matched_partition``'s ``tail``, which guarantees the names the control does not hold come
    before the holdings it is dropping, so a just-dropped name is never taken straight back.
    ``choose`` itself is called unchanged, so the band, the quarterly calendar, the ceiling, the
    sizing and the SPY filler are byte-identical to the arm this controls; the only thing that
    differs is which names fill the slots.
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
        tag="M0201",
        seed=p.seed,
        data_date=data_date,
    )
    out: dict[str, float] = {s: cut * (i + 1) / (len(keep) + 1) for i, s in enumerate(keep)}
    for j, s in enumerate(tail):
        out[s] = cut + (1.0 - cut) * (j + 1) / (len(tail) + 1)
    return out


class MatchedSizedPlaceboAllocator(SizedYieldBetaAllocator):
    """M0201's sized book filled by a blind draw of the bond book's own shape, under its own id.

    Everything but the order is ``SizedYieldBetaAllocator``'s: the screen, the band, the quarterly
    calendar, the sizing by company, the 10% ceiling and the SPY filler. Two things change. The
    order on a re-pick comes from ``matched_frac`` instead of ``ranked``. And the lookback rises to
    ``MATCHED_LOOKBACK``, because this control re-reads the bond ranking at the previous quarter's
    re-pick and ``loadings`` wants a year of weekly marks before whatever date it is given; the
    rise moves no window, since ``candidate_window`` floors at the member index's 1996-01-02 and
    SPY's 331st bar is 1994-05-19.
    """

    id = "M0201-A1"

    def lookback(self, params: Any) -> int:
        return max(super().lookback(params), MATCHED_LOOKBACK)

    def _run(self, prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizedYieldBetaParams) -> tuple[Target, ...]:
        p = _check_control(p)
        if len(prepared.series) == 0 or prepared.market is None:  # market-aware contract
            return ()
        inner = p.yb.inner
        if not trend_on(prepared.history, data_date, inner):
            return ()
        stocks = [s for s in held if s != p.yb.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = matched_frac(prepared, members, data_date, held, p) if repick else {}
        equal = choose(prepared.history, members, frac, data_date, held, p.yb)
        return resize(prepared, equal, data_date, p)


MATCHED = MatchedSizedPlaceboAllocator()


def _vm(suffix: str, params: SizedYieldBetaParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate, with the declaration of which recorded arm it replaces.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``): declared, never
    inferred from the target, and outside ``config_digest`` because ``config_text`` names its
    three attributes by hand. An arm that declares nothing retires nothing, so omitting it would
    leave M0201 blocked after the measurement was taken."""
    return Candidate(id=f"M0201-{suffix}", family="M0201", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_CONTROL_AMENDMENT = Amendment(
    added=AMENDED,
    why=(
        "The sized placebo re-drawn to the bond book's own churn, because the recorded pair "
        "trades 2.27x and 2.26x the book it controls and the gap was quoted against it"
    ),
    hypothesis=(
        "Written before any result. PLC1-MV10 and PLC2-MV10 order the same scoreable names by a "
        "hash re-keyed every month, so the whole book is re-drawn at every quarterly re-pick "
        "while Y20-MV10's own 40% keep band holds about fourteen of its twenty names; measured, "
        "they trade 2.27x and 2.26x it and turn over 2.13x and 2.12x it, outside D17's refuse "
        "band. These two arms keep the frame, the sizing, the 10% ceiling and the seeds and "
        "change only where the re-key comes from: at each re-pick the blind draw replaces exactly "
        "as many names as the bond book's own band lets go, counted by re-reading M0197's bond "
        "ranking at this date and at the previous quarter's re-pick. The direction, "
        "pre-registered: a control that traded 2.25x was over-paying Gotrade's fees on about "
        "twelve entries a quarter instead of five or six, so an honestly-shaped replacement pays "
        "less and earns MORE, and every lead quoted against the old pair NARROWS or REVERSES. "
        "Concretely, against Y20-MV10's 9.54% a year on the deposits (SPY TR 7.19%): PLC1-MV10's "
        "10.26% rises further, so the book's recorded -0.71 point deficit against seed 1 gets "
        "worse; PLC2-MV10's 8.06% rises, so the +1.48 point lead over seed 2 shrinks and may "
        "cross zero. The two-seed spread is kept deliberately, so the lead is read against a "
        "spread and not a single draw, and the spread already straddles the book before this "
        "runs. Success for the amendment is only this: both new arms land inside 0.80x-1.25x on "
        "trades and on turnover against Y20-MV10. Whatever the margin then says is the finding "
        "and is reported as it comes; no seed is tuned and no arm is re-drawn for a better one."
    ),
    expected_failure=(
        "The shape may match and the lead may still move the other way, and if it does the cause "
        "is not fees but name identity: a blind book of twenty members drawn with the real book's "
        "churn still holds a different twenty, and over 1996-2015 the dev store's surviving "
        "members earned enough that a random slow-turning book can beat a utilities-and-REITs "
        "book on luck alone -- seed 2's 8.06% against seed 1's 10.26% is already a 2.2 point "
        "spread between two draws of the same rule. Second, the match itself may miss: the "
        "entry count is derived by re-reading the bond ranking at the previous quarter with "
        "today's member set, which the walk put at 0.955 of the real book's entries, and the "
        "turnover axis carries an extra risk this trade-count derivation does not control -- "
        "M0201 re-sizes monthly by company size, and a blind book holds mega-caps the bond book "
        "never does, so its weight dispersion and its monthly resize trades differ even when its "
        "entries match. If either arm lands outside the band on turnover the amendment has failed "
        "its own test and the number is recorded as the failure, not corrected."
    ),
    candidates=(
        _vm("Y20-MV10-PLC1", _p("placebo", seed=1),
            "Placebo, shape-matched: the same scoreable names in a hash order (seed 1), re-drawn "
            "only as often as the bond book's own picks turn over, sized by market value",
            supersedes=("M0201-PLC1-MV10",)),
        _vm("Y20-MV10-PLC2", _p("placebo", seed=2),
            "Placebo, shape-matched: hash order seed 2, the same matched churn, sized by market "
            "value",
            supersedes=("M0201-PLC2-MV10",)),
    ),
)


METHOD = Method(
    id="M0201",
    name=(
        "The bond-like book sized by company size: the 20 stocks that rise most when yields fall, "
        "weighted by market value under a 10% ceiling instead of equal slots"
    ),
    family="stock-treasury-beta",
    source_kind="variation",
    source_ref=(
        "variation of M0197 (Treasury beta; D.E. Shaw research note, caia.org/node/6853); "
        "reserved by Sera 20261018-0517 for the theme 'books shaped like the market'"
    ),
    parent_id="M0197",
    hypothesis=(
        "M0197's bond-like book (the 20 screened members whose weekly returns rise most when the "
        "10-year yield falls, net of the market; quarterly re-picks, a 40% keep band, empty slots "
        "in SPY) beat its rate-rising opposite by about 5 points a year on the deposits without "
        "the switch (+12.5% vs +7.7%, SPY +7.2%, placebo M0187 +8.8% to +11.9%), but every book "
        "in that frame holds equal slots, a lean toward the smaller index members (insight 91), "
        "and SPY's big-company drift is the opponent. The rate-beta papers are from the 2010s, so "
        "the whole dev window is before publication. Keep M0197's picks exactly and weight each "
        "by its real point-in-time market value (shares as filed by that day times the close as "
        "it printed; held classes of one company are one company, sized once and capped "
        "together; an unknown size takes the median), capped at 10% of the account per company "
        "with the excess spread over the rest, stock "
        "weights summing to what the equal book holds, re-sized at every monthly check. "
        "Variants: Y20-MV10 (bond side, no switch), Y20-MV10-SW (behind the SPY 200-day switch), "
        "OPP-MV10 (the opposite side sized the same way, the paired control), Y20-DV10 (bond side "
        "sized by 63-day dollar volume instead, the bridge to M0122 and M0198), and PLC1-MV10, "
        "PLC2-MV10 (M0202's hash placebo over the same scoreable names, sized the same way: the "
        "meaningless book of the same shape). Fractional shares at Gotrade's real fees on the "
        "owner's monthly top-up. Reported beside the equal-weight M0197 rows, M0187 and M0198, "
        "with each variant's beta to SPY, on both the dev and the survivorship-check stores. "
        "Judged first on 2009-2015 against SPY, then the 2013 rate jump. Success: Y20-MV10 keeps "
        "a clear gap (2+ points a year on the deposits) over both OPP-MV10 and the sized "
        "placebo seeds, and does not trail SPY in 2009-2015."
    ),
    expected_failure=(
        "Sized by market value, the bond side becomes a book of its few biggest names at the 10% "
        "ceiling (the probe put the effective name count at 3.5-15; MSFT took 52% uncapped on "
        "2013-12-31, AAPL 36% on 2012-12-31), and the rest are utilities and REITs too small to "
        "matter, so it behaves like a handful of large defensives plus SPY. The equal-weight "
        "lean was part of M0197's lead (insight 91 and M0198's question), so the sized bond book "
        "loses 1-3 points a year against its equal twin and the gap to its opposite shrinks to "
        "the 1996-2008 falling-rate era; in 2009-2015 it trails SPY's tech-led rally, and the "
        "sized placebo seeds land within a point of it. Without the switch it falls about 45-55% "
        "in 2008 like every book in this frame; with the switch the worst fall drops near 20% "
        "but the switch sells the 2010 and 2011 dips. Re-sizing monthly to a drifting value adds "
        "small resize trades at Gotrade's minimums. DSR at N about 142 will not reach 0.90 unless "
        "the lead over the sized placebo is several points. The dollar-volume arm leans into the "
        "busiest names (1999-2000 tech) and differs from the market-value arm by more than the "
        "ranking does. From 2016 yields stopped falling and rose sharply in 2022, the regime a "
        "bond-like book suffers in, which dev cannot show; and the missing dead companies "
        "flattered M0197 by about half its lead, likely the same here."
    ),
    candidates=(
        _v("Y20-MV10", _p("bond"),
           "The bond-like 20, weighted by market value under a 10% ceiling, no switch"),
        _v("Y20-MV10-SW", _p("bond", trend=SW),
           "The size-weighted bond-like book behind the SPY 200-day switch"),
        _v("OPP-MV10", _p("opp"),
           "Control: the rate-rising 20, weighted by market value under a 10% ceiling, no switch"),
        _v("Y20-DV10", _p("bond", sizing="dv"),
           "The bond-like 20 weighted by 63-day dollar volume under a 10% ceiling, no switch"),
        _v("PLC1-MV10", _p("placebo", seed=1),
           "Placebo: the same scoreable names in a hash order (seed 1), sized by market value"),
        _v("PLC2-MV10", _p("placebo", seed=2),
           "Placebo: hash order seed 2, sized by market value"),
    ),
    seen_keys=(
        "concept:treasury-beta-size-weighted",
        "concept:market-value-weighting",
    ),
    amendments=(MATCHED_CONTROL_AMENDMENT,),
)
