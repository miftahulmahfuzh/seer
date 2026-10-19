"""M0230 — Buyback shrinkers as a tilt beside a market core: half SPY, half the biggest shrinkers.

Source: variation of M0227 (its ``S20`` book as the sleeve); Pontiff & Woodgate (2008), "Share
Issuance and Cross-Sectional Returns", Journal of Finance 63(2) 921-945; the core-plus-satellite
shape of P7a F9, M0030 and M0096. Reserved by Sera batch 20261019-0720 as an ``idea`` row; this
file refines it and keeps its id.

Why this shape. M0227 measured the buyback signal cleanly: the 20 biggest one-year shrinkers earned
+13.0% a year on the owner's deposits against SPY's +7.2%, beating both the opposite book (the 20
biggest issuers, +9.2%) and a hash-drawn placebo from the same pool (+7.7%). But it fell 58.7% in
2008, so the only version that passed the dev screen was the one hiding behind the SPY 200-day
switch -- and that switch sat out the 2009-11 rebound and lost two of the four walk-forward folds.
The switch is a market-timing bet bolted onto a stock-picking signal, and this lab has measured
twice (M0221, M0227) that it buys the drawdown bar by giving back the recovery.

The alternative tried here: no timing at all. Hold a fixed SPY core -- which owns the mega-caps an
equal-weight 20-name book never does (insight 91) and never steps out of a rebound -- and run the
shrinkers on what is left. A 50% core halves the sleeve's slots to 2.5% and halves its contribution
to both the lead and the fall.

What the reserved idea predicted, and why this file does not repeat it. The idea row guessed a
worst fall "near 35-40%". That is arithmetically unavailable: in 2008 the sleeve fell about 59% and
SPY about 55%, at the same time and for the same reason, so a half-and-half book falls about 57%,
not 37%. Blending correlated halves averages the fall; it does not diversify it. The pre-registered
prediction below therefore says the ungated arms break the 20% bar outright, and the method's real
question is the one the fold record asked: **does a market core recover the 2009-2015 years and the
walk-forward folds that the 200-day switch threw away?** One arm (``C50-SWS``) keeps the core
always invested and puts the switch on the sleeve alone, which is the only construction here that
can reach the drawdown bar without sitting out a recovery; it is pre-registered as evidence for
exactly that trade-off, not as a retreat to timing.

The sleeve. M0227's ``scored_pool`` verbatim: on each monthly check, every index member with a bar
dated ``data_date`` whose share count is public today and 365 calendar days ago, carried across
splits, the two figures counted at least 180 days apart, the ratio not within 3% of a common split
ratio and inside 0.5-3.0, one listing per company (two members answering the identical whole-company
count are one company listed twice; the more traded one stays). ``side="shrink"`` takes the ``top``
most-negative log changes; ``side="random"`` the placebo's fixed hash order over the same pool.

The sleeve's weights. ``weighting="equal"``: equal slots. ``weighting="size"``: each pick's real
point-in-time market value (shares as filed by that day x the close as it printed), rescaled inside
the sleeve and capped at ``ceiling`` with the excess re-spread pro rata (M0222's ``capped``). The
ceiling is measured **against the sleeve**, not the account: at 20 names a 10% sleeve ceiling lets
no shrinker weigh more than twice an equal slot, which is the cap M0047 warned an uncapped size book
needs. A pick the store cannot value is dropped from the size-weighted sleeve (it keeps its slot in
the equal one), so the two arms can hold slightly different books; that is stated here rather than
patched afterwards.

The core. ``core`` of equity in SPY, every check, whatever the market is doing. ``switch="none"``
is the idea as reserved: nothing is ever timed. ``switch="sleeve"`` empties only the shrinkers
while SPY closes at or under its 200-day average and leaves the core in SPY.

Rules are ``monthly-hold-frac-gotrade-tband``: fractional shares at Gotrade's real fees, monthly, on
the owner's monthly top-up, with the rebalance band measured against each holding's own target (20%)
rather than 1% of the account. This is a deliberate comparability choice, not a tuning one: M0227's
20 slots were 5% each, where the account-wide 1% band *is* 20% of target, so the plain preset
behaved as a target band for it. Halving those slots to 2.5% would make the same preset a 40%-of-
target band -- a looser book than the parent, measured against the parent. The tband preset keeps
the band where M0227 had it (insight on the resize band, 2026-10-14).

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by the
contract it targets nothing at all -- not even the SPY core, which on its own is not this method.
Pure: reads only bars and share counts public on or before ``data_date``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0222_raise_tilted_market_core import capped
from seer_engine.lab.methods.m0227_net_share_shrinkers import (
    ISSUANCE,
    IssuanceParams,
    IssuancePrepared,
    draw,
    scored_pool,
)
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import last_close, scale_weight, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 19)
MARKET = "SPY"  # the core, and the switch's signal
WEIGHTINGS: tuple[str, ...] = ("equal", "size")
SWITCHES: tuple[str, ...] = ("none", "sleeve")
_W_Q = Decimal("0.000001")

Weighting = Literal["equal", "size"]
Switch = Literal["none", "sleeve"]


@dataclass(frozen=True, slots=True)
class CoreShrinkParams:
    """``sleeve`` is M0227's book; ``core`` the fixed SPY share of equity; ``weighting`` how the
    sleeve splits its own money; ``ceiling`` the most one shrinker may weigh *inside the sleeve*
    when weighted by size; ``switch`` what the SPY-200 rule, if anything, empties."""

    sleeve: IssuanceParams
    core: Decimal
    weighting: Weighting = "equal"
    ceiling: Decimal = Decimal("0.10")
    switch: Switch = "none"

    def __post_init__(self) -> None:
        if not isinstance(self.sleeve, IssuanceParams):
            raise TypeError(f"sleeve must be IssuanceParams, got {type(self.sleeve).__name__}")
        if self.sleeve.trend is not None:
            raise ValueError("the sleeve carries no switch of its own; use switch='sleeve'")
        if not isinstance(self.core, Decimal) or not self.core.is_finite() or not 0 < self.core < 1:
            raise ValueError(f"core must be a Decimal in (0, 1), got {self.core!r}")
        if self.core % WEIGHT_QUANTUM != 0:
            raise ValueError(f"core must be a multiple of {WEIGHT_QUANTUM}, got {self.core}")
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if not isinstance(self.ceiling, Decimal) or not Decimal(0) < self.ceiling <= Decimal(1):
            raise ValueError(f"ceiling must be a Decimal in (0, 1], got {self.ceiling!r}")
        if self.ceiling * self.sleeve.top < 1:
            raise ValueError("ceiling x top must reach 1, or the sleeve's weights cannot fill it")
        if self.switch not in SWITCHES:
            raise ValueError(f"switch must be one of {SWITCHES}, got {self.switch!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"core": format(self.core.normalize(), "f"), "weighting": self.weighting,
               "ceiling": str(self.ceiling), "switch": self.switch, "market": MARKET,
               "ceiling_basis": "sleeve"}
        for k, v in self.sleeve.as_dict().items():
            out[f"sleeve.{k}"] = v
        return out


def _check(params: object) -> CoreShrinkParams:
    if not isinstance(params, CoreShrinkParams):
        raise TypeError(f"params must be CoreShrinkParams, got {type(params).__name__}")
    return params


def _gate(p: CoreShrinkParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.sleeve.top, trend=(MARKET, 200))


def picks(prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
          p: CoreShrinkParams) -> list[str]:
    """The sleeve's names on ``data_date``, in rank order: M0227's pool and ordering."""
    pool = scored_pool(prepared, members, data_date)
    if not pool:
        return []
    s = p.sleeve
    if s.side == "shrink":
        order = sorted(pool, key=lambda k: (pool[k], k))
    elif s.side == "issue":
        order = sorted(pool, key=lambda k: (-pool[k], k))
    else:
        order = sorted(pool, key=lambda k: (draw(s.seed, k), k))
    return order[: s.top]


def sleeve_weights(prepared: IssuancePrepared, names: list[str], data_date: date,
                   p: CoreShrinkParams) -> dict[str, Decimal]:
    """Each pick's share *of the sleeve*: equal slots, or market value capped at ``ceiling``."""
    if not names:
        return {}
    if p.weighting == "equal":
        w = equal_weight(len(names))
        return dict.fromkeys(names, w)
    m = prepared.market
    raw: dict[str, float] = {}
    for s in names:
        v = m.market_value(s, data_date)
        if v is None or not (math.isfinite(v) and v > 0):
            continue  # a pick the store cannot value leaves the size-weighted sleeve
        raw[s] = v
    if not raw:
        return {}
    out: dict[str, Decimal] = {}
    for s, v in capped(raw, float(p.ceiling)).items():
        q = Decimal(repr(v)).quantize(_W_Q, rounding=ROUND_FLOOR)
        if q > 0:
            out[s] = q
    return out


