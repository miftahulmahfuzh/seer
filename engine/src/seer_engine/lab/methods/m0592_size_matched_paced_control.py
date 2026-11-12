"""M0592 — Re-draw M0590's size-matched control at WIDE's own trading pace.

M0590-SM-WIDE was meant to answer one question: is M0590-WIDE's apparent edge (the 20 index
members with the widest estimated Corwin-Schultz bid-ask spread) a liquidity-risk premium, or is
it a small-company bet in a new coat, the way M0058's Amihud illiquidity book turned out to be?
It drew the same count of names per market-value quintile as WIDE held, hash-picked within the
quintile -- but the within-quintile pick used a DATE-FREE hash order (``m0293``'s ``draw``), so a
bucket's membership only changed when the bucket's NEED count changed. Measured by the lab's
control-shape check: 0.50x WIDE's trade count, 0.44x its turnover -- outside both the 0.80-1.25
clean band and the 0.50-2.00 refuse band, so `lab run` recorded it but the check could not call it
a fair control. SM-WIDE's calmer, better-looking ride (CAGR 35.3% vs WIDE's 34.9%, maxDD 23.9% vs
34.7%) is therefore not usable evidence either way: some of it may be paying half the fee bill,
not "the spread ranking adds nothing over size."

The fix. ``control_draw`` (built 2026-10-19 for exactly this class of problem) matches turnover by
construction: at each decision it reads the arm being controlled's own book today and at the
previous decision (both re-derived under TODAY's membership, so the comparison stays point-in-time
correct without needing historical membership), keeps all but ``e`` of its own names in a
date-free order, and draws ``e`` fresh ones in a month-keyed order, where ``e`` is the real arm's
own entry count. On an equal-weight chassis (this one: 20 equal slots) matching the trade count
matches the turnover too, because every slot moves the same fraction of the book per name
([[seer-matched-draw-cannot-match-turnover-on-weight-varying-chassis]] is about cap/size-WEIGHTED
books and does not apply here). This method applies that construction independently inside each of
the five market-value quintiles M0590-SM-WIDE already used -- so the size profile is unchanged --
with WIDE's own top-20 (re-scored at this decision and the previous one) as the arm each quintile's
slice is matched to. ``held`` is the book's own real previous holdings, read from the book runner
exactly as the module expects.

Frame: identical to M0590 (point-in-time members, F4's screen, 20 equal slots, monthly, fractional
shares at Gotrade's real fees, SPY's 200-day switch, market-aware on ``shares``). Two arms: PACED
(the re-drawn control, the new book this method records) and WIDE (M0590-WIDE's own book, repeated
under a new digest so the comparison runs in the same trial set instead of being read off a
different method's row).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0590_corwin_schultz_spread import CORWINSCHULTZ, SpreadParams, scored_names
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    factor_lookback,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 12)

BUCKETS = 5  # market-value quintiles, same cut as M0590-SM-WIDE
WIN_BARS = 22  # WIN=21 overlapping two-day pairs -> 22 bars, mirrors M0590's spread estimator


@dataclass(frozen=True, slots=True)
class PacedParams:
    """``inner`` is the shared host's screen, switch, book size and weighting; ``seed`` keys the
    control-draw hashes. No ``mode`` field: this allocator only ever draws the paced, size-matched
    control -- WIDE's own book is recorded by reusing M0590's own allocator, not this one."""

    inner: FactorParams
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"seed": str(self.seed), "buckets": str(BUCKETS), "rule": control_draw.RULE_ID}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> PacedParams:
    if not isinstance(params, PacedParams):
        raise TypeError(f"params must be PacedParams, got {type(params).__name__}")
    return params


def _wide_symbols(prepared: "PacedPrepared", members: AbstractSet[str], data_date: date,
                   inner: FactorParams) -> list[str]:
    """WIDE's own top-N picks at ``data_date``, re-derived under TODAY's ``members``.

    This is ``control_draw``'s documented contract for the earlier reading: both readings use
    today's membership, and only the prices/filings read at ``data_date`` differ -- which is why
    no point-in-time membership lookup for an earlier date is needed here at all."""
    if not trend_on(prepared.history, data_date, inner):
        return []
    rows = prepared.factor.rows_on(members, data_date, inner)
    syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
    spread = scored_names(prepared.history, syms, data_date)
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in spread]
    ranked = sorted(pool, key=lambda r: (-spread[r.symbol], r.symbol))
    return [r.symbol for r in ranked[: inner.top]]


def _sized_pool(prepared: "PacedPrepared", members: AbstractSet[str], data_date: date,
                 inner: FactorParams) -> dict[str, float]:
    """Market value of every name in the spread-scored pool on ``data_date`` -- the exact pool
    M0590-SM-WIDE cut into quintiles."""
    if not trend_on(prepared.history, data_date, inner):
        return {}
    rows = prepared.factor.rows_on(members, data_date, inner)
    syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
    spread = scored_names(prepared.history, syms, data_date)
    size: dict[str, float] = {}
    for s in syms:
        if s not in spread:
            continue
        v = prepared.market.market_value(s, data_date)
        if v is not None and np.isfinite(v) and v > 0.0:
            size[s] = float(v)
    return size


def paced_size_matched_names(prepared: "PacedPrepared", members: AbstractSet[str], data_date: date,
                              held: AbstractSet[str], p: PacedParams) -> list[str]:
    """SM-WIDE's book, re-drawn so each quintile's entry count -- and so the whole book's -- is
    matched to WIDE's own turnover by ``control_draw.matched_names``, not a sticky hash."""
    size = _sized_pool(prepared, members, data_date, p.inner)
    if not size:
        return []
    by_size = sorted(size, key=lambda s: (size[s], s))
    n = len(by_size)
    bucket = {s: min(BUCKETS - 1, i * BUCKETS // n) for i, s in enumerate(by_size)}
    now_wide = [s for s in _wide_symbols(prepared, members, data_date, p.inner) if s in bucket]
    prev_date = control_draw.previous_decision_date(data_date)
    prev_wide = [s for s in _wide_symbols(prepared, members, prev_date, p.inner) if s in bucket]
    out: list[str] = []
    for b in range(BUCKETS):
        pool_b = [s for s in size if bucket[s] == b]
        held_b = frozenset(s for s in held if bucket.get(s) == b)
        now_b = [s for s in now_wide if bucket[s] == b]
        prev_b = [s for s in prev_wide if bucket[s] == b]
        out.extend(control_draw.matched_names(
            pool=pool_b, held=held_b, real_now=now_b, real_prev=prev_b,
            tag=f"M0592-b{b}", seed=p.seed, data_date=data_date,
        ))
    return out


@dataclass
class PacedPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    market: Any = field(default=None, repr=False)


class PacedSizeMatchAllocator:
    """M0590-SM-WIDE's size-matched control for WIDE, re-drawn with ``control_draw`` so it trades
    at WIDE's own pace instead of a date-free sticky hash per quintile. Market-aware, like M0590:
    no store, no targets."""

    id = "M0592"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        inner = max(factor_lookback(p.inner), WIN_BARS)
        return control_draw.lookback_for(inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {"SPY"}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: PacedPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: PacedParams) -> tuple[Target, ...]:
        if prepared.market is None:  # the lab's market-aware contract: no panel, no targets
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        names = set(paced_size_matched_names(prepared, members, data_date, held, p))
        if not names:
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        chosen = [r for r in rows if r.symbol in names]
        return targets_from_rows(chosen, p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no market, so no arm targets anything (the contract)."""
        return self._run(PacedPrepared(history, prepare_factor(history), None), members,
                         data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> PacedPrepared:
        return PacedPrepared(history, prepare_factor(history), None)

    def prepare_market(self, market: Any) -> PacedPrepared:
        sized = len(market.shares) > 0
        return PacedPrepared(market.history, prepare_factor(market.history),
                             market if sized else None)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PacedPrepared):
            raise TypeError(f"prepared must be PacedPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


PACED = PacedSizeMatchAllocator()


def _v_paced(suffix: str, params: PacedParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0592-{suffix}", family="M0592", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=PACED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _v_wide(suffix: str, params: SpreadParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0592-{suffix}", family="M0592", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CORWINSCHULTZ, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0592",
    name="Re-draw M0590's size-matched control at WIDE's own trading pace",
    family="stock-corwin-schultz-spread",
    source_kind="variation",
    source_ref="M0590",
    parent_id="M0590",
    hypothesis=(
        "M0590-SM-WIDE (the size-matched blind-draw control for M0590-WIDE) was refused by the "
        "lab's control-shape check: it traded at 0.50x WIDE's trade count and 0.44x its turnover, "
        "outside both the 0.80-1.25 clean band and the 0.50-2.00 refuse band. The cause is its "
        "within-quintile pick order: a date-free hash (m0293's `draw`) that only reshuffles a "
        "bucket when WIDE's own need-count for that bucket changes, so most months the control's "
        "names do not move at all. This method re-draws the same five market-value quintiles "
        "M0590-SM-WIDE used, but inside each one applies `control_draw.matched_names` -- the "
        "lab's general-purpose turnover-matching construction, built 2026-10-19 -- keyed to "
        "WIDE's own entry count at that decision (WIDE's top-20 re-scored today and at the "
        "previous decision, both under today's point-in-time membership, which is the module's "
        "documented contract for a chassis with no keep-band). On an equal-weight book, matching "
        "the entry count matches the turnover too, because every slot moves the same fraction of "
        "the book per name regardless of which name it is. WIDE's own book is repeated under this "
        "method's own digest (candidate WIDE, reusing M0590's `CorwinSchultzAllocator` and its "
        "`SpreadParams(N20, 'wide')`) so the comparison runs inside one trial set rather than "
        "being read off a different method's row. Predictions, written now: PACED's trade count "
        "and turnover land inside the 0.80-1.25 band against WIDE's own recorded figures, closing "
        "the fairness gap the old control failed on. Because the old, under-traded SM-WIDE "
        "already beat WIDE on the raw 20-year number (CAGR 35.3% vs 34.9%, maxDD 23.9% vs 34.7%, "
        "PF 2.59 vs 1.31) while paying roughly half the fees, forcing it to pay WIDE's own fee "
        "pace should make the control look WORSE relative to WIDE, not better -- so if PACED's "
        "edge over WIDE narrows or reverses once both pay the same pace of fees, that argues "
        "WIDE's spread ranking adds nothing over size (M0058's conclusion, reached a different "
        "way); if PACED still clearly beats WIDE even at a fair pace, the size story gets "
        "stronger, because a correctly-paced random size-matched draw would then be beating the "
        "book that was supposed to be picking on more than size."
    ),
    expected_failure=(
        "The likeliest failure mirrors the direction the raw numbers already point: SM-WIDE beat "
        "WIDE on CAGR while trading at roughly half WIDE's pace, so paying WIDE's own, higher fee "
        "pace should erode PACED's edge -- the open question is only how much, and 'how much' is "
        "exactly what was unmeasurable before this run. A second, independent failure: the "
        "per-quintile application of `matched_names` may itself land outside the 0.80-1.25 band, "
        "because bucket boundaries are recomputed fresh every month from the day's sized pool, so "
        "a name can cross a quintile edge between decisions for reasons that have nothing to do "
        "with WIDE's own churn -- a second, different control-shape defect, to be reported and "
        "queued rather than hand-tuned away. A third: PACED's own fairness check could pass "
        "while its fold record or DSR still fails outright (the same fate M0590-WIDE itself had, "
        "DSR 0.704 < 0.90), in which case the size question is answered but the method as a whole "
        "is still not eligible."
    ),
    candidates=(
        _v_paced("PACED", PacedParams(N20, seed=592),
                 "The size-matched control re-drawn with control_draw.matched_names, keyed to "
                 "WIDE's own entry count per quintile: the fairly-paced comparison this method "
                 "exists to make"),
        _v_wide("WIDE", SpreadParams(N20, "wide"),
                "Host: repeats M0590-WIDE's book (trial #2099), run again under this method's own "
                "digest so PACED is compared against it inside one trial set"),
    ),
    seen_keys=(
        "concept:size-matched-control-redrawn-at-own-pace",
        "concept:control-shape-check-refused-sm-wide",
    ),
)
