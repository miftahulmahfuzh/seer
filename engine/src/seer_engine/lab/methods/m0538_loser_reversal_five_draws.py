"""M0538 — One-month market-stripped losers, with the sort proved and a real noise band.

Source: variation on M0537 (Baldi-Lanfranchi, Collin-Dufresne & Daniel, NBER WP 35840, 2026) and
M0490 (Blitz et al. 2013). The idea is published, so a dev edge can only be from before the crowd
traded it, and 2009-2015 is the first filter.

Why a re-run: M0537 sorted ``p.side * residual`` ascending and called side = -1 "losers". Ascending
on the negated residual puts the *largest* residual first, so its LOSS arm held last month's
market-stripped gainers (6.4% a year funded against a random 20's 7.5%, SPY 7.2%) and its GAIN arm
held the losers. M0490 shares the line (its ``scorable`` sort), so its "losers" arm probably held
gainers as well; that is a reading of the code, not a measurement. Nobody has yet bought the true
loser side. Here the pick is one named function, ``pick_extreme``, pinned by a unit test on
made-up scores (tests/test_m0538_pick.py), and the no-opinion control is five hash draws, each its
own seed, so the control is a band and not one coin (the lab's draw-noise error bar: nineteen
rules spanned 7.5 points a year).

Arms, all on ``MONTHLY_HOLD_FRAC_GOTRADE``, 20 equal slots, behind the SPY-200 switch:

    LOSER     the 20 most negative market residuals (the idea, correctly signed)
    RAND-A..E five date-and-seed-hashed random 20s: the band the loser book must clear

The winner side is not re-registered: it is M0537-LOSS's book (the mislabelled arm), already
recorded, and the variant cap is six. Gate-open arms are left for a follow-up amendment.

Pure: reads bars dated at or before the data date only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import ResidPrepared, ReturnGrid, build_grid
from seer_engine.lab.methods.m0490_size_neutral_residual_reversal import formation_returns
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 10)
SIGNALS = ("loser", "rand")


def pick_extreme(scores: Mapping[str, float], kind: str, k: int) -> list[str]:
    """The ``k`` symbols with the lowest (``loser``) score; ties break on the symbol."""
    if kind != "loser":
        raise ValueError(f"kind must be 'loser', got {kind!r}")
    return sorted(scores, key=lambda s: (scores[s], s))[:k]


@dataclass(frozen=True, slots=True)
class LoserParams:
    """``inner`` is F4's screen, gate and book size; ``signal`` is the loser sort or a hash draw.

    Field names match M0490's ``SnrParams`` so its ``formation_returns`` reads them unchanged.
    """

    inner: FactorParams
    signal: str = "loser"
    seed: int = 0
    rev_n: int = 21
    beta_n: int = 252
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        for name in ("seed", "rev_n", "beta_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.rev_n < 5 or self.beta_n < 60:
            raise ValueError("rev_n must be >= 5 and beta_n >= 60")

    def as_dict(self) -> dict[str, str]:
        out = {"signal": self.signal, "seed": str(self.seed), "rev_n": str(self.rev_n),
               "beta_n": str(self.beta_n), "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> LoserParams:
    if not isinstance(params, LoserParams):
        raise TypeError(f"params must be LoserParams, got {type(params).__name__}")
    return params


def _draw(symbol: str, data_date: date, seed: int) -> str:
    return hashlib.sha256(f"M0538|{seed}|{data_date.isoformat()}|{symbol}".encode()).hexdigest()


def targets_from(rows: Sequence[FactorRow], grid: ReturnGrid | None, data_date: date,
                 p: LoserParams) -> tuple[Target, ...]:
    rows = [r for r in rows if r.symbol not in EXCLUDED]
    if not rows:
        return ()
    by_symbol = {r.symbol: r for r in rows}
    if p.signal == "rand":
        names = sorted(by_symbol, key=lambda s: _draw(s, data_date, p.seed))[: p.inner.top]
    else:
        if grid is None:
            return ()
        _, resid = formation_returns(grid, list(by_symbol), data_date, p)  # type: ignore[arg-type]
        names = pick_extreme({s: v for s, v in resid.items() if s in by_symbol}, "loser",
                             p.inner.top)
    chosen = [by_symbol[s] for s in names]
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, p.inner), strict=True):
        if weight is None:
            continue
        t = target_from_close(row.symbol, row.close, weight)
        if t is not None:
            out.append(t)
    return tuple(out)

class LoserReversalAllocator:
    """The month's sharpest market-residual losers among screened names, or a seeded draw."""

    id = "M0538"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.beta_n + p.rev_n + 2)

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

    def targets(self, history: Mapping[str, Any], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from(rows, build_grid(history, p.market), data_date, p)

    def prepare(self, history: Mapping[str, Any]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from(rows, prepared.grid(p.market), data_date, p)


LOSER_ALLOC = LoserReversalAllocator()

GATED = FactorParams(rank="momentum", top=20, trend=("SPY", 200))


def _v(suffix: str, params: LoserParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0538-{suffix}", family="M0538", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LOSER_ALLOC, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0538",
    name="One-month market-stripped losers, measured against five random draws",
    family="stock-asymmetric-reversal",
    source_kind="variation",
    source_ref="M0537 (sort direction found backwards); Baldi-Lanfranchi et al. 2026, NBER WP 35840",
    parent_id="M0537",
    hypothesis=(
        "M0537's LOSS arm held the market-stripped gainers (sort inverted), so the loser side was "
        "never bought. Published 2026 (and Blitz et al. 2013 for the symmetric form), so the dev "
        "window is before the crowd. Book: each month, among liquid index members behind the "
        "SPY-200 switch, hold the 20 with the most negative residual (21 sessions, beta from the "
        "252 before), equal slots, fractional shares at Gotrade's real fees on the owner's "
        "monthly deposits. The sort is one function pinned by a unit test. The no-opinion control "
        "is five date-and-seed hash draws on the same chassis and gate (they may repeat earlier "
        "random books: book twins, not new books). Success: LOSER beats total-return SPY on the "
        "deposits, worst fall under 25%, profit factor >= 1.3, a positive edge in 2009-2015, and "
        "a funded return above ALL five draws (p = 1/6 by chance alone, so a lead over only some "
        "is not a finding). The winner side is M0537-LOSS's recorded book."
    ),
    expected_failure=(
        "M0490, M0158 and M0028 failed at real fees: about 16 turns a year on $28 slots, and "
        "short-horizon reversal is a liquidity payment that shrank after decimal ticks. The raw "
        "residual loads on small jumpy high-beta names, so the loser book may be a bet on risk "
        "that lags SPY in 2009-2015 and falls hard in 2008 behind a late gate. The five draws may "
        "span several points a year, leaving a small lead unreadable."
    ),
    candidates=(
        _v("LOSER", LoserParams(GATED), "20 most negative market residuals, gated (the idea, correctly signed)"),
        *(_v(f"RAND-{c}", LoserParams(GATED, signal="rand", seed=s),
             f"No opinion: hash draw seed {s}, same gate and monthly churn")
          for s, c in enumerate("ABCDE", start=1)),
    ),
    seen_keys=(
        "concept:asymmetric-residual-reversal-loser-side",
        "concept:residual-reversal-size-neutral",
        "concept:random-draw-error-bar",
    ),
)
