"""Phase 4 of control-draw-remedies: measure the weight-vector remedy before it is built.

Nothing here is lab code. It is a scratchpad prototype, it writes no trial, it opens no database
and it is imported by nothing under ``engine/``. It exists to answer one question for free:

    does attaching a weight vector to the lab's matched draw move a weight-varying control's
    turnover TOWARD the book it controls, or AWAY from it?

The direction is not known. ``M0221-C50-PLC`` already weights its drawn names by their own market
values with the chassis's own code, so it is already drift-neutral in the same way the book is;
its 1.95x excess is not drift. Measured from ``sim.book._beyond_band``, which under
``monthly-hold-frac-gotrade`` trades a held name only when its gap is worth 1% of the WHOLE
account, the resize band on a 50-name book is close to inert -- a name must drift half its own
target to move. So the excess is in the SIZE of the entry and exit trades, not in their number
(371 against 360, 1.03x) and not in drift. A cap-weighted top-50's entrant is the new number 50
and carries the smallest weight in the book; a blind draw's entrant carries about 1/50 of the
account. ``M0221-E50`` is that effect alone -- identical names, identical trades, every entrant at
1/50 -- and it reads 1.60x.

Four assignment rules are prototyped against that model, and all four are pre-registered in this
file's plan before any of them ran:

  A  the real book's sorted weight vector, down the control's own month-keyed order
  B  the same vector, down the date-free keep order
  C  the control's OWN market values, raised to a power fitted so the vector has the real book's
     Herfindahl index, then the chassis's own ceiling -- drift-neutral by construction
  D  keeps first in the keep order, this month's entrants last, down the same sorted vector, so an
     entrant always takes a BOTTOM rung, as a real top-N's entrant does

There is no rule E. If all four miss, the phase STOPs and that is the deliverable.

Every arm holds the SAME NAMES as the shipped control: ``control_draw.matched_names`` is called
unchanged, with the same tag and the same seed, and only the weight each drawn name is handed
differs. Every arm also holds the same TOTAL exposure as the shipped control: each rule is
renormalised to the shipped control's own weight sum, so a rule changes the shape of the vector
and never how much of the book is invested.

The same four rules are prototyped on M0201, where the gap runs the other way: that control needs
MORE turnover (1.9228 against the book's 2.4213, 0.794x, short of D17's 0.80 floor by 0.0059).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

from seer_engine import dates, research
from seer_engine.backtest.dev import DEV_END, MEMBERSHIP_START, Candidate, run_registry
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.lab import control_draw
from seer_engine.lab.methods import m0201_treasury_beta_size_weighted as m0201
from seer_engine.lab.methods import m0221_cap_weighted_top_n as m0221
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.f_factor import trend_on

STORE = Path(os.environ.get("SEER_RESEARCH_STORE", "/home/miftah/seer/engine/.research"))

#: Bisection bounds for rule C's exponent. 1.0 reproduces the chassis's own weighting exactly,
#: and the range is TWO-SIDED on purpose: measured on the dev store during planning, a blind draw
#: from M0221's sized pool is MORE concentrated than the real top 50 is, not less -- the draw
#: spans the whole size range while the top 50 are all mega-caps under a 10% ceiling. A
#: one-sided [1, 24] range therefore clamped at 1.0 every single month and made rule C a
#: byte-identical copy of the shipped control, which measures nothing. Below 1 the transform
#: flattens; above 1 it sharpens; the fit picks whichever side the month needs.
GAMMA_MIN = 0.05
GAMMA_MAX = 24.0
GAMMA_STEPS = 48


# --------------------------------------------------------------------------- shared shaping


def _hhi(w) -> float:
    """Herfindahl index of a weight vector: the one number rule C matches."""
    a = np.asarray(list(w), dtype=np.float64)
    return float(np.square(a).sum())


def _rescale(v: list[float], n: int, total: float) -> list[float]:
    """``v`` trimmed or padded to ``n`` rungs and renormalised to sum to ``total``.

    The control's book can be shorter than the real book's when the eligible pool is thin, and
    ``matched_names`` already handles that on the name axis; this handles it on the weight axis.
    Padding repeats the smallest rung, which is what a real top-N would do with one more name.
    ``total`` is always the SHIPPED control's own weight sum, so a rule never changes how much of
    the book is invested -- only its shape.
    """
    if n <= 0 or total <= 0.0:
        return [0.0] * max(0, n)
    if not v:
        return [total / n] * n
    out = list(v[:n]) if n <= len(v) else list(v) + [v[-1]] * (n - len(v))
    s = float(sum(out))
    if not np.isfinite(s) or s <= 0.0:
        return [total / n] * n
    return [x / s * total for x in out]


def _powered(values: list[float], gamma: float) -> np.ndarray:
    """``values`` scaled to a max of 1 and raised to ``gamma``, as a normalised vector.

    The scaling is there only so ``v ** 24`` cannot overflow on raw market values; normalising
    afterwards makes it exactly scale-invariant, so ``gamma == 1.0`` returns ``v / sum(v)``
    bit-for-bit as the chassis computes it.
    """
    v = np.asarray(values, dtype=np.float64)
    if len(v) == 0:
        return v
    top = float(v.max())
    if not np.isfinite(top) or top <= 0.0:
        return np.full(len(v), 1.0 / len(v))
    v = np.power(v / top, float(gamma))
    s = float(v.sum())
    if not np.isfinite(s) or s <= 0.0:
        return np.full(len(v), 1.0 / len(v))
    return v / s


def _capped(values: list[float], gamma: float, cap: float | None, *,
            exposure: float = 1.0, floor_to_equal: bool = True) -> np.ndarray:
    """``_powered``, scaled to ``exposure``, with the chassis's own ceiling applied.

    ``floor_to_equal`` is the one place the two chassis genuinely differ, and it is not a choice
    made here: ``m0221.weights`` caps at ``max(cap, 1/len)`` and ``m0201.sized_weights`` caps at
    ``cap`` flat, and each rule below passes the flag its own chassis uses. ``exposure`` is scaled
    in BEFORE the ceiling for the same reason -- ``sized_weights`` does, and the cap is an
    absolute share of the account, not a share of the invested part. At ``gamma == 1.0`` this
    returns exactly what that chassis's own function returns, which ``selfcheck`` asserts on two
    hundred random vectors.
    """
    w = _powered(values, gamma) * float(exposure)
    if cap is None or len(w) == 0:
        return w
    c = float(cap)
    if floor_to_equal:
        c = max(c, float(exposure) / len(w))
    return _apply_ceiling(w, c)


def fitted_gamma(values: list[float], cap: float | None, target_hhi: float, *,
                 exposure: float = 1.0, floor_to_equal: bool = True) -> float:
    """The exponent whose capped vector, NORMALISED, has Herfindahl index ``target_hhi``.

    Bisection on [GAMMA_MIN, GAMMA_MAX]. The index is non-decreasing in the exponent -- raising a
    normalised vector to a higher power moves mass to its largest entries, and the ceiling only
    flattens the result from above -- so bisection is well posed. The range straddles 1.0 because
    the control's own values can be either flatter or sharper than the real book's: on M0221 the
    probe measured them SHARPER every month, so a one-sided range would silently return 1.0 and
    rule C would be the shipped control under another name. The index is taken on the normalised
    vector so that it compares like with like whatever ``exposure`` is.
    """
    if len(values) < 2:
        return 1.0

    def hhi_at(g: float) -> float:
        w = np.asarray(_capped(values, g, cap, exposure=exposure, floor_to_equal=floor_to_equal))
        s = float(w.sum())
        return _hhi(w / s) if s > 0.0 else 0.0

    lo, hi = GAMMA_MIN, GAMMA_MAX
    if hhi_at(lo) >= target_hhi:
        return lo
    if hhi_at(hi) <= target_hhi:
        return hi
    for _ in range(GAMMA_STEPS):
        mid = 0.5 * (lo + hi)
        if hhi_at(mid) < target_hhi:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------- M0221 prototypes


class _CapWeightRule(m0221.MatchedCapTopAllocator):
    """``M0221-A1`` with the weight step replaced by ``_assign`` and nothing else touched.

    The sized pool, the two selections, the ``control_draw.matched_names`` call, its tag, its
    seed and its month-keyed return order are the shipped allocator's. So every subclass below
    holds the identical names in the identical months as ``M0221-C50-PLC`` and differs from it
    only in which weight each drawn name is given -- which is the whole experiment.
    """

    id = "PROTO"

    def _assign(self, picks: list[str], pool: dict[str, float], real_now: list[str],
                held: AbstractSet[str], data_date: date, p: Any) -> list[float]:
        raise NotImplementedError

    def _base(self, picks: list[str], pool: dict[str, float], p: Any) -> float:
        """The shipped control's own weight sum on these names: the exposure every rule keeps."""
        w = m0221.weights([pool[s] for s in picks], p)
        return float(sum(0.0 if x is None else float(x) for x in w))

    def _rungs(self, picks: list[str], pool: dict[str, float], p: Any) -> list[float]:
        """The real arm's own weight vector this month, biggest rung first.

        The real arm is the top ``p.top`` of the sized pool by market value and ``m0221.weights``
        is the chassis's own weighting code, so this is the vector the book actually holds. The
        NAMES are dropped here and never reach the control: only the numbers cross.
        """
        order = sorted(pool, key=lambda s: (-pool[s], s))[: p.top]
        w = m0221.weights([pool[s] for s in order], p)
        v = sorted((0.0 if x is None else float(x) for x in w), reverse=True)
        return _rescale(v, len(picks), self._base(picks, pool, p))

    def _matched(self, prepared: Any, members: AbstractSet[str], data_date: date,
                 held: frozenset[str], p: Any) -> tuple[Any, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, m0221._gate(p)):
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
            tag=m0221.DRAW_KEY,
            seed=p.seed,
            data_date=data_date,
        )
        if not picks:
            return ()
        ws = self._assign(list(picks), pool, list(now), held, data_date, p)
        out = []
        for s, x in zip(picks, ws, strict=True):
            w = _floor_weight(float(x))
            if w is None:
                continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)


