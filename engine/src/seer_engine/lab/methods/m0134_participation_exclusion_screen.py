"""M0134 — Refuse the most market-exposed quarter of a book that already works.

Source: variation of M0110 (downside participation as a ranking key). The participation measure is
M0110's own: a stock's summed return on SPY's down days over the past 252 sessions divided by SPY's
summed return on those same days. M0110 ordered a crash cleanly but, used as the *ranking*, bought a
low-beta book that lost 3-6 points a year to SPY after 2009. This method uses it the other way round:
as a *screen* in front of an engine whose ranking is left alone.

The two engines are M0072's standardised earnings-jump book (Brandt, Kishore, Santa-Clara &
Venkatachalam 2008, SSRN 909563, published 2008) and M0092's trading-value-sized version of it. Both
are dev-eligible and their kin is clean, so a result here is promotable, which a momentum engine's
would not be. The screen is applied to the rows each engine is allowed to look at: the F4-screened
members are scored on participation, the ``frac`` most exposed of the *scored* ones are removed,
and the engine then picks from what is left exactly as it always does (event filter, ranking,
held-first rule, hold, SPY park, SPY-200 switch). Names with no participation score (too short a
history) are kept, not barred: absence of a number is not evidence of exposure.

Every arm runs through this method's allocator, so the control (``frac = 0``) is the engine
unchanged and sits beside its treatment in the same run, on the same store and fees. Its own
numbers also show the wrapper reproduces the engine it wraps.

Reads only bars dated <= ``data_date`` (the 252-session window ends on it). Pure.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import build_grid
from seer_engine.lab.methods.m0072_standardised_earnings_jump import (
    ZJUMP,
    ZParams,
    ZPrepared,
)
from seer_engine.lab.methods.m0092_jump_trading_value_weight import SIZED, Z2_RAW, SizeParams
from seer_engine.lab.methods.m0110_downside_participation import (
    CaptureParams,
    capture_lookback,
    capture_scores,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, prepare_factor, trend_on

ADDED = date(2026, 10, 31)
WINDOW = 252


@dataclass(frozen=True, slots=True)
class ExclParams:
    """``base`` is an engine's whole configuration; ``frac`` of the scored pool is refused."""

    base: ZParams | SizeParams
    frac: float = 0.25

    def __post_init__(self) -> None:
        if not isinstance(self.base, (ZParams, SizeParams)):
            raise TypeError(f"base must be ZParams or SizeParams, got {type(self.base).__name__}")
        if isinstance(self.frac, bool) or not isinstance(self.frac, (int, float)):
            raise TypeError(f"frac must be a float, got {type(self.frac).__name__}")
        f = float(self.frac)
        if not (0.0 <= f < 1.0):  # NaN fails both comparisons
            raise ValueError(f"frac must be in [0, 1), got {f}")
        object.__setattr__(self, "frac", f)

    @property
    def z(self) -> ZParams:
        return self.base if isinstance(self.base, ZParams) else self.base.z

    def capture(self) -> CaptureParams:
        """The participation score read as 'most exposed first' (M0110's ``exposed`` side)."""
        return CaptureParams(inner=self.z.jump.inner, side="exposed", window=WINDOW,
                             market=self.z.jump.market)

    def as_dict(self) -> dict[str, str]:
        out = {"frac": repr(self.frac), "window": str(WINDOW)}
        for k, v in self.base.as_dict().items():
            out[f"base.{k}"] = v
        return out


def _check(params: object) -> ExclParams:
    if not isinstance(params, ExclParams):
        raise TypeError(f"params must be ExclParams, got {type(params).__name__}")
    return params


def exposed_names(scores: Mapping[str, float], frac: float) -> frozenset[str]:
    """The ``ceil(frac * n)`` most exposed of the ``n`` scored names (lowest score first, ties by symbol)."""
    if frac <= 0.0 or not scores:
        return frozenset()
    k = math.ceil(frac * len(scores))
    return frozenset(s for s, _ in sorted(scores.items(), key=lambda kv: (kv[1], kv[0]))[:k])


class ExclPrepared(ZPrepared):
    """M0072's prepared columns plus the one return grid the participation score reads."""

    def __init__(self, history: Mapping[str, History], factor: Any) -> None:
        super().__init__(history, factor)
        self._grids: dict[str, Any] = {}

    def grid(self, market: str) -> Any:
        if market not in self._grids:
            self._grids[market] = build_grid(self.history, market)
        return self._grids[market]


