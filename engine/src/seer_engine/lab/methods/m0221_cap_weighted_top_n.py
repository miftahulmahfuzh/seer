"""M0221 — The honest yardstick: the biggest index members held in proportion to their real market value.

Source: general knowledge (how the S&P 500 itself is built: members weighted by market value);
reserved by Sera batch 20261018-0517 for the owner's theme "books shaped like the market"; insight
391; M0122 (trading value as the size stand-in, which cost return on all three books it re-sized)
and M0198 (the placebo re-sized by trading value). Not a stock-picking idea. A yardstick.

Why it exists. Every book in this lab holds equal slots among index members, and SPY does not: it
holds each company in proportion to its market value. M0122 and M0198 could only approximate that
shape with trading value, because the store had no sound company size. Since 2026-10-17 it does
(``Market.market_value``: shares outstanding as filed by that day times the close as it printed).
So build the plainest market-shaped book there is and ask two things. (1) Does a cap-weighted
top-N of the store's own members track SPY, including 2009-2015? If it does, the store can price
the market's shape and the lab's long 2009-2015 shortfall is a property of equal slots and the
200-day switch, not of the data. If even this drifts from SPY, the drift is the store's coverage
(dead companies missing, share counts unknown) and every "beats SPY" in the lab carries that
error. (2) What does the switch cost a book shaped like the market?

How. On each monthly check, among the day's index members with a bar dated ``data_date`` and a
known market value, collapse share classes of one company (GOOG/GOOGL, FOX/FOXA, NWS/NWSA: the
store answers the whole company's count for each class, so two members with the identical share
count are one company; the class with the larger 60-session trading value stays), rank by market
value and hold the top ``top``. ``weighting="cap"``: weights proportional to market value, no name
above ``cap`` of the account, the excess spread over the names under it (M0034's water-filling);
fully invested, nothing parked. ``weighting="equal"``: the same names at 1/top each (the contrast
arm: the lab's usual shape on the market's biggest names). ``pick="random"``: the control of the
same shape -- ``top`` names drawn from the same eligible pool in a fixed hash order of
(seed, symbol) that knows nothing about prices or size, then cap-weighted exactly like the real
arm. The hash order does not change from month to month, so the control's book changes only when
membership or coverage does, as the real arm's does; it pays for no churn the real one does not.

The switch: ``trend=("SPY", 200)`` holds nothing while SPY closes at or below its 200-day average
(``f_factor.trend_on``); every variant sets it explicitly.

Assumptions written before any result. The 10% ceiling is the one pre-registered here; it binds
on top-20 in the late 1990s and 2012-2015 (GE, Microsoft, Apple, Exxon each near or above 10% of
a 20-name book) and almost never on top-50 or top-100. The weight is recomputed every month, so
a held name drifts with its price and the book engine's 1%-of-equity band decides whether the
drift trades; between months a cap-weighted book drifts toward its own cap weights for free.
Members with no known market value (about 44% of dev member-days, mostly names with no bars at
all) cannot be held by any arm, so the "biggest N" is the biggest N the store can see. BRK.B's
2010-11 figures count class A shares only and Alphabet goes unknown from 2014 (it files its count
per class), so both read too small or not at all; that is part of what this yardstick measures.

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by
the contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at
Gotrade's real fees, asked monthly. Pure: reads only bars and share counts dated <= ``data_date``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorParams, trend_on

ADDED = date(2026, 10, 18)
DV_N = 60  # sessions of trading value that decide which share class of a company stays
WEIGHTINGS = ("cap", "equal")
PICKS = ("size", "random")

#: The matched-draw amendment's own date. The originals were written on 2026-10-18; this block
#: was written on 2026-10-19 and pre-registered by the commit that added it.
AMENDED = date(2026, 10, 19)

#: The hash namespace of every blind draw on this chassis. It is the literal ``draw`` already
#: keys on, and M0225 deliberately reuses it (its own ``R50`` does, through ``draw``) so the two
#: blind books hold the same names wherever both stores size the same company. Changing it would
#: put a draw difference on top of the data difference the twin exists to measure.
DRAW_KEY = "M0221"


@dataclass(frozen=True, slots=True)
class CapTopParams:
    """``top`` names held; ``weighting`` cap or equal; ``cap`` the per-name ceiling (cap weighting
    only); ``pick`` size (the biggest) or random (the control); ``seed`` the control's hash seed;
    ``trend`` the switch, (symbol, n) or None, set by every variant."""

    top: int
    weighting: str = "cap"
    cap: float | None = 0.10
    pick: str = "size"
    seed: int = 0
    trend: tuple[str, int] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 500:
            raise ValueError(f"top must be an int in [1, 500], got {self.top!r}")
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if self.pick not in PICKS:
            raise ValueError(f"pick must be one of {PICKS}, got {self.pick!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if self.cap is not None:
            if self.weighting == "equal":
                raise ValueError("cap is meaningless on equal weights")
            if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
                raise TypeError(f"cap must be a number or None, got {type(self.cap).__name__}")
            if not 1.0 / self.top <= float(self.cap) <= 1.0:
                raise ValueError(f"cap must lie in [1/top, 1], got {self.cap}")
        FactorParams(rank="momentum", top=self.top, trend=self.trend)  # validates the switch

    def as_dict(self) -> dict[str, str]:
        return {"top": str(self.top), "weighting": self.weighting,
                "cap": "none" if self.cap is None else repr(float(self.cap)),
                "pick": self.pick, "seed": str(self.seed),
                "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
                "dv_n": str(DV_N), "class_rule": "identical-share-count"}


def _check(params: object) -> CapTopParams:
    if not isinstance(params, CapTopParams):
        raise TypeError(f"params must be CapTopParams, got {type(params).__name__}")
    return params


def _gate(p: CapTopParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def _check_control(params: object) -> CapTopParams:
    """``_check``, plus the one thing a control may not be: a book that ranks on size.

    The matched draw differs from ``R50`` in its allocator id and in nothing else -- the params
    are byte-identical -- so the params must still say ``pick="random"``. Saying ``"size"`` would
    record a configuration whose text claims a size ranking the allocator never performs.
    """
    p = _check(params)
    if p.pick != "random":
        raise ValueError(f"the matched draw is a control: pick must be 'random', got {p.pick!r}")
    return p


def draw(seed: int, symbol: str) -> int:
    """The control's fixed order: a hash of (seed, symbol) that knows nothing about the market."""
    key = f"M0221|{seed}|{symbol}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