class CapRuleA(_CapWeightRule):
    """A: the real book's sorted vector straight down ``matched_names``' own return order.

    That order is keyed on the calendar month (``control_draw.entry_key``), so it re-shuffles at
    every decision and every name is expected to be handed a different rung every month. This is
    the literal reading of the sentence leftover 2 was written in -- "the k-th drawn name takes
    the k-th largest weight the real book holds that month" -- and it is in the sweep because the
    brief asks for it, not because it is expected to win.
    """

    id = "PROTO-M0221-WA"

    def _assign(self, picks, pool, real_now, held, data_date, p):
        return self._rungs(picks, pool, p)


class CapRuleB(_CapWeightRule):
    """B: the same vector down the DATE-FREE keep order (``control_draw.keep_key``).

    ``keep_key`` carries no date term, so a name's position among the control's holdings is the
    same at every decision it survives: a held name keeps its rung, and moves only when a name
    ordered above it leaves. An entrant takes whatever rung its own hash puts it on, which is on
    average the middle of the vector.
    """

    id = "PROTO-M0221-WB"

    def _assign(self, picks, pool, real_now, held, data_date, p):
        order = sorted(picks, key=lambda s: (control_draw.keep_key(m0221.DRAW_KEY, p.seed, s), s))
        by = dict(zip(order, self._rungs(order, pool, p), strict=True))
        return [by[s] for s in picks]


