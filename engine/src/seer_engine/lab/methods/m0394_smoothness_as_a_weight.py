"""M0394 — Smoothness as a weight, not as a filter: the frog-in-the-pan tilt that replaces nobody.

Source: Da, Gurun & Warachka (2014), "Frog in the Pan: Continuous Information and Momentum",
Review of Financial Studies 27(7), 2171-2218 (SSRN 1777988), by way of M0036, which brought the
measure into this lab and is this method's parent.

**What the family already knows, and the one hole in it.** M0036 built the paper's reading --
information discreteness, ``sign(formation return) x (share of down days - share of up days)``
over the formation window -- on M0032's frame and sorted the top forty momentum names by it. The
drizzle book earned 12.1% a year on the owner's deposits where its own mirror, the jumps book,
earned 9.8%: 2.3 points a year, with a quarter less churn. M0043 took the same measure to the
residual pool and found nothing. M0044 put a brake on the drizzle book and got it under the fall
limit only by giving up the return. M0054 removed the cash switch and found the drizzle picks
alone lose to SPY by 2.3 points a year after 2009, which is the family's own verdict that the
edge was the switch and not the picking.

So four methods have asked whether the smooth names are better names. **None of them has ever
asked whether the plain twenty, chosen on momentum alone and left alone, would have done just as
well.** M0036's analysis says so in its own words: *"the lab has never run the plain twenty-name
one-year-gain book at real fees on your real deposits, so I cannot tell you whether the drizzle
book beats that. The only clean comparison this run supports is drizzle against jumps."* That is
the lab's single largest unpriced reversed pair -- a 2.3-point headline quoted against a mirror
that pays the same costs, so the costs cancel and the sentence cannot say whether acting on the
signal was worth what acting cost. Insight 523 measured 28 such pairs across 23 methods and found
only 6 priceable; this is one of the 22.

**Why a weight and not a filter.** Every arm this family has run *replaced* names: take forty,
keep twenty. That spends momentum rank 20-40 to buy smoothness, and the lab has now diagnosed
that exact mechanism four times over -- the price confirmation filter (M0380) and the three
buyback vetoes before it each cost 2.5 to 4.2 points a year against their own no-veto twins,
because a rule that throws a pick out must reach further down the ranked list to refill the slot
and the replacement is by construction a worse name. M0036's drizzle book is that design: it pays
the refill cost on ten of its twenty slots every month.

This method removes the mechanism rather than measuring it again. **Every arm holds exactly the
twenty names the plain momentum book holds.** Nothing is ever vetoed, nothing is ever replaced,
and the refill cost is structurally zero. Smoothness moves only the *slot sizes*: the smoothest
of the twenty gets a larger slice and the jumpiest a smaller one, on a signed dial, under M0047's
weight ceiling. Total exposure is held identical to equal weighting at every setting
(``_tilt_weights`` scales to ``len(chosen) / top``, M0034's rule verbatim), so a tilt moves money
between names and never changes how much of the book is invested. That matters because M0374
bought a better luck reading by investing only 57% of the account and then lost three folds of
four, and because a partial-weight book can record zero trades while its exposure moves.

**The arms are a dial, not a pair.** ``PLAIN`` is the dial at zero: the plain twenty, equal
slots, no opinion in it at all. It is the no-opinion twin the family never registered, and it is
the zero rung of the ladder. ``SM25``, ``SM50`` and ``SM90`` tilt toward the smooth names at
rising strength, and ``JM50`` is the same dial turned the other way, toward the jumpy ones. If
the paper's effect survives in this universe, the five readings must come out ordered -- JM50
below PLAIN below SM25 below SM50 -- and a monotone ladder is evidence a single pair cannot give.
The lab has written this down: a two-point slope read is wrong, and five rungs said 1.66x where
two said 8x. ``DRAW`` is twenty names pulled from the same pool by hash, turnover-matched to
PLAIN through ``control_draw``, because one blind draw erased a 3.2-point claim once already and
this lab's draws span seven and a half points a year.

**The frame is M0036's, unchanged**, which is M0032's: F4's liquidity and membership screen, the
SPY-200 trend gate, top twenty, monthly, fractional shares at Gotrade's real fees on
``monthly-hold-frac-gotrade``, funded 5,000,000 IDR on the 25th of each month. Only the slot
sizes differ between arms. The base ranking is 12-1 total momentum on every arm; the residual
side is deliberately absent, because M0043 closed it and ``base="residual"`` would only re-spend
trials on a question already answered.

Smoothness is measured exactly as M0036 measures it -- ``continuity_scores`` is imported from
that file rather than copied, so the two methods cannot drift apart -- over the same ``fip_n``
sessions ending ``skip`` sessions before the data date, on the market symbol's own calendar, with
a name scored only when it has 80% of the window. Every piece reads only bars dated <= d.

**A note on the family string.** This method's idea row was reserved under a new family,
``stock-information-discreteness``. It carries ``stock-momentum-attention`` instead, with
``parent_id="M0036"``. That is deliberate and it costs this method something: a fresh family
string would have hidden it from its four siblings' record under the hard gate's (K) kin clause,
and the lab's own rule is to name a family by what it ranks on. This ranks on the shape of a
momentum path, which is what M0036, M0043, M0044 and M0054 rank on. Hiding from kin is the one
thing the gate exists to prevent.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    ReturnGrid,
    build_grid,
)
from seer_engine.lab.methods.m0036_frog_in_the_pan import FipParams, continuity_scores
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 26)

MAX_TILT = 0.95
"""The dial's bound, and the line between a weight and a filter.

