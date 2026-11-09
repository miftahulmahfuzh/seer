"""M0537 — Asymmetric residual reversal: does the market-stripped loss reverse harder than the gain?

Source: Baldi-Lanfranchi, Collin-Dufresne & Daniel, Asymmetric Reversals, NBER WP 35840 (2026).
Published this year, so the dev window (to 2015) cannot have been traded on it; the risk is the
other way, that the older symmetric version (Blitz et al. 2013, M0490) was already arbitraged.
Idea: split last month's return into a market part and a residual (stock less beta times SPY, beta
from the 252 sessions before the window, as M0490 does). The paper says residual *losses* reverse
more than residual *gains*. Gotrade is long only, so the asymmetry can be tested from one side
only: buy the sharpest residual losers (LOSS) and, as the mirror, the sharpest residual winners
(GAIN). The paper predicts LOSS beats a no-opinion book by more than GAIN trails it.

What is different from M0490: the score is the plain market residual (no size regression), and
the no-opinion control is a *random* draw (a hash of the date and the symbol, not the most liquid
names), so the control carries no size tilt either. A random draw is one coin: it prices the
chassis, not a noise band (insight on one blind draw).

Arms, all on ``MONTHLY_HOLD_FRAC_GOTRADE``, 20 equal slots, F4's screen:

    LOSS         20 most negative market residuals, SPY-200 gate (the idea)
    GAIN         20 most positive market residuals, same gate (the mirror)
    CTRL-RAND    20 hash-random screened names, same gate and monthly churn
    CTRL-RAND-OPEN  the same random book with no gate: always invested, nothing stepping aside
    LOSS-OPEN    LOSS with no gate; the 2x2 pair that prices the gate's habit
    GAIN-OPEN    GAIN with no gate, so the asymmetry can be read with the gate out of it

Pure: reads bars dated at or before the data date only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
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

ADDED = date(2026, 11, 9)
SIGNALS = ("resid", "rand")


@dataclass(frozen=True, slots=True)
class AsymParams:
    """``inner`` is F4's screen, gate and book size; ``signal`` is the residual or a hash draw.

    ``side`` = -1 holds the residual losers, +1 the winners. Field names match M0490's
    ``SnrParams`` so its ``formation_returns`` reads them unchanged.
    """

    inner: FactorParams
    signal: str = "resid"
    side: int = -1
    rev_n: int = 21
    beta_n: int = 252
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if self.side not in (-1, 1):
            raise ValueError(f"side must be -1 or 1, got {self.side!r}")
        for name in ("rev_n", "beta_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.rev_n < 5 or self.beta_n < 60:
            raise ValueError("rev_n must be >= 5 and beta_n >= 60")

    def as_dict(self) -> dict[str, str]:
        out = {"signal": self.signal, "side": str(self.side), "rev_n": str(self.rev_n),
               "beta_n": str(self.beta_n), "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> AsymParams:
    if not isinstance(params, AsymParams):
        raise TypeError(f"params must be AsymParams, got {type(params).__name__}")
    return params


def _draw(symbol: str, data_date: date) -> str:
    return hashlib.sha256(f"M0537|{data_date.isoformat()}|{symbol}".encode()).hexdigest()


def targets_from(rows: list[FactorRow], grid: ReturnGrid | None, data_date: date,
                 p: AsymParams) -> tuple[Target, ...]:
    rows = [r for r in rows if r.symbol not in EXCLUDED]
    if not rows:
        return ()
    if p.signal == "rand":  # no opinion: a date-seeded draw, so no size or liquidity tilt
        chosen = sorted(rows, key=lambda r: _draw(r.symbol, data_date))[: p.inner.top]
    else:
        if grid is None:
            return ()
        _, resid = formation_returns(grid, [r.symbol for r in rows], data_date, p)  # type: ignore[arg-type]
        scorable = [r for r in rows if r.symbol in resid]
        chosen = sorted(scorable, key=lambda r: (p.side * resid[r.symbol], r.symbol))[: p.inner.top]
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, p.inner), strict=True):
        if weight is None:
            continue
        t = target_from_close(row.symbol, row.close, weight)
        if t is not None:
            out.append(t)
    return tuple(out)


class AsymmetricResidualReversalAllocator:
    """The month's sharpest market-residual losers or winners among screened names, or a draw."""

    id = "M0537"

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


