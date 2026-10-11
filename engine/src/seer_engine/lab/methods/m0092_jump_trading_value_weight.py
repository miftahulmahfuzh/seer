"""M0092 — News-day picks sized toward the giants: the filtered earnings-day book by trading value.

Source: variation of M0072-Z2-RAWRANK (the earnings-day drift of Brandt, Kishore, Santa-Clara &
Venkatachalam 2008, SSRN 909563, with M0072's own-swing filter).
Idea: M0072-Z2-RAWRANK beat SPY on dev and in 2009-2015 and cleared the luck bar, and failed only
the worst fall: 22.4% with the deposits taken out, in 1998. About 10 of those points were the
picks lagging SPY from April to August 1998 while fully invested -- a narrow market led by the
giants, in which 20 equal 5% slots of mostly mid-sized members sank. So keep the picks exactly
and change only how much money each pick gets: lean the book toward the big, heavily traded
names, the shape SPY itself has.

The store has no shares outstanding before 2009 (M0047 is blocked on it), so company size is read
through its point-in-time stand-in: a name's *trading value*, the median of close x volume over
the ``dv_base`` sessions ending on the data date. A median, because the news day itself trades
three or more times normal volume, and a mean over a window that holds it would rank a name by
its own event.

Selection is M0072's, unchanged: the live events that pass Z2's filter (volume >= 3x, up gap,
raw jump >= 4 points, jump >= 2 own daily swings), held names first, then by the raw jump, up to
20 names. Then, per ``weight``:

    * ``"equal"``  each pick 1/20, as M0072;
    * ``"dv"``     the picks share a budget of n/20 (the same money the 20-slot book gives n
                   picks) in proportion to trading value, each capped at ``cap``; weight a cap
                   cuts off is spread over the uncapped picks in the same proportions, repeated
                   until nothing exceeds the cap;
    * ``"sqrt"``   the same, in proportion to the square root of trading value (a half-way lean).

``universe_top`` (None = off) first narrows the screened members to the ``universe_top`` with
the highest trading value on the data date, so ``TOP100-EW`` asks whether the edge survives
inside the giants alone rather than whether bigger slots help. Whatever the picks leave goes to
SPY, behind the same monthly SPY-200 switch, on the same real-fee fractional preset.

Trading value at bar i reads bars i-dv_base+1..i; every event column reads as in M0072, so
nothing dated after the data date is read and the prepared and unprepared paths agree.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0072_standardised_earnings_jump import (
    JUMP20,
    StandardisedJumpAllocator,
    ZParams,
    ZPrepared,
    live_event,
)
from seer_engine.sim.book import Target, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 10, 11)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class SizeParams:
    """``z`` is M0072's event, filter, ranking and book; the rest sizes and narrows the picks."""

    z: ZParams
    weight: str = "dv"  # "equal", "dv" (trading value) or "sqrt" (its square root)
    cap: Decimal = Decimal("0.10")  # most one pick may hold
    dv_base: int = 60  # sessions in the trading-value median, ending on the data date
    universe_top: int | None = None  # keep only the most-traded N screened members (None = all)

    def __post_init__(self) -> None:
        if not isinstance(self.z, ZParams):
            raise TypeError(f"z must be ZParams, got {type(self.z).__name__}")
        if self.weight not in ("equal", "dv", "sqrt"):
            raise ValueError(f"weight must be 'equal', 'dv' or 'sqrt', got {self.weight!r}")
        top = self.z.jump.inner.top
        if not isinstance(self.cap, Decimal) or not self.cap.is_finite() or not (
            Decimal(1) / top <= self.cap <= 1
        ):
            raise ValueError(f"cap must be a Decimal in [1/top, 1], got {self.cap!r}")
        if isinstance(self.dv_base, bool) or not isinstance(self.dv_base, int) or self.dv_base < 5:
            raise ValueError(f"dv_base must be an int >= 5, got {self.dv_base!r}")
        u = self.universe_top
        if u is not None and (isinstance(u, bool) or not isinstance(u, int) or u < top):
            raise ValueError(f"universe_top must be None or an int >= top, got {u!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "weight": self.weight,
            "cap": str(self.cap),
            "dv_base": str(self.dv_base),
            "universe_top": "none" if self.universe_top is None else str(self.universe_top),
        }
        for k, v in self.z.as_dict().items():
            out[f"z.{k}"] = v
        return out


