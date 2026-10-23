"""M0283 — Calm stocks beside SPY: how much of the market should sit next to the low-beta book?

Source: Frazzini & Pedersen (2014), "Betting Against Beta", J. Financial Economics 111(1), whose
central claim is that the low-beta book's extra return can only be harvested by *leveraging* it up
to the market's sensitivity; Black, Jensen & Scholes (1972) for the flat beta-return line. Reserved
by Sera batch 20261023-0843 as an ``idea`` row with M0278 as its parent; this file refines it and
keeps its id.

WHY. M0278 measured the calm end of the index cleanly. Its 30 lowest-beta members (M0278-LB30)
moved 0.38 times the market and still earned +11.1% a year with deposits removed against SPY's
+7.9%, fell 29% at their worst against SPY's 50%, and -- the number that matters -- earned about
8 points a year MORE than a book of beta 0.38 is entitled to. In 2009-2015 that excess was 9.6
points a year, so the effect had not faded after publication. And yet LB30 *lost* to SPY in
2009-2015 (+14.4% against +14.9%), for a reason that has nothing to do with skill: a book moving a
third of a market that rises 15% a year starts ten points behind every January.

Frazzini & Pedersen's answer is leverage, which the owner does not have: Gotrade is long only and
unmargined. The cheap substitute is to buy the missing market sensitivity in the open market --
hold SPY itself beside the calm book. A 50/50 mix moves about 0.5 x 0.38 + 0.5 x 1.00 = 0.69 times
the market while keeping half of the calm book's excess return. The question this method asks is
not "does low beta work" (M0278 answered that) but **"what is the right share of SPY, and does any
rung of that dial beat SPY itself in the years most like today?"**

THE DIAL, FIVE RUNGS. Turning a dial twice reads a line through two points and the lab has been
wrong that way before, so the ladder is five rungs wide, two of them already recorded:

    SPY share   1.00      the benchmark itself, in every trial
                0.70      C70-LB
                0.50      C50-LB   -- the rung the idea names
                0.30      C30-LB
                0.00      M0278-LB30, recorded 2026-10-22 at this exact preset, fees and funding

Only the three middle rungs are run here; the two ends already exist and are directly comparable,
because M0278 ran on ``monthly-hold-frac-gotrade`` on the owner's deposits over the same window.
That is a deliberate saving: it buys the two arms below instead.

THE TWO ARMS THAT ARE NOT RUNGS.

    C50-PLC   the no-opinion arm. 50% SPY beside a blind draw of 30 names from the same scored
              pool, matched to the CALM book's own size and monthly entry count
              (``lab.control_draw``'s matched draw). Half the mix is SPY in both, so whatever the
              SPY half pays cancels, and what is left is "is it the calm names, or is it just
              thirty index members next to SPY?"
    C50-HB    the mirror. 50% SPY beside the 30 JUMPIEST members -- the same shape on the opposite
              side of the same sort. If calm is what pays, this one should fall much further and
              earn no more.

C50-LB against C50-PLC prices the signal; C50-LB against C50-HB proves the sort has a direction;
the three rungs plus the two recorded ends price the *dose*. No arm steps aside and no arm switches,
so there is no gate habit to price with a 2x2.

WHY A NEW ALLOCATOR RATHER THAN M0278'S. M0278's matched draw is hard-wired to control its HIGH
book: its ``_select`` returns ``ranked(pool, "high")``, so its placebo copies HB30's entry calendar,
not LB30's. The calm book is the one being controlled here, so the draw must be matched to the calm
book's entries. This allocator is M0278's ranking imported verbatim -- the same ``scored_pool``, the
same ``ranked``, the same 252-session window, the same 200-paired-return floor, the same
one-listing-per-company rule -- with the controlled book switched to the low end. The calm picks it
makes are therefore bit-identical to M0278-LB30's; only the control differs.

Assumptions, written before any result:
- The preset is ``monthly-hold-frac-gotrade``, M0278's own, not the fixed-tape twin. It keeps the
  recorded 0%-SPY rung comparable rung for rung. Under its 1%-of-equity resize band a 50% SPY
  sleeve is pinned tightly (a 2% relative drift trades it) while the 30 one-slot names drift
  exactly as they did in M0278, so the mix is maintained where it matters and the stock sleeve is
  unchanged.
- No trend gate and no cash anywhere. The point of the SPY half is to be *in* the market; a mix
  that steps aside is a different method.
- The calm book alone is not re-run. Its recorded trial is the ladder's endpoint.

Pure: every piece reads only bars dated <= ``data_date``; no clock, randomness or I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0278_market_sensitivity_ends import (
    DV_N,
    MIN_RETURNS,
    WINDOW,
    ranked,
    scored_pool,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart, last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 10, 23)
SIDES = ("low", "high", "control")
ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")


@dataclass(frozen=True, slots=True)
class CalmParams:
    """``top`` members held, sorted by trailing one-year beta to SPY.

    ``side`` is ``low`` (the calm end), ``high`` (the jumpy end, the mirror) or ``control`` (a
    blind draw matched to the CALM book's size and monthly entry count). ``seed`` keys the draw.
    """

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
        out = {"top": str(self.top), "signal": "beta", "side": self.side, "seed": str(self.seed),
               "window": str(WINDOW), "min_returns": str(MIN_RETURNS), "dv_n": str(DV_N),
               "class_rule": "identical-beta-and-vol", "ranking": "M0278"}
        if self.side == "control":
            out["control_rule"] = control_draw.RULE_ID
            out["control_of"] = "low"
        return out


def _check(params: object) -> CalmParams:
    if not isinstance(params, CalmParams):
        raise TypeError(f"params must be CalmParams, got {type(params).__name__}")
    return params


class CalmAllocator:
    """M0278's beta ranking, with the matched draw controlling the LOW book instead of the high one.

    The ``top`` members with the lowest (or highest) trailing one-year beta to SPY, or a blind draw
    matched to the low book's size and monthly entry count; equal slots, fully invested, no switch.
    """

    id = "M0283"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        inner = max(WINDOW + 1, DV_N)
        return control_draw.lookback_for(inner) if p.side == "control" else inner

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _select(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                p: CalmParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the scored pool, the CALM book) on ``data_date`` -- what the control is matched to."""
        pool = scored_pool(history, members, data_date, "beta")
        if not pool:
            return (), ()
        return tuple(sorted(pool)), tuple(ranked(pool, "low")[: p.top])

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if p.side == "control":
            names = control_draw.matched_book(
                lambda d: self._select(history, members, d, p),
                data_date, held, tag="M0283", seed=p.seed,
            )
        else:
            names = ranked(scored_pool(history, members, data_date, "beta"), p.side)[: p.top]
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history: Mapping[str, History]) -> Mapping[str, History]:
        return history

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


