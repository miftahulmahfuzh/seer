"""M0313 — Does the fall-width finding transfer to a momentum book behind the same switch?

Source: variation of M0306 (the gated-versus-ungated blind-draw spread, finished to nineteen
draws on a three-industry book). The question is again about the lab's own instrument, not about
the market.

**What M0306 found, verified from its own recorded trials and verdict.** Nineteen identical
three-industry draws run with the SPY 200-day switch ON were compared, coin for coin, against the
same nineteen run with the switch OFF (M0296). The switch cut every draw's worst fall by about 30
points on average (mean -30.42; worst fall 20.0% to 43.0% switch-on against 49.0% to 69.7%
switch-off) without narrowing the SPREAD of falls at all:

    worst-fall spread ratio  = 22.9 / 20.7 = 1.105   (dilution-by-time-invested null: 0.720)
    money-return spread ratio = 0.683                 (near the 0.720 null)
    worst-year spread ratio   = 0.378                 (real compression)

The proposed mechanism: the switch removes the one anchor every switch-off draw shares — 2008,
every ungated draw's deepest fall — and leaves each gated draw's deepest fall to be its own
private whipsaw accident (a sale into a dip, a miss of the bounce, a re-entry higher), so the
gated falls stop being pulled toward a common number and spread out around a much shallower
average instead. That mechanism is about the switch and the book's re-entry timing; it does not
read what the book ranks on. If it is right, the same non-narrowing should appear on any
re-picked, re-entering book behind the identical switch — in particular on the twenty-name
momentum-shaped books that are actually on this lab's leaderboard (M0007, M0020, M0022), which
M0306's three-industry draws were never built to resemble.

**What this method draws instead.** The same placebo mechanism M0295 and M0306 already use
(``blake2b(seed | key | year-month)``, M0187's placebo order) applied to the chassis the momentum
near misses actually run on: F4's screen (12-1 momentum eligibility window, close >= $5, 20-day
mean dollar volume > $20M, at least 253 bars) and its SPY-200-day trend gate, twenty equal slots,
re-picked every month end. The only thing this allocator does differently from a real momentum
book is the pick: instead of ranking the eligible pool by residual or total momentum, it orders
the pool by the seed-and-month hash and takes the top twenty. No ranking opinion survives
anywhere in it. An unfilled slot holds SPY, exactly as M0295's industry draw does.

**Scale: six matched pairs, not nineteen.** The reserved idea asked for nineteen gated draws
against nineteen ungated. A batch is limited to six candidates, and M0306 itself only reached
nineteen by stacking three sibling methods' worth of batches over several runs (M0295's seed 1,
M0307's seeds 2-7, M0306's seeds 8-19). Spending that scale on a first look at a brand-new chassis
— one this method has to build from nothing, unlike M0306's reuse of M0295's engine — is not
proportionate before the direction is even known. This file follows the pattern M0306 itself
names approvingly for M0307's six: a first block the lab can act on, with a widening queued if it
leaves the question genuinely open. Seeds 1-6 are run gated (the main candidates) and the
identical seeds 1-6 are run ungated (the amendment below), so the two populations are matched pair
for pair as well as comparable as independent spreads — strictly more information than
independent seeds would give, at no extra cost, exactly as M0306's assumption 3 argues.

**The deliverable.** Six numbers on each side (money return, worst fall, worst year,
gains-to-losses, turnover, trades) and the ratio of the gated spread to the ungated spread on
each, read beside M0306's nineteen-draw ratios (1.105 worst-fall, 0.683 money, 0.378 worst-year)
and beside M0306's exposure-dilution null (0.720). No arm is expected to be eligible and none is
designed to be: every arm is a hash draw with no opinion in it. A ratio pattern similar to
M0306's — fall spread at or above the switch-off spread, money spread near the dilution null —
says the fall-width finding generalises to the chassis that matters and M0306's practical rule
(never read a worst-fall difference between two gated books as evidence under about 20 points)
applies to the leaderboard's own book shape. A ratio that comes in clearly narrower says the
non-narrowing was a property of the three-industry draw specifically, and a momentum-shaped
control needs its own, separately measured ruler.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits, identical to every arm this is read against. Pure: reads only bars dated at or
before d; the hash is a function of the seed, the symbol and the data date's year-month, nothing
else.

Assumptions, written before the run:

1. A seed is an arbitrary label; seeds 1-6 are as good a sample of "a blind twenty-name F4-screen
   draw" as any other six would be.
2. The F4-screened pool on any given month end is far larger than twenty names (it is the same
   pool F4-MOM12-N20-TREND and M0007-N20 rank over), so six different seeds should select six
   genuinely different books rather than converging on the same large, liquid names. If the six
   gated draws (or the six ungated ones) land within a point or two of each other on every meter,
   that convergence — not a narrow true spread — is the likely explanation, and the expected
   failure below says what it would mean.
3. Pairing seed-for-seed with the gated arm is sound because both differ in exactly one field,
   the trend gate, on the same allocator object and the same store fingerprint.
4. Family is ``stock-portfolio-construction``, the reserved idea row's choice, matching M0306 and
   M0296 rather than any momentum family string: every arm here is a hash draw with no momentum
   opinion in it, so what it varies is construction, not a signal. The hard gate reads behaviour,
   not the family label, so this choice changes nothing in the kin rule.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0295_industry_bellwether_lead_lag import draw
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 23)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class BlindMomParams:
    """``inner`` is the F4 screen, eligibility window, trend gate and book size (top=20).

    The pick inside the eligible pool carries no opinion: each name's rank is a hash of the seed,
    the symbol and the decision month, M0295/M0306's placebo draw. ``inner.rank`` is never read
    for selection; it is kept at ``"momentum"`` only so the eligibility window matches
    F4-MOM12-N20-TREND's and M0007's byte for byte.
    """

    inner: FactorParams
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"seed": str(self.seed), "market": self.market, "pick": "blake2b-month-hash"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> BlindMomParams:
    if not isinstance(params, BlindMomParams):
        raise TypeError(f"params must be BlindMomParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the draw


def build(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
          p: BlindMomParams) -> tuple[Target, ...]:
    """The F4-screened pool, hash-ordered and truncated to ``inner.top``, equal-weighted.

    A slot the pool cannot fill holds the market symbol, as M0295's industry draw does.
    """
    close = {r.symbol: r.close for r in rows}
    chosen = sorted(
        (r.symbol for r in rows if r.symbol != p.market),
        key=lambda s: (draw(p.seed, s, data_date), s),
    )[: p.inner.top]
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in chosen:
        t = target_from_close(s, close[s], w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None:
        i = mh.index_of(data_date)
        if i is not None:
            t = target_from_close(p.market, float(mh.close[i]), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


@dataclass(frozen=True, slots=True, eq=False)
class BlindMomPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class BlindMomAllocator:
    """A twenty-name book drawn from the F4 momentum screen with no ranking opinion in it.

    Membership is decided by a hash of the seed, the symbol and the month, not by any score.
    Held symbols get no special treatment: the targets are exactly the new drawn set, so a name
    that falls out of it is signal-exited by the book engine, as F4 does.
    """

    id = "M0313"

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        if not rows:
            return ()
        return build(history, rows, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> BlindMomPrepared:
        return BlindMomPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BlindMomPrepared):
            raise TypeError(f"prepared must be BlindMomPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        return build(prepared.history, rows, data_date, p)


BLINDMOM = BlindMomAllocator()

TREND = ("SPY", 200)
GATED = FactorParams(rank="momentum", top=20, trend=TREND)
OPEN = FactorParams(rank="momentum", top=20, trend=None)

#: The seeds this method spends on each side of the switch: six matched pairs (see the docstring
#: for why six rather than nineteen). The identical seeds run gated and ungated.
SEEDS = (1, 2, 3, 4, 5, 6)


def _draw(suffix: str, seed: int, inner: FactorParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0313-{suffix}", family="M0313", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BLINDMOM, params=BlindMomParams(inner=inner, seed=seed),
                     rationale=rationale, added=ADDED, owner_inputs=())


# --------------------------------------------------------------------------- amendment

AMEND_1 = Amendment(
    added=ADDED,
    why=(
        "The ungated half of the same six matched pairs, pre-registered in the same commit as "
        "the gated half and before either runs. A batch is limited to six candidates, so the "
        "twelve trials this method spends split into two blocks; the reading rule below is fixed "
        "for both and admits no choice once the gated block's seeds are known."
    ),
    hypothesis=(
        "Seeds 1-6 run with the SPY 200-day trend gate OFF (always invested) reproduce the other "
        "half of M0306's comparison on this chassis: the switch-off population the six gated "
        "draws are read against. Under the same dilution-by-time-invested mechanism M0306 "
        "measured, exposure should fall from near 1.0 ungated to roughly M0306's 0.694-0.964 "
        "range gated, and the money-return spread ratio should sit near that exposure ratio while "
        "the worst-fall ratio is the one meter free to depart from it."
    ),
    expected_failure=(
        "With only six seeds per side the measured range is a lower bound on the true spread, "
        "exactly as M0307's first seven were for the industry draw: a six-draw ratio that looks "
        "like M0306's nineteen-draw one is suggestive, not conclusive, and a six-draw ratio that "
        "looks different cannot yet distinguish 'this chassis behaves differently' from 'six "
        "draws undersample the true spread.' Widening to nineteen per side is the queued "
        "follow-up if this run leaves the direction genuinely open."
    ),
    candidates=tuple(
        _draw(f"ODRAW-S{s}", s, OPEN,
              f"ungated twin of GDRAW-S{s}: identical hash draw on the F4 momentum screen, "
              "switch OFF, always invested")
        for s in SEEDS
    ),
)


METHOD = Method(
    id="M0313",
    name="Does the fall-width finding transfer to a momentum book behind the same switch?",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref="M0306",
    parent_id="M0306",
    hypothesis=(
        "M0306 measured nineteen opinion-free draws of a three-industry book on the gated chassis "
        "against the same nineteen run ungated, and found the SPY 200-day switch cuts every "
        "draw's worst fall by about 30 points (mean -30.42; 20.0%-43.0% gated against 49.0%-69.7% "
        "ungated) while narrowing the SPREAD of falls not at all: a ratio of 1.105 against a "
        "dilution-by-time-invested null of 0.720. On money the ratio was 0.683, near the "
        "dilution null; on worst single year 0.378, a real compression. The proposed mechanism — "
        "the switch removes the one anchor every ungated draw shares (2008) and leaves each gated "
        "draw's deepest fall to be its own private whipsaw accident — does not depend on what the "
        "book ranks on, so it should hold for any re-picked, re-entering book behind the "
        "identical switch. But M0306's draws are three-industry rotations, and the books on this "
        "lab's leaderboard (M0007, M0020, M0022) are twenty-name momentum-shaped books built on "
        "the F4 chassis. This method draws six twenty-name books from that exact chassis — its "
        "12-1 momentum eligibility window, its SPY-200 trend gate, its equal slots, re-picked "
        "monthly — with the pick replaced by a month-keyed hash so no ranking opinion survives, "
        "and runs the identical six seeds gated and ungated. Success is not a strategy and no arm "
        "is expected to be eligible: the deliverable is whether the gated fall spread on this "
        "chassis is also near or above the ungated one (M0306's practical rule generalises, and "
        "no worst-fall difference between two gated momentum-shaped books under about 20 points "
        "is readable evidence) or whether it narrows here (the non-narrowing was a property of "
        "three-industry draws specifically, and a momentum-shaped control needs its own ruler)."
    ),
    expected_failure=(
        "A hash-ordered momentum-shaped book is not a momentum book at all once the ranking is "
        "removed, so if the F4-screened pool at any month end is not much larger than twenty "
        "names, different seeds could draw heavily overlapping books and produce a spread too "
        "narrow to read anything into, on either side of the switch. The second likely failure is "
        "sample size: six draws per side is a lower bound on the true spread exactly as M0307's "
        "first seven were, so a six-draw ratio near 1.0 or near 0.72 is suggestive rather than "
        "conclusive, and only a wider draw (the queued follow-up) can turn a lower bound into the "
        "width. The third is that the mechanism is real but weaker on this chassis: a momentum "
        "screen already excludes the worst-behaved names (price and liquidity floors, a 12-1 "
        "window), so the 'private whipsaw accident' M0306 describes may have less room to differ "
        "seed to seed than it does among three blindly drawn industries."
    ),
    candidates=tuple(
        _draw(f"GDRAW-S{s}", s, GATED,
              f"gated blind draw {s} of six: twenty names hash-picked from the F4 momentum "
              "screen (top=20, 12-1 momentum eligibility, SPY-200 trend gate), switch ON")
        for s in SEEDS
    ),
    amendments=(AMEND_1,),
    seen_keys=(
        "concept:momentum-shaped-blind-draw",
        "concept:gated-draw-spread-transfer-to-momentum-chassis",
        "concept:fall-width-finding-generalization",
    ),
)