class CapRuleC(_CapWeightRule):
    """C: the control's OWN market values, re-shaped to the real book's concentration.

    The shipped control already weights by its drawn names' own market values, which is what makes
    it drift-neutral: a name's target share is its own market-value share, which moves with its own
    price, so the realised weight tracks the target and the 1%-of-equity band rarely fires. This
    rule keeps that property -- every weight stays a monotone function of that name's OWN size --
    and changes only how steep the function is, by raising each value to an exponent fitted that
    month so the resulting capped vector has the same Herfindahl index as the real book's.

    It reads ONE number off the real arm where A, B and D read fifty. Both are shape and neither
    is identity, which is the standard the entry count ``e`` already passes; C simply reads less.
    """

    id = "PROTO-M0221-WC"

    def _assign(self, picks, pool, real_now, held, data_date, p):
        rungs = self._rungs(picks, pool, p)
        total = float(sum(rungs))
        if total <= 0.0:
            return [0.0] * len(picks)
        target = _hhi([x / total for x in rungs])
        values = [pool[s] for s in picks]
        g = fitted_gamma(values, p.cap, target, exposure=total)
        return [float(x) for x in _capped(values, g, p.cap, exposure=total)]


class CapRuleD(_CapWeightRule):
    """D: keeps first in the keep order, this month's entrants last, down the sorted vector.

    Designed from the mechanism and pre-registered before the sweep: on a cap-weighted top-N the
    name that ENTERS is the new number ``top``, so it enters at the smallest weight in the book,
    and the name that left, left from there too. Under the shipped control and under rules A and B
    a blind entrant takes an average rung instead -- about 1/top of the account against the real
    book's rank-``top`` weight -- and an entry trade three or four times too large, taken 371
    times, is the whole excess. This rule reproduces WHERE the churn happens as well as how much
    of it there is.

    ``held`` is the only thing an allocator knows about its own past and it is enough: the
    entrants are ``picks - held`` by definition, at no cost and with no state. Nothing here is
    carried between calls, so the rule is a pure function of the date it is given (invariant I9).
    """

    id = "PROTO-M0221-WD"

    def _assign(self, picks, pool, real_now, held, data_date, p):
        keeps = sorted(
            (s for s in picks if s in held),
            key=lambda s: (control_draw.keep_key(m0221.DRAW_KEY, p.seed, s), s),
        )
        fresh = sorted(
            (s for s in picks if s not in held),
            key=lambda s: (control_draw.entry_key(m0221.DRAW_KEY, p.seed, s, data_date), s),
        )
        order = keeps + fresh
        by = dict(zip(order, self._rungs(order, pool, p), strict=True))
        return [by[s] for s in picks]


