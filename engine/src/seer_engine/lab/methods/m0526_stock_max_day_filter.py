"""M0526 -- The lottery-stock filter: drop last month's biggest one-day jumpers from a broad book.

Source: variation of M0525 (Sera batch 20261112-1645); Bali, Cakici & Whitelaw, Maxing Out:
Stocks as Lotteries and the Cross-Section of Expected Returns, Journal of Financial Economics 2011.
Idea: investors overpay for a stock that just had an outsized one-day pop, the same way lottery
buyers overpay for a long-shot ticket, and that overpayment is given back over the following
month. M0525 tested exactly this logic on the index as a whole -- SPY's own biggest day in the
last 21 sessions -- and it lost: the dial earned less than always-holding SPY and every dial arm
missed the DSR bar. Bali, Cakici and Whitelaw actually measured the effect one stock at a time:
each eligible member's own MAX (its largest one-day return in the trailing month) should predict
that stock's next month, not the index's. This method moves the idea down to where it was
measured.

On data date d:
  * **the pool**: liquid index members -- F4's liquidity screen only (at least ``DV_N`` bars,
    finite close, 20-day mean dollar volume above ``min_dollar_volume``, close >= ``min_price``),
    no momentum requirement, so a young company is not quietly thrown out the way a momentum or
    tenure screen would be. Ranked by 20-day mean dollar volume, the ``pool`` most heavily traded
    kept. This mirrors M0117's ``liquid_rows`` exactly.
  * **MAX**: for each pooled symbol, the largest single-day simple return over its trailing
    ``max_window`` sessions through d (Bali-Cakici-Whitelaw's MAX(1), their plainest measure).
  * **three arms, one pool, one rebalance, monthly**:
      - ALL: every pooled name, equal weight -- the unfiltered book this idea is judged against.
      - FILTER: drop the ``drop_frac_pct`` of the pool with the largest MAX (the "lottery"
        names), equal weight the rest.
      - RAND: drop the same COUNT of names as FILTER, chosen by a fixed hash of (seed, symbol,
        year-month) -- M0187's placebo draw -- with no opinion about MAX. Equal weight the rest.
        ALL vs RAND prices what dropping any third of the book costs on its own (fewer, larger
        slots); FILTER vs RAND prices whatever MAX adds or removes beyond that. Two seeds are run
        so the comparison is a spread, not one lucky draw.
  Held names get no special treatment: each month is a fresh pick, so a name dropped this month
  is sold and a name no longer dropped is bought back.

Published 2011 on data reaching into the 2000s, so by the dev window's own lesson a strong
whole-window result may already have been arbitraged away before the owner could trade it;
2009-2015 is read first for that reason.

Fractional shares at Gotrade's real fees: a ``pool``-name book on the owner's deposits needs
fractional slots to be invested at all (M0021).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import DV_N, EXCLUDED, FactorPrepared, prepare_factor

ADDED = date(2026, 11, 12)


def _check_int(name: str, v: object, lo: int) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < lo:
        raise ValueError(f"{name} must be >= {lo}, got {v}")
    return v


def _check_float(name: str, v: object, lo: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(v).__name__}")
    x = float(v)
    if not (x >= lo):
        raise ValueError(f"{name} must be >= {lo}, got {x}")
    return x


_MODES = ("all", "filter", "rand")


@dataclass(frozen=True, slots=True)
class LotteryParams:
    """The pool's size and liquidity floor, the MAX window, and which arm to run."""

    mode: str = "all"  # "all" | "filter" | "rand"
    pool: int = 100
    max_window: int = 21
    drop_frac_pct: int = 33  # percent of the pool dropped by FILTER/RAND (~ a third, the default)
    seed: int = 1  # RAND's hash seed; unused by ALL/FILTER
    min_dollar_volume: float = 20_000_000.0  # F4's floor: 20-day mean close x volume, strict
    min_price: float = 5.0

    def __post_init__(self) -> None:
        if not isinstance(self.mode, str) or self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        _check_int("pool", self.pool, 3)
        _check_int("max_window", self.max_window, 2)
        _check_int("drop_frac_pct", self.drop_frac_pct, 1)
        if self.drop_frac_pct >= 100:
            raise ValueError(f"drop_frac_pct must be < 100, got {self.drop_frac_pct}")
        _check_int("seed", self.seed, 0)
        object.__setattr__(
            self, "min_dollar_volume", _check_float("min_dollar_volume", self.min_dollar_volume, 0.0)
        )
        object.__setattr__(self, "min_price", _check_float("min_price", self.min_price, 0.01))

    def as_dict(self) -> dict[str, str]:
        return {
            "mode": self.mode,
            "pool": str(self.pool),
            "max_window": str(self.max_window),
            "drop_frac_pct": str(self.drop_frac_pct),
            "seed": str(self.seed),
            "min_dollar_volume": f"{self.min_dollar_volume:.0f}",
            "min_price": f"{self.min_price:.2f}",
        }


