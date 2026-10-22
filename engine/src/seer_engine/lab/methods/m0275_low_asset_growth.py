"""M0275 — Companies that stopped growing their balance sheet: the index members whose total assets
grew least over the past year.

Source: Cooper, Gulen & Schill (2008), "Asset Growth and the Cross-Section of Stock Returns",
Journal of Finance 63(4) 1609-1651; Fama & French (2015), the CMA ("conservative minus aggressive"
investment) factor; McLean & Pontiff (2016) on post-publication decay. Reserved by Sera batch
20261022-1918 as an ``idea`` row; this file refines it and keeps its id.

WHY. The paper finds that a firm's year-on-year growth in total assets predicts its next year's
return with a negative sign, in big companies as well as small: firms that bulk up (acquisitions,
stock and debt issues, capital spending sprees) go on to disappoint, and firms that stand still or
shrink do better. The usual reading is that investors extrapolate the growth and over-pay for it.
Critics answer that much of the spread lives in small stocks, in missing delisting returns and in
firms that have just raised capital -- which is why this method runs only on index members, is
read first on the survivorship-check store, and is compared with the buyback book's own picks.

THE SIGNAL, POINT IN TIME. On each monthly check, for every index member with a bar dated
``data_date``, read the ``assets`` instant facts of the SEC panel that were *filed* on or before
``data_date`` (``SymbolFundamentals`` selects by filed date, never by period end; a restatement
replaces a figure only from the day it was filed). Take the newest balance-sheet date visible, P,
and the balance-sheet date nearest to P minus 365 days, accepted only within 20 days of it -- in
practice the same fiscal quarter a year earlier. Growth is the ratio of the two figures, minus one.
A member is not scored when its newest balance sheet is over 200 days older than ``data_date``
(the company stopped filing in the panel), when no year-earlier balance is visible, when either
figure is not positive, or when the ratio sits outside 0.2-5.0: a fivefold jump in a year is a
filing stated in thousands next to one in units far more often than a real deal, and a deal that
large is not what the paper ranks on either. Two members answering the identical asset figure for
the identical balance-sheet date are one company listed twice (GOOG/GOOGL); only the one with the
larger 60-session trading value is kept.

THE CALENDAR, MEASURED ON THE DEV STORE BEFORE THIS FILE WAS WRITTEN (members with a bar, scored
under the rule above, at quarter-ends; pool counts only, no returns were looked at):

    2009-07   4     2010-01  38     2010-07 104     2011-01 280     2012-01 341
    2009-10  25     2010-04 166     2010-10 272     2011-07 295     2013-2015 350-386

The panel starts in 2009 and large filers' XBRL began with periods after mid-2009, so a same-quarter
comparison a year apart exists for most members only from the third quarter of 2010. ``START`` is
therefore the first decision on or after 2010-10-01, where the pool first holds over 250 names and
stays there. The median member grew its assets 4-8% a year over 2011-2015; the bottom tenth shrank
2-8% and the top tenth grew 18-28%.

BEFORE ``START`` EVERY ARM HOLDS SPY, ungated (M0153's rule and for the same reason): the dev row
covers 1996-2015 whether the signal exists or not, so holding the yardstick until it does makes the
whole-window row differ from SPY only from October 2010, deposits and Gotrade's fees included. The
whole-window row then fails the worst-fall screen on SPY's own 2008 fall; that is the yardstick's
fall, not the picker's, and the analysis says so. The measure that matters is the de-funded monthly
curve from 2010-10 to 2015-10 beside SPY's on the same slice.

ARMS, one scored pool, equal slots, fully invested, monthly, no switch:

    L30       the 30 members with the LOWEST asset growth -- the paper's long side
    H30       the 30 with the HIGHEST -- the opposite book the paper says lags
    L30-PLC   placebo: L30's own size and entry count drawn blind from the same pool
              (``lab.control_draw``'s matched draw), so it pays L30's fees and knows nothing
    L60       the 60 lowest: broader, closer to the market, a dose check on L30

L30 against H30 says whether the signal is real in these years; L30 against L30-PLC prices acting
on it, because the placebo is the same book with the opinion removed (the third arm the lab's
mirror rule asks for). No variant steps aside, so there is no gate habit to price with a 2x2.

UNPROMOTABLE BY CONSTRUCTION, AND RUN ANYWAY. The hard gate wants a majority of at least four
scoreable walk-forward folds; a 1996 curve yields three and only the last one sees a pick. The
question this method answers -- does the best-known investment anomaly pay among big US companies
in the years most like today? -- decides whether older fundamentals are worth buying, and it is
asked once, at the cost of one method id. The panel covers about a quarter of the dev window, so
``lab run`` must be told so (``--allow-coverage``) and prints the coverage table.

Market-aware (``market_fields = ("fundamentals",)``). Rules are ``monthly-hold-frac-gotrade``:
fractional shares at Gotrade's real fees on the owner's monthly top-up. Pure: reads only bars dated
on or before ``data_date`` and facts filed on or before it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.fundamentals import ASSETS, KIND_INSTANT
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0130_tree_ranker import _bench
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED

ADDED = date(2026, 10, 22)
START = date(2010, 10, 1)  # first decision the signal is read on; SPY held before it
YEAR_DAYS = 365  # the comparison balance sheet sits this far before the newest one...
PRIOR_TOLERANCE_DAYS = 20  # ...within this many days
MAX_STALE_DAYS = 200  # newest balance sheet older than this: the member is not scored
RATIO_BAND = (0.2, 5.0)  # a one-year asset ratio outside this is read as a units error
DV_N = 60  # sessions of trading value that decide which listing of one company stays
SIDES = ("low", "high", "control")


@dataclass(frozen=True, slots=True)
class AssetGrowthParams:
    """``top`` names held; ``side`` low, high or control (the matched-draw placebo of the low book);
    ``seed`` the placebo's hash seed."""

    top: int
    side: str = "low"
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"top": str(self.top), "side": self.side, "seed": str(self.seed),
               "start": START.isoformat(), "year_days": str(YEAR_DAYS),
               "prior_tolerance_days": str(PRIOR_TOLERANCE_DAYS),
               "max_stale_days": str(MAX_STALE_DAYS),
               "ratio_band": f"{RATIO_BAND[0]!r}:{RATIO_BAND[1]!r}", "dv_n": str(DV_N),
               "class_rule": "identical-assets-and-period", "before_start": "SPY"}
        if self.side == "control":
            out["control_rule"] = control_draw.RULE_ID
        return out