CAP_A, CAP_B, CAP_C, CAP_D = CapRuleA(), CapRuleB(), CapRuleC(), CapRuleD()


# --------------------------------------------------------------------------- M0201 prototypes

#: One prepared value per Market for every M0201 PROTOTYPE arm. ``dev.run_registry`` caches
#: ``prepare_for`` per ALLOCATOR ID, and this sweep runs four prototype ids on a chassis whose
#: ``prepare_market`` builds M0197's whole factor panel, so without this the sweep would build
#: that panel four times. It is a memo about DATA, keyed on the market object's identity; nothing
#: in it depends on a date, a candidate or a fold, so it is not the mutable allocator state the
#: lab forbids. The two SHIPPED baselines are deliberately left on their own singletons and build
#: their own, so the baseline rows come off the shipped code path untouched.
_PANEL: dict[int, Any] = {}


def _shared_panel(market: Any) -> Any:
    key = id(market)
    got = _PANEL.get(key)
    if got is None:
        got = m0201.SIZEDYB.prepare_market(market)
        _PANEL[key] = got
    return got


class _SizedWeightRule(m0201.MatchedSizedPlaceboAllocator):
    """``M0201-A1`` with ``resize``'s weighting replaced by ``_company_weights``.

    Everything that decides WHICH names the control holds is the shipped allocator's, unchanged:
    ``matched_frac``, ``matched_entries``, the 40% keep band, the quarterly calendar and
    ``m0197.choose``. The re-sizing step is re-implemented here line for line from
    ``m0201.resize`` -- the company collapse, the split of a company's weight over its held
    classes, the SPY filler and the exposure -- with one substitution: where ``resize`` calls
    ``m0201.sized_weights``, this calls ``_company_weights``.
    """

    id = "PROTO-SIZED"

    def prepare_market(self, market: Any) -> Any:
        return _shared_panel(market)

    def _company_weights(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: AbstractSet[str], keys: list[str], size: dict[str, float],
                         exposure: float, p: Any) -> list[Decimal | None]:
        raise NotImplementedError

    def _base(self, keys: list[str], size: dict[str, float], exposure: float,
              p: Any) -> float:
        """The shipped control's own company-weight sum: the exposure every rule keeps."""
        cw = m0201.sized_weights([size[k] for k in keys], exposure, float(p.cap))
        return float(sum(0.0 if x is None else float(x) for x in cw))

    def _rungs(self, prepared: Any, members: AbstractSet[str], data_date: date,
               keys: list[str], size: dict[str, float], exposure: float,
               p: Any) -> list[float]:
        """The bond book's own company-weight vector this month, biggest rung first.

        A FRESH top-20 of M0197's bond ranking stands in for the real held book, sized by the
        chassis's own ``sizes`` and ``sized_weights``. That stand-in carries exactly the freshness
        approximation this chassis's entry count already carries -- ``matched_entries`` derives
        ``e`` from a fresh re-pick too, and the walk measured it at 0.955 of the real entries --
        so the weight axis inherits the same bias the trade axis already has, and phase 5 inherits
        it with the rule if it builds one. Only numbers cross; the names are dropped here.
        """
        base = self._base(keys, size, exposure, p)
        now = m0201.real_frac_at(prepared, members, data_date, p)
        if not now:
            return _rescale([], len(keys), base)
        book = [s for _, s in sorted((v, s) for s, v in now.items())][: p.yb.inner.top]
        rsize = m0201.sizes(prepared, book, data_date, p)
        rkeys = list(rsize)
        cw = m0201.sized_weights(
            [rsize[k] for k in rkeys], len(book) / p.yb.inner.top, float(p.cap)
        )
        v = sorted((0.0 if x is None else float(x) for x in cw), reverse=True)
        return _rescale(v, len(keys), base)

    def _held_company(self, held: AbstractSet[str], keys: list[str]) -> set[str]:
        """The company keys the control already holds through any of their listed classes."""
        return {m0201.company(s) for s in held} & set(keys)

    def _resize(self, prepared: Any, members: AbstractSet[str], equal: tuple[Any, ...],
                data_date: date, held: AbstractSet[str], p: Any) -> tuple[Any, ...]:
        market = p.yb.market
        picks = [t.symbol for t in equal if t.symbol != market]
        if not picks:
            return tuple(equal)
        size = m0201.sizes(prepared, picks, data_date, p)
        keys = list(size)
        exposure = len(picks) / p.yb.inner.top
        cw = self._company_weights(prepared, members, data_date, held, keys, size, exposure, p)
        weight = dict(zip(keys, cw, strict=True))
        out = []
        for s in picks:
            w = weight[m0201.company(s)]
            if w is None:
                continue
            n = sum(1 for x in picks if m0201.company(x) == m0201.company(s))
            if n > 1:
                w = _floor_weight(float(w) / n)
                if w is None:
                    continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        rest = Decimal(1) - sum((t.weight for t in out), Decimal(0))
        mh = prepared.history.get(market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
        return tuple(out)

    def _run(self, prepared: Any, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: Any) -> tuple[Any, ...]:
        p = m0201._check_control(p)
        if len(prepared.series) == 0 or prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, p.yb.inner):
            return ()
        stocks = [s for s in held if s != p.yb.market and s not in m0201.EXCLUDED]
        repick = not stocks or data_date.month in m0201.REPICK_MONTHS
        frac = m0201.matched_frac(prepared, members, data_date, held, p) if repick else {}
        equal = m0201.choose(prepared.history, members, frac, data_date, held, p.yb)
        return self._resize(prepared, members, equal, data_date, held, p)


