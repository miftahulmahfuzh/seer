"""M0293 — Calmness as a safety filter on someone else's picks, not a ranking of its own.

Source: variation of M0283 / M0278 (Black, Jensen & Scholes 1972; Frazzini & Pedersen 2014,
Betting Against Beta, JFE 111(1)), applied to M0197-Y20-SW's book (D.E. Shaw's Treasury-beta
note, caia.org/node/6853).

Idea: M0278 and M0283 between them measured what the calm sort reliably buys and what it does
not. Against a blind draw of the same shape it bought about 7.5 points of shallower worst fall
and gains-vs-losses of 2.93 against 1.80 -- both steady when the draw's seed changes -- and at
most 0.56 points a year of return, which sits inside the 0.06-2.70 point seed-to-seed spread the
lab measured across nine seed-only draw groups. A quantity that is large and seed-stable on the
fall and unreadable on the return is a *safety filter*, not an engine; proximity to the 52-week
high showed the same signature. M0283 then proved the engine reading wrong from the other side:
every slice of SPY held beside the calm book earned less and fell further, monotonically, so
there is nothing to lever and nothing to blend. The remaining question is the filter one. Stop
ranking on calmness. Take a book that already leads SPY, throw away the jumpiest part of the
pool it picks from, and see whether the fall shrinks by more than the return does.

THE HOST, AND WHY (the whole risk of this method, named now). The lab's near misses that fail
on worst fall are momentum books, and their kin include four methods that have already lost
their test-window look, so a calm filter bolted to a momentum book can be informative and can
never be promoted. M0059 is exactly that cautionary case: it dropped the 10 or 20 highest-beta
names from a 40-name momentum pool, pulled the fall from 22.9-25.6% down to 19.8-20.9%, and its
verdict reads "softened the fall only by cutting the return". That verdict cannot be trusted,
because M0059 registered no blind-drop arm: dropping *any* ten names from a momentum pool costs
return too, and nobody measured it. This method does not repeat either mistake.

The host chosen is **M0197-Y20-SW**, the bond-like book: among F4-screened index members, one
shared yearly regression of 52 weekly log returns on SPY's and on the weekly change in the
10-year Treasury yield; hold the 20 names whose prices rise most when yields fall, equal slots,
re-ranked quarterly with a 40% keep band, behind the SPY 200-day switch, fractional shares at
Gotrade's real fees on the owner's monthly deposits. Four reasons:

  * it is **kin clean** -- `lab status` lists it as promotable now, so no family, ancestor,
    ingredient or behavioural twin of it has test-failed, and a win here is promotable;
  * it already **leads SPY** clearly: +11.8% a year on the owner's deposits against SPY's +7.2%,
    worst fall 22.0%, gains 3.08x losses, luck score 0.955, 3 of 4 walk-forward folds;
  * its **pool is deep** (every screened member, hundreds of names), so throwing away a quarter
    of it still leaves far more than 20 candidates and the book stays exactly 20 names, fully
    invested. That matters more than anything else here. On a thin pool -- the news-day book, the
    other promotable stock screen -- dropping names empties slots into SPY, and the lab has
    already been fooled by that twice: M0277 and M0279 ran six pick filters on the news-day book
    and all six lost, not because the filters were wrong but because they held 2-5 names where
    the unfiltered book held 13.6 and parked the rest in SPY through a rising decade. Here a drop
    changes **which** names, never **how many**, so the fall and the return move for one reason;
  * and the host **already computes the number this filter needs and throws it away**. Its
    yearly fit returns each member's market beta `b` alongside the yield loading `c`; the host
    ranks on `c` and discards `b`. This method keeps `b`. So the filter adds no new estimate, no
    new window and no new free parameter: it is the same regression, read twice.

M0197's own pre-registered fear is the reason to expect this to bite: on 2008-06-30 its fit put
Fannie Mae, Freddie Mac, KeyCorp, Fifth Third and REITs on the bond-like side at an average beta
of 2.0, and it named them as what would hurt the book in 2008.

The five arms. `drop_frac` is the share of the day's scored pool thrown away before ranking,
`side` says which end goes:

    ===========  ===========  ========  =========================================================
    arm          drop_frac    side      what it asks
    ===========  ===========  ========  =========================================================
    ``REF``      0            --        the host untouched: the no-opinion reference, which must
                                        reproduce M0197-Y20-SW's recorded trial bar for bar
    ``HI25``     0.25         high      drop the jumpiest quarter of the pool: the idea
    ``HI50``     0.50         high      drop the jumpiest half: the dose rung
    ``LO25``     0.25         low       drop the CALMEST quarter: the mirror
    ``BLIND25``  0.25         blind     drop the same count by a fixed per-symbol hash: the arm
                                        with no opinion in it, which prices the filter's habit
    ===========  ===========  ========  =========================================================

``BLIND25`` is the arm M0059 never registered and the one the lab's own audit says decides every
reversed pair: of 28 reversed pairs across 23 methods only 6 could be priced, because the other
22 left out the third arm. Its draw is **sticky** -- one hash per symbol, no date in the key --
because a stock's beta quartile is a slow-moving property and a re-drawn placebo churns about
fourteen times harder, which would price turnover rather than selection.

Dropped names lose their rank fraction, so a holding that drifts into the jumpy quarter falls
outside the 40% keep band at the next quarterly re-rank and is sold. That is the filter acting
on what is held as well as on what is bought, and it is the same rule in all five arms.

Pure: every read is M0197's -- bars dated <= data_date and the T10Y rows `MarketSeries.upto`
returns for that date -- plus a hash of the symbol. Market-aware (``market_fields = ("series",)``)
for the same reason the host is: with no yield series there is no fit, so no target.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0197_treasury_yield_beta import (
    REPICK_MONTHS,
    YieldBetaParams,
    YieldBetaPrepared,
    choose,
    loadings,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 23)

SIDES = ("high", "low", "blind")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class CalmFilterParams:
    """``inner`` is the host, term for term; the rest is the filter and nothing else.

    ``drop_frac`` is the share of the day's scored pool thrown away before the host ranks what
    is left. ``side`` is which end goes: the highest market betas ("high"), the lowest ("low",
    the mirror) or a fixed per-symbol hash order ("blind", the no-opinion arm). ``seed`` keys
    that hash and is read only when ``side == "blind"``.
    """

    inner: YieldBetaParams
    drop_frac: Decimal = Decimal("0")
    side: str = "high"
    seed: int = 293

    def __post_init__(self) -> None:
        if not isinstance(self.inner, YieldBetaParams):
            raise TypeError(f"inner must be YieldBetaParams, got {type(self.inner).__name__}")
        if not isinstance(self.drop_frac, Decimal) or not self.drop_frac.is_finite():
            raise TypeError(f"drop_frac must be a finite Decimal, got {self.drop_frac!r}")
        if not Decimal(0) <= self.drop_frac < Decimal(1):
            raise ValueError(f"drop_frac must be in [0, 1), got {self.drop_frac}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"drop_frac": str(self.drop_frac), "side": self.side, "seed": str(self.seed),
               "beta_from": "host-weekly-fit"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CalmFilterParams:
    if not isinstance(params, CalmFilterParams):
        raise TypeError(f"params must be CalmFilterParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the filter


def draw(seed: int, symbol: str) -> int:
    """A fixed, sticky number per symbol: no date in the key, so the blind drop set barely moves."""
    return int.from_bytes(hashlib.blake2b(f"{seed}|{symbol}".encode(), digest_size=8).digest(),
                          "big")


def drop_count(pool: int, drop_frac: Decimal) -> int:
    """How many of ``pool`` names go: ``pool * drop_frac`` rounded half up, never the whole pool."""
    if pool <= 0 or drop_frac <= 0:
        return 0
    k = int(Decimal(pool) * drop_frac + Decimal("0.5"))
    return min(k, pool - 1)


def survivors(lv: Mapping[str, tuple[float, float]], p: CalmFilterParams) -> dict[str, float]:
    """The pool's yield loadings with ``drop_frac`` of it removed; ``lv`` maps symbol -> (beta, c)."""
    k = drop_count(len(lv), p.drop_frac)
    if k <= 0:
        return {s: bc[1] for s, bc in lv.items()}
    if p.side == "high":
        order = sorted(lv, key=lambda s: (-lv[s][0], s))
    elif p.side == "low":
        order = sorted(lv, key=lambda s: (lv[s][0], s))
    else:
        order = sorted(lv, key=lambda s: (draw(p.seed, s), s))
    gone = set(order[:k])
    return {s: bc[1] for s, bc in lv.items() if s not in gone}


