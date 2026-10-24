"""M0345 — Dearest-third buybacks re-tested against a blind draw that trades like the book.

Variation of M0252 (the double sort of buybacks and the yearly-high band). Reserved by Sera batch
20261024-1817 as an ``idea`` row; this file refines it and keeps its id.

Why a re-test. M0252 read its dearest-third shrinkers (RICH-S) 7.7 points a year ahead of the
blind draw (RICH-R) in 2009-2015, but RICH-R re-hashed the whole band every month and traded
about twice as often as the shrinkers, which the lab flags outside its control band. Part of that
gap can be fees the control paid and the book did not. This file keeps M0252's pool, band cut,
20 slots, monthly clock and real fees, and swaps only the opponent: ``lab.control_draw``'s matched
draw, which each month keeps all but ``e`` of its own names and draws ``e`` fresh ones, where
``e`` is how many names the shrinker book itself adds at that decision. Same size, same entries,
none of the names. Its pool is the same dearest third the shrinkers pick from.

Arms: DEAR-S (the 20 biggest share-count shrinkers in the dearest third) and DEAR-MD1/2/3, the
matched draw on three seeds, so the blind arm's own scatter is measured and the lead is read
against a spread rather than one draw (M0252 left that at one seed). The matched draw is the arm
with no opinion in it and the same trading habit, which is the third arm this comparison needs.

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by
the contract it targets nothing. Pure: reads only bars and counts public on or before
``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0015_52week_high import HIGH_N, nearness
from seer_engine.lab.methods.m0227_net_share_shrinkers import (
    DV_N,
    LOOKBACK_DAYS,
    MIN_COUNT_GAP_DAYS,
    IssuancePrepared,
    scored_pool,
)
from seer_engine.lab.methods.m0252_cheap_band_buybacks import BAND_FRACTION, band_members
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 24)

PICKS = ("shrink", "matched")


@dataclass(frozen=True, slots=True)
class DearParams:
    """``top`` names held from the dearest third of the pool; ``pick`` is ``shrink`` (the biggest
    share-count shrinkers) or ``matched`` (the lab's matched blind draw on the shrinkers' own
    entry count); ``seed`` the draw's seed."""

    top: int
    pick: str = "shrink"
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.pick not in PICKS:
            raise ValueError(f"pick must be one of {PICKS}, got {self.pick!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if self.pick != "matched" and self.seed != 0:
            raise ValueError("seed is for the matched draw only")

    def as_dict(self) -> dict[str, str]:
        out = {
            "top": str(self.top),
            "pick": self.pick,
            "band": "rich",
            "band_fraction": f"1/{BAND_FRACTION}",
            "band_on": "nearness-ascending",
            "high_n": str(HIGH_N),
            "tiebreak": "symbol",
            "lookback_days": str(LOOKBACK_DAYS),
            "min_count_gap_days": str(MIN_COUNT_GAP_DAYS),
            "dv_n": str(DV_N),
        }
        if self.pick == "matched":
            out["seed"] = str(self.seed)
            out["control"] = control_draw.RULE_ID
        return out


def _check(params: object) -> DearParams:
    if not isinstance(params, DearParams):
        raise TypeError(f"params must be DearParams, got {type(params).__name__}")
    return params


class DearBandAllocator:
    """The ``top`` biggest share-count shrinkers inside the dearest third of M0227's scored pool
    by nearness to the 52-week high, or the matched blind draw shaped like that book. Equal
    slots, fully invested. No share counts (history-only path): no targets."""

    id = "M0345"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        _check(params)
        return control_draw.lookback_for(max(DV_N, HIGH_N))

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _select(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
                p: DearParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the dearest third, the shrinkers' own book) on ``data_date``."""
        scored = scored_pool(prepared, members, data_date)
        if not scored:
            return (), ()
        near: dict[str, float] = {}
        for s in scored:
            v = nearness(prepared.history, s, data_date, HIGH_N)
            if v is not None:
                near[s] = v
        band = band_members(near, "rich")
        order = sorted(band, key=lambda s: (scored[s], s))
        return tuple(sorted(band)), tuple(order[: p.top])

    def _run(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: DearParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if p.pick == "shrink":
            names = self._select(prepared, members, data_date, p)[1]
        else:
            names = tuple(control_draw.matched_book(
                lambda d: self._select(prepared, members, d, p),
                data_date, held, tag="M0345", seed=p.seed,
            ))
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no signal and no target."""
        return self._run(IssuancePrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> IssuancePrepared:
        return IssuancePrepared(history, None)

    def prepare_market(self, market: Any) -> IssuancePrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return IssuancePrepared(market.history, None)
        return IssuancePrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IssuancePrepared):
            raise TypeError(f"prepared must be IssuancePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


DEAR_BAND = DearBandAllocator()


def _v(suffix: str, params: DearParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0345-{suffix}", family="M0345", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DEAR_BAND, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0345",
    name="Dearest-third buybacks re-tested against a blind draw that trades like the book",
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref=(
        "variation of M0252 (dearest-third buyback shrinkers vs a monthly-redrawn blind draw); "
        "matched draw of lab.control_draw (M0227's amendment); Pontiff & Woodgate (2008) JF 63(2) "
        "921-945, https://ideas.repec.org/a/bla/jfinan/v63y2008i2p921-945.html"
    ),
    parent_id="M0252",
    hypothesis=(
        "M0252 found that inside the dearest third of the pool (nearest the yearly high) the 20 "
        "biggest share-shrinkers beat a blind draw by about 7.7 points a year in 2009-2015 on "
        "the dev store and 7.8 on the dead-company check store, while inside the cheapest third "
        "they added nothing. But that blind draw re-hashed the band every month and traded about "
        "2.1 times as often as the shrinkers (3752 trades against 1789 over the dev window, as "
        "M0252's own trials record), and the lab flags it outside its control band, so part of "
        "the gap may be fees the draw paid and the book did not. Keep M0252's pool, dearest-third "
        "cut, 20 equal slots, monthly clock, fractional shares and Gotrade's real fees, and "
        "replace only the opponent with the lab's matched draw: each month it keeps all but e of "
        "its names and draws e fresh ones from the same dearest third, where e is how many names "
        "the shrinker book adds at that decision, so it trades the shrinkers' own number of "
        "times. Three seeds (MD1, MD2, MD3), so the draw's own scatter is measured. Arms: DEAR-S "
        "and DEAR-MD1/2/3, all MONTHLY_HOLD_FRAC_GOTRADE, none timed. Published-anomaly note: "
        "buybacks (Pontiff-Woodgate 2008) are widely known and may have faded; the dev window "
        "can only show what existed before the crowd traded it. "
        "Predictions written before any result: (a) DEAR-S beats the MEDIAN matched draw by 3+ "
        "points a year in 2009-2015 on BOTH stores, which is what survives if the M0252 gap was "
        "mostly real; (b) each matched draw lands inside 0.80-1.25 of DEAR-S on both trades and "
        "turnover, which is the shape the rule promises; (c) the matched draws earn LESS than "
        "M0252's RICH-R, because they trade about half as often and pay about half the fees, so "
        "the lead shrinks from 7.7 but not to zero. Close-out rule: if DEAR-S's 2009-2015 lead "
        "over the median matched draw is under 3 points a year on either store, or smaller than "
        "the spread between the three draws, the dear-band result was churn and the family is "
        "closed on this question; if the lead holds on both stores it goes forward as a "
        "candidate to be judged by the full gate, and nothing here is itself a buy signal."
    ),
    expected_failure=(
        "Four ways. (1) The shape misses: a blind draw leaves the scored pool at its own rate, so "
        "its entries can exceed the shrinkers' e and its trades land above 1.25x. A miss on the "
        "rule is reported, not tuned away. (2) The lead was luck: twenty names from a dearest "
        "third of 30-80 names is a narrow pool and three seeds show a wide scatter, so a 7.7 point "
        "lead from one monthly-redrawn draw can shrink inside the new spread. (3) 2009-2015 "
        "fades or never held: the dear band's lead in M0252 was a post-hoc reading of one era "
        "and the arms are fixed here with no band width or lookback tuned afterwards. (4) "
        "Both arms fall past 48% at the 2008 worst, as M0252's dear arms did, so the dev "
        "drawdown screen fails whatever the lead says; the verdict is read on the lead, not on "
        "eligibility. A tweak after the result is a new method with new trials."
    ),
    candidates=(
        _v("DEAR-S", DearParams(20, "shrink"),
           "The idea: the 20 biggest one-year share-count shrinkers inside the dearest third"),
        _v("DEAR-MD1", DearParams(20, "matched", seed=1),
           "Placebo, hash-drawn from the same dearest third, matched to the shrinkers' own "
           "entry count and trades (seed 1)"),
        _v("DEAR-MD2", DearParams(20, "matched", seed=2),
           "Placebo, hash-drawn from the same dearest third, matched to the shrinkers' own "
           "entry count and trades (seed 2)"),
        _v("DEAR-MD3", DearParams(20, "matched", seed=3),
           "Placebo, hash-drawn from the same dearest third, matched to the shrinkers' own "
           "entry count and trades (seed 3)"),
    ),
    seen_keys=(
        "concept:dear-band-buybacks-matched-draw",
        "concept:buyback-shrinkers-dearest-third-vs-matched-placebo",
    ),
)