class SizedRuleA(_SizedWeightRule):
    """A on M0201: the bond book's sorted vector down the month-keyed entry order."""

    id = "PROTO-M0201-WA"

    def _company_weights(self, prepared, members, data_date, held, keys, size, exposure, p):
        order = sorted(keys, key=lambda k: (control_draw.entry_key("M0201", p.seed, k, data_date), k))
        rungs = self._rungs(prepared, members, data_date, order, size, exposure, p)
        by = dict(zip(order, rungs, strict=True))
        return [_floor_weight(by[k]) for k in keys]


class SizedRuleB(_SizedWeightRule):
    """B on M0201: the same vector down the date-free keep order."""

    id = "PROTO-M0201-WB"

    def _company_weights(self, prepared, members, data_date, held, keys, size, exposure, p):
        order = sorted(keys, key=lambda k: (control_draw.keep_key("M0201", p.seed, k), k))
        rungs = self._rungs(prepared, members, data_date, order, size, exposure, p)
        by = dict(zip(order, rungs, strict=True))
        return [_floor_weight(by[k]) for k in keys]


class SizedRuleC(_SizedWeightRule):
    """C on M0201: the control's own company sizes, re-shaped to the bond book's concentration.

    ``m0201.sized_weights``' own steps in its own order -- the median fill for an unknown size,
    the scaling to ``exposure``, then the ceiling -- with the sizes raised to a fitted exponent
    first. At exponent 1.0 this is ``sized_weights`` exactly, which ``selfcheck`` asserts.
    """

    id = "PROTO-M0201-WC"

    def _company_weights(self, prepared, members, data_date, held, keys, size, exposure, p):
        rungs = self._rungs(prepared, members, data_date, keys, size, exposure, p)
        total = float(sum(rungs))
        if total <= 0.0:
            return [None] * len(keys)
        target = _hhi([x / total for x in rungs])
        raw = [size[k] for k in keys]
        known = [x for x in raw if x > 0.0]
        med = float(np.median(known)) if known else 1.0
        filled = [x if x > 0.0 else med for x in raw]
        g = fitted_gamma(filled, float(p.cap), target, exposure=total, floor_to_equal=False)
        w = _capped(filled, g, float(p.cap), exposure=total, floor_to_equal=False)
        return [_floor_weight(float(x)) for x in w]


class SizedRuleD(_SizedWeightRule):
    """D on M0201: kept companies first in the keep order, entrants last, down the vector."""

    id = "PROTO-M0201-WD"

    def _company_weights(self, prepared, members, data_date, held, keys, size, exposure, p):
        mine = self._held_company(held, keys)
        keeps = sorted((k for k in keys if k in mine),
                       key=lambda k: (control_draw.keep_key("M0201", p.seed, k), k))
        fresh = sorted((k for k in keys if k not in mine),
                       key=lambda k: (control_draw.entry_key("M0201", p.seed, k, data_date), k))
        order = keeps + fresh
        rungs = self._rungs(prepared, members, data_date, order, size, exposure, p)
        by = dict(zip(order, rungs, strict=True))
        return [_floor_weight(by[k]) for k in keys]


SIZED_A, SIZED_B, SIZED_C, SIZED_D = SizedRuleA(), SizedRuleB(), SizedRuleC(), SizedRuleD()


# --------------------------------------------------------------------------- the registries

CAP_CTL = m0221.CapTopParams(50, pick="random", seed=1, trend=None)
CAP_BOOK = m0221.CapTopParams(50, trend=None)
SIZED_CTL = m0201._p("placebo", seed=1)
SIZED_BOOK = m0201._p("bond")


def _c(cid: str, family: str, allocator: Any, params: Any, why: str) -> Candidate:
    return Candidate(id=cid, family=family, rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=why,
                     added=date(2026, 10, 20), owner_inputs=())