def filtered_frac(history: Mapping[str, History], series: MarketSeries, rows: list[Any],
                  data_date: date, p: CalmFilterParams) -> dict[str, float]:
    """The host's rank fraction over the surviving pool: 0 is the first name the book wants."""
    inner = p.inner
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != inner.market)
    lv = loadings(history, series, pool, data_date, inner.market)
    if not lv:
        return {}
    kept = survivors(lv, p)
    if not kept:
        return {}
    if inner.side == "bond":
        key = dict(kept)
    elif inner.side == "opp":
        key = {s: -c for s, c in kept.items()}
    else:
        key = {s: abs(c) for s, c in kept.items()}
    order = sorted(kept, key=lambda s: (key[s], s))
    return {s: k / len(order) for k, s in enumerate(order)}


# --------------------------------------------------------------------------- the allocator


class CalmFilterAllocator:
    """M0197's bond-like book, picking from a pool with one end of the market-beta sort removed.

    Everything but the filter is the host's: the screen, the shared yearly fit, the 20 equal
    slots, the 40% keep band, the quarterly re-rank, the SPY 200-day switch and SPY in any slot
    left over. With ``drop_frac = 0`` nothing is removed and the book is the host exactly.
    """

    id = "M0293"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner.inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        inner = _check(params).inner
        fixed = {inner.market}
        if inner.inner.trend is not None:
            fixed.add(inner.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).inner.market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: CalmFilterParams) -> tuple[Target, ...]:
        inner = p.inner
        if len(prepared.series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, inner.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner.inner)
        stocks = [s for s in held if s != inner.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = filtered_frac(prepared.history, prepared.series, rows, data_date, p) if repick else {}
        return choose(prepared.history, members, frac, data_date, held, inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no yield, so no fit, no ranking and no target."""
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


CALMFILTER = CalmFilterAllocator()

SW = ("SPY", 200)
# M0197-Y20-SW term for term: F4's screen, 20 names, the SPY 200-day switch, the bond-like end,
# the 40% keep band. The rank field is unused by the host; only the screen is read.
HOST = YieldBetaParams(FactorParams(rank="momentum", top=20, trend=SW), side="bond")


def _v(suffix: str, drop_frac: Decimal, side: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0293-{suffix}", family="M0293", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CALMFILTER,
                     params=CalmFilterParams(HOST, drop_frac=drop_frac, side=side),
                     rationale=rationale, added=ADDED, owner_inputs=())


# --------------------------------------------------------------------------- amendment 1

# The run with the switch on answered the question it was asked and raised a sharper one. Every
# arm got the identical +34.8% lead in 2008, because the SPY 200-day switch had already taken the
# whole book to cash -- so the one crash in the window was spent out of the market and the calm
# filter's safety claim was never put in front of a falling tape at all. The 22.0% -> 20.3% the
# quarter-drop bought was bought somewhere else entirely. `lab run` said the same thing from its
# own side: the HI25/LO25 mirror pair cannot be priced while no arm of this method is ever fully
# invested. This block re-runs the whole experiment with the switch off, where 2008 is live.

NOSW = YieldBetaParams(FactorParams(rank="momentum", top=20, trend=None), side="bond")


def _a(suffix: str, drop_frac: Decimal, side: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0293-{suffix}", family="M0293", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CALMFILTER,
                     params=CalmFilterParams(NOSW, drop_frac=drop_frac, side=side),
                     rationale=rationale, added=date(2026, 10, 23), owner_inputs=())


GATE_OFF = Amendment(
    added=date(2026, 10, 23),
    why=(
        "With the SPY 200-day switch on, all five arms sat in cash through 2008 and scored the "
        "identical +34.8% lead there, so the one crash in the dev window never tested the filter. "
        "These four arms are the same 2x2 with the switch off, where the crash is live."
    ),
    hypothesis=(
        "A safety filter has to be judged against a falling tape, and the first run never showed "
        "it one. Every arm of M0293 sits behind M0197's SPY 200-day switch, every arm was "
        "therefore in cash through 2008, and all five scored the same +34.8% lead in that year to "
        "the decimal -- the switch's doing, not the filter's. So the 22.0% to 20.3% the "
        "quarter-drop bought came from somewhere other than crash protection, and whether "
        "calmness protects anything is still unmeasured. These four arms are the first four with "
        "the switch set to None and nothing else changed: REF-NOSW, HI25-NOSW, LO25-NOSW and "
        "BLIND25-NOSW. The host's own gate-off twin is already recorded as M0197-Y20 (worst fall "
        "62.1%, +12.5% a year on the deposits, luck score 0.732), so REF-NOSW has a reference to "
        "reproduce exactly as REF had. None of these four can be a candidate -- a book that falls "
        "sixty per cent is nowhere near the owner's 25% bar -- and none is meant to be. They are "
        "evidence about one question. Predictions, written before the run: REF-NOSW reproduces "
        "M0197-Y20 bar for bar, and if it does not the block is void and the analysis says so; "
        "HI25-NOSW's worst fall is at least 8 points shallower than REF-NOSW's 62.1%, because "
        "M0197's own 2008 fit put Fannie Mae, Freddie Mac, KeyCorp and Fifth Third on the "
        "bond-like side at an average beta of 2.0 and the jumpiest quarter is exactly where they "
        "sit; HI25-NOSW's fall is at least 4 points shallower than BLIND25-NOSW's, without which "
        "the shrink is the swapping and not the calmness; and LO25-NOSW falls deeper than "
        "REF-NOSW. If HI25-NOSW does not beat BLIND25-NOSW on the fall, then calmness is not a "
        "safety filter on this host and the gate-on result was an accident of which names the "
        "quarterly band happened to hold."
    ),
    expected_failure=(
        "A trailing one-year beta is backward-looking and a crash is forward-looking, so the "
        "names that destroyed 2008 may still have read calm in 2007: Fannie Mae and the regional "
        "banks spent 2006 and most of 2007 moving less than the market, and their beta only "
        "caught up after the damage. If so the filter leaves them in, every arm falls about sixty "
        "per cent together, and the honest answer is that market beta measured over the year "
        "before a crash does not see the crash coming. The second way this fails is the opposite "
        "and just as instructive: HI25-NOSW's fall shrinks, but BLIND25-NOSW's shrinks as much, "
        "because dropping any quarter of a pool of several hundred names moves a 20-name book off "
        "its concentrated corner and diversification alone buys the points. Third, with the "
        "switch off the book is a utilities-and-REITs portfolio through a falling-rate window, so "
        "the gate-off arms may differ mostly in how much REIT they held into 2008, which is a "
        "sector accident and not a statement about beta. None of these is a reason to change the "
        "quarter, the half or the host afterwards."
    ),
    candidates=(
        _a("REF-NOSW", Decimal("0"), "high",
           "Nothing dropped, switch off: the gate-off reference, which must reproduce M0197-Y20"),
        _a("HI25-NOSW", Decimal("0.25"), "high",
           "Drop the jumpiest quarter with the switch off: the idea, finally shown a crash"),
        _a("LO25-NOSW", Decimal("0.25"), "low",
           "Drop the calmest quarter with the switch off: the mirror, which must move the other way"),
        _a("BLIND25-NOSW", Decimal("0.25"), "blind",
           "Drop the same count blindly with the switch off: what dropping any quarter buys in a crash"),
    ),
)


# --------------------------------------------------------------------------- amendment 2

# Both headline numbers rest on ONE blind draw. With the switch on, HI25 fell 3.2 points less
# than BLIND25; with it off, HI25-NOSW lost 9.6 points less in 2008 than BLIND25-NOSW. A single
# hash is a single coin toss, and the lab has just been reminded that one coin toss is not a
# control when the thing being measured may be smaller than one coin toss. These six arms are
# three more blind draws on each side of the switch. They put a spread on the control and can
# only confirm the claim or withdraw it.


def _s(suffix: str, inner: YieldBetaParams, seed: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0293-{suffix}", family="M0293", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CALMFILTER,
                     params=CalmFilterParams(inner, drop_frac=Decimal("0.25"), side="blind",
                                             seed=seed),
                     rationale=rationale, added=date(2026, 10, 23), owner_inputs=())


BLIND_SPREAD = Amendment(
    added=date(2026, 10, 23),
    why=(
        "Both headline gaps are measured against a single blind draw. These are three more draws "
        "on each side of the switch, so the control gets a spread instead of a point."
    ),
    hypothesis=(
        "The two numbers this method rests on are differences against ONE blind draw: with the "
        "switch on the calm quarter-drop fell 3.2 points less than the blind quarter-drop (20.3% "
        "against 23.5%), and with the switch off it lost 9.6 points less in 2008 (−24.5% against "
        "−34.1%). One hash is one coin toss. The lab already knows that a blind-draw lead on "
        "RETURN under about 1.5 points a year is unreadable because the seed alone moves a "
        "twenty-year return by 0.06 to 2.70 points, and it believes the worst fall and the "
        "gains-to-losses ratio are the seed-stable readings -- but believes is not measures, and "
        "nobody has put a spread on a blind drop of a POOL, which is a different operation from "
        "a blind draw of a BOOK. Three more seeds on each side: 294, 295 and 296, drop fraction "
        "and everything else untouched. Predictions, written before the run: across the four "
        "gate-on blind draws the worst fall spans less than 2 points, so the 3.2-point margin "
        "survives with room; across the four gate-off blind draws the 2008 calendar loss spans "
        "less than 4 points, so the 9.6-point margin survives with room; and the four gate-on "
        "draws' yearly money returns span MORE than the 1.2 points the calm arm trails by, "
        "confirming that the return cost is unreadable while the fall saving is not. If a blind "
        "spread covers either margin, that margin is withdrawn in the analysis, in those words, "
        "and the method's claim shrinks to whatever is left."
    ),
    expected_failure=(
        "The sticky draw is the reason this could go either way. One hash per symbol with no date "
        "in it means a seed does not just reshuffle the order, it decides for the whole twenty "
        "years which quarter of the universe this book may never own -- so an unlucky seed can "
        "quietly bar most of the utilities, or most of the banks, for the entire window. That is "
        "a far heavier draw than a re-drawn monthly placebo, and the spread may be correspondingly "
        "wide: wide enough to swallow 3.2 points of worst fall, in which case the gate-on half of "
        "this method is withdrawn and only the 2008 result stands. The second way it disappoints "
        "is the reverse: all four draws land on top of each other because a quarter of several "
        "hundred names is a large enough sample that which quarter barely matters, in which case "
        "the control is tight, the margins stand, and the lab learns that a pool drop is much "
        "quieter than a book draw. Either answer is worth the arms; neither is a reason to change "
        "the drop fraction or the host afterwards."
    ),
    candidates=(
        _s("BLIND25-S2", HOST, 294, "A second blind quarter, switch on"),
        _s("BLIND25-S3", HOST, 295, "A third blind quarter, switch on"),
        _s("BLIND25-S4", HOST, 296, "A fourth blind quarter, switch on"),
        _s("BLIND25-NOSW-S2", NOSW, 294, "A second blind quarter, switch off, where 2008 is live"),
        _s("BLIND25-NOSW-S3", NOSW, 295, "A third blind quarter, switch off"),
        _s("BLIND25-NOSW-S4", NOSW, 296, "A fourth blind quarter, switch off"),
    ),
)


METHOD = Method(
    id="M0293",
    name="Calmness as a safety filter on someone else's picks, not a ranking of its own",
    family="stock-market-beta",
    source_kind="variation",
    source_ref=(
        "variation of M0283 / M0278 (Black, Jensen & Scholes 1972; Frazzini & Pedersen 2014, "
        "Betting Against Beta, JFE 111(1)) applied as a filter to M0197-Y20-SW's book (D.E. Shaw "
        "Treasury-beta note, caia.org/node/6853); the blind-drop arm M0059 never registered"
    ),
    parent_id="M0283",
    hypothesis=(
        "M0283 measured what the calm sort reliably buys and what it does not. Against a blind "
        "draw of the same shape it bought 7.5 points of shallower worst fall and gains-vs-losses "
        "of 2.93 against 1.80, both steady when the draw's seed changes, and at most 0.56 points "
        "a year of return, which sits inside the 0.06-2.70 point seed-to-seed spread measured "
        "across the lab's nine seed-only draw groups -- so the return advantage is unreadable "
        "rather than small. That is the signature of a safety filter, not an engine, the same "
        "shape proximity-to-the-52-week-high showed; and M0283 closed the engine reading from "
        "the other side, since every slice of SPY held beside the calm book earned less and fell "
        "further, monotonically. So stop ranking on calmness and start filtering with it. "
        "CHOOSING THE HOST IS THE WHOLE RISK, so it is named and argued here. The host is "
        "M0197-Y20-SW, the bond-like book: among F4-screened members, one shared yearly fit of 52 "
        "weekly log returns on SPY's and on the weekly change in the 10-year Treasury yield; hold "
        "the 20 names that rise most when yields fall, equal slots, re-ranked quarterly with a "
        "40% keep band, behind the SPY 200-day switch, fractional at Gotrade's real fees on the "
        "owner's monthly top-up. It was chosen for four reasons: (1) lab status lists it as "
        "promotable now, so no family, ancestor, ingredient or behavioural twin of it has "
        "test-failed and a win here can actually be promoted -- unlike M0059, which ran this very "
        "filter on a momentum book whose kin have already lost four looks; (2) it leads SPY "
        "clearly, +11.8% a year on the deposits against +7.2%, worst fall 22.0%, gains 3.08x "
        "losses, luck score 0.955, 3 of 4 folds; (3) its pool is every screened member, hundreds "
        "of names, so dropping a quarter still leaves far more than 20 candidates and the book "
        "stays exactly 20 names fully invested -- a drop changes WHICH names, never HOW MANY, "
        "which is the confound that sank M0277's and M0279's six pick filters on the thin "
        "news-day pool, where every filter emptied slots into SPY through a rising decade; and "
        "(4) the host already computes the market beta this filter needs and throws it away -- "
        "its fit returns beta and the yield loading together and ranks on the loading alone -- so "
        "the filter adds no new estimate, no new window and no new free parameter. M0197's own "
        "pre-registered fear is why it should bite: on 2008-06-30 its fit put Fannie Mae, Freddie "
        "Mac, KeyCorp, Fifth Third and REITs on the bond-like side at an average beta of 2.0. "
        "Five arms, all on the host's exact configuration: REF (nothing dropped, the no-opinion "
        "reference, which must reproduce M0197-Y20-SW bar for bar); HI25 (drop the jumpiest "
        "quarter of the pool before ranking, the idea); HI50 (drop the jumpiest half, the dose "
        "rung); LO25 (drop the CALMEST quarter, the mirror); and BLIND25 (drop the same count by "
        "a fixed per-symbol hash, the arm with no opinion in it, which prices what dropping any "
        "quarter costs). The blind draw is sticky, one hash per symbol with no date in the key, "
        "because a beta quartile is a slow-moving property and a re-drawn placebo churns about "
        "fourteen times harder and would price turnover instead of selection. BLIND25 is the arm "
        "M0059 never registered, which is why its verdict -- 'softened the fall only by cutting "
        "the return' -- cannot distinguish a calm filter from the plain arithmetic of swapping a "
        "quarter of the names. Predictions, written now, on returns with the deposits taken out: "
        "REF reproduces M0197-Y20-SW's recorded trial (same return, same trade count), and if it "
        "does not the whole comparison is void and the analysis says so; HI25's worst fall is at "
        "least 2 points below REF's 22.0%; HI50's fall is no deeper than HI25's, so the dose is "
        "monotone; HI25 gives up less than 1 point a year of funded return against REF, so the "
        "fall shrinks by more than the return does; HI25 beats BLIND25 on the worst fall by at "
        "least 1.5 points, without which the shrink was the swapping and not the calmness; and "
        "LO25 falls deeper than REF. Success for the gate: a filtered arm still beats total-return "
        "SPY with gains at least 1.3x losses and a luck score of 0.90 or better, at a shallower "
        "fall than REF and with a positive 2009-2015 edge."
    ),
    expected_failure=(
        "The likeliest failure is that the dial is simply inert, and for a reason the host "
        "already wrote down: M0197's own ranking probe found the correlation between a member's "
        "market beta and its yield loading running from -0.41 to 0.20 across years, negative in "
        "most of them. Negative means the bond-like end of the pool is ALREADY the calm end, so "
        "the jumpiest quarter is made of names the book was never going to buy, and all five arms "
        "land within a point of each other. That would be a real finding -- the host has done its "
        "own filtering -- but not a win. Second, the host's 22.0% fall is what is LEFT after the "
        "SPY 200-day switch, so most of it is the market's own fall during the weeks before a "
        "monthly switch reads, and no pick filter can touch that; the lab has measured the same "
        "thing on the news-day book, where better picks never moved a switch-shaped fall. Third, "
        "the one episode where the filter should earn its keep, 2008, is the one where a trailing "
        "beta is least likely to work: by mid-2008 Fannie, Freddie and the regional banks had not "
        "yet collapsed, so their trailing one-year beta may still read near one and the filter "
        "would leave them in. A backward-looking safety measure against a forward-looking crash "
        "is the standard way this kind of filter disappoints. Fourth, HI50 tilts the book hard "
        "into utilities and REITs, which is precisely the 2013 taper-scare exposure M0197 feared, "
        "so the dose rung may fall FURTHER in 2013-2015 and lose the 2009-2015 era outright -- "
        "and 2009-2015 is the lab's first filter, the best-covered years and the ones most like "
        "today. Fifth, BLIND25 may match HI25: with a deep pool of mostly bond-like names, "
        "removing any quarter leaves twenty near-identical utilities and the blind arm reproduces "
        "the idea arm, which is the equal-weight-placebo trap insight 462 caught. Sixth, "
        "betting against beta was published in 2014, at the very end of the dev window, so a "
        "strong dev result here is likely to have faded -- though the lab's own evidence is that "
        "the calm sort's SAFETY half survived the dead companies being put back, and the safety "
        "half is all this method asks for. None of these is a reason to tune the quarter, the "
        "half, the 252-session fit or the host after the fact."
    ),
    candidates=(
        _v("REF", Decimal("0"), "high",
           "Nothing dropped: the host untouched, the no-opinion reference every other arm is read "
           "against, and the check that this chassis reproduces M0197-Y20-SW"),
        _v("HI25", Decimal("0.25"), "high",
           "Drop the jumpiest quarter of the day's scored pool before ranking: the idea"),
        _v("HI50", Decimal("0.5"), "high",
           "Drop the jumpiest half: the dose rung, so the response is a slope and not a pair"),
        _v("LO25", Decimal("0.25"), "low",
           "Drop the calmest quarter instead: the mirror, which must move the other way"),
        _v("BLIND25", Decimal("0.25"), "blind",
           "Drop the same count by a fixed per-symbol hash: the arm with no opinion in it, which "
           "prices what dropping any quarter costs"),
    ),
    amendments=(GATE_OFF, BLIND_SPREAD),
    seen_keys=(
        "concept:market-beta-as-a-safety-filter-on-a-host-book",
        "concept:drop-jumpiest-quartile-of-the-scored-pool",
        "concept:blind-drop-control-for-a-pick-filter",
    ),
)