def _check(params: object) -> SizeParams:
    if not isinstance(params, SizeParams):
        raise TypeError(f"params must be SizeParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- sizing


def trading_value(h: History, i: int, dv_base: int) -> float | None:
    """Median close x volume over bars i-dv_base+1..i; None when short or not positive."""
    if i < dv_base - 1:
        return None
    lo = i - dv_base + 1
    v = np.median(h.close[lo : i + 1] * h.volume[lo : i + 1])
    return float(v) if np.isfinite(v) and v > 0 else None


def capped_shares(scores: list[float], budget: float, cap: float) -> list[float]:
    """Split ``budget`` in proportion to ``scores``, no share above ``cap``; excess re-spread.

    ``budget <= cap * len(scores)`` always holds here (budget is n/top and cap >= 1/top), so the
    loop ends with the whole budget placed.
    """
    n = len(scores)
    out = [0.0] * n
    free = list(range(n))
    left = budget
    while free:
        total = sum(scores[k] for k in free)
        if total <= 0:
            for k in free:
                out[k] = left / len(free)
            break
        over = [k for k in free if left * scores[k] / total > cap]
        if not over:
            for k in free:
                out[k] = left * scores[k] / total
            break
        for k in over:
            out[k] = cap
            left -= cap
        free = [k for k in free if k not in over]
    return out


# --------------------------------------------------------------------------- the allocator


class SizedJumpAllocator(StandardisedJumpAllocator):
    """M0072's filtered news-day picks, sized by trading value (or within the most-traded names)."""

    id = "M0092"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(super().lookback(p.z), p.dv_base + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return super().symbols(_check(params).z)

    def holds(self, params: Any) -> tuple[str, ...]:
        return super().holds(_check(params).z)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, prepared: ZPrepared, rows: list[Any], data_date: date,
                 held: frozenset[str], params: Any) -> tuple[Target, ...]:
        sp = _check(params)
        p = sp.z
        jp = p.jump
        tv: dict[str, float] = {}
        for r in rows:
            h = prepared.history.get(r.symbol)
            if h is None or r.symbol == jp.market:
                continue
            i = h.index_of(data_date)
            if i is None:
                continue
            v = trading_value(h, i, sp.dv_base)
            if v is not None:
                tv[r.symbol] = v
        if sp.universe_top is not None:
            keep = {s for _, s in sorted((-v, s) for s, v in tv.items())[: sp.universe_top]}
        else:
            keep = set(tv)
        live: list[tuple[int, float, str]] = []
        for s in sorted(keep):
            h = prepared.history[s]
            i = h.index_of(data_date)
            got = prepared.cols(s, jp.market, jp.vol_base, p.sd_base)
            if i is None or got is None:
                continue
            ev = live_event(got[0], got[1], i, p)
            if ev is None:
                continue
            score = ev[0] if p.rank == "z" else ev[1]
            live.append((0 if s in held else 1, -score, s))
        picks = [s for _, _, s in sorted(live)[: jp.inner.top]]
        slot = equal_weight(jp.inner.top)
        if sp.weight == "equal" or not picks:
            weights = [slot] * len(picks)
        else:
            raw = [tv[s] if sp.weight == "dv" else tv[s] ** 0.5 for s in picks]
            shares = capped_shares(raw, float(slot) * len(picks), float(sp.cap))
            weights = [to_weight(x) if x > 0 else None for x in shares]
        out: list[Target] = []
        for s, w in zip(picks, weights):
            if w is None:
                continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        if jp.park:
            rest = Decimal(1) - sum((t.weight for t in out), Decimal(0))
            mh = prepared.history.get(jp.market)
            if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
                t = target_from_close(jp.market, last_close(mh, data_date), rest)
                if t is not None:
                    out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        sp = _check(params)
        if not trend_on(history, data_date, sp.z.jump.inner):
            return ()
        rows = factor_rows(history, members, data_date, sp.z.jump.inner)
        return self._targets(ZPrepared(history, None), rows, data_date, held, sp)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ZPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared ZPrepared, got {type(prepared).__name__}")
        sp = _check(params)
        if not trend_on(prepared.history, data_date, sp.z.jump.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, sp.z.jump.inner)
        return self._targets(prepared, rows, data_date, held, sp)


SIZED = SizedJumpAllocator()
Z2_RAW = ZParams(JUMP20, z_min=Decimal("2"), rank="raw")  # M0072-Z2-RAWRANK's picks, exactly


def _v(suffix: str, params: SizeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0092-{suffix}", family="M0092", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SIZED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0092",
    name="News-day picks sized toward the giants: the filtered earnings-day book weighted by "
         "trading value instead of equal slots",
    family="stock-event-drift",
    source_kind="variation",
    source_ref="variation of M0072-Z2-RAWRANK (Brandt, Kishore, Santa-Clara & Venkatachalam 2008, "
               "SSRN 909563, with M0072's own-swing filter); trading value as the size stand-in "
               "because the store has no shares outstanding before 2009",
    parent_id="M0072",
    hypothesis=(
        "Published 2008 (the earnings-day drift), so the dev window can only show the edge from "
        "before and just after it was widely known; 2009-2015 is judged first. M0072-Z2-RAWRANK "
        "(news days kept only when the jump is at least 4 points and at least 2 of the stock's "
        "own daily swings, ranked by the raw jump) earned +12.3% a year vs SPY's +7.2% on the "
        "owner's deposits, cleared the luck bar (0.914 at N=59) and beat SPY by almost 4 points a "
        "year in 2009-2015, but fell 22.4% (no deposits) in 1998. Month by month, about 10 of "
        "those points were the picks lagging SPY from April to August 1998 while fully invested: "
        "a narrow, giant-led market in which 20 equal 5% slots of mostly mid-sized members sank. "
        "Keep Z2-RAWRANK's event, filter, ranking, held-first rule, 60-session hold, SPY park, "
        "monthly SPY-200 switch and real-fee fractional preset (monthly-hold-frac-gotrade) "
        "exactly; change only the slot sizes. Size is read as trading value, the median close x "
        "volume over the 60 sessions ending on the data date (a point-in-time stand-in for "
        "company size; the store has no shares outstanding before 2009; a median so the news "
        "day's own volume spike does not rank the name). The picks share the same money the "
        "20-slot book gives them (n picks get n x 5%), each capped at 10%, the rest SPY. "
        "Variants: DV-CAP10 (in proportion to trading value), SQRT-CAP10 (to its square root, a "
        "half-way lean), TOP100-EW (screened members narrowed first to the 100 most-traded, then "
        "Z2-RAWRANK's picks at equal 5%: is the edge alive inside the giants alone?). The "
        "equal-weight control is the parent's own recorded trial M0072-Z2-RAWRANK (same preset, "
        "fees and deposits), not re-run. I expect SQRT-CAP10 to be best. Success: worst fall "
        "under 20% with the excess over SPY and a luck score >= 0.90 kept, and positive against "
        "SPY in 2009-2015."
    ),
    expected_failure=(
        "The news-day drift is strongest in smaller, less-followed names (the 2008 paper and the "
        "earnings-drift literature before it), so leaning toward giants may give back much of the "
        "edge and the luck score may drop under 0.90; TOP100-EW may hold few picks and drift "
        "toward plain SPY. The August 1998 crash hit everything and the monthly SPY-200 switch "
        "sold late and bought back late, so the switch may still owe about half the fall and no "
        "variant reach 20%. A 10% cap on two or three giants makes the book less diversified, "
        "so one bad earnings reaction in a big slot costs more than it did in a 5% slot. "
        "Trading value is a rough proxy: busy mid-caps after news and heavily traded tech names "
        "in 1999-2000 read as 'big', which may tilt the book into the bubble. Back-adjusted "
        "closes understate older trading value for high-yield payers a little. And this is a "
        "published anomaly, so a strong dev result may have faded in 2016-2026."
    ),
    candidates=(
        _v("DV-CAP10", SizeParams(Z2_RAW, weight="dv"),
           "Z2-RAWRANK's picks, money split by 60-day median trading value, 10% cap, rest SPY"),
        _v("SQRT-CAP10", SizeParams(Z2_RAW, weight="sqrt"),
           "The same split by the square root of trading value: a half-way lean to the giants"),
        _v("TOP100-EW", SizeParams(Z2_RAW, weight="equal", universe_top=100),
           "Only the 100 most-traded screened members may be picked, equal 5% slots as the parent"),
    ),
    seen_keys=(
        "concept:trading-value-weighted-event-book",
        "concept:size-tilted-earnings-drift",
        "concept:dollar-volume-weighting",
    ),
)
