"""M0303 — What the honest tape actually measures: safety, or just a different set of names.

Source: variation of M0293 (which is itself a variation of M0283 / M0278). The question comes
from the lab's own record, not from a paper.

THE CLAIM UNDER TEST. Two rules in this lab have ever read BETTER on the survivorship-check
store than on the dev store -- that is, their worst fall got *shallower* when the companies that
went bankrupt or were bought are put back on the tape. One is proximity to the 52-week high. The
other is M0293's calm filter, and M0293's evidence is unusually sharp because it is a monotone
ladder rather than a single pair: the dev-to-honest change in worst fall ran in perfect order
from drop-the-calmest through drop-nothing to drop-the-jumpiest-quarter and drop-the-jumpiest-
half, and the same order appeared again with the cash switch off. The mechanism is plain. Roughly
four in ten index member-days the dev store cannot price belong to companies that died, dying
companies are jumpy before they die, and a filter that throws out the jumpy quarter has already
thrown most of them out before they can hurt it.

If that mechanism is right it is not a fact about calmness. It is a fact about *what a screen is
for*. Any screen whose job is to avoid trouble should read better on the honest tape, because the
trouble it avoids is exactly what the dev store is missing; any screen whose job is to chase
return should read worse, because the dev store has already quietly removed the names that would
have punished it. If that holds, the lab gets something it badly wants: a free, look-free test of
whether a new rule is really a safety filter or an engine wearing a safety filter's clothes --
which is precisely the question M0283 and M0293 each had to spend a method id to answer.

WHY THIS IS A MATCHED LADDER AND NOT A SURVEY. The obvious way to ask the question is to re-run
the best variant of a dozen recorded methods on both stores and see whether the safety-labelled
ones cluster on the shallow side. That survey is free and it is run beside this method, but it
cannot settle anything, because those dozen methods differ in host, pool, name count, cadence,
turnover and concentration all at once. Any clustering it finds could be any of those. So the
experiment proper holds every one of them fixed and varies ONLY what the screen is for.

Every arm is M0197-Y20-SW, term for term: among F4-screened index members, one shared yearly
regression of 52 weekly log returns on SPY's and on the weekly change in the 10-year Treasury
yield; hold the 20 names whose prices rise most when yields fall, equal slots, re-ranked
quarterly with a 40% keep band, behind the SPY 200-day switch, fractional shares at Gotrade's
real fees on the owner's monthly deposits. Every opinionated arm throws away the same share of
the same pool -- a quarter -- before the host ranks what is left. The pool is deep (hundreds of
screened members), so a drop changes WHICH names and never HOW MANY: the book stays exactly 20
names, fully invested, in all six arms. That is the confound that sank M0277's and M0279's six
pick filters on the thin news-day pool, and it is closed here by construction.

The only thing that differs between the four opinionated arms is which number the quarter is
chosen by -- and, critically, every one of those numbers is already computed by the host's own
screen and thrown away. F4 scores each eligible member's 12-1 momentum, its 60-day realised
volatility and its 20-day mean dollar volume on the way to deciding eligibility; the host reads
none of them for ranking. So this method adds no new estimate, no new window, no new lookback and
no new free parameter, exactly as M0293 added none. Market beta is deliberately NOT one of the
arms: M0293 already measured it on this identical host, so it is read from the record as the
anchor rather than re-run here.

    ==========  ===========  ==================================================================
    arm         metric       what the screen is FOR, declared now
    ==========  ===========  ==================================================================
    ``REF``     --           nothing dropped: the no-opinion reference, which must reproduce
                             M0197-Y20-SW and M0293-REF bar for bar
    ``BLIND``   hash         drop the same count by a fixed per-symbol hash, seed 293: the arm
                             with no opinion in it, which prices the *habit* of dropping a
                             quarter. Seed 293 is M0293's, so this arm must also reproduce
                             M0293-BLIND25 bar for bar and prove the two chassis identical
    ``VOL``     vol-high     drop the jumpiest quarter by 60-day realised volatility: SAFETY
    ``DV``      dv-low       drop the thinnest-traded quarter by dollar volume: SAFETY
    ``MOM``     mom-low      drop the worst-performing quarter by 12-1 momentum: RETURN
    ``AMOM``    mom-high     drop the best-performing quarter by 12-1 momentum: RETURN, and the
                             mirror of MOM
    ==========  ===========  ==================================================================

MOM and AMOM are each other's mirror, so BLIND is the third arm the lab's own audit says decides
every reversed pair -- of 28 reversed pairs across 23 methods only 6 could be priced, because the
other 22 left it out. Its draw is sticky (one hash per symbol, no date in the key) because a
stock's volatility or size quartile is a slow-moving property and a re-drawn placebo churns about
fourteen times harder, which would price turnover rather than selection.

Having MOM and AMOM point in opposite directions is the sharpest part of the design. They are
both return engines' screens -- MOM is what a momentum book does to a pool, AMOM is what a
long-term-loser book does to the same pool -- and they disagree completely about which names are
good. If the honest tape is reading *what a screen is for*, both must land on the deep side of
BLIND despite choosing opposite names. If instead they straddle BLIND, then the honest tape is
reading WHICH names a screen picks and not what it is for, the diagnostic is dead, and the lab
has learned not to quote a survivorship gap as evidence of safety again.

THE GATE STAYS ON, and that is a choice worth defending. M0293's first run was almost wasted
because every arm sat behind the same cash switch through 2008 and scored an identical lead
there, so the one crash in the window never tested the filter at all; it took an amendment with
the switch off to show the arms a falling tape. The temptation here is to repeat that and run
gate-off. This method does not, for three reasons. First, M0293 ended up with the ladder visible
in BOTH settings and the gate-on spread was no narrower than the gate-off one, which says the
dead companies bite outside the crashes too -- and if they do, that is the more interesting fact,
because it means the diagnostic works on the books the lab actually wants to screen. Second,
every book the lab would ever apply this diagnostic to is gated, so a diagnostic measured only on
ungated books would be measured in a setting that never occurs. Third, a gate-off arm on this
host falls about sixty per cent and can never be a candidate, so running gate-off would guarantee
this method produced evidence and nothing else; gate-on leaves open the possibility that one of
these filters is also a good book. The cost is accepted and named: if all six arms turn out to
have spent the crashes in cash and their falls differ for reasons unrelated to dying companies,
the analysis must say the gate-on setting could not see the effect, and the follow-up is the
gate-off twin.

Pure: every read is M0197's -- bars dated <= data_date and the T10Y rows ``MarketSeries.upto``
returns for that date -- plus the three F4 features the host already computed for that date, plus
a hash of the symbol. Market-aware (``market_fields = ("series",)``) for the same reason the host
is: with no yield series there is no fit, so no target.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0197_treasury_yield_beta import (
    REPICK_MONTHS,
    YieldBetaParams,
    YieldBetaPrepared,
    choose,
    loadings,
)

# The drop machinery is M0293's, imported rather than copied so the two chassis cannot drift:
# BLIND at seed 293 then has to reproduce M0293-BLIND25 bar for bar, which is the check that
# every cross-method comparison in the analysis rests on.
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw, drop_count
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

# What the quarter is chosen by. "blind" is the no-opinion draw; the other four name a feature
# the host's own F4 screen already computed, and which end of it goes.
METRICS = ("blind", "vol-high", "dv-low", "mom-low", "mom-high")

# Declared before the run, and the whole point of the method: what each screen is FOR.
PURPOSE = {
    "blind": "none",
    "vol-high": "safety",
    "dv-low": "safety",
    "mom-low": "return",
    "mom-high": "return",
}


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class DropMetricParams:
    """``inner`` is the host, term for term; the rest is the filter and nothing else.

    ``drop_frac`` is the share of the day's scored pool thrown away before the host ranks what
    is left -- identical in every opinionated arm, so the arms differ only in WHICH names go.
    ``metric`` says which number the quarter is chosen by and which end of it goes. ``seed`` keys
    the per-symbol hash and is read only when ``metric == "blind"``.
    """

    inner: YieldBetaParams
    drop_frac: Decimal = Decimal("0")
    metric: str = "blind"
    seed: int = 293

    def __post_init__(self) -> None:
        if not isinstance(self.inner, YieldBetaParams):
            raise TypeError(f"inner must be YieldBetaParams, got {type(self.inner).__name__}")
        if not isinstance(self.drop_frac, Decimal) or not self.drop_frac.is_finite():
            raise TypeError(f"drop_frac must be a finite Decimal, got {self.drop_frac!r}")
        if not Decimal(0) <= self.drop_frac < Decimal(1):
            raise ValueError(f"drop_frac must be in [0, 1), got {self.drop_frac}")
        if self.metric not in METRICS:
            raise ValueError(f"metric must be one of {METRICS}, got {self.metric!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "drop_frac": str(self.drop_frac),
            "metric": self.metric,
            "purpose": PURPOSE[self.metric],
            "seed": str(self.seed),
            "features_from": "host-f4-screen",
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> DropMetricParams:
    if not isinstance(params, DropMetricParams):
        raise TypeError(f"params must be DropMetricParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the filter


def order_key(metric: str, seed: int, symbol: str, feat: tuple[float, float, float]) -> tuple:
    """Sort key putting the names that GO first; ``feat`` is (vol, dollar_volume, momentum)."""
    vol, dv, mom = feat
    if metric == "vol-high":
        return (-vol, symbol)
    if metric == "dv-low":
        return (dv, symbol)
    if metric == "mom-low":
        return (mom, symbol)
    if metric == "mom-high":
        return (-mom, symbol)
    return (draw(seed, symbol), symbol)


def survivors(
    lv: Mapping[str, tuple[float, float]],
    feat: Mapping[str, tuple[float, float, float]],
    p: DropMetricParams,
) -> dict[str, float]:
    """The pool's yield loadings with ``drop_frac`` of it removed, chosen by ``p.metric``.

    ``lv`` maps symbol -> (market beta, yield loading); only the loading is kept, exactly as the
    host expects. A name with no F4 features cannot be scored by any metric, so it is never
    dropped by one -- but it is still eligible for the blind draw, which needs no features. That
    cannot bite in practice: ``lv`` is built from the F4 rows, so every name in it has features.
    """
    k = drop_count(len(lv), p.drop_frac)
    if k <= 0:
        return {s: bc[1] for s, bc in lv.items()}
    scoreable = [s for s in lv if p.metric == "blind" or s in feat]
    zero = (0.0, 0.0, 0.0)
    order = sorted(scoreable, key=lambda s: order_key(p.metric, p.seed, s, feat.get(s, zero)))
    gone = set(order[:k])
    return {s: bc[1] for s, bc in lv.items() if s not in gone}


def filtered_frac(
    history: Mapping[str, History],
    series: MarketSeries,
    rows: list[Any],
    data_date: date,
    p: DropMetricParams,
) -> dict[str, float]:
    """The host's rank fraction over the surviving pool: 0 is the first name the book wants."""
    inner = p.inner
    keep = [r for r in rows if r.symbol not in EXCLUDED and r.symbol != inner.market]
    pool = sorted(r.symbol for r in keep)
    feat = {r.symbol: (float(r.vol), float(r.dollar_volume), float(r.momentum)) for r in keep}
    lv = loadings(history, series, pool, data_date, inner.market)
    if not lv:
        return {}
    kept = survivors(lv, feat, p)
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