CALM = CalmAllocator()

LB30 = CalmParams(30, side="low")
HB30 = CalmParams(30, side="high")
PLC30 = CalmParams(30, side="control", seed=1)


def _mix(spy_share: str, params: CalmParams) -> BlendParams:
    """``spy_share`` of equity in SPY at all times, the rest in the 30-name book."""
    c = Decimal(spy_share)
    return BlendParams((BlendPart(TIMING, ALWAYS_SPY, c), BlendPart(CALM, params, Decimal(1) - c)))


def _v(suffix: str, params: BlendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0283-{suffix}", family="M0283", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BLEND, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0283",
    name="Calm stocks beside SPY: how much of the market should sit next to the low-beta book?",
    family="stock-market-beta",
    source_kind="variation",
    source_ref=(
        "Frazzini & Pedersen (2014) Betting Against Beta, JFE 111(1); Black, Jensen & Scholes "
        "(1972); the core-satellite frame of M0030 and M0104; lab M0278"
    ),
    parent_id="M0278",
    hypothesis=(
        "Betting against beta was published in 2014, at the very end of the dev window, and its "
        "central claim is that the calm book's extra return can only be collected by leveraging it "
        "up to the market's sensitivity. In M0278 the 30 lowest-beta index members earned about 8 "
        "points a year more than their 0.38 market sensitivity alone entitles them to (9.6 points "
        "in 2009-2015, so the effect had not faded after publication), fell only 29% at worst "
        "against SPY's 50%, and kept their record when the dead companies were put back. They "
        "trailed SPY in 2009-2015 only because a book moving a third of a rising market starts far "
        "behind. The owner cannot borrow, so the substitute for leverage is to buy the missing "
        "market sensitivity outright: hold SPY itself beside the calm book. A 50/50 mix moves about "
        "0.69 times the market while keeping roughly half the excess return. Arms: a three-rung "
        "dose ladder on the SPY share (C70-LB 70%, C50-LB 50%, C30-LB 30% SPY beside the calm 30), "
        "which together with SPY itself at 100% and the recorded M0278-LB30 at 0% makes five rungs; "
        "C50-PLC, 50% SPY beside a blind draw of 30 from the same pool matched to the calm book's "
        "own size and monthly entry count (the no-opinion arm); and C50-HB, 50% SPY beside the 30 "
        "JUMPIEST members (the mirror). All monthly, fully invested, no switch, fractional shares "
        "at Gotrade's real fees on the owner's monthly top-up, on M0278's own preset so the 0% rung "
        "stays comparable. Predictions written before any result, on de-funded monthly returns: "
        "C50-LB ties SPY within one point a year over 2009-2015 and its 2008 fall is at least 10 "
        "points shallower than SPY's; C50-LB beats C50-PLC by 3 or more points a year over the "
        "twenty years; the ladder is monotone, so return per point of worst fall (MAR) rises as the "
        "SPY share falls from 100% to 0%; and C50-HB falls at least 15 points deeper than C50-LB "
        "while earning no more."
    ),
    expected_failure=(
        "The most likely failure is that the SPY half pays nothing extra while the calm half's "
        "monthly rebalancing fees and its 2009-2015 lag leave the mix one to two points a year "
        "behind SPY in exactly the era most like today, making it a candidate on falls alone -- "
        "and a book judged on falls has to survive 2008, where a 50/50 of a book that fell 23% and "
        "a market that fell 36% cannot do much better than 30%, well above the owner's 20% bar even "
        "though the lab's dev screen allows 50%. Three more ways it can fail: (1) the ladder is not "
        "monotone, because a mix of two imperfectly correlated books earns a rebalancing bonus that "
        "peaks in the middle rather than at an end, so the dose reading would be a shape artefact "
        "rather than a dose; (2) C50-PLC lands within a point of C50-LB, which would say that what "
        "pays next to SPY is holding thirty index members at all -- the equal-weight shape M0275 "
        "and M0278 already caught -- and not the calm sort; (3) the luck test refuses every arm, "
        "since the calm book alone reached only 0.892 against the bar of 0.90 at N=178 and diluting "
        "it with SPY lowers the Sharpe ratio the luck test reads. None of these is a reason to tune "
        "the 252-session window, the book size or the rungs after the fact."
    ),
    candidates=(
        _v("C50-LB", _mix("0.5", LB30),
           "50% SPY, 50% the 30 calmest index members by trailing one-year beta, resized monthly"),
        _v("C70-LB", _mix("0.7", LB30),
           "Dose rung: 70% SPY, 30% the calm 30 -- less of the opinion"),
        _v("C30-LB", _mix("0.3", LB30),
           "Dose rung: 30% SPY, 70% the calm 30 -- more of the opinion"),
        _v("C50-PLC", _mix("0.5", PLC30),
           "No-opinion arm: 50% SPY beside a blind draw of 30 from the same scored pool, matched "
           "to the calm book's size and monthly entry count"),
        _v("C50-HB", _mix("0.5", HB30),
           "Mirror: 50% SPY beside the 30 JUMPIEST members, the same shape on the other side of "
           "the same sort"),
    ),
    seen_keys=(
        "concept:low-beta-book-levered-with-spy",
        "concept:betting-against-beta-unlevered-substitute",
        "concept:core-satellite-spy-low-beta-dose-ladder",
    ),
)