At ``tilt`` the slot multipliers run from ``1 - tilt`` to ``1 + tilt`` across the twenty ranks,
so ``tilt = 1.0`` would hand the jumpiest name a multiplier of exactly zero -- which is a veto
wearing a weight's clothes, and the whole point of this method is that no name is ever dropped.
0.95 leaves the bottom rank a twentieth of an equal slot: small, still held, still trading."""


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class WeightParams:
    """``inner`` is F4's screen, trend gate and book size; ``tilt`` is the only thing that varies.

    ``tilt`` is signed and in ``[-MAX_TILT, MAX_TILT]``. Zero is equal slots -- the plain book,
    no opinion. Positive tilts money toward the smooth names, negative toward the jumpy ones, and
    the magnitude is the rung. ``inner.rank`` stays ``"momentum"``: it does the selecting here
    (unlike M0036, where the allocator chose), so the twenty names are F4-MOM12-N20-TREND's
    twenty, name for name, at every tilt.

    ``cap`` is M0047's weight ceiling as a fraction of the book, water-filled by ``_apply_ceiling``
    so the capped excess lands on the names still under it. At ``top = 20`` an equal slot is 5%,
    so ``cap = 0.10`` binds only above ``tilt = 0.90`` and is a rail rather than a dial.

    ``seed`` is the blind draw and is mutually exclusive with a non-zero ``tilt``: when it is set
    the arm ignores smoothness entirely and holds twenty names drawn from the same pool by hash,
    turnover-matched to the ``tilt = 0`` book.

    The smoothness window (``fip_n``, ``skip``, ``market``) is carried as M0036's own
    ``FipParams`` rather than as loose fields, so ``continuity_scores`` is called with exactly the
    object it was written against and the two methods measure the identical thing.
    """

    inner: FactorParams
    tilt: float = 0.0
    cap: float | None = 0.10
    fip_n: int = 252
    skip: int = 21
    market: str = "SPY"
    seed: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.tilt, bool) or not isinstance(self.tilt, (int, float)):
            raise TypeError(f"tilt must be a number, got {type(self.tilt).__name__}")
        if not math.isfinite(float(self.tilt)) or abs(float(self.tilt)) > MAX_TILT:
            raise ValueError(f"tilt must be finite and |tilt| <= {MAX_TILT}, got {self.tilt}")
        if self.cap is not None:
            if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
                raise TypeError(f"cap must be a number or None, got {type(self.cap).__name__}")
            if not 1.0 / self.inner.top <= float(self.cap) <= 1.0:
                raise ValueError(
                    f"cap must lie between the equal weight {1.0 / self.inner.top:.4f} and 1.0, "
                    f"got {self.cap}"
                )
        for name in ("fip_n", "skip"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.fip_n < 20:
            raise ValueError(f"fip_n must be >= 20, got {self.fip_n}")
        if self.skip < 0:
            raise ValueError(f"skip must be >= 0, got {self.skip}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")
        if self.seed is not None:
            if isinstance(self.seed, bool) or not isinstance(self.seed, int):
                raise TypeError(f"seed must be an int or None, got {type(self.seed).__name__}")
            if float(self.tilt) != 0.0:
                raise ValueError("a drawn arm reads no smoothness: set tilt=0.0 beside a seed")

    @property
    def fip(self) -> FipParams:
        """M0036's parameters for the smoothness reading, so its code is called as it was written.

        ``mode`` and ``pool`` are untouched defaults: ``continuity_scores`` reads neither, and
        this method never calls M0036's ``choose``, which is the function they steer.
        """
        return FipParams(
            inner=self.inner, fip_n=self.fip_n, skip=self.skip, market=self.market
        )

    def as_dict(self) -> dict[str, str]:
        out = {
            "tilt": f"{float(self.tilt):.4f}",
            "cap": "none" if self.cap is None else f"{float(self.cap):.4f}",
            "fip_n": str(self.fip_n),
            "skip": str(self.skip),
            "market": self.market,
            "seed": "none" if self.seed is None else str(self.seed),
            "draw_rule": control_draw.RULE_ID if self.seed is not None else "none",
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> WeightParams:
    if not isinstance(params, WeightParams):
        raise TypeError(f"params must be WeightParams, got {type(params).__name__}")
    return params


def weight_lookback(params: WeightParams) -> int:
    """Bars through d the decision needs: the screen's window, or the smoothness window."""
    return max(factor_lookback(params.inner), params.skip + params.fip_n + 2)