def _check(params: object) -> AssetGrowthParams:
    if not isinstance(params, AssetGrowthParams):
        raise TypeError(f"params must be AssetGrowthParams, got {type(params).__name__}")
    return params


def asset_growth(panel: Any, symbol: str, data_date: date) -> tuple[float, date, float] | None:
    """(one-year growth in total assets, the newest balance-sheet date, its assets), or None."""
    sf = panel.get(symbol)
    if sf is None:
        return None
    best = sf._best_by_period(ASSETS, KIND_INSTANT, data_date)
    if not best:
        return None
    newest = max(best)
    if (data_date - newest).days > MAX_STALE_DAYS:
        return None
    target = newest - timedelta(days=YEAR_DAYS)
    near = [p for p in best if p != newest and abs((p - target).days) <= PRIOR_TOLERANCE_DAYS]
    if not near:
        return None
    prior = min(near, key=lambda p: (abs((p - target).days), p))
    a1, a0 = best[newest][0].val, best[prior][0].val
    if not (math.isfinite(a1) and math.isfinite(a0) and a1 > 0.0 and a0 > 0.0):
        return None
    ratio = a1 / a0
    if not RATIO_BAND[0] < ratio < RATIO_BAND[1]:
        return None
    return ratio - 1.0, newest, a1


@dataclass(frozen=True, slots=True, eq=False)
class AssetGrowthPrepared:
    history: Mapping[str, History]
    panel: Any  # the Market's fundamentals panel, or None on the history-only path


def scored_pool(prepared: AssetGrowthPrepared, members: AbstractSet[str],
                data_date: date) -> dict[str, float]:
    """The asset-growth score of every member that can be held on ``data_date``, one per company."""
    if prepared.panel is None:
        return {}
    by_company: dict[tuple[date, float], tuple[float, str, float]] = {}
    for s in sorted(members):
        if s in EXCLUDED:
            continue
        h = prepared.history.get(s)
        if h is None or h.index_of(data_date) is None:
            continue
        read = asset_growth(prepared.panel, s, data_date)
        if read is None:
            continue
        growth, newest, assets = read
        dv = trading_value(h, data_date, DV_N)
        seen = by_company.get((newest, assets))
        if seen is None or (dv, s) > (seen[0], seen[1]):
            by_company[(newest, assets)] = (dv, s, growth)
    return {s: g for _, s, g in by_company.values()}


def ranked(pool: Mapping[str, float], side: str) -> list[str]:
    """``pool`` lowest growth first (``low``) or highest first (``high``), ties by symbol."""
    if side == "high":
        return sorted(pool, key=lambda s: (-pool[s], s))
    return sorted(pool, key=lambda s: (pool[s], s))