class CoreShrinkAllocator:
    """A fixed SPY core plus M0227's buyback-shrinker book on the rest of the money.

    ``BLEND`` cannot do this: it prepares its parts from bars alone, so the shrinker sleeve inside
    it would see no share counts and target nothing (M0096 hit the same wall with dividends). This
    allocator prepares M0227's ``IssuancePrepared`` from the whole ``Market`` and scales the
    sleeve's weights itself, the way ``BLEND._merge`` does.
    """

    id = "M0230"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(ISSUANCE.lookback(p.sleeve), 200 if p.switch == "sleeve" else 0)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (MARKET,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (MARKET,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
             p: CoreShrinkParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()  # no share counts: target nothing (market-aware contract)
        share = Decimal(1) - p.core
        on = p.switch == "none" or trend_on(prepared.history, data_date, _gate(p))
        order: list[str] = []
        first: dict[str, Target] = {}
        total: dict[str, Decimal] = {}
        if on:
            names = picks(prepared, members, data_date, p)
            for s, w in sleeve_weights(prepared, names, data_date, p).items():
                scaled = scale_weight(w, share)
                if scaled is None:
                    continue
                t = target_from_close(s, last_close(prepared.history[s], data_date), scaled)
                if t is None:
                    continue
                order.append(s)
                first[s] = t
                total[s] = scaled
        mh = prepared.history.get(MARKET)
        if mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(MARKET, last_close(mh, data_date), p.core)
            if t is not None:
                order.append(MARKET)
                first[MARKET] = t
                total[MARKET] = to_weight(t.weight)
        return tuple(replace(first[s], weight=total[s]) for s in order)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no sleeve and no target."""
        return self._run(IssuancePrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> IssuancePrepared:
        return ISSUANCE.prepare(history)

    def prepare_market(self, market: Any) -> IssuancePrepared:
        return ISSUANCE.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IssuancePrepared):
            raise TypeError(f"prepared must be IssuancePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


CORE = CoreShrinkAllocator()
S20 = IssuanceParams(20)  # M0227-S20's book, verbatim, minus its (absent) switch
R20 = IssuanceParams(20, side="random", seed=1)  # M0227-R20's placebo, verbatim


def _v(suffix: str, params: CoreShrinkParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0230-{suffix}", family="M0230", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=CORE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0230",
    name=(
        "Buyback shrinkers as a tilt inside a market-shaped book: half SPY, half the 20 biggest "
        "share-count shrinkers, no 200-day switch"
    ),
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref=(
        "variation of M0227 (S20 as the sleeve); Pontiff & Woodgate (2008) JF 63(2) 921-945, "
        "https://ideas.repec.org/a/bla/jfinan/v63y2008i2p921-945.html; core-satellite shape of "
        "P7a F9, M0030 and M0096"
    ),
    parent_id="M0227",
    hypothesis=(
        "Published 2008. M0227's plain shrinker book (the 20 index members whose split-adjusted "
        "share count fell most over a year) earned +13.0% a year on the owner's deposits against "
        "SPY's +7.2% and beat both its opposite book and its hash-drawn placebo, but fell 58.7% in "
        "2008; only the arm behind the SPY 200-day switch passed the dev screen, and that arm sat "
        "out the 2009-11 rebound and lost 2 of 4 walk-forward folds. Replace the timing with a "
        "market core: hold a fixed share of equity in SPY -- which owns the mega-caps an "
        "equal-weight book never does and never steps out of a recovery -- and run M0227's sleeve "
        "on the rest, monthly, fractional, at Gotrade's real fees, on the owner's top-up, with the "
        "rebalance band measured against each holding's own target (the tband preset) so halving "
        "the parent's 5% slots to 2.5% does not also halve how often they are rebalanced. Arms: "
        "C50 (50% SPY, equal slots: the idea as reserved), C70 and C30 (the same at 70% and 30%, "
        "the dose-response), C50-SZ (50% SPY with the shrinkers weighted by real point-in-time "
        "market value, capped at 10% of the sleeve, so no shrinker weighs over twice an equal "
        "slot), C50-R (50% SPY with M0227's hash-drawn placebo in the sleeve: the same frame, "
        "names that know nothing about buybacks) and C50-SWS (50% SPY always held, the SPY-200 "
        "switch emptying the sleeve alone). Predictions written before any result. (1) The lead: "
        "C50 beats total-return SPY on the deposits by 2 to 3 points a year, roughly half the "
        "parent's 5.8-point lead, and C70 and C30 land near 1.5 and 4 points -- a lead that scales "
        "with the sleeve is the signal surviving dilution rather than a frame effect. (2) C50 "
        "beats C50-R by 1.5 points or more; if it does not, the half-SPY frame is doing the work. "
        "(3) The fall, stated against the reserved idea's own guess of 35-40%, which is "
        "arithmetically unavailable: the sleeve and SPY fell 59% and 55% in the same months for "
        "the same reason, so C50 falls about 55-57% and C70 and C30 both land near 55% too. Every "
        "ungated arm breaks the 20% bar; that is expected, pre-registered, and not a surprise to "
        "be explained afterwards. (4) The real question: 2009-2015 and the folds. The core should "
        "lift the 2009-2015 era above the parent's switched arm and win 3 of 4 walk-forward folds, "
        "because the one fold the switch lost outright (2009-11, +38% against SPY's +61%) was lost "
        "to cash, and a core that never leaves cannot lose it that way. (5) C50-SWS is the only "
        "arm that can reach the 20% bar: its fall should be near 30% (half of SPY's 55% plus a "
        "sleeve that leaves), still over the bar, and it should lose the 2009-11 fold less badly "
        "than the parent did. Success is (2) and (4) together: the signal survives dilution and "
        "the core buys back the folds. Success on (1) alone, with the folds still lost, is a "
        "rejection."
    ),
    expected_failure=(
        "Five ways, in order of likelihood. (1) Dilution without repair: the core halves the lead "
        "and halves nothing else, so C50 lands near +10% a year with a 56% fall, still loses the "
        "2006-08 fold, and the fold record does not move -- the switch was not what lost 2006-08, "
        "the 2008 crash was, and a core that holds SPY through it loses it too. Then the method is "
        "a worse M0227 and the family is out of ideas that do not involve timing. (2) The frame is "
        "the result: C50-R lands within half a point of C50 because half an account in SPY "
        "dominates twenty 2.5% slots, the buyback signal is no longer visible through it, and the "
        "method measures the core rather than the idea. (3) Size weighting makes it worse: M0047 "
        "and M0201 both measured that weighting picks by company size costs 2.5-3.3 points a year "
        "and does not soften the fall, and a 10% sleeve ceiling on 20 names is a weak brake, so "
        "C50-SZ should trail C50; it is here as a measurement, and if it wins it wins against two "
        "prior readings and deserves suspicion, not a variation. (4) Survivorship: M0227's "
        "shrink-minus-issue spread already faded once the dead companies were put back, and half "
        "of this book is SPY, which the check store prices correctly, so the check store should "
        "cut the lead by roughly half of whatever it cut from the parent -- and if the parent's "
        "whole lead was missing dead companies, this one's is too. (5) Decay: the anomaly was "
        "public from 2006-2008, buybacks became the default way US companies return cash, and the "
        "dev window's best-covered years are exactly the post-publication ones. An edge that is "
        "all pre-2009 is a dead edge whatever the twenty-year average says. None of these is a "
        "reason to tune the core share, the ceiling or the 365-day window afterwards."
    ),
    candidates=(
        _v("C50", CoreShrinkParams(S20, Decimal("0.5")),
           "The idea: 50% SPY + 50% in the 20 biggest shrinkers, equal slots, nothing timed"),
        _v("C70", CoreShrinkParams(S20, Decimal("0.7")),
           "Dose-response: 70% SPY + 30% shrinkers"),
        _v("C30", CoreShrinkParams(S20, Decimal("0.3")),
           "Dose-response: 30% SPY + 70% shrinkers"),
        _v("C50-SZ", CoreShrinkParams(S20, Decimal("0.5"), weighting="size"),
           "50% SPY + 50% shrinkers weighted by market value, capped at 10% of the sleeve"),
        _v("C50-R", CoreShrinkParams(R20, Decimal("0.5")),
           "Placebo: the same frame with 20 hash-drawn names from the same scored pool"),
        _v("C50-SWS", CoreShrinkParams(S20, Decimal("0.5"), switch="sleeve"),
           "50% SPY always held; the SPY-200 switch empties the shrinker sleeve alone"),
    ),
    seen_keys=(
        "concept:net-share-issuance",
        "concept:buyback-shrinkers",
        "concept:core-satellite-spy-shrinkers",
    ),
)