class DropMetricAllocator:
    """M0197's bond-like book, picking from a pool with one quarter removed by a named feature.

    Everything but the filter is the host's: the screen, the shared yearly fit, the 20 equal
    slots, the 40% keep band, the quarterly re-rank, the SPY 200-day switch and SPY in any slot
    left over. With ``drop_frac = 0`` nothing is removed and the book is the host exactly.
    """

    id = "M0303"
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

    def _run(
        self,
        prepared: YieldBetaPrepared,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        p: DropMetricParams,
    ) -> tuple[Target, ...]:
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

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        """The history-only path: no yield, so no fit, no ranking and no target."""
        return self._run(
            YieldBetaPrepared(history, EMPTY_SERIES, None), members, data_date, held, _check(params)
        )

    def prepare(self, history: Mapping[str, History]) -> YieldBetaPrepared:
        return YieldBetaPrepared(history, EMPTY_SERIES, prepare_factor(history))

    def prepare_market(self, market: Any) -> YieldBetaPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return YieldBetaPrepared(market.history, series, prepare_factor(market.history))

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, YieldBetaPrepared):
            raise TypeError(f"prepared must be YieldBetaPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


DROPMETRIC = DropMetricAllocator()

SW = ("SPY", 200)
# M0197-Y20-SW term for term, and byte for byte the same object M0293 built: F4's screen, 20
# names, the SPY 200-day switch, the bond-like end, the 40% keep band. The rank field is unused
# by the host; only the screen is read, and the screen is where the three features come from.
HOST = YieldBetaParams(FactorParams(rank="momentum", top=20, trend=SW), side="bond")

QUARTER = Decimal("0.25")


def _v(suffix: str, drop_frac: Decimal, metric: str, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0303-{suffix}",
        family="M0303",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=DROPMETRIC,
        params=DropMetricParams(HOST, drop_frac=drop_frac, metric=metric, seed=293),
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0303",
    name="The rules that earn more when the dead companies come back: find the rest of them",
    family="stock-market-beta",
    source_kind="variation",
    source_ref=(
        "variation of M0293 (calmness as a safety filter on M0197-Y20-SW's book), asking whether "
        "M0293's survivorship signature is a property of calmness or a property of what any "
        "screen is FOR; the family string is inherited from the reserved idea row and from the "
        "parent, though none of these four arms sorts on market beta"
    ),
    parent_id="M0293",
    hypothesis=(
        "Only two rules in this lab have ever read BETTER on the survivorship-check store than on "
        "the dev store -- proximity to the 52-week high, and M0293's calm filter, whose evidence "
        "is a monotone ladder in both gate settings rather than a single pair. The mechanism "
        "offered for it is not about calmness at all: roughly four in ten index member-days the "
        "dev store cannot price belong to companies that went bankrupt or were bought, dying "
        "companies are jumpy before they die, and a filter whose job is to avoid trouble has "
        "already thrown most of them out. If that is the mechanism then it generalises, and the "
        "dev-to-honest change in worst fall is a free, look-free test of whether a screen is a "
        "safety filter or a return engine. THE TEST. Six arms, every one of them M0197-Y20-SW "
        "term for term -- same pool of F4-screened index members, same shared yearly fit on SPY "
        "and the 10-year yield, same 20 equal slots, same 40% keep band, same quarterly re-rank, "
        "same SPY 200-day switch, same fractional shares at Gotrade's real fees on the owner's "
        "monthly deposits. Every opinionated arm throws away the same quarter of the same pool "
        "before the host ranks what is left, so a drop changes WHICH names and never HOW MANY: "
        "the book stays 20 names fully invested in all six, which is the confound that sank "
        "M0277's and M0279's pick filters on the thin news-day pool. The only difference between "
        "the four opinionated arms is which number the quarter is chosen by, and every one of "
        "those numbers is already computed by the host's own F4 screen and thrown away, so this "
        "method adds no new estimate, no new window, no new lookback and no new free parameter. "
        "VOL drops the jumpiest quarter by 60-day realised volatility and DV drops the "
        "thinnest-traded quarter by dollar volume; both are declared SAFETY screens before the "
        "run. MOM drops the worst-performing quarter by 12-1 momentum and AMOM drops the best; "
        "both are declared RETURN screens. REF drops nothing and must reproduce M0197-Y20-SW and "
        "M0293-REF bar for bar. BLIND drops the same count by a fixed per-symbol hash at M0293's "
        "own seed 293, so it must also reproduce M0293-BLIND25 bar for bar -- that is the check "
        "that proves the two chassis identical and makes every cross-method comparison in the "
        "analysis legitimate -- and it prices the habit of dropping a quarter, the third arm the "
        "lab's audit says decides every reversed pair and which 22 of 28 reversed pairs left "
        "out. THE PREDICTION, written now: measuring the change in worst fall from the dev store "
        "to the survivorship-check store, with positive meaning the book falls deeper once the "
        "dead companies are back, both safety arms come in at or below BLIND and both return "
        "arms at or above it, with no overlap between the pair {VOL, DV} and the pair {MOM, "
        "AMOM}. MOM and AMOM disagree completely about which names are good -- one is what a "
        "momentum book does to a pool and the other what a long-term-loser book does to the same "
        "pool -- so if both still land deep, the honest tape is reading what a screen is FOR and "
        "not which names it picks, and the lab has a free diagnostic. Market beta is deliberately "
        "not an arm here: M0293 measured it on this identical host, so it is read from the record "
        "as the anchor rather than paid for twice. None of these arms is expected to be a better "
        "book than the host; the gate is left ON, against the temptation to repeat M0293's "
        "gate-off amendment, because every book the lab would apply this diagnostic to is gated, "
        "because M0293's gate-on ladder was no narrower than its gate-off one, and because a "
        "gate-off arm on this host falls about sixty per cent and could never also be a candidate."
    ),
    expected_failure=(
        "The likeliest failure is that the split is real but is not about safety. The four "
        "opinionated arms differ in turnover -- a momentum-chosen quarter reshuffles far harder "
        "than a dollar-volume-chosen one, because size and volatility quartiles are slow-moving "
        "and last year's return is not -- so an ordering that looks like safety-versus-return "
        "could just be low-churn-versus-high-churn, and the honest tape would be measuring how "
        "often a book trades rather than what it is trying to avoid. The second confound is "
        "overlap with the host: the host ranks on yield loading, and bond-like names are already "
        "the calmer, larger, duller end of the index, so dropping the jumpiest or the thinnest "
        "quarter may remove names the host was never going to hold anyway, making VOL and DV "
        "near-copies of REF while MOM and AMOM genuinely move the book. If so the ordering is "
        "really a measure of how far each filter moved the book off the host's picks, and the "
        "fix is to report the share of REF's holdings each arm keeps and read the falls against "
        "that, not against the safety label. The third is the gate, named and accepted above: "
        "with the SPY 200-day switch on, the book sits in cash through 2008 and much of "
        "2000-2002, which are exactly the episodes in which the missing companies died, so the "
        "whole effect may be invisible here and all six arms may land within the draw's own "
        "width -- the lab has measured that width at several points a year of return and twenty "
        "points of fall across identical rules, which is wide enough to swallow this entirely. "
        "The fourth is simply that M0293's ladder was one method's accident: four in ten "
        "member-days missing is an average, and if the missing names happen to be concentrated "
        "in the jumpy, thin, low-momentum corner of the index then every one of these filters "
        "removes some of them and the arms separate by how much of that corner they touch, which "
        "is a statement about the dev store's holes and not about markets. Any of these would "
        "mean a survivorship gap must never again be quoted as evidence that a rule is safe, "
        "which is worth knowing and is the reason this is worth a method id even if it fails."
    ),
    candidates=(
        _v("REF", Decimal("0"), "blind",
           "Nothing dropped: the no-opinion reference, which must reproduce M0197-Y20-SW"),
        _v("BLIND", QUARTER, "blind",
           "Drop a quarter by a fixed per-symbol hash at M0293's seed: the habit's price, and the "
           "arm that must reproduce M0293-BLIND25 and prove the two chassis identical"),
        _v("VOL", QUARTER, "vol-high",
           "Drop the jumpiest quarter by 60-day realised volatility: declared a SAFETY screen"),
        _v("DV", QUARTER, "dv-low",
           "Drop the thinnest-traded quarter by dollar volume: declared a SAFETY screen"),
        _v("MOM", QUARTER, "mom-low",
           "Drop the worst-performing quarter by 12-1 momentum: declared a RETURN screen"),
        _v("AMOM", QUARTER, "mom-high",
           "Drop the best-performing quarter by 12-1 momentum: declared a RETURN screen, and the "
           "mirror of MOM"),
    ),
    seen_keys=(
        "concept:survivorship-gap-as-a-safety-filter-diagnostic",
        "concept:matched-pick-filter-ladder-by-screen-purpose",
    ),
)