class ParticipationExclusionAllocator:
    """An engine's own book, picked from the pool minus its most market-exposed names."""

    id = "M0134"

    @staticmethod
    def _engine(p: ExclParams) -> Any:
        return ZJUMP if isinstance(p.base, ZParams) else SIZED

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(self._engine(p).lookback(p.base), capture_lookback(p.capture()))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return self._engine(p).symbols(p.base)

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return self._engine(p).holds(p.base)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: ExclPrepared, rows: list[Any], data_date: date,
             held: frozenset[str], p: ExclParams) -> tuple[Target, ...]:
        if p.frac > 0.0 and rows:
            grid = prepared.grid(p.z.jump.market)
            if grid is not None:
                scores = capture_scores(grid, [r.symbol for r in rows], data_date, p.capture())
                barred = exposed_names(scores, p.frac)
                rows = [r for r in rows if r.symbol not in barred]
        return self._engine(p)._targets(prepared, rows, data_date, held, p.base)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = p.z.jump.inner
        if not trend_on(history, data_date, inner):
            return ()
        rows = factor_rows(history, members, data_date, inner)
        return self._run(ExclPrepared(history, None), rows, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> ExclPrepared:
        return ExclPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ExclPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared ExclPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = p.z.jump.inner
        if not trend_on(prepared.history, data_date, inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, inner)
        return self._run(prepared, rows, data_date, held, p)


EXCL = ParticipationExclusionAllocator()

Z2R = Z2_RAW  # M0072-Z2-RAWRANK's picks, exactly (z >= 2, ranked by the raw jump)
M92 = SizeParams(Z2_RAW, weight="sqrt")  # M0092-SQRT-CAP10's book, exactly


def _v(suffix: str, params: ExclParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0134-{suffix}", family="M0134", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=EXCL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0134",
    name="Market participation as an exclusion, not a ranking: drop the most exposed quarter of a "
         "book that already works",
    family="stock-downside-participation",
    source_kind="variation",
    source_ref="variation of M0110 (downside participation: summed return on SPY's down days over "
               "252 sessions, divided by SPY's own); engines M0072-Z2-RAWRANK and "
               "M0092-SQRT-CAP10 (Brandt, Kishore, Santa-Clara & Venkatachalam 2008, SSRN 909563)",
    parent_id="M0110",
    hypothesis=(
        "M0110 proved that downside participation orders a crash cleanly: five books built along "
        "that ranking fell 39.9%, 41.4%, 43.3%, 74.0% and 90.6% in exactly the order the ranking "
        "predicted. It also proved that using it as the book's ranking key is a bad trade, because "
        "the 20 lowest participants are a low-beta book that lost 3 to 6 points a year to SPY over "
        "2009-2015. The remaining use is as a screen rather than a ranker: keep an existing "
        "engine's ranking and refuse to hold the most market-exposed quarter of the scored pool. "
        "That costs the book only its most exposed names rather than replacing its whole "
        "selection, so it should give up far less return than ranking on participation did. The "
        "engines are M0072's z-scored event book (arm Z2-RAWRANK) and M0092's trading-value-sized "
        "version (arm SQRT-CAP10), the two the hard gate calls promotable, not a momentum engine, "
        "which would read as behavioural kin of the test-failed books. The underlying earnings-day "
        "drift was published in 2008, so a strong dev result may have faded by 2016-2026; "
        "2009-2015 is judged first. Variants, all through this method's allocator so every "
        "control sits beside its treatment: Z2R-CTRL and M92-CTRL (nothing excluded: the engines "
        "unchanged, which also checks the wrapper reproduces them), Z2R-X25 and M92-X25 (the most "
        "exposed 25% of scored names refused), and Z2R-X50 (the most exposed half refused, to "
        "price the dose). Success, against the control in the same run: the worst fall at least 5 "
        "points smaller, less than 1 point a year of return given up, and the 2009-2015 lead "
        "not going backwards; if it does, this is the low-beta trade again in a smaller dose and "
        "should be dropped."
    ),
    expected_failure=(
        "The excluded names are the engine's best performers, because the same exposure that "
        "deepens the fall is what earns the return: an earnings-jump book buys high-beta names "
        "right after good news, and the most exposed quarter of the pool is where those live. The "
        "screen then costs about what ranking on it cost, a few points a year, for a smaller fall "
        "that the SPY-200 switch was already partly buying, and the whole participation measure "
        "is closed for good. A second failure is that the 1998 fall is market-wide, so removing "
        "exposed names shrinks the fall by under 5 points. A third is that with 25% of the pool "
        "gone the event filter has fewer live names, more slots go to SPY, and the book drifts "
        "toward plain SPY without any edge of its own."
    ),
    candidates=(
        _v("Z2R-CTRL", ExclParams(Z2R, frac=0.0),
           "M0072-Z2-RAWRANK unchanged: the control for the first engine"),
        _v("Z2R-X25", ExclParams(Z2R, frac=0.25),
           "M0072-Z2-RAWRANK with the most exposed quarter of scored names refused: the headline"),
        _v("Z2R-X50", ExclParams(Z2R, frac=0.50),
           "The same with the most exposed half refused: prices the dose"),
        _v("M92-CTRL", ExclParams(M92, frac=0.0),
           "M0092-SQRT-CAP10 unchanged: the control for the second engine"),
        _v("M92-X25", ExclParams(M92, frac=0.25),
           "M0092-SQRT-CAP10 with the most exposed quarter refused: the second engine, same dose"),
    ),
    seen_keys=(
        "concept:participation-quartile-exclusion-screen",
    ),
)