def registry_m0221() -> list[Candidate]:
    """The book, the shipped control, and the four rules -- in that order, one sweep.

    Every id carries a PROTO- prefix. Nothing here is recorded and nothing here is a lab arm; the
    prefix is so a reader of the results file can never mistake a row for a recorded trial.
    """
    return [
        _c("PROTO-M0221-C50", "M0221", m0221.CAPTOP, CAP_BOOK,
           "Baseline: the book, re-run on today's store"),
        _c("PROTO-M0221-PLC", "M0221", m0221.MATCHED, CAP_CTL,
           "Baseline: the shipped matched draw, re-run on today's store"),
        _c("PROTO-M0221-WA", "M0221", CAP_A, CAP_CTL,
           "Rule A: the real vector down the month-keyed order"),
        _c("PROTO-M0221-WB", "M0221", CAP_B, CAP_CTL,
           "Rule B: the real vector down the date-free keep order"),
        _c("PROTO-M0221-WC", "M0221", CAP_C, CAP_CTL,
           "Rule C: the control's own values re-shaped to the real concentration"),
        _c("PROTO-M0221-WD", "M0221", CAP_D, CAP_CTL,
           "Rule D: keeps in keep order, entrants last, down the real vector"),
    ]


def registry_m0201() -> list[Candidate]:
    """The bond book, the shipped seed-1 control, and the four rules, in that order.

    The two baselines run FIRST and on the shipped singletons, so ``run_registry`` frees their
    factor panels before the four prototypes share one through ``_shared_panel``.
    """
    return [
        _c("PROTO-M0201-BOOK", "M0201", m0201.SIZEDYB, SIZED_BOOK,
           "Baseline: the bond book, re-run on today's store"),
        _c("PROTO-M0201-PLC1", "M0201", m0201.MATCHED, SIZED_CTL,
           "Baseline: the shipped matched draw, seed 1, re-run on today's store"),
        _c("PROTO-M0201-WA", "M0201", SIZED_A, SIZED_CTL,
           "Rule A: the bond vector down the month-keyed order"),
        _c("PROTO-M0201-WB", "M0201", SIZED_B, SIZED_CTL,
           "Rule B: the bond vector down the date-free keep order"),
        _c("PROTO-M0201-WC", "M0201", SIZED_C, SIZED_CTL,
           "Rule C: the control's own company sizes re-shaped to the bond concentration"),
        _c("PROTO-M0201-WD", "M0201", SIZED_D, SIZED_CTL,
           "Rule D: kept companies in keep order, entrants last, down the bond vector"),
    ]


REGISTRIES = {"m0221": registry_m0221, "m0201": registry_m0201}


# --------------------------------------------------------------------------- self-check


def cmd_selfcheck(_args: argparse.Namespace) -> int:
    """Assert the shaping machinery is the chassis's own code at exponent 1, and that the four
    M0221 rules hand out the same total exposure as the shipped control.

    No store, no market, no database: pure arithmetic, under a second. If this is red the sweep
    is measuring something other than the rules it claims to.
    """
    rng = np.random.default_rng(20261020)
    bad = 0
    # The chassis's own functions quantise DOWN to ``sim.book.WEIGHT_QUANTUM`` (1e-6) and return
    # None below it; these helpers do not quantise at all, because the caller floors afterwards.
    # So the tolerance is the quantum, not float noise, and a None is compared as 0.0.
    tol = dict(rtol=1e-6, atol=2e-6)
    for _ in range(200):
        n = int(rng.integers(10, 60))  # CapTopParams needs cap >= 1/top, and cap is 0.10
        values = [float(x) for x in rng.lognormal(mean=10.0, sigma=2.0, size=n)]
        p = m0221.CapTopParams(n, pick="random", seed=1, trend=None)
        want = [0.0 if x is None else float(x) for x in m0221.weights(values, p)]
        got = [float(x) for x in _capped(values, 1.0, p.cap)]
        if not np.allclose(want, got, **tol):
            bad += 1
            print(f"FAIL cap: n={n} max|d|={max(abs(a - b) for a, b in zip(want, got)):.3e}")
        exposure = float(rng.uniform(0.3, 1.0))
        wl = [0.0 if x is None else float(x)
              for x in m0201.sized_weights(values, exposure, 0.10)]
        gl = [float(x) for x in
              _capped(values, 1.0, 0.10, exposure=exposure, floor_to_equal=False)]
        if not np.allclose(wl, gl, **tol):
            bad += 1
            print(f"FAIL sized: n={n} max|d|={max(abs(a - b) for a, b in zip(wl, gl)):.3e}")
        v = sorted((float(x) for x in rng.random(n)), reverse=True)
        r = _rescale(list(v), n, 0.97)
        if abs(sum(r) - 0.97) > 1e-9:
            bad += 1
            print(f"FAIL rescale: n={n} sum={sum(r)}")
    print("selfcheck: OK" if bad == 0 else f"selfcheck: {bad} FAILURES")
    return 0 if bad == 0 else 1


