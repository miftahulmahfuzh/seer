"""M0297 — The missing third arm: a shape-matched blind draw for stock screens that only ever had a mirror.

Source: variation of M0295 (the industry lead-lag book), whose six arms produced the lab's first
clean counter-example; reserved by Sera batch 20261023-1305 as an ``idea`` row and refined here.

WHY. M0295 ran a stock screen beside its own mirror and the pair looked like a confirmed signal:
follow earned +7.3% a year on the owner's deposits and fade +5.5%, a 1.75-point spread running the
right way, which ``lab dressing`` prices at +0.87 points a year of "what the opinion knows". A
blind draw of the same shape then earned +7.6% -- above BOTH arms. The spread was the mirror
losing, not the idea winning, and without the third arm M0295 would have been written up as a
working lead-lag signal.

That is not a fact about M0295. ``lab dressing --all`` finds **35 reversed pairs across 27
methods** and can price only 8 of them; the other 27 belong to methods that never registered an
opinion-free arm at all. ``lab control`` finds a shape-matched blind draw in 37 methods, and the
two sets barely overlap: of the 27 methods holding a mirror pair, **20 have no control arm of any
kind**. Among those twenty are four methods the lab currently calls **dev-eligible** -- promotion
candidates, one counted test look away from the owner's money -- whose only evidence that their
ranking carries information is a mirror gap of exactly the kind M0295 just showed can be empty.

So this method does not look for a new signal. It buys the missing arm for four recorded books,
and asks one question of the record: **does a mirror gap systematically over-state what a stock
screen knows?**

WHY A NEW METHOD AND NOT AN AMENDMENT. ``methods.source_sha`` is written once and
trigger-protected, so a control arm cannot be added to a method whose trials are recorded. The
repair has to be a new pre-registration. It costs one method id for four books.

THE CHASSIS, AND WHY ONLY FOUR BOOKS. ``lab.control_draw``'s matched draw reproduces a book's
size and its monthly entry count exactly, and is provably exact only on a chassis that re-picks a
**fresh top-N every month with no keep band** -- the module's own v2 note measures the error on a
banded chassis at 0.487x entries. Of the twenty unrepaired methods, four are band-free, equal-slot,
monthly F4 books: M0058, M0069, M0091 and M0093. M0083, M0088, M0179, M0184, M0185, M0188 and
M0192 all hold names through a band or a quarterly re-pick and need the v2 shadow and a
chassis-specific previous-re-pick; they are left for a follow-up and queued as such.

HOW EACH DRAW IS BUILT. At every monthly decision the draw asks the arm it controls for its own
eligible pool and its own book, today and at the previous decision; keeps all but ``e`` of its own
names in a date-free hash order, where ``e`` is the number the real book is adding; and draws ``e``
fresh names from that same pool in a month-keyed hash order. It then hands the drawn names back to
the **parent's own target builder**, so the slot size, the dollar-volume screen, the SPY-200 switch
and the SPY filler are the parent's code and not a re-implementation. The only thing replaced is
which names are chosen. Nothing in the draw reads a score, a rank or a return.

ARMS. Two books get two seeds, because the lab has measured that a seed alone moves a twenty-year
return by 0.06-2.70 points (median 1.40), so a one-seed lead under about 1.5 points is unreadable
on return and must be read on the fall and the profit factor instead.

    D93-S1, D93-S2   the blind twin of M0093-LO5-S60-N20-T (dev-eligible; mirror gap +3.04)
    D58-S1, D58-S2   the blind twin of M0058-ILL20-T       (dev-eligible; mirror gap +1.76)
    D91-S1           the blind twin of M0091-LO5-N20-T     (rejected; mirror gap -0.36, backwards)
    D69-S1           the blind twin of M0069-L60-N20       (rejected; mirror gap +1.20, ungated)

M0091 is in deliberately as the negative case: its mirror already reads backwards, so if the draw
beats it too the two readings agree, and if the draw loses to it the mirror was the misleading one
in the other direction.

Rules are each parent's own (``monthly-hold-frac-gotrade``): fractional shares at Gotrade's real
fees on the owner's monthly top-up, so every draw pays what the book it controls paid.

NOT A STRATEGY. Every arm here is a placebo. If one clears the lab's screen that is a finding
about the screen -- a blind twenty-name book behind the SPY 200-day switch inherits the roughly
3.6 points a year insight 462 prices that switch at -- and it must never be promoted.

Pure: a calendar, two hashes and the parents' own pure selectors. Reads only bars dated on or
before ``data_date``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, NamedTuple

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods import m0058_illiquidity_premium as p58
from seer_engine.lab.methods import m0069_long_term_reversal as p69
from seer_engine.lab.methods import m0091_lottery_avoidance as p91
from seer_engine.lab.methods import m0093_scaled_lottery_spike as p93
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 23)

WIDE_TOP = 1000
"""``FactorParams.MAX_TOP``. Asking a parent's ranker for this many names returns its whole scored
pool in rank order -- the dev store prices about 540 symbols, so the slice never bites -- and the
first ``inner.top`` of it is that parent's real book, because every ranker below sorts once on
``(key, symbol)`` and then slices. One pass therefore yields both the pool the draw draws from and
the book the draw is matched to, and they can never disagree about who was eligible."""


class _Parent(NamedTuple):
    """One recorded arm this method draws a blind twin of.

    ``rank`` returns the parent's whole scored pool as ``FactorRow``s in its own rank order;
    ``build`` is the parent's own target builder, so weights, the SPY filler and the dollar-volume
    screen are never re-implemented here. ``alloc`` and ``params`` are the recorded candidate's,
    looked up by id rather than copied, so a drift between this file and the parent's is
    impossible."""

    alloc: Any
    params: Any
    rank: Callable[[list[FactorRow], Mapping[str, History], date, Any], list[FactorRow]]
    build: Callable[[list[FactorRow], Mapping[str, History], date, Any], tuple[Target, ...]]


def _candidate(module: Any, arm_id: str) -> Any:
    for c in module.METHOD.candidates:
        if c.id == arm_id:
            return c
    raise ValueError(f"{arm_id} is not an arm of {module.METHOD.id}")


def _rows_ranker(choose: Callable[..., list[FactorRow]], history_second: bool):
    """The parent's ``choose`` under one signature: ``(rows, history, data_date, params)``."""
    if history_second:
        return lambda rows, history, d, p: choose(rows, history, d, p)
    return lambda rows, history, d, p: choose(rows, p)


