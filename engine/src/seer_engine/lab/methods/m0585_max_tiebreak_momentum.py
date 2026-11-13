"""M0585 -- Score the lottery-day jump inside a momentum book, instead of filtering a flat one.

Source: variation of M0526 (Sera 20261113-1758); Bali, Cakici & Whitelaw, Maxing Out: Stocks as
Lotteries and the Cross-Section of Expected Returns, Journal of Financial Economics 2011.
Idea: M0526 dropped a stock's lottery-day jump (its largest one-day gain in the trailing month)
from a flat, equal-weight, liquidity-ranked pool. The filter beat its own random-drop controls --
money-weighted +6.5%/yr vs +5.2-5.6%/yr, PF 1.52 vs 1.28-1.30, worst fall 47% vs 58-60% -- but the
unfiltered base book itself already lost to SPY on the owner's deposits (+5.8%/yr vs +7.2%/yr), so
no filter on top of a losing book could close the gap. M0353's plain-MAX, lowest-MAX-20 book
behind the SPY 200-day switch came closest of any MAX-based book in this lab (DSR 0.907, N=227),
missing only by about 0.1 point a year on the owner's deposits.

This method gives MAX a winning base to act on instead of re-testing it alone. M0032's
``M0032-N20-RAW-FRAC-GT`` (first recorded trial #129, dev-eligible) is the realistic, Gotrade-fee,
fractional-share twin of M0007's residual-momentum book -- it already beats a deposit-matched SPY
TR (funded +13.7%/yr vs +7.2%/yr) and fails only the fall limit, by about half a point (20.6% vs
20%). Inside that exact book, the trailing-``max_window``-session MAX (Bali-Cakici-Whitelaw's
MAX(1)) is used as a tie-break: every name that already clears the residual-momentum screen keeps
its place in the pool, but its rank score is nudged down by how extreme its own recent one-day
jump was, so between two similar momentum names the one that got there on a single lottery-like
pop ranks slightly lower. This is a soft secondary rank, not a veto over a flat pool (M0526's
mechanism) and not a sole score (M0353's mechanism): it only ever reorders names the momentum
screen already let in.

**Control, not re-run.** ``M0032-N20-RAW-FRAC-GT`` (trial #129) IS the zero-penalty arm of this
dial -- the unmodified momentum book, same chassis, same rules, same funding. Re-running it here
would record a book twin and spend nothing new, so it is cited instead: the dial's four weighted
arms below are judged against its recorded +13.7%/yr funded return, 20.6% max DD and DSR 0.9122.

On data date d, for the symbols that already clear M0007-N20-RAW's residual-momentum screen
(F4's liquidity/price floor, SPY-200 trend gate, 12-1 market-model residual momentum, unscaled):

  * **MAX**: each eligible name's largest one-day simple return over its trailing
    ``max_window`` sessions through d (M0526's ``max_day_return``, identical function).
  * **the combined score**: ``resid_score - penalty_weight * zscore(MAX)``, the z-score taken
    over the same eligible pool on the same day. A name with no computable MAX (too few bars) is
    scored on its residual momentum alone, unpenalised, rather than dropped -- MAX is a tie-break,
    never a disqualifier.
  * the ``top`` (20) highest combined scores are held, equal-weighted, exactly as the parent book
    weights. Held names get no special treatment: each month is a fresh pick.

Four weights (0.25, 0.5, 1.0, 2.0) trace the dial from a light nudge to a score where MAX can
dominate a middling residual-momentum reading. Success: a weight exists where the combined book's
worst fall drops below 20% while funded CAGR stays above the deposit-matched SPY's 7.2%/yr --
closing the 0.6-point fall gap that is M0032's only failure, the way its own analysis suggested a
volatility brake might (4/5 of a CAGR point per point of fall removed, there; this dial is untested
at that rate). Fractional shares at Gotrade's real fees throughout, on the owner's real funding
plan, matching the control book it is judged against.

Pure. Reads only bars dated <= ``data_date``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    FACTOR_SYMBOLS,
    ResidParams,
    ResidPrepared,
    resid_lookback,
    residual_scores,
    targets_from_scores,
)
from seer_engine.lab.methods.m0526_stock_max_day_filter import max_day_return
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import prepare_factor, trend_on

ADDED = date(2026, 11, 13)


def _check_float(name: str, v: object, lo: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(v).__name__}")
    x = float(v)
    if not (x >= lo):
        raise ValueError(f"{name} must be >= {lo}, got {x}")
    return x


def _check_int(name: str, v: object, lo: int) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < lo:
        raise ValueError(f"{name} must be >= {lo}, got {v}")
    return v


@dataclass(frozen=True, slots=True)
class TieBreakParams:
    """``resid`` fixes the momentum screen, the trend gate and the eligible pool verbatim; MAX
    only ever reorders what that screen already let through."""

    resid: ResidParams
    max_window: int = 21
    penalty_weight: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.resid, ResidParams):
            raise TypeError(f"resid must be ResidParams, got {type(self.resid).__name__}")
        _check_int("max_window", self.max_window, 2)
        object.__setattr__(
            self, "penalty_weight", _check_float("penalty_weight", self.penalty_weight, 0.0)
        )

    def as_dict(self) -> dict[str, str]:
        out = {"max_window": str(self.max_window), "penalty_weight": f"{self.penalty_weight:.4f}"}
        for k, v in self.resid.as_dict().items():
            out[f"resid.{k}"] = v
        return out


def _check(params: object) -> TieBreakParams:
    if not isinstance(params, TieBreakParams):
        raise TypeError(f"params must be TieBreakParams, got {type(params).__name__}")
    return params


def combined_scores(
    history: Mapping[str, History],
    resid_scored: Mapping[str, float],
    data_date: date,
    p: TieBreakParams,
) -> dict[str, float]:
    """Each already-eligible name's residual-momentum score, nudged down by its own MAX z-score.

    A name whose MAX cannot be computed (too few trailing bars) keeps its unpenalised residual
    score rather than being dropped: MAX tie-breaks among eligible names, it never disqualifies.
    """
    max_vals = {
        s: m
        for s in resid_scored
        if (m := max_day_return(history, s, data_date, p.max_window)) is not None
    }
    if not max_vals or p.penalty_weight == 0.0:
        return dict(resid_scored)
    values = list(max_vals.values())
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    sd = math.sqrt(var)
    if sd <= 0.0:
        return dict(resid_scored)
    out: dict[str, float] = {}
    for s, score in resid_scored.items():
        mv = max_vals.get(s)
        if mv is None:
            out[s] = score
        else:
            out[s] = score - p.penalty_weight * ((mv - mean) / sd)
    return out


class MaxTiebreakMomentumAllocator:
    """M0007-N20-RAW's book (equivalently M0032's fractional-Gotrade twin), re-ranked by MAX.

    The eligible pool, the trend gate and the equal weighting are M0007's, read verbatim; only the
    rank key changes, from the raw residual score alone to that score minus a MAX penalty.
    """

    id = "M0585"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(resid_lookback(p.resid), p.max_window + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({p.resid.market, *FACTOR_SYMBOLS(p.resid.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(
        self,
        prepared: ResidPrepared,
        members: AbstractSet[str],
        data_date: date,
        p: TieBreakParams,
    ) -> tuple[Target, ...]:
        if not trend_on(prepared.history, data_date, p.resid.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.resid.inner)
        if not rows:
            return ()
        grid = prepared.grid(p.resid.market)
        if grid is None:
            return ()
        resid_scored = residual_scores(grid, [r.symbol for r in rows], data_date, p.resid)
        if not resid_scored:
            return ()
        scores = combined_scores(prepared.history, resid_scored, data_date, p)
        return targets_from_scores(rows, scores, p.resid)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        return self._run(ResidPrepared(history, prepare_factor(history)), members, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


TIEBREAK = MaxTiebreakMomentumAllocator()

BASE = ResidParams(N20, scaled=False)  # M0007-N20-RAW == M0032-N20-RAW-FRAC-GT's chassis


def _v(suffix: str, weight: float, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0585-{suffix}",
        family="M0585",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=TIEBREAK,
        params=TieBreakParams(BASE, penalty_weight=weight),
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0585",
    name="Score the lottery-day jump inside a momentum book instead of filtering a flat book",
    family="stock-max-day-rank",
    source_kind="variation",
    source_ref=(
        "variation of M0526 (Sera 20261113-1758); Bali, Cakici & Whitelaw, Maxing Out: Stocks as "
        "Lotteries and the Cross-Section of Expected Returns, Journal of Financial Economics 2011"
    ),
    parent_id="M0526",
    hypothesis=(
        "M0526 found that dropping a stock's lottery-day jump from a flat, equal-weight, "
        "liquidity-ranked book earned more than dropping an equal-size random subset "
        "(money-weighted +6.5%/yr vs +5.2-5.6%/yr, PF 1.52 vs 1.28-1.30, worst fall 47% vs "
        "58-60%), but the unfiltered base book itself already lost to SPY on the owner's deposits "
        "(+5.8%/yr vs +7.2%/yr), so no filter on top of it could close the gap. M0353's "
        "MAX5-LO-N20-T (plain MAX, lowest-MAX 20 names behind the SPY-200 switch) came closest of "
        "any MAX-based book in this lab (DSR 0.907, N=227), missing beating SPY TR by about 0.1 "
        "point a year on the owner's deposits. This method gives MAX a winning base to act on "
        "instead: inside M0007-N20-RAW's momentum-ranked, residual-screened book -- whose "
        "fractional, Gotrade-fee, funded twin M0032-N20-RAW-FRAC-GT (trial #129, dev-eligible) "
        "already beats a deposit-matched SPY TR funded +13.7%/yr vs +7.2%/yr and fails only the "
        "20% fall limit, by about half a point at 20.6% -- MAX is used as a tie-break on the rank "
        "score among names the residual-momentum screen already admitted, never as a sole score "
        "(M0353's mechanism) or a veto over a flat pool (M0526's mechanism). The combined score is "
        "resid_score - penalty_weight * zscore(MAX) at four weights (0.25, 0.5, 1.0, 2.0); the "
        "unmodified book, M0032-N20-RAW-FRAC-GT, is this dial's own zero-weight arm and is cited "
        "by its recorded trial rather than re-run. Success: some weight lowers the worst fall "
        "below 20% while funded CAGR stays above 7.2%/yr, closing the 0.6-point fall gap that is "
        "M0032's only failure."
    ),
    expected_failure=(
        "The lottery-day effect is a cross-sectional, stock-level prediction about that stock's "
        "own next month (Bali-Cakici-Whitelaw measured it on a broad, unscreened universe), and "
        "this book's pool is already pre-selected for strong recent idiosyncratic momentum -- a "
        "name that is there because of a genuine, persistent move, not a one-day fluke, may show "
        "almost no MAX signal left to extract, so the dial does nothing: all four weights trace "
        "one curve, or nearly M0032's own, because the z-score penalty rarely changes who is in "
        "the top 20. If it does move the book, the more likely direction is the wrong one: a stock "
        "whose momentum run included one outsized day is not obviously a worse momentum stock, and "
        "down-ranking it may simply remove some of the best-performing names from the book, trading "
        "away CAGR for a fall reduction that does not materialise, or moving both the wrong way at "
        "once. Either failure leaves M0032's 0.6-point fall gap unclosed by this dial, and the next "
        "session's own note on M0032 already named a volatility brake, not a rank tie-break, as the "
        "more directly targeted fix to try next."
    ),
    candidates=(
        _v("TB025", 0.25, "lightest nudge: MAX penalty at a quarter weight"),
        _v("TB050", 0.50, "half weight"),
        _v("TB100", 1.00, "MAX and residual momentum weighted equally in the combined score"),
        _v("TB200", 2.00, "MAX dominant: the heaviest tie-break tried, where MAX can outweigh a middling residual reading"),
    ),
    seen_keys=(
        "concept:lottery-effect-inside-momentum-book",
        "concept:max-day-tiebreak-momentum",
        "concept:bali-cakici-whitelaw-max",
    ),
)
