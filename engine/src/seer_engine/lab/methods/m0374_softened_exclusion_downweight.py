"""M0374 — Hold momentum's favourite names at half a slot instead of zero.

Source: a variation of M0160 (the asymmetry book with momentum's top names barred, bought back
on a positive quarter), reserved as a backlog idea and named in M0160's own closing opinion.

M0133-G40, this family's undiluted book, is the best-shaped book the lab holds: +13.5% a year on
the owner's deposits against SPY TR's +7.2%, a 21.6% worst fall. It cannot be promoted because its
monthly returns, less their fit on SPY's, move with the test-failed M0002-REL-85 at 0.8964
(hardgate D14). M0150 tried fixing that by removing momentum's own top names from the ranking pool
before the asymmetry rank ever sees them: the cheapest width (momentum's top 20 barred, 40 names
held, plain 200-day gate, "X20-G40") held the fall almost exactly (21.7%) and read clean against
the failed book (0.551, worst case 0.814 against any), but the return fell from 13.5% to 10.3% a
year and the book lost both post-2009 folds. M0160 then added M0113's better re-entry trigger (buy
back on a positive trailing quarter, not the instant the 200-day line is crossed) on top of that
same exclusion and recovered about two-thirds of the 2009-2015 shortfall — X20-G40-UP63 funded
+11.4% a year, 23.6% fall, DSR 0.854 against the 0.90 bar (N=237), winning three of four
walk-forward folds — but it could not close the rest, because the trigger changes only *when* the
book re-enters, never *which* companies it may hold once it is in. M0160's own closing line named
the next move directly: "a softer exclusion: instead of fully barring momentum's top names, hold
them at a smaller slot rather than zero, so the book keeps some of their 2009-2015 contribution
while still moving away from the correlation that motivated barring them in the first place."

This method is that softer exclusion, built the smallest way the idea allows. The pool is **not**
narrowed before ranking — the asymmetry rank sees every F4-screened row, exactly as M0133's own
allocator does, so the 40 names it picks are bit-identical to what the undiluted book would pick.
The only change is afterwards: any chosen name that sits inside momentum's own top ``momentum_top_n``
(F4's 12-1 column, same point-in-time order M0150 already uses) has its slot weight multiplied by
``down_weight`` instead of zeroed. A ``down_weight`` of 0.5 means that name's dollars are halved and
the other half sits in cash for that check; 0.25 holds a quarter; 1.0 (never registered here) would
be the plain book unchanged. This is a genuinely different lever from M0150/M0160's pool exclusion:
it changes *how much* of a name the book holds, never *whether* it is held at all, so the picks a
reader would see on any given day look like M0133's, just lighter on a subset.

Three arms, each comparable to one recorded trial by changing exactly one dial:

* ``SOFT20-W50-G40-UP63`` — momentum's top 20 at half weight, 40-name book, 200-day exit,
  positive-quarter re-entry (M0160's exact chassis otherwise). Pairs against M0160-X20-G40-UP63
  (same width and gate, full bar instead of half weight) and against M0150-X20-G40 (same width,
  full bar, plain gate).
* ``SOFT40-W50-G40-UP63`` — momentum's top 40 at half weight instead of top 20: the width
  dose-response twin at the same weight. Pairs against M0160-X40-G40-UP63.
* ``SOFT20-W25-G40-UP63`` — momentum's top 20 at a quarter weight instead of half: the weight
  dose-response twin at the same width. Pairs against ``SOFT20-W50-G40-UP63`` to read how much of
  any gain is bought by leaving more weight on, as opposed to simply touching the names at all.

Assumptions, written before the run:

- "Momentum's top N" is computed from the exact same F4-screened rows and sort order
  (``-momentum`` descending, ties by symbol ascending) that M0150's ``outside_momentum`` already
  uses, so the set a name is judged by is identical whether this method bars it, halves it, or
  leaves it alone.
- Down-weighted dollars are left uninvested for that check, not redistributed to other names. This
  keeps the mechanism legible (one dial, one effect) at the cost of some exposure; the recorded
  exposure will say how much of the book sits in cash because of it, separately from the gate's own
  cash periods.
- Because the picks are unchanged from M0133's own book, the kin correlation to the failed momentum
  book is **not** assumed to improve the way M0150's pool-narrowing did. M0150's fix worked by
  changing which companies could ever be held; this fix changes none of that, only their size. The
  honest expectation, stated now, is that the resemblance may barely move — see expected failure.
- Reads only bars dated <= ``data_date``. Pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import build_grid
from seer_engine.lab.methods.m0110_downside_participation import CapturePrepared, targets_from_scores
from seer_engine.lab.methods.m0133_gated_updown_asymmetry import ASYM, N40, AsymParams, asym_scores
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorRow, factor_rows

ADDED = date(2026, 10, 26)


@dataclass(frozen=True, slots=True)
class SoftExclParams:
    """M0133's whole configuration, plus a weight multiplier on momentum's own top names."""

    asym: AsymParams
    momentum_top_n: int = 20
    down_weight: float = 0.5

    def __post_init__(self) -> None:
        if not isinstance(self.asym, AsymParams):
            raise TypeError(f"asym must be AsymParams, got {type(self.asym).__name__}")
        if isinstance(self.momentum_top_n, bool) or not isinstance(self.momentum_top_n, int):
            raise TypeError(f"momentum_top_n must be an int, got {type(self.momentum_top_n).__name__}")
        if self.momentum_top_n < 1:
            raise ValueError(f"momentum_top_n must be >= 1, got {self.momentum_top_n}")
        if isinstance(self.down_weight, bool) or not isinstance(self.down_weight, (int, float)):
            raise TypeError(f"down_weight must be a float, got {type(self.down_weight).__name__}")
        dw = float(self.down_weight)
        if not (dw == dw) or not (0.0 <= dw <= 1.0):  # dw == dw excludes NaN
            raise ValueError(f"down_weight must be within [0, 1], got {dw}")
        object.__setattr__(self, "down_weight", dw)

    def as_dict(self) -> dict[str, str]:
        out = {"momentum_top_n": str(self.momentum_top_n), "down_weight": repr(self.down_weight)}
        for key, v in self.asym.as_dict().items():
            out[f"asym.{key}"] = v
        return out


def _check(params: object) -> SoftExclParams:
    if not isinstance(params, SoftExclParams):
        raise TypeError(f"params must be SoftExclParams, got {type(params).__name__}")
    return params


def momentum_top(rows: list[FactorRow], top_n: int) -> frozenset[str]:
    """The ``top_n`` symbols by F4's momentum column (same order as M0150's ``outside_momentum``)."""
    k = min(top_n, len(rows))
    return frozenset(r.symbol for r in sorted(rows, key=lambda r: (-r.momentum, r.symbol))[:k])


def _scale_weight(w: Decimal, factor: float) -> Decimal | None:
    """``w * factor``, quantized down; ``None`` if that floors to zero."""
    scaled = Decimal(repr(float(w) * factor))
    if scaled < WEIGHT_QUANTUM:
        return None
    return to_weight(scaled)


def downweight(targets: tuple[Target, ...], barred: frozenset[str], down_weight: float) -> tuple[Target, ...]:
    """``targets`` with every symbol in ``barred`` scaled to ``down_weight`` of its slot, never raised."""
    if down_weight >= 1.0 or not barred:
        return targets
    out: list[Target] = []
    for t in targets:
        if t.symbol not in barred:
            out.append(t)
            continue
        w = _scale_weight(t.weight, down_weight)
        if w is not None:
            out.append(replace(t, weight=w))
    return tuple(out)


class SoftExclusionAllocator:
    """M0133's gated asymmetry book, unchanged in composition, with momentum's own top names held lighter.

    The gate decision, the screen and the ranking are exactly M0133's (``ASYM``'s own code, reused):
    this allocator never narrows the pool before ranking, so the names it picks are bit-identical to
    what the plain book would pick. Only the weight on a chosen name inside momentum's own top
    ``momentum_top_n`` differs, scaled by ``down_weight`` with the remainder left in cash.
    """

    id = "M0374"

    def lookback(self, params: Any) -> int:
        return ASYM.lookback(_check(params).asym)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ASYM.symbols(_check(params).asym)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _pick(self, rows: list[FactorRow], grid: Any, data_date: date, p: SoftExclParams) -> tuple[Target, ...]:
        targets = targets_from_scores(rows, asym_scores(grid, [r.symbol for r in rows], data_date, p.asym), p.asym)
        if not targets:
            return targets
        return downweight(targets, momentum_top(rows, p.momentum_top_n), p.down_weight)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = factor_rows(history, members, data_date, p.asym.inner)
        if not rows or not ASYM._invested(history, data_date, held, p.asym):
            return ()
        grid = build_grid(history, p.asym.market)
        if grid is None:
            return ()
        return self._pick(rows, grid, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> CapturePrepared:
        return ASYM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CapturePrepared):
            raise TypeError(f"prepared must be CapturePrepared, got {type(prepared).__name__}")
        p = _check(params)
        rows = prepared.factor.rows_on(members, data_date, p.asym.inner)
        if not rows or not ASYM._invested(prepared.history, data_date, held, p.asym):
            return ()
        grid = prepared.grid(p.asym.market)
        if grid is None:
            return ()
        return self._pick(rows, grid, data_date, p)


SOFT = SoftExclusionAllocator()


def _v(suffix: str, params: SoftExclParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0374-{suffix}", family="M0374", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SOFT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0374",
    name="Hold momentum's favourite names at half a slot instead of zero",
    family="stock-updown-asymmetry",
    source_kind="variation",
    source_ref=(
        "variation of M0160 (asymmetry book with momentum's top names barred, bought back on a "
        "positive quarter); the exact next move M0160's own closing opinion named"
    ),
    parent_id="M0160",
    hypothesis=(
        "M0150 measured that barring momentum's own top 20 names from the asymmetry book's ranking "
        "pool (40-name book, plain 200-day gate) breaks the resemblance to the test-failed momentum "
        "book (0.551 against it, 0.814 worst case against any) but pulls funded return from "
        "M0133-G40's 13.5%/yr down to 10.3%/yr, at an almost unchanged 21.7% fall. M0160 then put "
        "M0113's positive-quarter re-entry trigger on that same exclusion and recovered about "
        "two-thirds of the 2009-2015 shortfall the exclusion caused (X20-G40-UP63: funded +11.4%/yr, "
        "23.6% fall, DSR 0.854 against the 0.90 bar at N=237, 3 of 4 walk-forward folds) but still "
        "fell short, because the trigger only changes when the book re-enters, never which companies "
        "it may hold. This method keeps the exact same picks the undiluted book would make (the pool "
        "is never narrowed before ranking) and instead scales the weight of any chosen name inside "
        "momentum's own top N to down_weight instead of excluding it outright, so the book keeps part "
        "of that name's contribution rather than none. Three arms: SOFT20-W50-G40-UP63 (top 20 at "
        "half weight, pairs against M0160-X20-G40-UP63 and M0150-X20-G40), SOFT40-W50-G40-UP63 (top "
        "40 at half weight, pairs against M0160-X40-G40-UP63), and SOFT20-W25-G40-UP63 (top 20 at a "
        "quarter weight, pairs against the first arm to read the weight dial alone). Success: a "
        "funded return between the full-bar figure (11.4%/yr at width 20) and the undiluted book's "
        "13.5-16.7%/yr, at a fall that does not cross 25%, moving the DSR materially closer to 0.90 "
        "than M0160's 0.843-0.854."
    ),
    expected_failure=(
        "The likeliest failure is that this buys little and costs the thing M0150 actually bought. "
        "M0150's fix worked because it changed which companies the book could ever hold -- the "
        "resemblance to the failed momentum book is carried by a minority of shared names, and "
        "removing them from the pool is what broke the tie. This method never removes them from the "
        "pool: the picks are bit-identical to M0133's own book, and the only change is that some "
        "slots are smaller. A smaller position in the same company, held on the same days, still "
        "moves with that company's return -- the monthly pattern that the kin check reads may barely "
        "shift, because the correlation is a question of co-movement, not of dollar size, and a 50% "
        "position still moves almost exactly like a 100% one in sign and rough magnitude. If kin stays "
        "at or above 0.85, this line is a dead end regardless of what the DSR or the return shows, and "
        "the honest reading is that only removing a name from the pool, never merely shrinking it, "
        "breaks the resemblance. Second, even setting kin aside: the uninvested cash left by every "
        "downweighted slot is a drag of its own, separate from the gate's own cash periods, and at "
        "down_weight 0.25 that drag may erase most of the return gained back from holding the name at "
        "all, leaving a result that is worse than M0160's full bar on both DSR and complexity. Third, "
        "survivorship is deferred again: nothing in this family has been dev-eligible, so no check has "
        "been owed yet, and this run likely will not change that."
    ),
    candidates=(
        _v("SOFT20-W50-G40-UP63",
           SoftExclParams(AsymParams(N40, gate="sma200-up63"), momentum_top_n=20, down_weight=0.5),
           "Momentum's top 20 held at half weight instead of barred: the headline"),
        _v("SOFT40-W50-G40-UP63",
           SoftExclParams(AsymParams(N40, gate="sma200-up63"), momentum_top_n=40, down_weight=0.5),
           "Momentum's top 40 at half weight instead of top 20: the width dose-response twin"),
        _v("SOFT20-W25-G40-UP63",
           SoftExclParams(AsymParams(N40, gate="sma200-up63"), momentum_top_n=20, down_weight=0.25),
           "Momentum's top 20 at a quarter weight instead of half: the weight dose-response twin"),
    ),
    seen_keys=(
        "concept:asymmetry-exclusion-as-weight-downscale-not-bar",
    ),
)