# --------------------------------------------------------------------------- the weighting


def _apply_ceiling(w: np.ndarray, ceiling: float) -> np.ndarray:
    """``w`` with every entry capped at ``ceiling``, the excess spread over the names still under it.

    M0034's water-filling, verbatim and for its reason: at most ``len(w)`` passes, because each
    pass caps at least one more name. Feasible whenever ``ceiling`` is at least the mean of ``w``,
    which holds here -- ``WeightParams`` validates ``cap >= 1 / top`` and the mean is the equal
    weight by construction.
    """
    w = w.astype(np.float64, copy=True)
    for _ in range(len(w)):
        over = w > ceiling
        if not over.any():
            break
        excess = float((w[over] - ceiling).sum())
        w[over] = ceiling
        free = (~over) & (w > 0.0)
        if not free.any():
            break
        w[free] += excess * w[free] / float(w[free].sum())
    return np.minimum(w, ceiling)


def _floor_weight(x: float) -> Decimal | None:
    """``to_weight(x)``, or None when ``x`` floors to zero (``f_factor``'s rule, verbatim)."""
    if not np.isfinite(x) or Decimal(repr(x)) < WEIGHT_QUANTUM:
        return None
    return to_weight(x)


def tilt_weights(
    chosen: Sequence[FactorRow], cont: Mapping[str, float], params: WeightParams
) -> list[Decimal | None]:
    """One weight per chosen row, tilted by smoothness rank. Σ of the non-None is ``len / top``.

    The dial is built on the *rank* of smoothness inside the twenty, not on its level. Information
    discreteness is a bounded, lumpy statistic -- it is a difference of day counts over a day
    count, so on 252 sessions it moves in steps of about 0.008 and its spread inside a top-twenty
    momentum book is narrow. Weighting by the level would hand almost-equal slots whenever the
    book happened to be homogeneous that month, which is to say the dial would quietly turn itself
    off exactly when the names were hardest to tell apart, and the ladder would read as a flat
    line for a reason that has nothing to do with the market. Ranking forces the same spread of
    slot sizes every month, so a flat ladder means the signal is flat and not that the month was.

    With ``n`` names ranked 0 (jumpiest) to ``n - 1`` (smoothest), the multiplier is
    ``1 + tilt * z`` where ``z`` runs ``-1 .. +1``. Every multiplier is strictly positive for
    ``|tilt| <= MAX_TILT``, so no name is ever dropped -- the property this whole method rests on.

    Total exposure is ``len(chosen) / top`` under every tilt, the same as equal weighting, so a
    tilt moves money between names and never changes how much of the book is invested. A name
    with no smoothness reading is not droppable either: it is ranked at the middle of the book,
    which is the one position that expresses no opinion about it.
    """
    if not chosen:
        return []
    top = params.inner.top
    eq = equal_weight(top)
    n = len(chosen)
    if float(params.tilt) == 0.0 or n == 1:
        return [eq for _ in chosen]

    mid = (n - 1) / 2.0
    order = sorted(
        range(n),
        key=lambda k: (cont.get(chosen[k].symbol) is None, cont.get(chosen[k].symbol, 0.0),
                       chosen[k].symbol),
    )
    place = np.full(n, mid, dtype=np.float64)
    rank = 0
    for k in order:
        if chosen[k].symbol in cont:
            place[k] = float(rank)
        rank += 1

    z = (2.0 * place / (n - 1)) - 1.0
    raw = 1.0 + float(params.tilt) * z
    raw = np.clip(raw, 1.0 - MAX_TILT, 1.0 + MAX_TILT)
    w = raw / float(raw.sum()) * (n / top)
    if params.cap is not None:
        w = _apply_ceiling(w, float(params.cap))
    return [_floor_weight(float(x)) for x in w]