def _check(params: object) -> LotteryParams:
    if not isinstance(params, LotteryParams):
        raise TypeError(f"params must be LotteryParams, got {type(params).__name__}")
    return params


# ---- the pool (M0117's liquid_rows, verbatim pattern) ---------------------------------------


def liquid_rows(
    fp: FactorPrepared, members: AbstractSet[str], data_date: date, p: LotteryParams
) -> list[tuple[float, str, float]]:
    """``(dollar_volume, symbol, close)`` for every member that clears the liquidity screen on d."""
    day = as_day(data_date)
    lo = int(np.searchsorted(fp.dates, day, side="left"))
    hi = int(np.searchsorted(fp.dates, day, side="right"))
    if lo == hi:
        return []
    window = slice(lo, hi)
    close = fp.close[window]
    dv = fp.dollar_volume[window]
    ok = (
        (fp.nbars[window] >= DV_N)
        & np.isfinite(close)
        & np.isfinite(dv)
        & (dv > p.min_dollar_volume)
        & (close >= p.min_price)
    )
    out: list[tuple[float, str, float]] = []
    for j in (int(j) for j in np.flatnonzero(ok)):
        symbol = fp.symbols[int(fp.sym[lo + j])]
        if symbol in EXCLUDED or symbol not in members:
            continue
        out.append((float(dv[j]), symbol, float(close[j])))
    return out


# ---- the signal and the control draw ---------------------------------------------------------