ASYM = AsymmetricResidualReversalAllocator()

GATED = FactorParams(rank="momentum", top=20, trend=("SPY", 200))
OPEN = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: AsymParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0537-{suffix}", family="M0537", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ASYM, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0537",
    name="Asymmetric reversal: buy the stocks whose market-stripped loss last month was sharpest",
    family="stock-asymmetric-reversal",
    source_kind="paper",
    source_ref=("Baldi-Lanfranchi, Collin-Dufresne & Daniel 2026, 'Asymmetric Reversals', "
                "NBER Working Paper 35840"),
    parent_id="M0490",
    hypothesis=(
        "Published 2026, after the dev window, so dev cannot have been traded on it; the older "
        "symmetric residual reversal (Blitz et al. 2013) was published long before, and M0490, "
        "its size-neutral version, was rejected (funded 6.2% a year against SPY 7.2%, with its "
        "no-opinion gated control ahead of it). Per the paper, a stock's return left after "
        "removing beta times SPY reverses more after a loss than after a gain. Book: each month, "
        "among liquid index members behind the SPY-200 switch, hold the 20 with the most negative "
        "residual (21 sessions, beta from the 252 before), equal slots, fractional shares at "
        "Gotrade's real fees on the owner's monthly deposits. Long-only means only the loss side "
        "can be owned as the idea; the gain side (the 20 most positive residuals) is run as the "
        "mirror, and the asymmetry claim is read as LOSS beating CTRL-RAND by more than GAIN "
        "trails it. CTRL-RAND and CTRL-RAND-OPEN are a date-seeded random 20, gated and always "
        "invested, so what acting costs is separable from what the signal earns; LOSS-OPEN and "
        "GAIN-OPEN take the gate out. These always-invested and no-opinion arms may repeat "
        "earlier books (book twins); they are not new books. Success: beat total-return SPY on "
        "the deposits with worst fall under 25%, profit factor >= 1.3, a positive edge in "
        "2009-2015, and LOSS beating GAIN, CTRL-RAND and CTRL-RAND-OPEN. Failure of the "
        "asymmetry alone (LOSS and GAIN alike) is also a result: the paper's effect may need the "
        "short leg."
    ),
    expected_failure=(
        "M0490, M0158 and M0028 all failed at real fees: about 16 turns a year on $28 slots, and "
        "short-horizon reversal is a liquidity-provision payment that shrank after decimal ticks. "
        "The asymmetry may live in the short leg (the overpriced winners), which Gotrade cannot "
        "take, so the long-only loss side may be the weak half. The raw residual also loads on "
        "small jumpy high-beta names, so the book may be a bet on risk that lags SPY in 2009-2015. "
        "The 200-day gate reacts late in a crash. One random control is a single coin, so a small "
        "lead over it will be unreadable."
    ),
    candidates=(
        _v("LOSS", AsymParams(GATED), "20 most negative market residuals, gated (the idea)"),
        _v("GAIN", AsymParams(GATED, side=1), "Mirror: 20 most positive market residuals, gated"),
        _v("CTRL-RAND", AsymParams(GATED, signal="rand"),
           "No opinion: date-seeded random 20, same gate and monthly churn"),
        _v("CTRL-RAND-OPEN", AsymParams(OPEN, signal="rand"),
           "No opinion, no gate: always invested; prices what acting costs"),
        _v("LOSS-OPEN", AsymParams(OPEN), "LOSS with no gate: the pair that prices the gate's habit"),
        _v("GAIN-OPEN", AsymParams(OPEN, side=1), "GAIN with no gate: the asymmetry without the gate"),
    ),
    seen_keys=(
        "concept:asymmetric-residual-reversal",
        "concept:residual-reversal-size-neutral",
        "concept:reversal-always-invested-control",
    ),
)