def plain_book(rows: Sequence[FactorRow], params: WeightParams) -> list[FactorRow]:
    """The twenty names the plain momentum book holds, in rank order. Every arm holds these."""
    scorable = [r for r in rows if r.symbol not in EXCLUDED and math.isfinite(r.momentum)]
    return sorted(scorable, key=lambda r: (-r.momentum, r.symbol))[: params.inner.top]


def _targets(chosen: Sequence[FactorRow], cont: Mapping[str, float],
             params: WeightParams) -> tuple[Target, ...]:
    out: list[Target] = []
    for row, weight in zip(chosen, tilt_weights(chosen, cont, params), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


class SmoothWeightAllocator:
    """The plain momentum twenty, with the slots sized by how smoothly each name got there.

    Selection is F4-MOM12-N20-TREND's, name for name, at every tilt: the trend gate, F4's screen,
    the twenty highest 12-1 momentum names. Only the slot sizes carry an opinion, so the arms of
    this method differ from one another in nothing but weight -- which is the one way to ask what
    smoothness is worth without also paying for a replaced pick.
    """

    id = "M0394"

    def lookback(self, params: Any) -> int:
        return weight_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def prepare(self, history: Mapping[str, History]) -> "Prepared":
        return Prepared(history, prepare_factor(history))

    # -- the two readings a drawn arm needs -------------------------------------------------

    def _select(self, prepared: "Prepared", members: AbstractSet[str], data_date: date,
                params: WeightParams) -> tuple[list[str], list[str]]:
        """``control_draw.Select``: the eligible pool on ``data_date``, and the plain twenty.

        Reads the gate too, so on a date the gate is off the real book is empty and
        ``matched_book`` returns nothing -- the draw sits in cash exactly when the book does,
        which is what keeps its exposure comparable rather than flattering it.
        """
        if not trend_on(prepared.history, data_date, params.inner):
            return [], []
        rows = prepared.factor.rows_on(members, data_date, params.inner)
        pool = [r.symbol for r in rows if r.symbol not in EXCLUDED]
        return pool, [r.symbol for r in plain_book(rows, params)]

    def _drawn(self, prepared: "Prepared", members: AbstractSet[str], data_date: date,
               held: frozenset[str], params: WeightParams) -> tuple[Target, ...]:
        names = control_draw.matched_book(
            lambda d: self._select(prepared, members, d, params),
            data_date, held, tag="M0394", seed=int(params.seed or 0),
        )
        if not names:
            return ()
        rows = {r.symbol: r for r in prepared.factor.rows_on(members, data_date, params.inner)}
        chosen = [rows[s] for s in names if s in rows]
        return _targets(chosen, {}, params)

    # -- the allocator contract -------------------------------------------------------------

    def _book(self, history: Mapping[str, History], rows: list[FactorRow],
              grid: ReturnGrid | None, data_date: date,
              params: WeightParams) -> tuple[Target, ...]:
        chosen = plain_book(rows, params)
        if not chosen:
            return ()
        cont: Mapping[str, float] = {}
        if float(params.tilt) != 0.0 and grid is not None:
            cont = continuity_scores(
                grid, [r.symbol for r in chosen], data_date, params.fip
            )
        return _targets(chosen, cont, params)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if p.seed is not None:
            return self._drawn(Prepared(history, prepare_factor(history)),
                               members, data_date, held, p)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._book(history, rows, build_grid(history, p.market), data_date, p)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Prepared):
            raise TypeError(f"prepared must be Prepared, got {type(prepared).__name__}")
        p = _check(params)
        if p.seed is not None:
            return self._drawn(prepared, members, data_date, held, p)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._book(prepared.history, rows, prepared.grid(p.market), data_date, p)


