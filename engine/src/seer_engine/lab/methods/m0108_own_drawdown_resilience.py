"""M0108 — The stocks that fall least: hold the big names whose own worst twelve-month fall was mildest.

Source: Goldberg & Mahmoud, and the Han, Chu & Zhang line on maximum drawdown as a
cross-sectional signal -- "Maximum Drawdown, Recovery, and Momentum", Journal of Risk and
Financial Management 14(11) 542 (2021), doi:10.3390/jrfm14110542 -- which reports books ranked on
each stock's own past drawdown beating cumulative-return momentum books on Sharpe with a markedly
smaller worst fall. It sits beside the low-risk anomaly of Ang, Hodrick, Xing & Zhang (2006),
Journal of Finance 61(1), 259-299.

Idea: every method in this lab that beats SPY on average dies on the 20% worst-fall rule, and the
only answer tried so far is a market-wide timing switch, which three batches have shown loses more
after 2009 than it saves. This tries the other answer: do not time the market at all, pick stocks
that do not fall much in the first place. For each liquid index member, measure its own worst
peak-to-trough fall over the past twelve months and hold the mildest, equal-weighted, re-picked
monthly, with no switch of any kind.

A stock's own past drawdown is not its volatility and not its beta. It reads the *shape* of the
loss rather than its average size: it penalises a name that fell 40% once and recovered, while
sparing one that merely jiggles daily. The lab has tested calm (volatility, M0021/M0088) and
low-swing-with-the-market (beta, M0059) filters inside other books and found both cut the return
about as much as they cut the fall. The open question is whether ranking on the fall itself breaks
that one-for-one trade.

The frame is F4's -- point-in-time S&P 500 / Nasdaq-100 members, the $5 price and 20M-dollar
volume screen, monthly re-picks, equal weights, fractional shares at Gotrade's real fees on
``monthly-hold-frac-gotrade`` -- with two changes: **no trend gate** (the idea is explicitly a
stock-selection answer to drawdown, not a timing one, so a market switch would confound it), and a
ranking key that is each symbol's own maximum drawdown over the ``window`` closes ending at d:

    MDD(s) = max over t in the window of (1 - close_t / max(close_u : u <= t, u in window))

``side="low"`` holds the ``top`` mildest; ``side="high"`` holds the ``top`` deepest, the paired
control that must trail -- the effect has to show as a spread, not only as low beta.

Assumptions, written before the run:

- The reserved idea named an ``EW-ALL`` yardstick: equal weight across the whole liquid universe,
  to say how much of any result is just equal weighting rather than the drawdown rank. A literal
  all-names book is untradeable here -- the lab starts at 20M IDR (about $1,250) and splitting it
  300+ ways is a $4 slot, where Gotrade's fee minimum alone would decide the result. So the
  yardstick is ``EW40-DV``: the 40 most-traded eligible members, equal weighted, the same book
  size and the same screen as DD40, differing only in the ranking key. That is also the
  equal-weight big-company yardstick insight 91 asked for (the RSP question), at a slot size the
  account can actually fill.
- ``inner.rank`` is unused: ``choose`` re-ranks every eligible row itself. It is kept at
  ``"momentum"`` so the recorded screen reads identically to every other F4-framed method
  (M0091's precedent); the momentum column still gates eligibility through its finiteness.
- Bars are split- and dividend-adjusted, so an ex-dividend day is not read as a fall.
- Reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20_NOTREND
from seer_engine.sim.book import Target
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
    factor_weights,
    prepare_factor,
)

ADDED = date(2026, 10, 12)

Rank = Literal["mild", "deep", "traded"]
_RANKS: tuple[str, ...] = ("mild", "deep", "traded")


@dataclass(frozen=True, slots=True)
class DrawdownParams:
    """``inner`` is F4's screen, book size and weighting; the rest is the ranking."""

    inner: FactorParams
    side: Rank = "mild"
    window: int = 252  # closes in the drawdown window (252 = one year, 378 = eighteen months)

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.side, str) or self.side not in _RANKS:
            raise ValueError(f"side must be one of {_RANKS}, got {self.side!r}")
        if isinstance(self.window, bool) or not isinstance(self.window, int):
            raise TypeError(f"window must be an int, got {type(self.window).__name__}")
        if self.window < 21:
            raise ValueError(f"window must be >= 21, got {self.window}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "window": str(self.window)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> DrawdownParams:
    if not isinstance(params, DrawdownParams):
        raise TypeError(f"params must be DrawdownParams, got {type(params).__name__}")
    return params


def drawdown_lookback(params: DrawdownParams) -> int:
    """Bars each read symbol needs through d: F4's screen, or the drawdown window if longer.

    Declared truthfully, because ``choose`` really reads ``window`` closes. M0069 declares only
    its screen and lets the members' longer formation window gate eligibility instead, which
    keeps its run start early; here that would be a false declaration the allocator contract
    catches, so DD20-L18 simply starts about six months later than the 252-bar variants. The
    cost is that its first months are not directly comparable with theirs; the analysis says so.
    """
    return max(factor_lookback(params.inner), params.window)


def own_drawdown(h: History, data_date: date, window: int) -> float | None:
    """The symbol's worst peak-to-trough fall over the ``window`` closes ending at ``data_date``.

    0.18 means "at its worst it was 18% below its own running high inside the window". None when
    the window is not fully covered or any close in it is not finite and positive.
    """
    i = h.index_of(data_date)
    if i is None or i + 1 < window:
        return None
    c = h.close[i + 1 - window : i + 1]
    if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
        return None
    x = float(np.max(1.0 - c / np.maximum.accumulate(c)))
    return x if np.isfinite(x) else None


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           params: DrawdownParams) -> list[FactorRow]:
    """The chosen rows in rank order; ties by symbol ascending."""
    scored: list[tuple[float, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED:
            continue
        if params.side == "traded":  # the equal-weight yardstick: most-traded first
            scored.append((-r.dollar_volume, r.symbol, r))
            continue
        h = history.get(r.symbol)
        if h is None:
            continue
        x = own_drawdown(h, data_date, params.window)
        if x is None:
            continue
        scored.append((x if params.side == "mild" else -x, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in scored[: params.inner.top]]


def targets_from_rows(chosen: list[FactorRow], params: DrawdownParams) -> tuple[Target, ...]:
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


@dataclass
class DrawdownPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class OwnDrawdownAllocator:
    """F4's screen, ranked on each member's own worst fall over the past ``window`` closes.

    No trend gate: the book is always invested. Held symbols get no special treatment -- a name
    that leaves the chosen set is signal-exited by the book engine.
    """

    id = "M0108"

    def lookback(self, params: Any) -> int:
        return drawdown_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.inner.trend[0],) if p.inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from_rows(choose(rows, history, data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> DrawdownPrepared:
        return DrawdownPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, DrawdownPrepared):
            raise TypeError(f"prepared must be DrawdownPrepared, got {type(prepared).__name__}")
        p = _check(params)
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.history, data_date, p), p)


DRAWDOWN = OwnDrawdownAllocator()

N20 = N20_NOTREND  # F4's screen, 20 equal slots, always invested
N40 = replace(N20_NOTREND, top=40)


def _v(suffix: str, params: DrawdownParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0108-{suffix}", family="M0108", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DRAWDOWN, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0108",
    name="The stocks that fall least: hold the big names whose own worst twelve-month fall was mildest",
    family="stock-drawdown-resilience",
    source_kind="paper",
    source_ref=(
        "Maximum Drawdown, Recovery, and Momentum, Journal of Risk and Financial Management "
        "14(11) 542 (2021), doi:10.3390/jrfm14110542; Ang, Hodrick, Xing and Zhang (2006), "
        "Journal of Finance 61(1), 259-299 for the low-risk anomaly beside it"
    ),
    parent_id=None,
    hypothesis=(
        "Every method in this lab that beats SPY on average dies on the 20% worst-fall rule, and "
        "the only answer tried so far is a market-wide timing switch, which three batches have "
        "shown loses more after 2009 than it saves. This tries the other answer: pick stocks that "
        "do not fall much in the first place. Each month, among F4-screened point-in-time "
        "S&P 500 / Nasdaq-100 members ($5 price, 20M-dollar daily volume), measure every name's "
        "own worst peak-to-trough fall over the past 252 closes and hold the 20 mildest at 5% "
        "each, equal weighted, fractional shares at Gotrade's real fees "
        "(monthly-hold-frac-gotrade), with no market switch of any kind. A stock's own past "
        "drawdown is not its volatility and not its beta: it reads the shape of the loss rather "
        "than its average size, so it penalises a name that fell 40% once and recovered while "
        "sparing one that merely jiggles, and the published work finds it ranks the cross-section "
        "better than either. The lab has tested calm (volatility) and low-swing-with-the-market "
        "(beta) filters inside other books and found both cut the return about as much as they "
        "cut the fall; the open question is whether ranking on the fall itself breaks that "
        "one-for-one trade. Variants: DD20 and DD40 (the 20 or 40 mildest), DD20-L18 (an "
        "eighteen-month drawdown window instead of one year, so a book picked in 2009 still "
        "remembers 2008 -- the longest window the method contract fixture can prove), WORST20 (the 20 deepest, the paired control that must trail), and "
        "EW40-DV (the 40 most-traded eligible members, equal weighted) as the yardstick that says "
        "how much of any result is just equal weighting rather than the drawdown rank -- it is "
        "also the equal-weight big-company yardstick insight 91 asked for. Turnover should be "
        "low, so fees should not decide this one. Success: a DD variant beats SPY TR on "
        "deposit-matched money with a worst fall under 20%, clears a majority of the "
        "walk-forward folds, beats the EW40-DV yardstick, and the control trails it clearly."
    ),
    expected_failure=(
        "The mildest-fall names before 2008 were financials and utilities, exactly the group that "
        "then fell hardest, so the signal may be a trap in precisely the crash it is meant to "
        "survive: a book picked in mid-2007 on 2006-2007 drawdowns would have been full of banks. "
        "A long-only equity book with no timing rule has nowhere to hide in 2008, so the 20% bar "
        "may be out of reach whatever it holds. The likeliest quieter failure is that the "
        "drawdown rank collapses onto low volatility in large caps, in which case this is the "
        "calm-stock book again: a shallower fall bought with a lower return, trailing SPY on CAGR "
        "through the 2009-2015 growth run, and no better than EW40-DV. The paper is from 2021, "
        "well after the dev window ends, so the dev window at least sees the signal before any "
        "crowd traded this particular form of it; but the low-risk anomaly it sits beside has "
        "been traded since 2006 and has faded."
    ),
    candidates=(
        _v("DD20", DrawdownParams(N20, side="mild", window=252),
           "The 20 members whose own worst 12-month fall was mildest, always invested: the book"),
        _v("DD40", DrawdownParams(N40, side="mild", window=252),
           "The 40 mildest-fall members: broader, less single-stock risk, same signal"),
        _v("DD20-L18", DrawdownParams(N20, side="mild", window=378),
           "The 20 mildest over an 18-month window: does the signal want a crash in its memory"),
        _v("WORST20", DrawdownParams(N20, side="deep", window=252),
           "The 20 members that fell hardest: the paired control, expected to trail"),
        _v("EW40-DV", DrawdownParams(N40, side="traded", window=252),
           "The 40 most-traded members equal weighted: the equal-weight yardstick, no drawdown rank"),
    ),
    seen_keys=(
        "concept:own-max-drawdown-cross-section",
        "concept:drawdown-resilient-stock-picking",
        "doi:10.3390/jrfm14110542",
    ),
)
