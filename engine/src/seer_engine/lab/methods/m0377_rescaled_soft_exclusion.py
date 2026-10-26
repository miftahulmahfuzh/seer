"""M0377 — Keep the half-weight discount, but stop leaving its freed cash in the bank.

Source: a variation of M0374, named in M0374's own closing opinion.

M0374 kept M0133's undiluted asymmetry book's exact picks and halved (or quartered) the weight of
any chosen name inside momentum's own top N, leaving the freed half of that slot in cash rather
than giving it to anything else. Measured on the shared research store: the half-weight arm
(SOFT20-W50-G40-UP63) was the first in this exclusion line to clear both the luck test (DSR 0.906
at N=242) and the resemblance test (worst reading 0.81 against the 0.85 limit) at once, but it
invested only 56.7% of the account on average against the fully-barred book's 71.7%, and it then
won only 1 of 4 walk-forward folds — the worst record in the line — so the hard gate refused it on
the fold majority, not on DSR or kin. The two other arms (top-20 at a quarter weight, 48.1%
invested; top-40 at half weight, 45.8% invested) fell further from the fully-barred exposure and
missed the DSR bar outright (0.866 and 0.890). M0374's own closing opinion named the next move
directly: keep the same half-weight discount, but scale every other slot in the book up
proportionally so the total invested fraction stays near the fully-barred version's 72% instead of
falling to the 46–57% the plain discount leaves behind.

This method is that rescale, built as the smallest possible change to M0374's own mechanism. The
screen, the rank and the discount itself are untouched — a chosen name inside momentum's own top
``momentum_top_n`` is still scaled to ``down_weight`` of its ordinary slot, exactly as M0374 does
it. The only new step: whatever weight that discount frees up is handed to the book's *other* held
names, in proportion to the weight each already has, so the check's total invested weight returns
to exactly what the undiluted M0133 book would have invested that same day — never more. 72% is
not a target this method aims for directly; it is simply what that undiluted investment level
averages to across the dev window, the same average the fully-barred book shares because it, too,
never narrows the book below its full count. When there is no "other" name to give the freed weight
to — every held name falls inside the barred set, which can only happen when ``momentum_top_n``
covers the whole book — the freed weight has nowhere to go and is left in cash exactly as M0374
left it; see the top-40 arm below.

Three arms, one for each of M0374's recorded configurations, so every number here reads against one
specific prior trial by changing exactly one thing: where the discount's freed dollars go.

* ``RESCALE20-W50-G40-UP63`` — momentum's top 20 at half weight, freed weight rescaled into the
  other ~20 held names. Pairs against M0374-SOFT20-W50-G40-UP63 (same discount, freed weight left
  in cash) and against M0160-X20-G40-UP63 (same width and gate, the full bar this method is trying
  to match on exposure).
* ``RESCALE40-W50-G40-UP63`` — momentum's top 40 at half weight: the width dose-response twin,
  and the mechanical control for the mechanism itself. With a 40-name book and
  ``momentum_top_n=40``, every held name can fall inside the barred set, so there is no "other"
  name to rescale into and this arm is expected to reproduce M0374-SOFT40-W50-G40-UP63 almost
  exactly — a predicted null result, not a second shot at the same question.
* ``RESCALE20-W25-G40-UP63`` — momentum's top 20 at a quarter weight, rescaled. Pairs against
  M0374-SOFT20-W25-G40-UP63 (same discount, cash) and against this method's own
  ``RESCALE20-W50-G40-UP63`` (same rescale, half weight instead of a quarter) to read the weight
  dial alone once exposure is restored.

Assumptions, written before the run:

- "Momentum's top N" and the half/quarter weight discount are unchanged from M0374: computed from
  the same F4-screened rows and sort order, applied before any rescaling.
- The freed weight is spread over the non-barred held names in proportion to their own existing
  weight (so a name already holding a bigger slot gets a proportionally bigger share of the
  rescale, not an equal share regardless of size). Any barred name's own weight is never raised
  above its discounted level by this step — the discount itself is never undone, only the *rest*
  of the book is topped up.
- Restoring exposure is not assumed to be free. The central open question this run is built to
  answer: M0374's softer discount broke the resemblance to the failed momentum book partly *because*
  it left money uninvested. If giving that money back to the book's other names also gives back
  most of the resemblance — because those other names are still asymmetry-ranked, momentum-adjacent
  picks from the same universe — then restoring exposure and clearing the kin test may turn out to
  be the same two things this family has never managed at once, not two independent levers.
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
from seer_engine.lab.methods.m0374_softened_exclusion_downweight import (
    SoftExclParams,
    downweight,
    momentum_top,
)
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorRow, factor_rows

ADDED = date(2026, 10, 26)


def _check(params: object) -> SoftExclParams:
    if not isinstance(params, SoftExclParams):
        raise TypeError(f"params must be SoftExclParams, got {type(params).__name__}")
    return params


def rescale_freed(before: tuple[Target, ...], after: tuple[Target, ...],
                   barred: frozenset[str]) -> tuple[Target, ...]:
    """``after``'s non-``barred`` weights scaled up so the total returns to ``before``'s total.

    ``before`` is the book's picks prior to any discount; ``after`` is the same picks with
    ``downweight`` already applied. The gap between the two totals is handed back to the
    non-barred names, in proportion to the weight each already holds in ``after``. A barred name's
    own weight is left exactly as ``downweight`` set it. When ``after`` holds no non-barred name
    (every held name is inside ``barred``) there is nothing to rescale into and ``after`` is
    returned unchanged.
    """
    total_before = sum((t.weight for t in before), Decimal(0))
    total_after = sum((t.weight for t in after), Decimal(0))
    freed = total_before - total_after
    if freed <= 0:
        return after
    non_barred_total = sum((t.weight for t in after if t.symbol not in barred), Decimal(0))
    if non_barred_total <= 0:
        return after
    factor = float((non_barred_total + freed) / non_barred_total)
    out: list[Target] = []
    for t in after:
        if t.symbol in barred:
            out.append(t)
            continue
        out.append(replace(t, weight=to_weight(Decimal(repr(float(t.weight) * factor)))))
    return tuple(out)


class RescaledSoftExclusionAllocator:
    """M0374's soft exclusion, with the discount's freed weight recycled into the book, not cash.

    Screen, rank and the per-name discount are exactly M0374's own code (``downweight``,
    ``momentum_top``, both imported unchanged). The only new step: the weight a discounted name
    gives up is handed back to the book's other held names, proportional to their own weight, so
    the check's total invested weight matches what the undiluted M0133 book would have held that
    day.
    """

    id = "M0377"

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
        barred = momentum_top(rows, p.momentum_top_n)
        discounted = downweight(targets, barred, p.down_weight)
        return rescale_freed(targets, discounted, barred)

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


RESCALE = RescaledSoftExclusionAllocator()


def _v(suffix: str, params: SoftExclParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0377-{suffix}", family="M0377", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=RESCALE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0377",
    name="Rescale the softened-exclusion book to keep full exposure",
    family="stock-updown-asymmetry",
    source_kind="variation",
    source_ref="variation of M0374 (soft exclusion on momentum's top names); the exact next move M0374's own closing opinion named",
    parent_id="M0374",
    hypothesis=(
        "M0374 measured that halving the weight of momentum's top 20 names inside the undiluted "
        "M0133 asymmetry book (instead of fully barring them, M0160's approach) was the first arm "
        "in this exclusion line to clear both the luck test (DSR 0.906 at N=242) and the "
        "resemblance test to the failed momentum book (worst reading 0.81 against the 0.85 limit) "
        "at once. But it invested only 56.7% of the account on average, against the fully-barred "
        "book's 71.7%, and it then won just 1 of 4 walk-forward folds -- the worst record in the "
        "line -- so the hard gate refused it on the fold majority. The two other arms (top-20 at a "
        "quarter weight, 48.1% invested; top-40 at half weight, 45.8% invested) fell further from "
        "full exposure and missed the DSR bar outright (0.866 and 0.890). This method keeps the "
        "exact same discount and instead hands the weight it frees to the book's other held names, "
        "proportional to what each already holds, so the total invested weight returns to what the "
        "undiluted book would hold that day -- near the fully-barred book's 72% average, not the "
        "46-57% the plain discount leaves idle. Three arms, each paired one-for-one against a "
        "recorded M0374 trial by changing only where the freed weight goes: "
        "RESCALE20-W50-G40-UP63 against SOFT20-W50-G40-UP63, RESCALE40-W50-G40-UP63 against "
        "SOFT40-W50-G40-UP63 (a predicted null result: with momentum_top_n=40 on a 40-name book "
        "there may be no non-barred name left to rescale into), and RESCALE20-W25-G40-UP63 against "
        "SOFT20-W25-G40-UP63. Success: the top-20, half-weight arm keeps its DSR at or above 0.90 "
        "and its resemblance reading under 0.85 while its invested fraction rises materially above "
        "56.7%, and its walk-forward fold record improves on M0374's 1 of 4 -- ideally to a "
        "majority, which the hard gate requires before any promotion."
    ),
    expected_failure=(
        "The likeliest failure is that restoring exposure also restores the resemblance that going "
        "light on these names was what bought in the first place. The book's other held names are "
        "still asymmetry-ranked picks from the same momentum-adjacent universe as the names being "
        "discounted; handing them a bigger share of the book is not obviously different, in its "
        "effect on the book's monthly pattern, from simply holding more of the undiluted book. If "
        "the resemblance reading on the rescaled arm rises back toward or past 0.85, the honest "
        "reading is that this family has never actually had two separable levers -- exposure and "
        "resemblance move together, and the discount's earlier win on the kin test was only ever "
        "borrowing against the exposure it was giving up, not a free improvement. Second, the "
        "top-40 arm is expected to do nothing: with every held name inside the barred set, "
        "``rescale_freed`` has no non-barred name to give the freed weight to, and that arm should "
        "reproduce M0374-SOFT40-W50-G40-UP63's numbers almost exactly -- a predicted null result "
        "that would read as a bug if it did not happen. Third, even if resemblance stays clean and "
        "exposure recovers, nothing here guarantees the walk-forward fold record improves: M0374's "
        "weak fold record may trace to which years the discount happened to touch, not simply how "
        "much cash was idle, in which case rescaling restores the return and the exposure without "
        "fixing the one thing the hard gate actually checks. Fourth, survivorship is deferred again: "
        "the buy-data signal needs a majority fold record first, which is exactly what is in "
        "question here."
    ),
    candidates=(
        _v("RESCALE20-W50-G40-UP63",
           SoftExclParams(AsymParams(N40, gate="sma200-up63"), momentum_top_n=20, down_weight=0.5),
           "Momentum's top 20 at half weight, freed weight rescaled into the rest of the book: the headline"),
        _v("RESCALE40-W50-G40-UP63",
           SoftExclParams(AsymParams(N40, gate="sma200-up63"), momentum_top_n=40, down_weight=0.5),
           "Momentum's top 40 at half weight: the mechanical null arm, no non-barred name to rescale into"),
        _v("RESCALE20-W25-G40-UP63",
           SoftExclParams(AsymParams(N40, gate="sma200-up63"), momentum_top_n=20, down_weight=0.25),
           "Momentum's top 20 at a quarter weight, rescaled: the weight dose-response twin"),
    ),
    seen_keys=(
        "concept:proportional-exposure-rescale-on-downweighted-book",
    ),
)