class Prepared:
    """F4's prepared rows plus M0036's return grid, built once per run and cached per market."""

    __slots__ = ("history", "factor", "_grids")

    def __init__(self, history: Mapping[str, History], factor: FactorPrepared) -> None:
        self.history = history
        self.factor = factor
        self._grids: dict[str, ReturnGrid | None] = {}

    def grid(self, market: str) -> ReturnGrid | None:
        if market not in self._grids:
            self._grids[market] = build_grid(self.history, market)
        return self._grids[market]


SMOOTH = SmoothWeightAllocator()


# --------------------------------------------------------------------------- the arms


def _v(suffix: str, params: WeightParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0394-{suffix}", family="M0394", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SMOOTH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0394",
    name="Smoothness as a weight, not as a filter: what the frog-in-the-pan tilt is worth when it replaces nobody",
    family="stock-momentum-attention",
    source_kind="variation",
    source_ref=(
        "M0036 (Da, Gurun & Warachka 2014, Frog in the Pan: Continuous Information and Momentum, "
        "Review of Financial Studies 27(7), 2171-2218, SSRN 1777988)"
    ),
    parent_id="M0036",
    hypothesis=(
        "M0036 found that among last year's winners, the ones that climbed quietly beat the ones "
        "that climbed in jumps by 2.3 points a year on the owner's deposits (12.1% against 9.8%) "
        "with a quarter less churn, and three siblings have since worked on that book. Not one of "
        "the four ever ran the plain twenty-name momentum book beside them, and M0036's own "
        "analysis says so: the only clean comparison it supports is drizzle against jumps. Both "
        "of those arms pay the same cost to act, so the cost cancels and the 2.3 points price the "
        "SIGNAL while saying nothing about whether ACTING on it was worth what acting cost. This "
        "method registers the missing third arm -- the plain twenty, equal slots, no opinion in it "
        "-- and prices the whole family's headline against it for the first time. "
        "It also changes how the signal is used, for a reason the lab has now measured four "
        "times. Every arm in this family REPLACED names: take the forty highest momentum names, "
        "keep the twenty smoothest. That spends momentum rank 20-40 to buy smoothness, and a rule "
        "that throws a pick out must reach further down the ranked list to refill the slot, so "
        "the replacement is by construction a worse name -- the diagnosis that cost the price "
        "confirmation filter 4.2 points a year (M0380) and the three buyback vetoes 2.5 to 4.2 "
        "each. Here nothing is ever replaced. Every arm holds exactly the twenty names the plain "
        "momentum book holds, and smoothness moves only the slot sizes, on a signed dial under a "
        "weight ceiling, with total exposure held identical to equal weighting at every setting "
        "so that no arm can buy a better reading by sitting in cash the way M0374 did. The refill "
        "cost is therefore structurally zero, and whatever the dial earns or loses is the "
        "weighting alone. "
        "The arms are a ladder rather than a pair, because a two-point slope read is wrong and "
        "this lab has been burned by one: PLAIN at zero tilt, SM25, SM50 and SM90 tilting toward "
        "the smooth names at rising strength, and JM50 the same dial turned toward the jumpy "
        "ones. If the paper's effect is real in this universe the five must come out ordered, "
        "JM50 below PLAIN below SM25 below SM50, and monotonicity across five rungs is evidence "
        "no single pair can give. DRAW is twenty names pulled from the same pool by hash, "
        "turnover-matched to PLAIN, because one blind draw erased a 3.2-point claim in this lab "
        "once already and the draws span seven and a half points a year. "
        "The frame is M0036's unchanged, which is M0032's: F4's liquidity and membership screen, "
        "the SPY-200 trend gate, top twenty, monthly, fractional shares at Gotrade's real fees on "
        "monthly-hold-frac-gotrade, funded 5,000,000 IDR on the 25th of each month. The residual "
        "pool is deliberately absent because M0043 closed it."
    ),
    expected_failure=(
        "The likeliest outcome is that the ladder is flat and the direction closes. M0054 has "
        "already measured that the drizzle picks alone lose to SPY by 2.3 points a year after "
        "2009 and concluded the family's edge was the cash switch and not the picking; M0043 "
        "found the plain residual top-twenty beat both of its sorts. If both readings generalise, "
        "PLAIN will match or beat every tilted arm, JM50 will not be distinguishable from SM50, "
        "and all six will sit inside the blind draw's own width -- which would say the 2.3 points "
        "M0036 reported was the cost of the jumps book's extra churn (1,582 trades against 1,203) "
        "rather than any virtue in the smooth names, and that the family's headline has been "
        "quoted against a handicapped opponent for seventeen days. "
        "The second way it fails is narrower and more interesting: the dial is real but too small "
        "to see. Information discreteness is a difference of day counts over a day count, so on "
        "252 sessions it steps in units of about 0.008, and inside a top-twenty momentum book -- "
        "539 large, liquid, heavily covered index members with a 20M USD dollar-volume floor -- "
        "its spread may be narrow enough that ranking on it is ranking on noise. Ranking rather "
        "than levelling protects the dial from turning itself off in a homogeneous month, but it "
        "cannot manufacture information that is not there, and a weighting effect worth under a "
        "point a year is invisible against draw noise of seven and a half. "
        "The third is the fall. Every M0036 arm lost 22.2% to 22.8% from a peak against the "
        "owner's 20% limit, and the reason was a six-week market crash that the 200-day average "
        "takes months to react to. Re-weighting twenty names cannot touch that: the fall is "
        "caused by owning stocks at all, so every arm here should fail the real-money fall bar "
        "for the same reason its parent did, whatever the ladder says about return. This method "
        "is registered to settle what smoothness is worth, not to produce a promotable book, and "
        "kin alone should refuse it -- two of the lab's five test-failed methods are momentum "
        "books that a plain momentum book will move with."
    ),
    candidates=(
        _v("PLAIN", WeightParams(inner=N20, tilt=0.0),
           "The plain twenty, equal slots: the no-opinion twin this family never registered, and "
           "the zero rung every tilt is read against."),
        _v("SM25", WeightParams(inner=N20, tilt=0.25),
           "A mild rung of the smoothness dial: slots run 0.75x to 1.25x of equal across the "
           "twenty, smoothest largest, nothing replaced."),
        _v("SM50", WeightParams(inner=N20, tilt=0.50),
           "The middle rung of the smoothness dial, 0.5x to 1.5x of equal: the setting the mirror "
           "is drawn against."),
        _v("SM90", WeightParams(inner=N20, tilt=0.90),
           "The strongest rung of the smoothness dial, 0.1x to 1.9x of equal and the only one the "
           "weight ceiling binds: as close to a filter as a weight can get while still holding "
           "every name."),
        _v("JM50", WeightParams(inner=N20, tilt=-0.50),
           "The mirror rung of the dial, pointed at the jumpy names instead: it must lose to the "
           "plain twenty by about what SM50 wins, or the paper's effect is not what is being "
           "measured."),
        _v("DRAW", WeightParams(inner=N20, tilt=0.0, seed=394),
           "Control: twenty names drawn from the same pool by hash, turnover-matched to the plain "
           "twenty, because one blind draw is not a control and this lab's draws span seven and a "
           "half points a year."),
    ),
    seen_keys=(
        "concept:smoothness-as-a-weight-not-a-filter",
        "concept:information-discreteness-dose-ladder",
        "concept:frog-in-the-pan-no-opinion-twin",
    ),
)