def max_day_return(
    history: Mapping[str, History], symbol: str, data_date: date, window: int
) -> float | None:
    """The largest one-day simple return over ``symbol``'s trailing ``window`` sessions through d.

    None when there are fewer than ``window + 1`` bars through d (not enough closes to form
    ``window`` daily returns) or any of them is non-finite.
    """
    h = history.get(symbol)
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None or i < window:
        return None
    closes = h.close[i - window : i + 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        rets = closes[1:] / closes[:-1] - 1.0
    if not np.all(np.isfinite(rets)):
        return None
    return float(np.max(rets))


def draw(seed: int, symbol: str, data_date: date) -> int:
    """M0187's deterministic hash draw: a fixed pseudo-random order, no run-time randomness."""
    key = f"{seed}|{symbol}|{data_date.year:04d}-{data_date.month:02d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


@dataclass(frozen=True, eq=False)
class LotteryPrepared:
    """``has_market`` is False on the history-only path (``prepare``): no membership calendar came
    with it, so by the market-aware contract the allocator targets nothing rather than silently
    treating the test kit's probe members as a real panel."""

    factor: FactorPrepared = field(repr=False)
    history: Mapping[str, History] = field(repr=False)
    has_market: bool = False


class LotteryAllocator:
    """A broad liquid book with its lottery names (FILTER), or a matched random third (RAND), dropped."""

    id = "M0526"
    market_fields = ()  # reads Market.membership, which every store carries

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(DV_N, p.max_window + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()  # no fixed instrument: it reads members only

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(
        self,
        prepared: LotteryPrepared,
        members: AbstractSet[str],
        data_date: date,
        p: LotteryParams,
    ) -> tuple[Target, ...]:
        if not prepared.has_market:
            return ()
        rows = liquid_rows(prepared.factor, members, data_date, p)
        rows.sort(key=lambda r: (-r[0], r[1]))  # most traded first, ties by symbol
        base = rows[: p.pool]
        if not base:
            return ()
        symbols = [s for _, s, _ in base]
        drop_n = len(symbols) * p.drop_frac_pct // 100
        dropped: set[str] = set()
        if p.mode == "filter" and drop_n > 0:
            scored = [
                (symbol, max_day_return(prepared.history, symbol, data_date, p.max_window))
                for symbol in symbols
            ]
            finite = [(s, m) for s, m in scored if m is not None]
            finite.sort(key=lambda r: (-r[1], r[0]))  # largest MAX first
            dropped = {s for s, _ in finite[:drop_n]}
        elif p.mode == "rand" and drop_n > 0:
            ordered = sorted(symbols, key=lambda s: (draw(p.seed, s, data_date), s))
            dropped = set(ordered[:drop_n])
        kept = [(dv, s, close) for dv, s, close in base if s not in dropped]
        if not kept:
            return ()
        weight = equal_weight(len(kept))
        out: list[Target] = []
        for _, symbol, close in kept:
            target = target_from_close(symbol, close, weight)
            if target is not None:
                out.append(target)
        return tuple(out)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._run(
            LotteryPrepared(prepare_factor(history), history), members, data_date, _check(params)
        )

    def prepare(self, history: Mapping[str, History]) -> LotteryPrepared:
        return LotteryPrepared(prepare_factor(history), history)

    def prepare_market(self, market: Any) -> LotteryPrepared:
        return LotteryPrepared(prepare_factor(market.history), market.history, has_market=True)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, LotteryPrepared):
            raise TypeError(f"prepared must be LotteryPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


LOTTERY = LotteryAllocator()


def _v(suffix: str, params: LotteryParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0526-{suffix}",
        family="M0526",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=LOTTERY,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0526",
    name="Lottery-day filter inside a stock book: skip stocks with a huge one-day jump last month",
    family="stock-max-day-filter",
    source_kind="variation",
    source_ref=(
        "variation of M0525 (Sera batch 20261112-1645); Bali, Cakici & Whitelaw, Maxing Out: "
        "Stocks as Lotteries and the Cross-Section of Expected Returns, Journal of Financial "
        "Economics 2011"
    ),
    parent_id="M0525",
    hypothesis=(
        "M0525 tested the same 'overpay after a lottery-like jump' idea on SPY alone -- the "
        "index's own biggest day in the last month -- and it lost: the dial earned +6.6%/yr "
        "against always-holding SPY's +7.7%/yr, and every dial arm missed the DSR bar. Bali, "
        "Cakici and Whitelaw measured the effect at the stock level, not the index level: a "
        "company whose shares just had an outsized one-day pop gets bought by investors chasing "
        "a lottery payoff, and that overpayment is given back the following month, so the "
        "prediction is about that stock's next return, not the market's. This method moves the "
        "idea down to where it was actually measured. Three arms share one pool (the pool most "
        "heavily traded, F4-liquid index members, no momentum requirement) and one rebalance, "
        "monthly, fractional shares at Gotrade's real fees: ALL holds the whole pool equal-weight "
        "(the unfiltered book this idea is judged against); FILTER drops the third of the pool "
        "with the largest trailing-21-session single-day return (the lottery names) and "
        "equal-weights what is left; RAND drops a different, equal-size third chosen by a fixed "
        "hash with no opinion about MAX, so ALL-vs-RAND prices what dropping any third of the "
        "book costs on its own (fewer, larger slots) and FILTER-vs-RAND prices whatever MAX adds "
        "or removes beyond that. Two RAND seeds are run so that comparison is a spread, not one "
        "lucky draw. Success: FILTER beats both ALL and RAND, beats total-return SPY, with a "
        "worst fall under 20%, and the edge survives into 2009-2015, not just the whole window."
    ),
    expected_failure=(
        "Published in 2011 on data running into the 2000s, so by the dev window's own lesson a "
        "strong whole-window result is likely to have already been arbitraged away by the time "
        "the owner could trade it; 2009-2015 is read first for exactly that reason. The more "
        "basic risk, carried over from M0525's own result: the base book is a broad, "
        "liquidity-ranked equal-weight large-cap pool, the same shape insight 91 says loses to "
        "SPY's big-company drift from 2018 on, and a filter that removes a third of names on top "
        "of it cannot rescue a losing base book -- ALL itself may already trail SPY, in which "
        "case FILTER beating ALL is a win against the wrong yardstick. It is also possible RAND "
        "alone beats ALL (fewer, larger equal slots trading less often can be cheaper in fees and "
        "concentration than a big flat book), in which case FILTER must clear RAND specifically, "
        "not just ALL, to say MAX did anything. A MAX measured over 21 session closes with no "
        "intraday high is a coarser, noisier version of Bali-Cakici-Whitelaw's own measure, so "
        "even a real effect may show up weaker here than in the original paper."
    ),
    candidates=(
        _v("ALL", LotteryParams(mode="all"), "unfiltered: the 100 most traded pool members, equal weight"),
        _v(
            "FILTER",
            LotteryParams(mode="filter"),
            "drop the pool's third with the largest trailing-21-day max one-day return",
        ),
        _v(
            "RAND1",
            LotteryParams(mode="rand", seed=1),
            "control: drop an equal-size random third (hash seed 1), no opinion on MAX",
        ),
        _v(
            "RAND2",
            LotteryParams(mode="rand", seed=2),
            "control: drop an equal-size random third (hash seed 2), no opinion on MAX",
        ),
    ),
    seen_keys=(
        "concept:stock-max-daily-return-filter",
        "concept:lottery-stock-exclusion",
        "concept:bali-cakici-whitelaw-max",
    ),
)