# --------------------------------------------------------------------------- the free probe


def decision_dates() -> list[date]:
    return [
        dates.prev_session(s)
        for s in dates.sessions(MEMBERSHIP_START, DEV_END)
        if is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, s)
    ]


def _targets_of(market: Any, allocator: Any, params: Any, prepared: Any, d: date,
                held: frozenset[str]) -> dict[str, float]:
    members = market.membership.members_on(d)
    ts = allocator.targets_prepared(prepared, members, d, held, params)
    return {t.symbol: float(t.weight) for t in ts}


def _closes(market: Any, symbols, d: date) -> dict[str, float]:
    out = {}
    for s in symbols:
        c = last_close(market.history.get(s), d)
        if c is not None and np.isfinite(c) and c > 0.0:
            out[s] = float(c)
    return out


def probe_arm(market: Any, allocator: Any, params: Any, prepared: Any, label: str) -> dict:
    """A free, backtest-free estimate of annual turnover, plus the entrant's mean weight.

    At each monthly decision the previous decision's weights are drifted forward by their own
    price moves and compared with today's weights; the L1 distance is the fraction of the book
    the decision asks to trade. Summed over the window and divided by the years, that is an
    UPPER BOUND on ``trials.turnover`` -- the 1%-of-equity band suppresses small moves this
    counts, and deposits buy shares this does not. It is triage and ordering only: the recorded
    answer is the sweep, and the results file says so.

    ``entry_w`` is the mechanism headline: the mean weight handed to a name on the decision it
    enters the book.
    """
    prev_w: dict[str, float] = {}
    prev_c: dict[str, float] = {}
    l1 = 0.0
    entry_w: list[float] = []
    entries = 0
    months = 0
    held: frozenset[str] = frozenset()
    ds = decision_dates()
    for d in ds:
        now = _targets_of(market, allocator, params, prepared, d, held)
        if not now:
            held = frozenset()
            prev_w, prev_c = {}, {}
            continue
        cnow = _closes(market, set(now) | set(prev_w), d)
        drifted: dict[str, float] = {}
        if prev_w:
            grown = {}
            for s, w in prev_w.items():
                a, b = prev_c.get(s), cnow.get(s)
                grown[s] = w * (b / a) if (a and b) else w
            tot = sum(grown.values())
            scale = (sum(prev_w.values()) / tot) if tot > 0 else 1.0
            drifted = {s: v * scale for s, v in grown.items()}
        for s in set(now) | set(drifted):
            l1 += abs(now.get(s, 0.0) - drifted.get(s, 0.0))
        fresh = [s for s in now if s not in held]
        entries += len(fresh)
        entry_w.extend(now[s] for s in fresh)
        held = frozenset(now)
        prev_w = dict(now)
        prev_c = {s: cnow[s] for s in now if s in cnow}
        months += 1
    years = (ds[-1] - ds[0]).days / 365.25 if len(ds) > 1 else 1.0
    out = {
        "label": label,
        "months": months,
        "entries": entries,
        "entry_w": float(np.mean(entry_w)) if entry_w else 0.0,
        "l1_per_year": l1 / years,
    }
    print(f"{label:22s} months {out['months']:3d}  entries {out['entries']:4d}  "
          f"mean entrant weight {out['entry_w']:.4f}  predicted turnover {out['l1_per_year']:.4f}")
    return out


def cmd_probe(args: argparse.Namespace) -> int:
    data = research.load_store(STORE)
    market = data.market
    rows = []
    if args.chassis in ("m0221", "both"):
        prep = m0221.CAPTOP.prepare_market(market)
        rows.append(probe_arm(market, m0221.CAPTOP, CAP_BOOK, prep, "M0221-C50 book"))
        rows.append(probe_arm(market, m0221.MATCHED, CAP_CTL, prep, "M0221 shipped control"))
        for a, name in ((CAP_A, "M0221 rule A"), (CAP_B, "M0221 rule B"),
                        (CAP_C, "M0221 rule C"), (CAP_D, "M0221 rule D")):
            rows.append(probe_arm(market, a, CAP_CTL, prep, name))
    if args.chassis in ("m0201", "both"):
        prep = _shared_panel(market)
        rows.append(probe_arm(market, m0201.SIZEDYB, SIZED_BOOK, prep, "M0201 bond book"))
        rows.append(probe_arm(market, m0201.MATCHED, SIZED_CTL, prep, "M0201 shipped control"))
        for a, name in ((SIZED_A, "M0201 rule A"), (SIZED_B, "M0201 rule B"),
                        (SIZED_C, "M0201 rule C"), (SIZED_D, "M0201 rule D")):
            rows.append(probe_arm(market, a, SIZED_CTL, prep, name))
    Path(args.out).write_text(json.dumps(rows, indent=2) + "\n")
    print(f"wrote {args.out}")
    return 0