def _parent(module: Any, arm_id: str, *, history_second: bool, build) -> _Parent:
    c = _candidate(module, arm_id)
    return _Parent(alloc=c.allocator, params=c.params,
                   rank=_rows_ranker(module.choose, history_second), build=build)


PARENTS: Mapping[str, _Parent] = {
    "M0058-ILL20-T": _parent(
        p58, "M0058-ILL20-T", history_second=True,
        build=lambda rows, history, d, p: p58.targets_from_rows(rows, p),
    ),
    "M0069-L60-N20": _parent(
        p69, "M0069-L60-N20", history_second=False,
        build=lambda rows, history, d, p: p69.build(rows, history, d, p),
    ),
    "M0091-LO5-N20-T": _parent(
        p91, "M0091-LO5-N20-T", history_second=True,
        build=lambda rows, history, d, p: p91.targets_from_rows(rows, p),
    ),
    "M0093-LO5-S60-N20-T": _parent(
        p93, "M0093-LO5-S60-N20-T", history_second=True,
        build=lambda rows, history, d, p: p93.targets_from_rows(rows, p),
    ),
}
ARMS: tuple[str, ...] = tuple(sorted(PARENTS))


@dataclass(frozen=True, slots=True)
class DrawParams:
    """``arm`` is the recorded arm whose shape this draw wears; ``seed`` keys the two hashes.

    Nothing else is a parameter. Everything about the book -- its screen, its size, its switch,
    its slot weights, its fees -- is read off ``arm``'s own recorded configuration, because a
    control with a dial of its own is a control somebody tuned."""

    arm: str
    seed: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.arm, str) or self.arm not in PARENTS:
            raise ValueError(f"arm must be one of {ARMS}, got {self.arm!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"arm": self.arm, "seed": str(self.seed),
               "control_rule": control_draw.RULE_ID, "wide_top": str(WIDE_TOP)}
        for k, v in PARENTS[self.arm].params.as_dict().items():
            out[f"arm.{k}"] = v
        return out


def _check(params: object) -> DrawParams:
    if not isinstance(params, DrawParams):
        raise TypeError(f"params must be DrawParams, got {type(params).__name__}")
    return params


def _inner(p: DrawParams) -> FactorParams:
    inner = PARENTS[p.arm].params.inner
    if not isinstance(inner, FactorParams):
        raise TypeError(f"{p.arm}: inner must be FactorParams, got {type(inner).__name__}")
    return inner


def _wide(p: DrawParams) -> Any:
    """The parent's params with the book opened to the whole pool: the ranking is unchanged."""
    parent = PARENTS[p.arm].params
    return replace(parent, inner=replace(parent.inner, top=WIDE_TOP))


