"""M0135 — The quarter-return buy-back under a real stock book: the near misses, three months sooner.

Source: a variation of M0128 (the near misses re-measured on the fixed tape), carrying M0113's
one finding onto books that can qualify. M0113 is the frame; M0128 is the book and the capital.

Idea: M0113 split the lab's shared 200-day safety switch into its two halves on a SPY-only book
and priced them separately. Holding the exit fixed and buying back when SPY's 63-session return
turns positive (M0113-UP63) beat the symmetric control on funded return (+32.14% against +31.68%
against a deposit-matched SPY's +30.57%) and did not give it back in the crashes the switch
exists for. Every price-LEVEL trigger did the opposite: back in above the 50-day average cost
2.4 points of worst fall and above the 20-day average cost 10.7 points, both by buying bear
rallies; and re-entering even later, at a 20-session high, was worse on every measure at once
(+29.56%, a 27.07% fall, and it was the one arm that lost to SPY). The finding is bracketed on
both sides -- faster beats slower, and realised return beats price level -- and its mechanism is
clean: inside a real crash a positive three-month return is very hard to produce, but after a
genuine bottom a quarter turns positive long before a 200-day average does.

What M0113 could not do was be a candidate. A book holding nothing but SPY trades 11 to 43 times
in 22 years against a 100-trade condition, so it measured a FRAME and could never clear the bar.
This method spends that frame on books that can. M0128's two strongest fixed-tape books sit
behind the identical 200-day switch, and both are eligible-shaped: M0128-RAW20 (+37.64% funded
against SPY's +32.40%, a 20.65% worst fall, gains 1.98 times losses, 1,607 trades, 69.4%
invested, DSR 0.9142) is dev-eligible under the bars in force, and M0128-B70-CASH (+36.40%,
18.23%, 2.03, 2,786 trades, DSR 0.9554) is the deepest-tested shape the lab holds.

ONE thing changes, and the machinery is built so that it is provably one thing. The inner books
carry their 200-day gate inside their own params (``FactorParams.trend``); every one of those is
stripped to None here, and the identical gate is re-applied from OUTSIDE by this allocator --
``f_factor.trend_on`` against M0113's own ``EXIT_GATE``, the same function and the same
("SPY", 200) that M0007, M0030, M0113 and M0128 all run. Applied symmetrically, an outer gate
is exactly the stateless inner gate: on a session the gate is off the book is all cash whether
or not it was held, and on a session it is on the book is the inner book, whether or not it was
held. So ``RAW20-SMA200`` is M0128-RAW20 re-expressed, and it must reproduce its row. That
reproduction is the only evidence that the other five numbers mean anything.

The asymmetry is then expressed exactly as M0113 expressed it, through ``held``: the EXIT rule
applies only while the book is in the market, the ENTRY rule only while it is out. M0113 could
read "in or out" as ``"SPY" in held`` because SPY was all it held; a stock book reads it as
``bool(held)`` -- any position at all means in. The two coincide for every session a 20-name
book from the liquid S&P 500 union Nasdaq-100 pool is on, because such a book is never empty
while its gate is on; the one way they could part is an "on" session where the inner book found
nothing to buy, which would leave the entry rule governing the next check. It does not happen in
this window and the control's trade count is what says so.

The buy-back rule itself is imported, not re-written: ``m0113.entry_on`` evaluated on an
``m0113.ReentryParams``, so the trigger is M0113's code byte for byte and inherits its
validation. Only ``entry`` and ``entry_n`` reach this method's own ``as_dict`` (and therefore the
config digest), because ``month_end_window`` is False in every variant here -- this method has no
weekly arm.

CASH INTEREST, and why its absence is not a thumb on the scale. Every variant runs on
``monthly-hold-frac-gotrade-tband``, the fixed tape WITHOUT the T-bill credit, so that all six
are mutually comparable on one preset and every one of them can be eligible (the cash-yield
lever is an unverified owner input and would disqualify the lot). Idle cash therefore earns
nothing, which flatters whichever arm is out of the market least -- the faster buy-backs. The
size of that thumb, stated before the run: on SPY alone the swap moved time-in-market from 71.1%
to 73.4%, and 1996-2015 T-bills paid roughly 2.5% a year, so the bias on the PAIRED DIFFERENCE
is about 2.5% x 2.3%, under a tenth of a point a year. It is far too small to explain a result
worth reporting, and any gap under 0.1 points a year here is noise for this reason alone.

Pure: every piece reads only bars dated <= d. ``prepare`` is lazy per book and memoised, which is
a cache and not a state -- ``targets_prepared`` equals ``targets`` bit for bit either way.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, TREND, ResidParams
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0113_trend_switch_reentry import (
    EXIT_GATE,
    ReentryParams,
    entry_on,
)
from seer_engine.lab.methods.m0021_momentum_lowvol_blend import _blend
from seer_engine.sim.book import Target
from seer_engine.sim.rules import PRESETS, TradeRules, rule_owner_inputs
from seer_engine.strategies.allocator import BLEND, Allocator, BlendParams, BlendPart
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 14)
BENCH = "SPY"  # the switch's yardstick; never held by either book
SMA_N = EXIT_GATE.trend[1] if EXIT_GATE.trend is not None else 200  # the exit average, frozen


def _preset(rules_id: str) -> TradeRules:
    """The ``PRESETS`` entry whose id is ``rules_id``: the rule set exactly as a trial records it."""
    for rules in PRESETS:
        if rules.id == rules_id:
            return rules
    raise LookupError(f"sim.rules.PRESETS has no rule set {rules_id!r}")


#: M0128's fixed tape without the T-bill credit: the one preset here, so all six arms compare and
#: none of them carries an unverified owner input.
MONTHLY_TBAND = _preset("monthly-hold-frac-gotrade-tband")


# ----------------------------------------------------------------- the books, with gates stripped


def _ungate(p: FactorParams) -> FactorParams:
    """``p`` with its trend gate removed, having first checked it was the lab's shared one.

    The guard is the point: if M0011 or M0021 ever changes which gate its book carries, this
    raises instead of silently moving the thing this method claims to hold fixed.
    """
    if p.trend != TREND:
        raise ValueError(f"expected the shared {TREND} gate to strip, found {p.trend!r}")
    return replace(p, trend=None)


def _ungate_resid(p: ResidParams) -> ResidParams:
    return replace(p, inner=_ungate(p.inner))


def _ungate_blend(bp: BlendParams) -> BlendParams:
    """Every sleeve of ``bp`` with its own trend gate stripped; shares and allocators untouched."""
    parts: list[BlendPart] = []
    for part in bp.parts:
        if isinstance(part.params, ResidParams):
            inner = _ungate_resid(part.params)
        elif isinstance(part.params, FactorParams):
            inner = _ungate(part.params)
        else:
            raise TypeError(f"a sleeve this method cannot un-gate: {type(part.params).__name__}")
        parts.append(BlendPart(part.allocator, inner, part.share))
    return BlendParams(tuple(parts))


#: M0007-N20-RAW's residual-momentum top 20, as M0011 and M0128 spell it, with no inner gate.
RAW20_UNGATED = _ungate_resid(RAW20)
#: M0021-B70-RAW's 70/30 residual-momentum and calm-stock blend, both sleeves un-gated.
B70_UNGATED = _ungate_blend(_blend("0.7", braked=False))

Book = Literal["raw20", "b70"]
#: name -> (allocator, params). The name is what ``as_dict`` records; the pair is what runs.
BOOKS: dict[str, tuple[Allocator, Any]] = {
    "raw20": (RESIDMOM, RAW20_UNGATED),
    "b70": (BLEND, B70_UNGATED),
}


# ------------------------------------------------------------------------------- the switch


@dataclass(frozen=True, slots=True)
class SwitchParams:
    """Which book runs, and how it is bought back. The exit carries no parameter."""

    book: Book = "raw20"
    entry: str = "sma200"
    entry_n: int = 0  # window the entry rule reads; 0 for "sma200", which reads SMA_N

    def __post_init__(self) -> None:
        if not isinstance(self.book, str) or self.book not in BOOKS:
            raise ValueError(f"book must be one of {tuple(sorted(BOOKS))}, got {self.book!r}")
        ReentryParams(self.entry, self.entry_n)  # M0113's own validation, verbatim

    @property
    def reentry(self) -> ReentryParams:
        """The buy-back rule as M0113 spells it; ``month_end_window`` is never set here."""
        return ReentryParams(self.entry, self.entry_n)

    def as_dict(self) -> dict[str, str]:
        out = {"book": self.book, "entry": self.entry, "entry_n": str(self.entry_n)}
        _, params = BOOKS[self.book]
        for k, v in params.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> SwitchParams:
    if not isinstance(params, SwitchParams):
        raise TypeError(f"params must be SwitchParams, got {type(params).__name__}")
    return params


@dataclass(eq=False)
class SwitchPrepared:
    """``history`` plus each book's own ``prepare`` output, built on first use and kept.

    Laziness is why this exists: one ``SwitchPrepared`` is shared by every candidate in a run
    (``dev`` prepares once per allocator id), and a candidate must not pay to precompute the book
    it does not run. Memoising changes nothing observable -- each entry is exactly
    ``BOOKS[book][0].prepare(history)``, so ``targets_prepared`` still equals ``targets``.
    """

    history: Mapping[str, History]
    cache: dict[str, Any] = field(default_factory=dict)

    def book(self, name: str) -> Any:
        if name not in self.cache:
            self.cache[name] = BOOKS[name][0].prepare(self.history)
        return self.cache[name]


class FastReentryBookSwitch:
    """A gated stock book whose exit is the 200-day cross and whose buy-back is a variant's own.

    On data date d: when the book holds anything, the EXIT rule decides (the lab's shared
    ``trend_on`` against SPY's 200-day average, strictly above to stay in); when it holds nothing,
    the ENTRY rule decides (M0113's ``entry_on``). Off means all cash -- no targets at all, which
    is what the book engine reads as "sell everything". On means the inner book's own targets,
    unchanged: this allocator never re-ranks, re-weights or filters a pick.
    """

    id = "M0135"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        allocator, inner = BOOKS[p.book]
        return max(allocator.lookback(inner), SMA_N, p.entry_n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        allocator, inner = BOOKS[p.book]
        return tuple(sorted({*allocator.symbols(inner), BENCH}))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        allocator, inner = BOOKS[p.book]
        return allocator.holds(inner)

    def uses_members(self, params: Any) -> bool:
        p = _check(params)
        allocator, inner = BOOKS[p.book]
        return allocator.uses_members(inner)

    def _on(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
            p: SwitchParams) -> bool:
        """Should the book be held after this check? The exit rule when in, the entry rule when out."""
        if held:
            return trend_on(history, data_date, EXIT_GATE)
        if p.entry == "sma200":
            return trend_on(history, data_date, EXIT_GATE)
        return entry_on(history.get(BENCH), data_date, p.reentry)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not self._on(history, data_date, held, p):
            return ()
        allocator, inner = BOOKS[p.book]
        return allocator.targets(history, members, data_date, held, inner)

    def prepare(self, history: Mapping[str, History]) -> SwitchPrepared:
        return SwitchPrepared(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SwitchPrepared):
            raise TypeError(f"prepared must be SwitchPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not self._on(prepared.history, data_date, held, p):
            return ()
        allocator, _ = BOOKS[p.book]
        return allocator.targets_prepared(prepared.book(p.book), members, data_date, held,
                                          BOOKS[p.book][1])


SWITCH = FastReentryBookSwitch()


def _v(suffix: str, params: SwitchParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0135-{suffix}", family="M0135", rules=MONTHLY_TBAND, allocator=SWITCH,
                     params=params, rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(MONTHLY_TBAND))


METHOD = Method(
    id="M0135",
    name="Put the quarter-return buy-back under a real stock book: the near misses, three months sooner",
    family="near-miss-fixed-tape",
    source_kind="variation",
    source_ref="variation of M0128 (the near misses on the fixed tape); frame and trigger from M0113-UP63",
    parent_id="M0128",
    hypothesis=(
        "The 200-day switch is old (the banded rule 1992, Faber's monthly version 2007), so "
        "nothing here is a new anomaly and no fade argument applies; what is new is which HALF of "
        "it is paid for. M0113 held the exit fixed and moved only the buy-back on a SPY-only book: "
        "a positive 63-session return (UP63) returned +32.14% a year funded against the symmetric "
        "control's +31.68% and a deposit-matched SPY's +30.57%, while every price-LEVEL trigger "
        "lost -- above the 50-day average +30.86% at a 25.25% fall, above the 20-day average "
        "+30.76% at 29.58%, both from buying bear rallies -- and re-entering LATER, at a "
        "20-session high, was worst of all (+29.56%, a 27.07% fall, the one arm that lost to SPY). "
        "Faster beats slower and realised return beats price level, bracketed on both sides. The "
        "mechanism: inside a real crash a positive three-month return is nearly impossible, but "
        "after a genuine bottom a quarter turns positive long before a 200-day average does. "
        "M0113 could not be a candidate -- 11 to 43 trades in 22 years against a 100-trade "
        "condition -- so it measured a frame. This method spends that frame on M0128's two "
        "strongest fixed-tape books, which trade 1,607 and 2,786 times and sit behind the "
        "identical switch. EXACTLY ONE THING CHANGES: the inner books' own 200-day gate "
        "(FactorParams.trend) is stripped to None and the identical gate is re-applied from "
        "outside, asymmetrically through `held` -- exit rule while in, entry rule while out. "
        "Applied symmetrically an outer gate IS the stateless inner gate, so M0135-RAW20-SMA200 "
        "is M0128-RAW20 re-expressed and MUST reproduce its row (+37.64% against +32.40%, a "
        "20.65% worst fall, gains 1.98 times losses, 1,607 trades, 69.4% invested, DSR 0.9142). "
        "If it does not, the machinery is wrong and none of the other five numbers is readable; "
        "that check comes before every other claim in the analysis. "
        "ALL SIX RUN ON ONE PRESET, monthly-hold-frac-gotrade-tband -- the fixed tape, fractional "
        "shares, Gotrade's real fee schedule, the owner's monthly deposits, and NO T-bill credit "
        "on idle cash -- so the arms are mutually comparable and every one of them can be "
        "eligible, which the cash-yield owner input would have prevented. Idle cash earning "
        "nothing flatters whichever arm is out least, i.e. the faster buy-backs; the size of that "
        "thumb, stated now: on SPY the swap moved time-in-market 71.1% to 73.4%, and 1996-2015 "
        "T-bills paid about 2.5% a year, so the bias on the paired difference is roughly 2.5% x "
        "2.3% = under 0.1 points a year, and any gap smaller than that is noise for this reason "
        "alone. "
        "PREDICTIONS, written before the run. (1) UP63 raises time-in-market by 2 to 4 points on "
        "both books, mostly in 2003 and 2009. (2) It adds 0.5 to 2 points a year of funded return "
        "over its own paired control on each book -- less than it added on SPY alone in relative "
        "terms, because a book that is out of the market less often than a pure switch has less "
        "re-entry lag to recover, and because M0128's picks already earn 3.5 to 4.5 points a year "
        "over a plain switched equal-weight book and may absorb what the frame costs. (3) The "
        "worst fall DEEPENS by 1 to 3 points, more than the 1.8 points it deepened on SPY, "
        "because what gets bought back into a bear rally here is twenty individual momentum names "
        "rather than the index, and individual names fall further. On RAW20 that starts at 20.65% "
        "and is already past the owner's 25% real-money bar's comfort; on B70 it starts at 18.23% "
        "and has room. Both stay inside the 50% dev screen either way, so drawdown will not be "
        "what rejects this. (4) The gain must be visible in 2009-2015, the best-covered era and "
        "the one most like today, or it is a pre-2009 artefact and the verdict says so first -- "
        "this is the condition the idea is really being judged on, because M0128's own picking "
        "edge collapsed to about a point a year after 2009. (5) UP126 lands between the control "
        "and UP63 and UP21 overshoots into bear rallies, which would make 63 a point on a "
        "monotone ramp rather than a peak; if instead UP21 wins, the finding is simply 'sooner is "
        "better' and the quarter is arbitrary, and that is a different and weaker claim. "
        "SUCCESS: a variant that keeps its worst fall inside 25%, keeps over 100 trades, and adds "
        "at least a point a year over its OWN paired control with the gain present after 2009. "
        "WHAT THIS CANNOT DO is be promoted, and that is known now rather than discovered later: "
        "the line runs through M0128 to M0030, the blend's ingredients are M0021's (test-failed) "
        "and M0029 is its fixed-fee twin (test-failed), and behavioural kin will match these "
        "curves to M0022's. The hard gate refuses on kin whatever this scores. It is registered "
        "as a method because it is a real measurement that must be held to these predictions, and "
        "it adds one look to the lab's N."
    ),
    expected_failure=(
        "The likeliest outcome is that the two points a year do not survive contact with real "
        "picks. M0128's books are already 3.5 to 4.5 points a year better than a plain switched "
        "equal-weight book, and they are invested 69% of the time rather than a pure switch's "
        "71%; a book with less re-entry lag has less to recover, so the frame's gain can shrink "
        "to nothing or to under the 0.1-point noise floor the cash-interest bias sets. If the "
        "paired differences land inside a tenth of a point, the honest verdict is that the "
        "buy-back finding is a property of holding the index and does not transfer, which would "
        "be a real result about a frame roughly half the lab shares. "
        "The second risk is the one the SPY run already showed in miniature and which should be "
        "LARGER here: a faster buy-back puts twenty individual momentum names, not the index, "
        "back into a bear rally. Individual names fall further than the index, so the 1.8 points "
        "of extra worst fall UP63 cost on SPY could be 3 to 5 points here, and on RAW20 that "
        "starts from 20.65%. A variant that buys a point of return with four points of fall has "
        "not improved anything the owner cares about, and the verdict must read the pair together "
        "rather than quote the return alone. "
        "Third, and the way this method could fool itself: the gain may be one event. UP63's "
        "whole SPY advantage plausibly lives in 2009, where the slow average kept the control out "
        "through the recovery. One good year inside twenty, on a method whose kin already fail "
        "out of sample, is not an edge; it is a single draw. The analysis must report the "
        "year-by-year difference and the 2009-2015 split before the whole-window average, and "
        "M0113's own fold record is the warning -- it won 1 of 4 walk-forward folds and the fold "
        "it won was the 2006-2008 crash, which is the stretch the exit is already good at rather "
        "than evidence about the entry. "
        "Fourth, the machinery. If RAW20-SMA200 does not reproduce M0128-RAW20 to within what "
        "nothing should move, the gate-stripping or the `bool(held)` reading of 'in or out' is "
        "wrong, and the correct response is to report the method as unreadable rather than to "
        "explain the gap away. The specific way `bool(held)` can part from the truth is an 'on' "
        "session where the inner book targets nothing, which would hand the next check to the "
        "entry rule; the control's trade count against M0128-RAW20's 1,607 is what detects it. "
        "Fifth, deposits soften every worst fall here alike and the rupiah's fall is not in these "
        "dev-window numbers at all, so none of these may be lined up against an unfunded parent's. "
        "Sixth, the DSR. RAW20's control sits at 0.9142 against a 0.90 bar at N = 86 and rising; "
        "N has grown since M0128 ran, so a variant can lose eligibility here purely because the "
        "lab has looked more times, and that must be reported as the lab's cost rather than the "
        "method's failure."
    ),
    candidates=(
        _v("RAW20-SMA200", SwitchParams("raw20", "sma200", 0),
           "Control and machinery check: the symmetric 200-day switch, which must reproduce M0128-RAW20"),
        _v("RAW20-UP63", SwitchParams("raw20", "up", 63),
           "The residual-momentum top 20, bought back when SPY's last quarter has actually returned positive"),
        _v("B70-SMA200", SwitchParams("b70", "sma200", 0),
           "Control: M0021-B70-RAW's 70/30 blend behind the symmetric switch, on the same sessions"),
        _v("B70-UP63", SwitchParams("b70", "up", 63),
           "The same blend with the quarter-return buy-back: the deepest-tested shape, three months sooner"),
        _v("B70-UP126", SwitchParams("b70", "up", 126),
           "Probe: a positive HALF-year return instead, a slower buy-back than the quarter"),
        _v("B70-UP21", SwitchParams("b70", "up", 21),
           "Probe: a positive ONE-month return, the fastest buy-back, most exposed to bear rallies"),
    ),
    seen_keys=(
        "concept:fast-reentry-under-a-stock-book",
        "concept:realised-return-reentry-trigger",
        "concept:asymmetric-switch-on-near-miss-books",
    ),
)
