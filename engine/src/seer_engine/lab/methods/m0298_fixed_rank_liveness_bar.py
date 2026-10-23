"""M0298 — Pin the liveness bar to a fixed rank so it cannot move between the two tapes.

Source: variation of M0288, which carried M0284's volume ladder onto M0032's chassis
(M0007-N20-RAW in fractional shares at Gotrade's real fees on the owner's deposits; Blitz, Huij
& Martens 2011, residual momentum). M0288's own analysis named this method as its next step.

Idea: two methods now agree that how heavily a stock trades is a proxy for whether it is still
alive, and therefore for whether a book's measured edge is an artefact of the companies the dev
store cannot price. M0284 swung the dev-minus-check-store gap 3.9 points a year across its ladder
on a news-event book; M0288 swung it 3.5 points on a price-only momentum screen. But **both
ladders used a bar that moves between the two tapes**, and that is the hole this method exists to
close.

**The confound, stated exactly.** M0288's bar is a *percentile of each day's own candidate list*.
The check store holds 989 symbols where the dev store holds 539, so putting the dead companies
back does not only add candidates to choose from -- it moves where the bar sits. A rung that keeps
"the better-traded three fifths" keeps a different *number* of names on each tape, and a different
set of marginal companies. The measured gap therefore mixes the liveness effect with a change in
the pool the percentage is taken of, and M0288's numbers cannot separate them. This method
replaces the percentile with a **fixed rank**: keep only the ``dv_rank`` most-traded eligible
names by 20-day mean dollar volume, the same count on both tapes, so the bar is identical in both
runs and the only difference is which companies exist to fill it.

**What that trade actually buys, and what it costs.** It does not produce a clean measurement
where M0288 had a dirty one. It produces the *mirror image* of M0288's confound, and the pair is
worth more than either alone:

    =========================  ==========================  ==========================
    .                          M0288 (percentile bar)      M0298 (fixed-rank bar)
    =========================  ==========================  ==========================
    fraction of pool kept      identical on both tapes     differs between tapes
    number of names kept       differs between tapes       identical on both tapes
    =========================  ==========================  ==========================

Neither design can hold both constant, because the two pools are different sizes and that is the
whole point of the honest tape. So the question "is the swing liveness, or is it pool
composition?" is not settled by running a cleaner experiment -- there is no cleaner experiment --
it is settled by running the confound **both ways round**. Pool composition pushes the two designs
in different directions; liveness pushes them the same way. **If this ladder reproduces M0288's
swing in sign, shape and rough size, the swing is liveness and the lab has a free diagnostic it
can trust. If it collapses or inverts, M0288's 3.5 points was mostly pool composition and the
liveness reading -- which two methods now rest on -- is much weaker than it looks.**

**Measured before this file was written, so the ladder is known not to be degenerate** (237
decision months, 170 of them with the trend switch on, both tapes, 1996-2015). Three things were
checked, because the last several filtering attempts in this lab all failed for boring reasons
that would have been easy to repeat:

- **The bar bites, monotonically, on both tapes.** Names shared with the no-bar book, of 20:
  dev 20.00, 17.45, 15.57, 13.27, 10.25, 5.48 as K falls 250 -> 50; check store 20.00, 14.38,
  12.68, 10.64, 7.74, 4.10. It bites *harder* on the check tape at every rung, which is the
  arithmetic consequence of its larger pool and is exactly what the design intends.
- **It never starves the book.** Average names held is 20.00 at every rung on both tapes, and
  there is not one month at any rung on either tape where the book holds fewer than 20. M0279
  measured the cost of parking empty slots at 2 to 6 points a year; that cost cannot be the
  explanation for anything seen here, on either tape.
- **The rungs are bite-matched to M0288's at the median**, so the two ladders can be read against
  each other rung by rung: the dev pool's median is 261, so K=200 keeps about what DV20 kept,
  K=150 about DV40, K=100 about DV60 and K=50 about DV80.

**The era problem, pre-registered rather than discovered.** M0288 chose a percentile bar on the
grounds that a fixed *dollar* bar would be a disguised date filter, because dollar volumes grew
more than tenfold across the window. A fixed *rank* has the same disease in mirror image, and the
measurement above shows it plainly. The dev pool grows from a median of 133 names in 1996-2000 to
361 in 2009-2015, so the share of months on which each rung binds at all runs:

    =====  ===========  ===========  ===========  ===========
    K      1996-2000    2001-2005    2006-2008    2009-2015
    =====  ===========  ===========  ===========  ===========
    250    0% / 32%     31% / 100%   100% / 100%  100% / 100%
    200    0% / 38%     100% / 100%  100% / 100%  100% / 100%
    150    30% / 49%    100% / 100%  100% / 100%  100% / 100%
    100    77% / 89%    100% / 100%  100% / 100%  100% / 100%
    50     100% / 100%  100% / 100%  100% / 100%  100% / 100%
    =====  ===========  ===========  ===========  ===========

(dev % / check-store %.) So **K=250 and K=200 are near-inert on the dev tape before 2001 while
already active on the check tape**, and their gap in that era is not a like-for-like comparison of
anything. **K=100 and K=50 bind on both tapes in essentially every month of the window and are
the rungs the conclusion must rest on.** That is written here, before the run, so that leaning on
the tight rungs afterwards is a pre-registered reading and not a choice made once the numbers were
visible.

``K0`` is the arm with no opinion in it: the same book, never declining a name, with the dial set
to off. Every other rung is read against it directly, and it must reproduce M0032's and
M0288-DV00's recorded trials bar for bar. A new allocator id is needed because ``config_digest``
reads the allocator id and ``K0``'s parameters are M0032's exactly; without it the reference rung
would collide with a recorded configuration and could never run. The allocator forwards every
other decision to M0007's code, so the arithmetic is the same and any difference is the dial.

Dollar volume and not company size, for the same reason M0288 gave: the lab's market-cap figure is
an unadjusted share count against split-adjusted closes and is wrong by an arbitrary per-symbol
factor, while dollar volume is sound.

Pure: the bar reads one feature F4 already computed from bars ending at d, and nothing else is
touched, so nothing dated after the data date is read.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    RESIDMOM,
    FACTOR_SYMBOLS,
    ResidParams,
    ResidPrepared,
    build_grid,
    residual_scores,
    resid_lookback,
    targets_from_scores,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorRow, factor_rows, trend_on

ADDED = date(2026, 10, 23)


@dataclass(frozen=True, slots=True)
class RankParams:
    """``inner`` is M0032's configuration verbatim; ``dv_rank`` is the only dial.

    ``dv_rank`` is a **count**, not a percentage: keep the this-many most-traded eligible names.
    0 means no bar at all. That is the whole difference from M0288's ``dv_pct``, and the reason
    this method exists.
    """

    inner: ResidParams
    dv_rank: int = 0  # keep the this-many most-traded names of the day's pool; 0 = no bar

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if isinstance(self.dv_rank, bool) or not isinstance(self.dv_rank, int):
            raise TypeError(f"dv_rank must be an int, got {type(self.dv_rank).__name__}")
        if self.dv_rank < 0:
            raise ValueError(f"dv_rank must be >= 0, got {self.dv_rank}")

    def as_dict(self) -> dict[str, str]:
        out = {"dv_rank": str(self.dv_rank)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def apply_rank(rows: list[FactorRow], dv_rank: int) -> list[FactorRow]:
    """``rows`` cut to the ``dv_rank`` most-traded by dollar volume, back in symbol order.

    A pool already at or below ``dv_rank`` is returned unchanged, so the bar can only ever remove
    names and never invents one. Ties are broken by symbol ascending, as everywhere else in the
    lab, and the cut is by rank, so the rungs nest exactly: the set kept at a smaller ``dv_rank``
    is always a subset of the one kept above it. ``dv_rank`` of 0 returns ``rows`` unchanged,
    which is what makes the reference rung bit-identical to the parent's path.
    """
    if dv_rank <= 0 or len(rows) <= dv_rank:
        return rows
    by_dv = sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[:dv_rank]
    return sorted(by_dv, key=lambda r: r.symbol)


def _check(params: object) -> RankParams:
    if not isinstance(params, RankParams):
        raise TypeError(f"params must be RankParams, got {type(params).__name__}")
    return params


class FixedRankAllocator:
    """M0032's residual-momentum book with a fixed-rank dollar-volume bar on the pool.

    Held symbols get no special treatment, exactly as in M0007: the targets are the new top set,
    so a name that falls out of it is signal-exited by the book engine.
    """

    id = "M0298"

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

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = p.inner
        if not trend_on(history, data_date, inner.inner):
            return ()
        rows = apply_rank(factor_rows(history, members, data_date, inner.inner), p.dv_rank)
        if not rows:
            return ()
        grid = build_grid(history, inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
        return targets_from_scores(rows, scores, inner)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = p.inner
        if not trend_on(prepared.history, data_date, inner.inner):
            return ()
        rows = apply_rank(prepared.factor.rows_on(members, data_date, inner.inner), p.dv_rank)
        if not rows:
            return ()
        grid = prepared.grid(inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
        return targets_from_scores(rows, scores, inner)


DVRANK = FixedRankAllocator()

#: M0032-N20-RAW-FRAC-GT's configuration, which every rung shares but for ``dv_rank``.
BASE = ResidParams(N20, scaled=False)


def _v(suffix: str, dv_rank: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0298-{suffix}", family="M0298", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DVRANK, params=RankParams(BASE, dv_rank), rationale=rationale,
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0298",
    name="Pin the liveness bar to a fixed rank so it cannot move between the two tapes",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref=(
        "variation of M0288 (its dollar-volume liveness ladder and the dev-minus-check-store "
        "swing it produced), with the percentile bar replaced by a fixed rank; same chassis -- "
        "M0007-N20-RAW in fractional shares at Gotrade's real fees on the owner's deposits "
        "(Blitz, Huij & Martens 2011, Residual momentum, J. Empirical Finance 18(3), 506-521)"
    ),
    parent_id="M0288",
    hypothesis=(
        "Two methods now agree that a traded-volume bar is a liveness proxy: M0284 swung the "
        "dev-minus-check-store gap 3.9 points a year across its ladder on a news-event book and "
        "M0288 swung it 3.5 points on a price-only momentum screen, with the strictest rung the "
        "only arm in each method that earns MORE once the dead companies are put back. But both "
        "ladders used a PERCENTILE of each day's own candidate list, and the check store holds "
        "989 symbols where the dev store holds 539, so putting the dead companies back does not "
        "only add candidates -- it moves where the bar sits. The measured swing therefore mixes "
        "the liveness effect with a change in the pool the percentage is taken of, and neither "
        "method's numbers can separate them. This replaces the percentile with a FIXED RANK: "
        "keep only the dv_rank most-traded eligible names by 20-day mean dollar volume, the same "
        "count on both tapes. Six arms on M0032's chassis verbatim -- top-20 raw cumulative "
        "residual momentum, F4's screen, the SPY-200 monthly trend switch, equal weights, "
        "fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade, the owner's "
        "5,000,000 IDR monthly deposits -- adding one requirement to the pool and moving nothing "
        "else: K0 (no bar, the reference arm with no opinion in it, which must reproduce M0032 "
        "and M0288-DV00 bar for bar), then K250, K200, K150, K100 and K50. The rungs are "
        "bite-matched to M0288's at the dev median pool of 261, so the two ladders read against "
        "each other rung by rung: K200 is about DV20, K150 about DV40, K100 about DV60 and K50 "
        "about DV80. I measured the geometry on BOTH tapes before writing this file, over all "
        "237 decision months: the bar bites monotonically (names shared with the no-bar book, of "
        "20, run 20.00, 17.45, 15.57, 13.27, 10.25, 5.48 on dev and 20.00, 14.38, 12.68, 10.64, "
        "7.74, 4.10 on the check store, so it bites harder on the honest tape at every rung, as "
        "its larger pool implies), and it never starves the book -- 20.00 names held on average "
        "at every rung on both tapes, with not one month anywhere below 20, so M0279's 2-to-6-"
        "point cost of parking empty slots cannot explain anything seen here. The honest framing "
        "is NOT that this is the clean experiment M0288 was not. It is the MIRROR IMAGE of "
        "M0288's confound: a percentile holds the fraction constant and lets the count move, a "
        "rank holds the count constant and lets the fraction move, and no design can hold both "
        "because the two pools are different sizes -- which is the whole point of the honest "
        "tape. Pool composition pushes the two designs in different directions; liveness pushes "
        "them the same way. Success for the idea: this ladder reproduces M0288's swing in sign "
        "and shape across at least four rungs and within about a point in size, which together "
        "with M0288 would settle that the swing is liveness and give the lab a free diagnostic "
        "it can trust on every stock screen it already owns. Failure of the idea, equally "
        "informative: the swing collapses or inverts, which would mean M0288's 3.5 points was "
        "mostly pool composition and the liveness reading that two methods now rest on is much "
        "weaker than it looks."
    ),
    expected_failure=(
        "First and most likely, a fixed rank has the disguised-date-filter disease that made "
        "M0288 choose a percentile, in mirror image, and I measured it rather than guessed it: "
        "the dev pool's median grows from 133 names in 1996-2000 to 361 in 2009-2015, so the "
        "share of months on which a rung binds at all runs, dev then check store, 0%/32% and "
        "0%/38% for K250 and K200 in 1996-2000 against 100%/100% for both from 2006. K250 and "
        "K200 are therefore near-inert on the dev tape in the early years while already active "
        "on the check tape, and their gap in that era compares nothing to nothing; only K100 "
        "(77%/89% early, 100% after) and K50 (100% everywhere) bind on both tapes across "
        "essentially the whole window, so the conclusion must rest on the tight rungs. That is "
        "written down before the run so that leaning on them afterwards is pre-registered and "
        "not a choice made once the numbers were visible -- but it does mean the loose half of "
        "this ladder is weaker evidence than it will look in a table. Second, the swing may "
        "simply shrink toward nothing once the bar stops moving between tapes, which is the "
        "result that would overturn two methods' worth of belief and is the main reason to run "
        "this. Third, a fixed rank binds harder on the check store than on dev at the same K "
        "because its pool is larger -- 405 names at the median against 261 -- so the two runs "
        "hold different NUMBERS of candidates even though the bar is identical; that is the "
        "trade this design makes knowingly, and it means a narrowing gap could still be read as "
        "the check-store book simply being filtered more aggressively. Fourth, M0288 measured "
        "the cost of this dial at 5.4 points a year through a large-company tilt -- its breadth "
        "table showed the book's return in months when a few giants carried the index climbing "
        "+5.6% to +11.4% across the ladder while its return in broad months fell +6.4% to -4.7% "
        "-- and a rank bar is the same tilt by another name, so the tight rungs should lose dev "
        "return steadily and the drawdown and luck screens will probably reject them. Fifth, "
        "residual momentum was published in 2011, inside this window, so a crowding tilt toward "
        "the most-traded names is where a published edge fades first and 2009-2015 is where it "
        "would show. And sixth, as with M0288 this is evidence about DATA and about how to build "
        "books, not a candidate: the chassis has kin that already failed the test window "
        "(M0021, M0022, M0029 -- three looks on what is substantially one book), so the hard "
        "gate refuses promotion whatever the numbers, exactly as it refused M0288. That was "
        "known before the run and the method is worth running anyway, because what it measures "
        "is whether the lab can trust a diagnostic it is about to start applying everywhere."
    ),
    candidates=(
        _v("K0", 0,
           "No bar: M0032's book unchanged, the reference rung with no opinion about volume"),
        _v("K250", 250, "The 250 most-traded eligible names: barely binds on dev before 2001"),
        _v("K200", 200, "The 200 most-traded: bite-matched to M0288's DV20 at the dev median"),
        _v("K150", 150, "The 150 most-traded: bite-matched to M0288's DV40"),
        _v("K100", 100, "The 100 most-traded: bite-matched to DV60, and binds on both tapes"),
        _v("K50", 50, "The 50 most-traded: bite-matched to DV80, and binds in every month"),
    ),
    seen_keys=(
        "concept:fixed-rank-liveness-bar",
        "concept:liveness-confound-mirrored-both-ways",
    ),
)