@dataclass
class DrawPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class MatchedDrawAllocator:
    """A blind twin of one recorded arm: that arm's pool, size, entry count, switch and slots,
    with the ranking replaced by two hashes.

    Held symbols are the draw's own holdings and are read only through ``control_draw``: a name
    stays or goes because of ``e``, never because of anything about the name.
    """

    id = "M0297"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return control_draw.lookback_for(PARENTS[p.arm].alloc.lookback(PARENTS[p.arm].params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return PARENTS[p.arm].alloc.symbols(PARENTS[p.arm].params)

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return PARENTS[p.arm].alloc.holds(PARENTS[p.arm].params)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _ranked(self, history: Mapping[str, History], rows: list[FactorRow], data_date: date,
                p: DrawParams) -> list[FactorRow]:
        """The parent's whole scored pool on ``data_date``, in the parent's own rank order."""
        parent = PARENTS[p.arm]
        if not rows:
            return []
        return parent.rank(rows, history, data_date, _wide(p))

    def _select(self, history: Mapping[str, History], factor: FactorPrepared | None,
                members: AbstractSet[str], data_date: date,
                p: DrawParams) -> tuple[list[FactorRow], Sequence[str], Sequence[str]]:
        """``(the pool's rows, the pool, the parent's book)`` on ``data_date``.

        Empty on a month the parent's switch holds it in cash, which is how the draw inherits the
        switch: a control that stayed invested while the book it controls sat out would be a
        different arrangement, not a blinder one."""
        inner = _inner(p)
        if not trend_on(history, data_date, inner):
            return [], (), ()
        rows = (factor_rows(history, members, data_date, inner) if factor is None
                else factor.rows_on(members, data_date, inner))
        ranked = self._ranked(history, rows, data_date, p)
        pool = tuple(r.symbol for r in ranked)
        return ranked, pool, pool[: inner.top]

    def _run(self, history: Mapping[str, History], factor: FactorPrepared | None,
             members: AbstractSet[str], data_date: date, held: frozenset[str],
             p: DrawParams) -> tuple[Target, ...]:
        """The parent's own builder, handed a blind set of names of the parent's own size.

        The switch is read here and the builder is then ALWAYS called, even on a month the pool
        turns up empty. That is not a tidiness point: M0069 sends the slots its ranking could not
        fill to SPY, so a draw that returned cash whenever its own draw came back empty would hold
        cash exactly where the book it controls holds the market, and the gap between them would
        be that difference rather than the signal. The one month the draw is allowed to be in cash
        is the month the parent's own switch puts it there."""
        inner = _inner(p)
        if not trend_on(history, data_date, inner):
            return ()
        ranked, pool, book_now = self._select(history, factor, members, data_date, p)
        prev = control_draw.previous_decision_date(data_date)
        _, _, book_prev = self._select(history, factor, members, prev, p)
        names = control_draw.matched_names(
            pool=pool, held=held, real_now=book_now, real_prev=book_prev,
            tag=p.arm, seed=p.seed, data_date=data_date,
        )
        by_symbol = {r.symbol: r for r in ranked}
        chosen = [by_symbol[s] for s in names if s in by_symbol]
        return PARENTS[p.arm].build(chosen, history, data_date, PARENTS[p.arm].params)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, None, members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> DrawPrepared:
        return DrawPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, DrawPrepared):
            raise TypeError(f"prepared must be DrawPrepared, got {type(prepared).__name__}")
        return self._run(prepared.history, prepared.factor, members, data_date, held,
                         _check(params))


DRAW = MatchedDrawAllocator()


def _v(suffix: str, params: DrawParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0297-{suffix}", family="M0297", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DRAW, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0297",
    name=(
        "The missing third arm: a shape-matched blind draw for the stock screens that only ever "
        "had a mirror"
    ),
    family="placebo-hash-order",
    source_kind="variation",
    source_ref=(
        "lab M0295 (a mirror pair whose blind draw beat both arms); lab.control_draw's matched "
        "draw; lab dressing --all and lab control, swept 2026-10-23"
    ),
    parent_id="M0295",
    hypothesis=(
        "M0295 showed a mirror pair can read as a clean signal while a blind draw of the same "
        "shape beats both arms: the gap was the mirror losing, not the idea winning. Swept on "
        "2026-10-23, the lab holds 35 reversed pairs across 27 methods and can price only 8; 20 "
        "of those 27 methods have no control arm of any kind, and four of the twenty are "
        "dev-eligible. This method buys the missing arm for the four of them whose chassis the "
        "matched draw is exact on -- band-free, equal-slot, monthly F4 books -- and asks whether "
        "a mirror gap systematically over-states what a stock screen knows. Each draw takes its "
        "parent's own pool, book size, monthly entry count, switch, slot weights, SPY filler and "
        "fees, and replaces only the choice of names, with a date-free keep hash and a "
        "month-keyed entry hash. Arms: D93-S1 and D93-S2 (two seeds against M0093-LO5-S60-N20-T, "
        "dev-eligible, mirror gap +3.04 points a year on the prices), D58-S1 and D58-S2 (two "
        "seeds against M0058-ILL20-T, dev-eligible, +1.76), D91-S1 (against M0091-LO5-N20-T, "
        "rejected, mirror -0.36 and so already backwards) and D69-S1 (against M0069-L60-N20, "
        "rejected, ungated, +1.20). Predictions, written before any result: (1) for at least two "
        "of the four books the straight arm's lead over its own blind draw is SMALLER than the "
        "half-gap lab dressing prices from its mirror, which is what over-statement looks like; "
        "(2) M0093 still beats its draw, because a lowest-scaled-spike ranking is a real "
        "low-volatility tilt rather than an empty opinion, but by under 3 points a year; (3) the "
        "two seed pairs differ by less than 1.5 points a year, the lab's own measured blind-draw "
        "noise, so the single-seed reads on M0091 and M0069 can be read at all; (4) each draw's "
        "worst fall lands within 5 points of its parent's and its profit factor within 0.3, "
        "because those axes are seed-stable and the shape is matched by construction. No arm here "
        "is a strategy; every one is a placebo and none may be promoted."
    ),
    expected_failure=(
        "The headline failure is that the sweep finds nothing: all four straight arms beat their "
        "draws by about what their mirrors implied, M0295 was a one-off, and the convention "
        "matters only going forward. That is the honest outcome and is pre-registered as such. "
        "Second, the seed pairs may differ by more than 1.5 points a year, in which case the "
        "single-seed reads on M0091 and M0069 are unreadable on return and the method can only "
        "report the fall and the profit factor for them. Third, a draw may clear the lab's screen "
        "outright: a blind twenty-name book behind the SPY 200-day switch inherits whatever that "
        "switch is worth (insight 462 prices it near 3.6 points a year in 2009-2015), so an "
        "eligible placebo would be a finding about the screen and not a strategy, and promoting "
        "it is forbidden. Fourth, M0069's draw inherits a book that fell over 70%, so nothing on "
        "that row will be near a go-live bar whichever way it lands. Fifth, lab control cannot "
        "resolve a control that lives in a different method from the arm it controls, so these "
        "six arms will report as unresolved and the comparison has to be made by hand from the "
        "recorded trade and turnover counts; that is a gap in the tool, not in the draws."
    ),
    candidates=(
        _v("D93-S1", DrawParams("M0093-LO5-S60-N20-T", seed=1),
           "Placebo: M0093-LO5-S60-N20-T's book size and monthly entry count drawn blind from its "
           "own pool in a hash order, seed 1"),
        _v("D93-S2", DrawParams("M0093-LO5-S60-N20-T", seed=2),
           "Placebo: the same blind draw of M0093-LO5-S60-N20-T at a second seed, to price the "
           "draw's own seed noise"),
        _v("D58-S1", DrawParams("M0058-ILL20-T", seed=1),
           "Placebo: M0058-ILL20-T's book size and monthly entry count drawn blind from its own "
           "pool in a hash order, seed 1"),
        _v("D58-S2", DrawParams("M0058-ILL20-T", seed=2),
           "Placebo: the same blind draw of M0058-ILL20-T at a second seed, to price the draw's "
           "own seed noise"),
        _v("D91-S1", DrawParams("M0091-LO5-N20-T", seed=1),
           "Placebo: M0091-LO5-N20-T's book size and monthly entry count drawn blind from its own "
           "pool in a hash order, the negative case whose mirror already reads backwards"),
        _v("D69-S1", DrawParams("M0069-L60-N20", seed=1),
           "Placebo: M0069-L60-N20's book size and monthly entry count drawn blind from its own "
           "pool in a hash order, the ungated book with a 71% fall"),
    ),
    seen_keys=(
        "concept:matched-blind-draw-for-recorded-mirror-pairs",
        "concept:mirror-gap-overstates-what-a-screen-knows",
        "concept:retrofit-control-arm-as-a-new-method",
    ),
)