@dataclass(frozen=True, slots=True, eq=False)
class CapTopPrepared:
    history: Mapping[str, History]
    market: Any  # the Market (share counts and market value), or None on the history-only path


def sized_pool(prepared: CapTopPrepared, members: AbstractSet[str], data_date: date) -> dict[str, float]:
    """Market value of every member that can be held on ``data_date``, one share class per company."""
    mk = prepared.market
    if mk is None:
        return {}
    by_count: dict[float, tuple[float, str, float]] = {}
    for s in sorted(members):
        if s in EXCLUDED:
            continue
        h = prepared.history.get(s)
        if h is None or h.index_of(data_date) is None:
            continue
        v = mk.market_value(s, data_date)
        n = mk.shares_on(s, data_date)
        if v is None or n is None or not (np.isfinite(v) and v > 0.0):
            continue
        dv = trading_value(h, data_date, DV_N)
        seen = by_count.get(n)
        if seen is None or (dv, s) > (seen[0], seen[1]):
            by_count[n] = (dv, s, v)
    return {s: v for _, s, v in by_count.values()}


def weights(values: list[float], p: CapTopParams) -> list[Decimal | None]:
    """One weight per pick, summing to at most 1."""
    if p.weighting == "equal":
        return [equal_weight(p.top) for _ in values]
    w = np.array(values, dtype=np.float64)
    w = w / float(w.sum())
    if p.cap is not None:
        w = _apply_ceiling(w, max(float(p.cap), 1.0 / len(values)))
    return [_floor_weight(float(x)) for x in w]