class AssetGrowthAllocator:
    """SPY before ``START``. From it: the ``top`` members with the lowest (or highest) one-year growth
    in total assets, or a matched blind draw of the low book from the same pool; equal slots, fully
    invested. No fundamentals (history-only path): SPY before ``START``, nothing after."""

    id = "M0275"
    market_fields = ("fundamentals",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return control_draw.lookback_for(DV_N) if p.side == "control" else DV_N

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _select(self, prepared: AssetGrowthPrepared, members: AbstractSet[str], data_date: date,
                p: AssetGrowthParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the scored pool, the low book) on ``data_date`` -- what the control is matched to."""
        pool = scored_pool(prepared, members, data_date)
        if not pool:
            return (), ()
        return tuple(sorted(pool)), tuple(ranked(pool, "low")[: p.top])

    def _run(self, prepared: AssetGrowthPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: AssetGrowthParams) -> tuple[Target, ...]:
        if data_date < START:
            return _bench(prepared.history, data_date)
        if prepared.panel is None:
            return ()
        if p.side == "control":
            names = control_draw.matched_book(
                lambda d: self._select(prepared, members, d, p),
                data_date, held, tag="M0275", seed=p.seed,
            )
        else:
            pool = scored_pool(prepared, members, data_date)
            names = ranked(pool, p.side)[: p.top]
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no filings, so SPY before ``START`` and no target after it."""
        return self._run(AssetGrowthPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> AssetGrowthPrepared:
        return AssetGrowthPrepared(history, None)

    def prepare_market(self, market: Any) -> AssetGrowthPrepared:
        panel = getattr(market, "fundamentals", None)
        if panel is None or len(panel) == 0:
            return AssetGrowthPrepared(market.history, None)
        return AssetGrowthPrepared(market.history, panel)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, AssetGrowthPrepared):
            raise TypeError(f"prepared must be AssetGrowthPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


ASSET_GROWTH = AssetGrowthAllocator()


def _v(suffix: str, params: AssetGrowthParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0275-{suffix}", family="M0275", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ASSET_GROWTH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0275",
    name=(
        "Companies that stopped growing their balance sheet: buy the index members whose total "
        "assets grew least over the past year"
    ),
    family="stock-asset-growth",
    source_kind="paper",
    source_ref=(
        "Cooper, Gulen & Schill (2008) Asset Growth and the Cross-Section of Stock Returns, "
        "J. Finance 63(4); Fama-French (2015) CMA factor; McLean & Pontiff (2016) "
        "post-publication decay"
    ),
    parent_id=None,
    hypothesis=(
        "Published 2008, so the only years this lab can test it on (October 2010 to October 2015, "
        "where the SEC panel carries a balance sheet a year apart for 270-380 index members) are "
        "all after publication. Cooper, Gulen and Schill report that low year-on-year growth in "
        "total assets beats high growth among large companies as well as small; Fama and French "
        "made it a factor in 2015. Signal: each month, for each index member with a bar, the "
        "newest total-assets figure filed by that day against the one for the balance-sheet date "
        "a year earlier (within 20 days), filed by that day too; skip members whose newest balance "
        "sheet is over 200 days old or whose ratio sits outside 0.2-5.0 (a units error), one "
        "listing per company. Arms: L30 (the 30 lowest growers), H30 (the 30 highest, the "
        "opposite book), L30-PLC (L30's size and entry count drawn blind from the same pool: the "
        "no-opinion arm) and L60 (the 60 lowest). Equal slots, monthly, fully invested, no switch, "
        "fractional shares at Gotrade's real fees on the owner's monthly top-up; SPY is held "
        "before October 2010, so the whole-window row differs from SPY only after it. Predictions "
        "written before any result, on the de-funded monthly curve from 2010-10 to 2015-10: L30 "
        "beats H30 by 2 or more points a year; L30 beats L30-PLC by a point or more; L30 ends "
        "within a point a year of total-return SPY, ahead or behind. Unpromotable by construction (three "
        "walk-forward folds, one with picks): run as evidence on whether older fundamentals are "
        "worth buying."
    ),
    expected_failure=(
        "Four ways, in order of likelihood. (1) Decay and crowding: the effect was published in "
        "2008 and made a Fama-French factor in 2015, and the conservative-minus-aggressive factor "
        "earned close to nothing in US large caps over 2010-2015, so L30 lands near the placebo and "
        "behind SPY, the gap being the lab's usual equal-weight shortfall against a market led by "
        "a few fast-growing giants -- which are exactly the high-asset-growth names this book "
        "avoids. (2) The low-growth book is a disguised value-and-distress tilt: shrinking balance "
        "sheets belong to utilities, energy write-downs, and companies selling divisions, so the "
        "2014-2015 oil fall hurts it and H30 (growth, healthcare and tech acquirers) wins. "
        "(3) It is the buyback book re-dressed: buybacks shrink assets, so L30 may hold many of the "
        "shrinking-share-count book's names; the analysis compares their picks month by month. "
        "(4) Five years is one regime and about 60 monthly decisions; any gap under 3 points a "
        "year is inside the noise. Any of these is a rejection; none is a reason to tune the "
        "365-day window, the band or the book size afterwards."
    ),
    candidates=(
        _v("L30", AssetGrowthParams(30, side="low"),
           "The 30 members with the lowest one-year growth in total assets, monthly, no switch"),
        _v("H30", AssetGrowthParams(30, side="high"),
           "Opposite: the 30 members with the highest one-year growth in total assets"),
        _v("L30-PLC", AssetGrowthParams(30, side="control", seed=1),
           "Placebo: L30's book size and monthly entry count drawn blind from the same scored pool "
           "in a hash order, the no-opinion arm"),
        _v("L60", AssetGrowthParams(60, side="low"),
           "Broader: the 60 members with the lowest one-year growth in total assets"),
    ),
    seen_keys=(
        "concept:asset-growth",
        "concept:investment-factor-cma",
    ),
)
