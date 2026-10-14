"""M0122 — Does the market's shape explain the lab's whole 0-for-5 record?

Source: the lab's own backlog entry M0122, raised from insight 58 (all four roster strategies
lost to deposit-matched SPY over 2018-2026 by a similar margin) and insight 91 (a book that
equal-weights index members is betting against the market's shape, not only picking stocks).
M0117-C measured that bet for the first time: fifty of the most-traded members in equal 2% slots,
no picking rule at all, earned 6.5% a year against SPY's 7.2% and fell 57%.

**The question.** Every book in this lab holds equal slots. SPY does not. If equal weighting is a
roughly constant handicap, then it is a large share of the roster's shortfall, and the lab has
spent 146 methods blaming its picking rules for a loss its PORTFOLIO SHAPE was always going to
deliver. No amount of better picking can repair a shape handicap.

**The design: one paired difference, three times over.** Each parent book runs twice, in the same
batch, on the same deposits, fees, cadence, screen and name count -- differing in exactly one
field of one params object: ``weight="equal"`` against ``weight="dv"``. Both arms go through the
identical code path in ``Reweighted`` below, so the control is not the parent's recorded trial
but a fresh run of the same wrapper with the weighting switched off. That matters twice over: it
removes the cross-trial comparison M0125 warned about, and it means a digest collision with the
parent's own recorded configuration is impossible, because every variant here carries the
wrapper's ``weight``/``cap``/``dv_base`` fields.

**Why a wrapper and not three re-implementations.** M0092 asked this question for ONE parent by
re-implementing the weighting inside the jump book's own allocator. That answered it for the
jump book and nothing else. Re-weighting a parent's OUTPUT targets instead is strictly a sizing
change -- the parent chooses exactly the names it always chose, in the order it always chose them
-- so the difference is the weighting scheme and provably nothing else, and the same wrapper
works for any parent the lab ever wants to ask about.

**The SPY park is passed through untouched, and this is the load-bearing detail.** All three
parents park their unfilled slots in SPY, and M0088's park is a large part of what it does. A
wrapper that re-weighted the park by its trading value would quietly turn "re-size the picks"
into "re-size the picks and the market core together", and the paired difference would no longer
mean what it says. Each parent declares its park symbols through ``holds()``; those targets keep
their weight exactly, and only the picks are re-spread, over exactly the budget the picks already
held. The invested fraction is therefore identical in both arms by construction.

**Dollar volume, not market value, and the analysis must say so.** The lab's own market-cap
figure is broken -- unadjusted share count times split-adjusted close, wrong by an arbitrary
per-symbol factor and look-ahead-shaped. Dollar volume is the best size signal this store can
give and needs no new data. It is a proxy. No verdict from this method may claim a cap-weighted
book was built.

**Prior evidence, and it points the other way.** M0092 ran this swap on the filtered news-day
book and the trading-value arm made the 1998 fall WORSE (23.5-24.5% against 22.4%) while still
losing to SPY after 2009. That is one parent, which is exactly why this method pairs three. If
all three twins fail to improve, the market-shape theory is dead and a question open since the
owner's money runs in October closes -- which the backlog entry calls just as valuable as a win,
and this file agrees.

Parents were chosen for having no test-failed kin, so that a win would be usable: the
dividend-raise and declaration books qualify; the momentum and blend books do not.

Pure: every piece reads only bars dated <= d; no clock, randomness or I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import (
    ANNOUNCED,
    R25,
    AnnParams,
)
from seer_engine.lab.methods.m0082_declaration_discipline import (
    DISCIPLINE,
    T40,
    DisciplineParams,
)
from seer_engine.lab.methods.m0088_calm_big_raisers import CALM, X, CalmParams
from seer_engine.lab.methods.m0092_jump_trading_value_weight import capped_shares, trading_value
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, rule_owner_inputs
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 14)

WEIGHTS = ("equal", "dv", "sqrt")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class ShapeParams:
    """``inner`` is the parent's own params, verbatim; the rest only re-sizes what it picked."""

    inner: Any
    weight: Literal["equal", "dv", "sqrt"] = "equal"
    cap: Decimal = Decimal("0.10")  # most any one pick may hold
    dv_base: int = 60  # sessions in the trading-value median, ending on the data date

    def __post_init__(self) -> None:
        if self.inner is None:
            raise TypeError("inner must be the parent's params object, got None")
        if self.weight not in WEIGHTS:
            raise ValueError(f"weight must be one of {WEIGHTS}, got {self.weight!r}")
        if not isinstance(self.cap, Decimal) or not self.cap.is_finite() or not (
            Decimal(0) < self.cap <= Decimal(1)
        ):
            raise ValueError(f"cap must be a Decimal in (0, 1], got {self.cap!r}")
        if isinstance(self.dv_base, bool) or not isinstance(self.dv_base, int) or self.dv_base < 5:
            raise ValueError(f"dv_base must be an int >= 5, got {self.dv_base!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"weight": self.weight, "cap": str(self.cap), "dv_base": str(self.dv_base)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ShapeParams:
    if not isinstance(params, ShapeParams):
        raise TypeError(f"params must be ShapeParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the wrapper


class Reweighted:
    """A parent allocator's own picks, re-spread by trading value over the budget they already held.

    One instance per parent. ``weight="equal"`` returns the parent's targets unchanged, so the
    control arm is the parent itself reached through this same code -- the only honest control
    for a one-field difference.

    Park targets (the symbols the parent declares through ``holds()``) are never re-weighted and
    never counted in the budget, so the invested fraction is identical in both arms.
    """

    id = "M0122"

    def __init__(self, parent: Any, tag: str, name: str) -> None:
        self._parent = parent
        self._name = name
        # One allocator object per id: the lab pins that, and three parents means three objects.
        self.id = f"M0122-{tag}"
        fields = getattr(parent, "market_fields", None)
        if fields is not None:
            self.market_fields = fields

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(self._parent.lookback(p.inner), p.dv_base + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return self._parent.symbols(_check(params).inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        return self._parent.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        return self._parent.uses_members(_check(params).inner)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return self._parent.prepare(history)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        got = self._parent.targets(history, members, data_date, held, p.inner)
        return self._respread(history, got, data_date, p)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        got = self._parent.targets_prepared(prepared, members, data_date, held, p.inner)
        return self._respread(self._history_of(prepared), got, data_date, p)

    @staticmethod
    def _history_of(prepared: Any) -> Mapping[str, History]:
        h = getattr(prepared, "history", None)
        if h is None:
            raise TypeError(f"{type(prepared).__name__} carries no history to re-weight against")
        return h

    def _respread(self, history: Mapping[str, History], got: tuple[Target, ...],
                  data_date: date, p: ShapeParams) -> tuple[Target, ...]:
        if p.weight == "equal" or not got:
            return got
        park = set(self.holds(p))
        picks = [t for t in got if t.symbol not in park]
        if len(picks) < 2:
            return got
        tv: dict[str, float] = {}
        for t in picks:
            h = history.get(t.symbol)
            i = None if h is None else h.index_of(data_date)
            v = None if (h is None or i is None) else trading_value(h, i, p.dv_base)
            if v is None:  # a pick the store cannot size is left at its own weight
                return got
            tv[t.symbol] = v
        budget = sum((t.weight for t in picks), Decimal(0))
        if budget <= 0:
            return got
        raw = [tv[t.symbol] if p.weight == "dv" else tv[t.symbol] ** 0.5 for t in picks]
        shares = capped_shares(raw, float(budget), float(p.cap))
        out: list[Target] = []
        for t in got:
            if t.symbol in park:
                out.append(t)
        for t, x in zip(picks, shares):
            if x <= 0:
                continue
            w = to_weight(x)
            if w <= 0:
                continue
            nt = target_from_close(t.symbol, last_close(history[t.symbol], data_date), w)
            if nt is not None:
                out.append(nt)
        return tuple(out)


class ReweightedMarketAware(Reweighted):
    """``Reweighted`` for a parent that prepares from the whole ``Market``.

    ``isinstance(x, MarketAware)`` is exactly "``x`` has a ``prepare_market`` attribute", so the
    wrapper must not define one unconditionally: a plain parent wrapped by a class that claims
    ``prepare_market`` would be routed down the panel path it never reads. ``reweighted`` below
    picks this class only when the parent itself is market-aware, and all three parents here are
    -- they read the dividend calendar.
    """

    def prepare_market(self, market: Any) -> Any:
        return self._parent.prepare_market(market)


def reweighted(parent: Any, tag: str, name: str) -> Reweighted:
    """The wrapper class that matches ``parent``'s own preparation contract."""
    cls = ReweightedMarketAware if callable(getattr(parent, "prepare_market", None)) else Reweighted
    return cls(parent, tag, name)


CALM_W = reweighted(CALM, "CALM", "M0088-C-LIVE-63")
DECL_W = reweighted(DISCIPLINE, "DECL", "M0082-X-N40")
ANN_W = reweighted(ANNOUNCED, "ANN", "M0076-X-M")

CALM_P = CalmParams(X, "calm", "live", 63)  # M0088-C-LIVE-63's params, verbatim
DECL_P = DisciplineParams(T40, "gap")  # M0082-X-N40's params, verbatim
ANN_P = AnnParams(R25, "ex")  # M0076-X-M's params, verbatim


def _v(suffix: str, allocator: Reweighted, params: ShapeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0122-{suffix}", family="M0122", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(MONTHLY_HOLD_FRAC_GOTRADE))


METHOD = Method(
    id="M0122",
    name=(
        "Does the market-shape handicap explain the lab's whole 0-for-5 record? Three near-"
        "eligible books re-sized by trading value against their own equal-weight twins"
    ),
    family="market-shape-yardstick",
    source_kind="variation",
    source_ref=(
        "parents M0088-C-LIVE-63, M0082-X-N40 and M0076-X-M, each run twice; insight 58 "
        "(the roster's common shortfall to deposit-matched SPY), insight 91 (equal weighting as "
        "a bet against the market's shape), M0117-C (the shape priced alone: 6.5% a year against "
        "SPY's 7.2%, a 57% fall), M0092 (the same swap on one event-drift parent, which failed)"
    ),
    parent_id="M0088",
    hypothesis=(
        "Every book in this lab holds equal slots and SPY does not, and M0117-C priced that "
        "choice alone at roughly half a point a year before any signal is added. If the handicap "
        "is roughly constant it is most of the roster's shortfall, and 146 methods have been "
        "blaming their picking rules for a loss the portfolio's SHAPE was always going to "
        "deliver. This method tests it directly instead of by inference. Three near-eligible "
        "parents with no test-failed kin -- the calm big-raiser book M0088-C-LIVE-63, the "
        "declaration-discipline book M0082-X-N40 and the announcement-timed raise book M0076-X-M "
        "-- each run twice in this one batch on the owner's real deposits at Gotrade's real fees, "
        "monthly, in fractional shares. Both arms pass through the same wrapper and differ in one "
        "field: the picks are spread equally, or in proportion to their 60-session median trading "
        "value capped at 10% of the account. The parent chooses the same names in the same order "
        "either way, and each parent's SPY park keeps its weight untouched, so the invested "
        "fraction matches and the paired difference is the weighting scheme and nothing else. "
        "The hypothesis: each trading-value twin beats its own equal-weight control by roughly 1 "
        "to 1.5 points a year with a materially shallower worst fall, in which case equal "
        "weighting is a free handicap every book here has been paying and the fix is a sizing "
        "change rather than a new signal. Prior evidence points the other way and is stated "
        "before the run: M0092 made this exact swap on the filtered news-day book and the "
        "trading-value arm deepened the 1998 fall (23.5-24.5% against 22.4%) while still losing "
        "to SPY after 2009. That was one parent; this is three, paired. Trading value is a proxy "
        "for size and not market value -- the lab's own market-cap figure is broken (unadjusted "
        "share count times split-adjusted close) -- and no verdict from this method may claim a "
        "cap-weighted book was built."
    ),
    expected_failure=(
        "What would make this method's answer wrong rather than merely negative. (1) Trading "
        "value is not market value. A book re-sized by it leans toward heavily traded names, "
        "which correlates with size but also with turmoil in the name; a twin that wins may be "
        "paid for the second thing. The verdict must say 'trading value', never 'cap-weighted'. "
        "(2) Concentration is the mechanism and the risk at once. M0092's twin deepened its worst "
        "fall, and the 10% cap is the only thing standing between a volume tilt and a one-stock "
        "bet -- the lab has seen 61% in a single name when that cap was absent. If a twin wins on "
        "return and loses on worst fall, the honest reading is that the handicap and the risk "
        "have different causes, not that the shape theory is confirmed. (3) The parents all park "
        "in SPY, and the park is untouched here by construction; a parent that is mostly parked "
        "has little for the weighting to act on, so a null result on M0088 specifically may mean "
        "'not much was re-weighted' rather than 'weighting does not help'. The share of account "
        "in picks versus park must be reported beside each pair. (4) Three parents from two "
        "families is not the lab. A win here licenses re-running the near misses this way; it "
        "does not license a claim about every book on the books. (5) The dev window contains "
        "dot-com and 2008, both of which punish concentration, while the era the lab is judged on "
        "was carried by a few giant names. A twin that loses on dev may still be the right shape "
        "for the test window, and this method cannot see that -- so a negative result closes the "
        "dev-window question only, and must be written that way. (6) If every twin lands within "
        "0.2 points a year of its control, the weighting scheme is empty at this cap and the "
        "finding is that the handicap M0117-C measured does not transfer to books that pick."
    ),
    candidates=(
        _v("CALM-EQ", CALM_W, ShapeParams(CALM_P, "equal"),
           "Control: M0088-C-LIVE-63's calm big raisers, equal slots, reached through this wrapper"),
        _v("CALM-DV", CALM_W, ShapeParams(CALM_P, "dv"),
           "The same picks spread by 60-session median trading value, capped at 10% of the account"),
        _v("DECL-EQ", DECL_W, ShapeParams(DECL_P, "equal"),
           "Control: M0082-X-N40's declaration-discipline book, equal slots, through this wrapper"),
        _v("DECL-DV", DECL_W, ShapeParams(DECL_P, "dv"),
           "The same picks spread by trading value, capped at 10%: the paired difference for M0082"),
        _v("ANN-EQ", ANN_W, ShapeParams(ANN_P, "equal"),
           "Control: M0076-X-M's announcement-timed raise book, equal slots, through this wrapper"),
        _v("ANN-DV", ANN_W, ShapeParams(ANN_P, "dv"),
           "The same picks spread by trading value, capped at 10%: the paired difference for M0076"),
    ),
    seen_keys=(
        "concept:equal-weight-shape-handicap",
        "concept:trading-value-weighted-twin-paired",
    ),
)