class CapTopAllocator:
    """The top-N index members by real market value (or N in a fixed hash order), cap- or
    equal-weighted, fully invested; nothing while the switch, if any, is off. No share counts
    (history-only path): no targets."""

    id = "M0221"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(DV_N, 0 if p.trend is None else p.trend[1])

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: CapTopPrepared, members: AbstractSet[str], data_date: date,
             p: CapTopParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        pool = sized_pool(prepared, members, data_date)
        if not pool:
            return ()
        if p.pick == "size":
            order = sorted(pool, key=lambda s: (-pool[s], s))
        else:
            order = sorted(pool, key=lambda s: (draw(p.seed, s), s))
        picks = order[: p.top]
        out: list[Target] = []
        for s, w in zip(picks, weights([pool[s] for s in picks], p), strict=True):
            if w is None:
                continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no size and no target."""
        return self._run(CapTopPrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CapTopPrepared:
        return CapTopPrepared(history, None)

    def prepare_market(self, market: Any) -> CapTopPrepared:
        if not hasattr(market, "market_value") or len(market.shares) == 0:
            return CapTopPrepared(market.history, None)
        return CapTopPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CapTopPrepared):
            raise TypeError(f"prepared must be CapTopPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


CAPTOP = CapTopAllocator()


# ---- amendment 1 (2026-10-19): the honest control ---------------------------------------------
#
# R50's hash order keys on (seed, symbol) and carries no date, so its book changes only when the
# sized pool does: 76 trades and 0.222 turnover on the dev window against C50's 360 and 0.445,
# which is 0.21x and 0.50x and which D17 refuses. A control that trades a fifth as often pays a
# fifth of Gotrade's fees, so C50's recorded 1.09-point deficit to R50 was quoted against an
# opponent running downhill. This block replaces it with the lab's one matched-draw rule
# (``lab.control_draw``) under a NEW allocator id, so not one byte of what the six recorded M0221
# trials read is touched. The params are R50's own, reused verbatim -- ``CapTopParams`` already
# carries every input the matched draw reads, and a field added to it would move every recorded
# M0221 and M0225 digest (``registry._canon`` renders a dataclass by ``dataclasses.fields()``).


class MatchedCapTopAllocator(CapTopAllocator):
    """The same blind book as ``R50``, re-keyed at the real arm's OWN churn instead of never.

    ``R50`` draws its fifty names in ``draw(seed, symbol)``, a hash with no date term, so its
    book changes only when the pool does. Measured on the dev window: 76 trades against C50's
    360 and 0.222 turnover against 0.445 -- 0.21x and 0.50x, which ``lab control`` refuses (D17).
    A control that trades a fifth as often pays a fifth of the fees, so C50's recorded 1.09-point
    deficit to R50 was quoted against an opponent running downhill, and the deficit is not
    evidence about size ranking. M0243's own file records the same error with the sign flipped --
    its author saw a sticky draw trade 41 times in twenty years, re-drew monthly by hand, and
    overshot to 3.01x. The re-key period is not something to choose; it is something to derive.

    So this allocator keeps everything about R50 except that period, and takes it from the book
    it controls. At each monthly decision it recomputes the real arm's own selection -- the top
    ``top`` of the day's sized pool -- at this data date and at the previous decision's data date
    (``control_draw.previous_decision_date``), counts the names that entered, keeps that many
    fewer of its own holdings in R50's date-free hash order, and draws the rest fresh from the
    same eligible pool in a hash order seeded on the current month
    (``control_draw.matched_names``). The entry count per rebalance is matched by construction, so
    the trade axis is ~1.00 analytically rather than by tuning -- which is the whole reason the
    rule lives in one shared module and is not re-invented per method file.

    **It is still blind.** Nothing it reads about a name decides whether that name is drawn. The
    only thing it takes from the real arm is HOW MANY names changed this month, which is shape,
    not identity. The weighting is R50's unchanged: the drawn names' own market values,
    cap-weighted with the same 10% ceiling, so the only difference between R50 and this arm is
    the draw's re-key period and nothing else at all.

    **The hash namespace** is ``DRAW_KEY``, not the allocator id, for the same reason ``draw``
    hardcodes "M0221": M0225's twin of this arm inherits this class and must draw the same names
    wherever both stores size the same company, or the before-and-after would carry a draw change
    on top of the data change it exists to measure.

    No share counts (the history-only path): no size, so no churn to match and no targets.
    """

    id = "M0221-A1"

    def lookback(self, params: Any) -> int:
        """One month more than the real arm's: ``DV_N`` bars of trading value at the PREVIOUS
        decision's data date. ``control_draw.lookback_for`` adds the 26 bars phase 1 measured as
        the widest gap on the dev calendar, so 86 at the default -- far inside the 473-bar smoke
        fixture ``test_allocator_contract`` runs."""
        p = _check_control(params)
        return max(control_draw.lookback_for(DV_N), 0 if p.trend is None else p.trend[1])

    def _selection(self, prepared: CapTopPrepared, members: AbstractSet[str], at: date,
                   p: CapTopParams) -> tuple[tuple[str, ...], dict[str, float]]:
        """The real arm's own book at ``at``, and the sized pool it was drawn from.

        Membership is the caller's -- today's -- at both dates: the index's composition today is
        known today, so reading it at an earlier date adds no look-ahead, and the prices and share
        counts are still read only as of ``at``.
        """
        pool = sized_pool(prepared, members, at)
        if not pool:
            return (), {}
        return tuple(sorted(pool, key=lambda s: (-pool[s], s))[: p.top]), pool

    def _matched(self, prepared: CapTopPrepared, members: AbstractSet[str], data_date: date,
                 held: frozenset[str], p: CapTopParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        now, pool = self._selection(prepared, members, data_date, p)
        if not pool:
            return ()
        prev, _ = self._selection(
            prepared, members, control_draw.previous_decision_date(data_date), p
        )
        picks = control_draw.matched_names(
            pool=tuple(sorted(pool)),
            held=held,
            real_now=now,
            real_prev=prev,
            tag=DRAW_KEY,
            seed=p.seed,
            data_date=data_date,
        )
        out: list[Target] = []
        for s, w in zip(picks, weights([pool[s] for s in picks], p), strict=True):
            if w is None:
                continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no size, no churn to match and no target."""
        _check_control(params)
        return ()

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CapTopPrepared):
            raise TypeError(f"prepared must be CapTopPrepared, got {type(prepared).__name__}")
        return self._matched(prepared, members, data_date, held, _check_control(params))