# --------------------------------------------------------------------------- the sweep


def cmd_sweep(args: argparse.Namespace) -> int:
    """One ``dev.run_registry`` call over one chassis's six arms, funded as the trials were.

    ``contributions=OWNER_MONTHLY`` and ``initial_idr=INITIAL_IDR`` are passed EXPLICITLY, as
    ``lab.runner.run_method`` passes them and as ``trial_funding`` and ``trial_provenance`` record
    them for every arm in play (10,000,000 IDR, +5,000,000 on the 25th, 237 deposits). A later
    change to ``INITIAL_IDR`` therefore cannot silently re-point this measurement.

    Every row is appended to the JSONL as it finishes, so a kill loses only the arms that had not
    run and the file is still the record of the ones that had.
    """
    data = research.load_store(STORE)
    out = Path(args.out)
    out.write_text("")
    candidates = REGISTRIES[args.chassis]()

    def on_result(i: int, _result: Any, row: Any) -> None:
        rec = {
            "id": row.candidate.id,
            "allocator": row.candidate.allocator.id,
            "start": row.start.isoformat(),
            "end": row.end.isoformat(),
            "trades": int(row.stats.metrics.trades),
            "turnover": float(row.stats.turnover),
            "exposure": float(row.stats.exposure),
            "costs_usd": float(row.stats.costs_usd),
            "mwr": None if row.stats.metrics.mwr is None else float(row.stats.metrics.mwr),
            "spy_tr_mwr": None if row.spy_tr.mwr is None else float(row.spy_tr.mwr),
            "max_drawdown": None if row.stats.metrics.max_drawdown is None
                            else float(row.stats.metrics.max_drawdown),
        }
        with out.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"[{i + 1}/{len(candidates)}] {rec['id']:20s} trades {rec['trades']:4d}  "
              f"turnover {rec['turnover']:.4f}", flush=True)

    run_registry(
        data.market,
        data.dividends,
        data.spy_dividends,
        candidates,
        on_result=on_result,
        contributions=OWNER_MONTHLY,
        initial_idr=INITIAL_IDR,
    )
    print(f"wrote {out}")
    return 0


# --------------------------------------------------------------------------- the report


WARN_LO, WARN_HI = 0.80, 1.25


def cmd_report(args: argparse.Namespace) -> int:
    """The markdown table phase-4-results.md carries, built from a sweep's JSONL.

    The first row of the file is the BOOK and every ratio is taken against it, inside the same
    sweep -- re-run against re-run (invariant I8). Recorded columns are never mixed in here.
    """
    rows = [json.loads(line) for line in Path(args.jsonl).read_text().splitlines() if line.strip()]
    if not rows:
        print("no rows", file=sys.stderr)
        return 1
    book = rows[0]
    print(f"book: {book['id']}  {book['trades']} trades / {book['turnover']:.4f} turnover")
    print()
    print("| arm | trades | turnover | trades x | turnover x | verdict |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        tx = r["trades"] / book["trades"] if book["trades"] else float("nan")
        ux = r["turnover"] / book["turnover"] if book["turnover"] else float("nan")
        ok = WARN_LO <= tx <= WARN_HI and WARN_LO <= ux <= WARN_HI
        miss = []
        if not WARN_LO <= tx <= WARN_HI:
            miss.append("trades")
        if not WARN_LO <= ux <= WARN_HI:
            miss.append("turnover")
        verdict = "**OK**" if ok else "miss: " + "+".join(miss)
        if r is book:
            verdict = "— the book —"
        print(f"| `{r['id']}` | {r['trades']} | {r['turnover']:.4f} | {tx:.3f} | {ux:.3f} | {verdict} |")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("selfcheck", help="assert the shaping is the chassis's own code at gamma 1")
    s.set_defaults(fn=cmd_selfcheck)
    s = sub.add_parser("probe", help="free L1 triage, no backtest")
    s.add_argument("--chassis", choices=("m0221", "m0201", "both"), required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_probe)
    s = sub.add_parser("sweep", help="one dev.run_registry sweep over one chassis")
    s.add_argument("--chassis", choices=("m0221", "m0201"), required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_sweep)
    s = sub.add_parser("report", help="the markdown ratio table from a sweep's JSONL")
    s.add_argument("--jsonl", required=True)
    s.set_defaults(fn=cmd_report)
    args = ap.parse_args()
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