MATCHED = MatchedCapTopAllocator()

SW = ("SPY", 200)


def _v(suffix: str, params: CapTopParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0221-{suffix}", family="M0221", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CAPTOP, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _a(suffix: str, allocator: Any, params: CapTopParams, rationale: str,
       supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate: its own ``added`` date, its own allocator and the declaration of
    which recorded arm it replaces, otherwise ``_v``.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``). It is DECLARED and never
    inferred from the target, and it is outside ``config_digest`` because ``config_text`` names
    its three attributes by hand. An arm that declares nothing retires nothing, so leaving this
    off would leave M0221 blocked after the measurement was taken."""
    return Candidate(id=f"M0221-{suffix}", family="M0221", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_AMENDMENT = Amendment(
    added=AMENDED,
    why=(
        "R50, the control C50's margin is quoted against, trades 0.21x and turns over 0.50x what "
        "C50 does, so D17 refuses it; re-draw it at C50's own monthly churn and re-state the gap"
    ),
    hypothesis=(
        "Written before any result. C50 earned 5.63% a year of the owner's money on the dev "
        "window and R50 earned 6.72% against the same 7.19% SPY total return, so the blind draw "
        "currently BEATS the book by 1.09 points -- and R50 got there on 76 trades where C50 "
        "paid for 360. R50's hash has no date term, so it drew fifty names once and held them "
        "for twenty years whatever the market did; the only fees it ever paid were the ones "
        "membership forced on it. C50-PLC is the same fifty-name cap-weighted blind book with "
        "one thing changed: the number of names it re-draws each month is C50's own number of "
        "entrants that month, taken from C50's calendar rather than chosen by hand. Prediction, "
        "and the direction is the point: the honest control trades about five times as often, "
        "pays those fees, and therefore earns LESS than R50 did, so C50's deficit NARROWS -- to "
        "somewhere between 0 and 1 point, and possibly past zero into a lead. Second prediction, "
        "about shape rather than money, and the one that decides whether the first is readable "
        "at all: C50-PLC lands inside 0.80x-1.25x of C50 on both trades and turnover, which is "
        "what makes the re-stated gap evidence instead of a handicap. Success here is a yardstick "
        "whose control is honest, not an arm that wins: no arm of this method is for promotion."
    ),
    expected_failure=(
        "The fee channel is small in absolute terms and the identity channel may swamp it. C50 "
        "turns over only 0.445 of the account a year, so matching it raises the control's "
        "turnover by about 0.22 a year, and Gotrade's bill on that is tens of basis points, not "
        "a point -- while re-keying the draw monthly changes WHICH names the control holds for "
        "twenty years, and a draw re-sampled every month converges on the sized pool's own mean "
        "return instead of resting on one lucky 1996 sample. If that mean is above what R50's "
        "single sticky draw happened to earn, the matched control earns MORE, C50's deficit "
        "WIDENS rather than narrows, and the pre-registered direction is simply wrong. That is "
        "the finding and it is reported as one; it is not re-drawn for. Second, the shape may "
        "miss on the turnover axis alone: E50 holds C50's exact names and trades C50's exact 360 "
        "times, yet turns over 1.60x as much, because a flatter weight vector crosses the resize "
        "band more often -- and a blind draw from the sized pool is flatter than the top fifty "
        "are, since it rarely holds a name big enough for the 10% ceiling to bind. If C50-PLC "
        "clears the trade axis and lands above 1.25x on turnover, the matched-draw rule does not "
        "settle this chassis and the honest answer is to say so rather than to re-draw. Third, "
        "the previous decision's selection is recomputed with TODAY's membership, so a name that "
        "joined the index in between is counted as a non-entrant and the matched entry count "
        "reads slightly low; the effect is one or two names a year on a 50-name book."
    ),
    candidates=(
        _a("C50-PLC", MATCHED, CapTopParams(50, pick="random", seed=1, trend=None),
           "Placebo, shape-matched: the same fifty-name cap-weighted blind book, hash-drawn at "
           "C50's own monthly churn instead of once and forever",
           supersedes=("M0221-R50",)),
    ),
)


METHOD = Method(
    id="M0221",
    name=(
        "The honest yardstick: the biggest index members held in proportion to their real market "
        "value, with and without the 200-day switch"
    ),
    family="market-shape-yardstick",
    source_kind="knowledge",
    source_ref=(
        "S&P 500 cap-weighting; Sera 20261018-0517 owner theme 'books shaped like the market'; "
        "insight 391; M0122 and M0198 (trading value as the size stand-in)"
    ),
    parent_id=None,
    hypothesis=(
        "Not a picker but the yardstick every picker needs. Now that the store carries point-in-time "
        "market value, hold each month the top N index members by real market value (one share "
        "class per company), weighted by market value with no name above 10% of the account, fully "
        "invested, fractional shares at Gotrade's real fees on the owner's monthly top-up. Arms: "
        "C50 (top 50, no switch), C100 (top 100, no switch, the closest to SPY's shape), C20 (top "
        "20, no switch, concentrated), C50-SW (top 50 behind the SPY 200-day switch), E50 (the same "
        "top 50 at equal weight: the lab's usual shape on the biggest names), and R50 (50 members "
        "drawn in a fixed hash order that ignores size and price, cap-weighted: the meaningless "
        "control of the same shape). Predictions, written before any result: C100 and C50 track "
        "total-return SPY within about a point a year over 1996-2015 and within about a point in "
        "2009-2015, with worst falls near SPY's 55% in 2008; C20 trails SPY after 2009 by more, "
        "because the 10% ceiling binds on the giants; C50-SW gives up return after 2009 to whipsaws "
        "but roughly halves the 2008 fall; E50 leads the cap arms before 2009 and trails after; "
        "R50 lands nearer the equal-weight arm than SPY, because without size ranking it holds "
        "mostly mid-sized members. Success is a yardstick that tracks SPY, not a book that beats "
        "it: no arm is expected to pass the gate, and none is for promotion (it would simply be "
        "SPY with fees). Cap weighting is not a published anomaly; it is the market itself."
    ),
    expected_failure=(
        "The store, not the shape. About 44% of dev member-days have no market value (mostly "
        "members with no bars at all, many of them the companies that later died), so the biggest "
        "N is the biggest N the store can see; Berkshire reads too small in 2010-11 and Alphabet "
        "goes unknown from 2014. If C100 drifts from SPY by more than about a point a year -- "
        "above it because the missing names were the losers (survivorship), or below it because "
        "missing giants carried SPY -- the yardstick measures the store's holes and the verdict "
        "must say so; the survivorship-check store re-run then decides which. Second, fees: a "
        "100-name book on a 20M IDR account means slots of about $15 at the start, where Gotrade's "
        "minimum charges bite hardest, so C100 may trail C50 on fees alone in the early years. "
        "Third, the 10% ceiling on C20 moves money from the biggest names to the rest every month "
        "and may trade more than the uncapped arms. Fourth, a 2009-2015 lag on C50 would mean the "
        "lab's measuring frame itself handicaps any member book against SPY, which is worth knowing "
        "even though it is the uncomfortable answer."
    ),
    candidates=(
        _v("C50", CapTopParams(50, trend=None),
           "Top 50 members by market value, cap-weighted with a 10% ceiling, no switch"),
        _v("C100", CapTopParams(100, trend=None),
           "Top 100 members by market value, cap-weighted with a 10% ceiling, no switch"),
        _v("C20", CapTopParams(20, trend=None),
           "Top 20 members by market value, cap-weighted with a 10% ceiling, no switch"),
        _v("C50-SW", CapTopParams(50, trend=SW),
           "Top 50 by market value, cap-weighted, behind the SPY 200-day switch"),
        _v("E50", CapTopParams(50, weighting="equal", cap=None, trend=None),
           "Contrast: the same top 50 by market value at equal weight, no switch"),
        _v("R50", CapTopParams(50, pick="random", seed=1, trend=None),
           "Control: 50 members in a fixed size-blind hash order, cap-weighted, no switch"),
    ),
    seen_keys=(
        "concept:cap-weighted-top-n",
        "concept:market-shape-yardstick-real-cap",
    ),
    amendments=(MATCHED_AMENDMENT,),
)
