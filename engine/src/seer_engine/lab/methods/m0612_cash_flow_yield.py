"""M0612 -- Cash-flow yield: Lakonishok, Shleifer and Vishny's value signal on cash, not earnings.

Source: Lakonishok, J., Shleifer, A., Vishny, R. (1994), "Contrarian Investment, Extrapolation and
Risk", Journal of Finance 49(5), 1541-1578. Reserved by Sera batch 20261113-0828 as an ``idea`` row;
this file refines it and keeps its id.

Why this shape. Every value book this lab has run ranks on price arithmetic (book-to-market,
discount from the yearly high) or on reported earnings. LSV's claim is that *cash flow to price*
sorts stocks about as well as book-to-market and is harder to dress up than earnings (Sloan's
accruals trap: M0369 and M0574 chased that and were blocked on panel coverage, so nothing on the
accruals side was ever measured). Cash flow yield here is net operating cash flow divided by company
size (shares outstanding as filed, times the close as it printed).

Assumption written down because the spec said "trailing four quarters": the filing panel does not
difference the year-to-date figures 10-Qs carry for cash flow (``fundamentals/panel.py``: "this
module does not difference YTD facts"), so the numerator is the **latest fiscal year's** operating
cash flow visible by the day (a flow from a year that ended at most ``MAX_FY_AGE_DAYS`` ago). It
moves once a year per company, hence the buffer that keeps incumbents.

Filings begin 2009-04, so before the panel scores ``MIN_POOL`` companies every arm holds SPY (same
device as M0569/M0276). The early dev stretch is SPY's own curve; the method cannot reach four
walk-forward folds, so it is **not promotable by construction** and runs as evidence, under
``lab run --allow-coverage`` as M0277 and M0279 did.

How it chooses, on each monthly check (``monthly-hold-frac-gotrade``):

    * THE SWITCH (all arms but the two NOSW arms): SPY close above its 200-day mean. Below it, the
      book is in cash. Once the pool is big enough, a failed switch means no targets.
    * THE POOL. Index members (not SPY) with a bar on the day, close >= $5, 20-session mean trading
      value above $20M, a visible fiscal year of operating cash flow ending within
      ``MAX_FY_AGE_DAYS``, and company size >= $500M. One listing per company: listings with the
      identical cash flow and fiscal year end are one filer (GOOG/GOOGL...); sizes are summed and
      the most-traded listing kept.
    * THE SCORE. Cash-flow yield = operating cash flow / company size.
    * THE BOOK. 20 names, equal slots, fully invested, incumbents keep their slot while within the
      best ``BUFFER`` x 20 of their arm's order.

Arms, 20 names, same pool, same fees:

    CFY20        the idea, behind the switch
    LO20         the mirror: lowest cash-flow yield first (the paper's growth leg), behind the switch
    RANDOM20     the opinion-free arm: the pool in a yearly-redrawn hash order, behind the switch
    CFY20-NOSW   the idea with no switch
    RANDOM20-NOSW  the no-opinion arm with no switch: with RANDOM20 and CFY20-NOSW this is the
                 2x2 that prices the switch's habit apart from the signal

Market-aware (``market_fields = ("fundamentals", "shares")``). Pure: reads only bars dated
``<= data_date``, facts filed ``<= data_date`` and share counts public by ``data_date``.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.fundamentals import ladder
from seer_engine.fundamentals.panel import KIND_ANNUAL
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.indicators import mean_dollar_volume_window, sma_window

ADDED = date(2026, 11, 13)

DV_N = 20
MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME = 20_000_000.0
MIN_MARKET_VALUE = 500_000_000.0  # below this a filed share count is usually in the wrong units
MAX_FY_AGE_DAYS = 480
MIN_POOL = 150  # scored companies needed before the book acts; below it, hold SPY
BUFFER = 2
MARKET = "SPY"
SWITCH_N = 200

ARMS = ("hi", "lo", "random")


@dataclass(frozen=True, slots=True)
class CfyParams:
    """``top`` names held; ``arm`` which order fills them; ``switch`` whether the SPY 200-day
    switch applies; ``seed`` the random arm's hash seed."""

    top: int = 20
    arm: str = "hi"
    switch: bool = True
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 100:
            raise ValueError(f"top must be an int in [1, 100], got {self.top!r}")
        if self.arm not in ARMS:
            raise ValueError(f"arm must be one of {ARMS}, got {self.arm!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if self.arm != "random" and self.seed != 0:
            raise ValueError("seed is for the random arm only")

    def as_dict(self) -> dict[str, str]:
        out = {
            "top": str(self.top),
            "arm": self.arm,
            "score": "operating_cash_flow_fy/market_value",
            "switch": f"SPY:{SWITCH_N}" if self.switch else "none",
            "min_pool": str(MIN_POOL),
            "before_pool": MARKET,
            "buffer": str(BUFFER),
            "max_fy_age_days": str(MAX_FY_AGE_DAYS),
            "min_price": "5",
            "min_dollar_volume": "20000000",
            "min_market_value": "500000000",
            "dv_n": str(DV_N),
        }
        if self.arm == "random":
            out["seed"] = str(self.seed)
            out["redraw"] = "yearly"
        return out


def _check(params: object) -> CfyParams:
    if not isinstance(params, CfyParams):
        raise TypeError(f"params must be CfyParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True)
class CfyRow:
    symbol: str
    close: float
    dollar_volume: float
    cfy: float


@dataclass(frozen=True, slots=True, eq=False)
class CfyPrepared:
    history: Mapping[str, History]
    market: Any  # None on the history-only path


def _fin(x: float | None) -> bool:
    return x is not None and math.isfinite(x)


def operating_cash(sf: Any, t: date) -> tuple[float, date] | None:
    """``(operating cash flow, fiscal year end)`` of the latest fiscal year visible at ``t``, or
    None when none is visible or it ended more than ``MAX_FY_AGE_DAYS`` ago."""
    annual = {pe: e[0].val for pe, e in sf._best_by_period(ladder.OPERATING_CASH_FLOW, KIND_ANNUAL, t).items()}
    if not annual:
        return None
    fy0 = max(annual)
    if (t - fy0).days > MAX_FY_AGE_DAYS:
        return None
    v = annual[fy0]
    return (float(v), fy0) if _fin(v) else None


def _dollar_volume(h: History, i: int) -> float:
    close = h.close[i + 1 - DV_N : i + 1].reshape(1, DV_N)
    volume = h.volume[i + 1 - DV_N : i + 1].reshape(1, DV_N)
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(mean_dollar_volume_window(close, volume, DV_N)[0])


def switch_on(history: Mapping[str, History], data_date: date) -> bool:
    """SPY close strictly above its 200-day mean on ``data_date``; False without the bars."""
    h = history.get(MARKET)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < SWITCH_N:
        return False
    window = h.close[i + 1 - SWITCH_N : i + 1].reshape(1, SWITCH_N)
    sma = float(sma_window(window, SWITCH_N)[0])
    return bool(np.isfinite(sma) and window[0, -1] > sma)


def pool(prepared: CfyPrepared, members: AbstractSet[str], data_date: date) -> list[CfyRow]:
    """The scored pool on ``data_date``, one listing per company, sorted by symbol."""
    m = prepared.market
    if m is None:
        return []
    groups: dict[tuple[float, date], list[tuple[str, float, float, float]]] = {}
    for s in sorted(members):
        if s == MARKET:
            continue
        h = prepared.history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < DV_N:
            continue
        close = float(h.close[i])
        if not math.isfinite(close) or close < MIN_PRICE:
            continue
        dv = _dollar_volume(h, i)
        if not math.isfinite(dv) or not dv > MIN_DOLLAR_VOLUME:
            continue
        sf = m.fundamentals.get(s)
        if sf is None:
            continue
        oc = operating_cash(sf, data_date)
        if oc is None:
            continue
        mv = m.market_value(s, data_date)
        if not _fin(mv) or mv < MIN_MARKET_VALUE:  # type: ignore[operator]
            continue
        groups.setdefault(oc, []).append((s, close, dv, float(mv)))
    out: list[CfyRow] = []
    for (ocf, _fy0), listings in groups.items():
        size = sum(x[3] for x in listings)
        s, close, dv, _mv = max(listings, key=lambda x: (x[2], x[0]))
        out.append(CfyRow(s, close, dv, ocf / size))
    out.sort(key=lambda r: r.symbol)
    return out


def _draw(seed: int, symbol: str, data_date: date) -> int:
    key = f"{seed}|{symbol}|{data_date.year:04d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def order(rows: list[CfyRow], data_date: date, p: CfyParams) -> list[str]:
    """The arm's preference order over the whole pool."""
    if p.arm == "hi":
        key = lambda r: (-r.cfy, r.symbol)  # noqa: E731
    elif p.arm == "lo":
        key = lambda r: (r.cfy, r.symbol)  # noqa: E731
    else:
        key = lambda r: (_draw(p.seed, r.symbol, data_date), r.symbol)  # noqa: E731
    return [r.symbol for r in sorted(rows, key=key)]


def choose(ranked: list[str], held: frozenset[str], top: int) -> list[str]:
    """Incumbents within the best ``BUFFER * top`` keep their slot; the rest fill in rank order."""
    keep_zone = set(ranked[: BUFFER * top])
    kept = [s for s in ranked if s in held and s in keep_zone][:top]
    chosen = list(kept)
    for s in ranked:
        if len(chosen) >= top:
            break
        if s not in chosen:
            chosen.append(s)
    return chosen


class CashFlowYieldAllocator:
    """Twenty index members chosen by operating cash flow over company size (or a control order),
    equal slots, fully invested; cash while SPY is below its 200-day mean (switch arms); plain SPY
    until the filing panel scores at least ``MIN_POOL`` companies."""

    id = "M0612"
    market_fields = ("fundamentals", "shares")

    def lookback(self, params: Any) -> int:
        _check(params)
        return max(DV_N, SWITCH_N)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (MARKET,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (MARKET,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _spy(self, prepared: CfyPrepared, data_date: date) -> tuple[Target, ...]:
        h = prepared.history.get(MARKET)
        if h is None or h.index_of(data_date) is None:
            return ()
        t = target_from_close(MARKET, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def _run(self, prepared: CfyPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: CfyParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        rows = pool(prepared, members, data_date)
        if len(rows) < MIN_POOL:
            return self._spy(prepared, data_date)
        if p.switch and not switch_on(prepared.history, data_date):
            return ()
        picks = choose(order(rows, data_date, p), held, p.top)
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in picks:
            h = prepared.history.get(s)
            if h is None or h.index_of(data_date) is None:
                continue
            t = target_from_close(s, last_close(h, data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no filings, no share counts, so no signal and no target."""
        return self._run(CfyPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CfyPrepared:
        return CfyPrepared(history, None)

    def prepare_market(self, market: Any) -> CfyPrepared:
        if len(getattr(market, "fundamentals", ())) == 0 or len(getattr(market, "shares", ())) == 0:
            return CfyPrepared(market.history, None)
        return CfyPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CfyPrepared):
            raise TypeError(f"prepared must be CfyPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


CASH_FLOW_YIELD = CashFlowYieldAllocator()


def _v(suffix: str, params: CfyParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0612-{suffix}", family="M0612", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CASH_FLOW_YIELD, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0612",
    name="Cash-flow yield: the 20 index members that generate the most operating cash for each dollar of market value, behind the 200-day switch",
    family="stock-cash-flow-yield",
    source_kind="paper",
    source_ref=(
        "Lakonishok, J., Shleifer, A., Vishny, R. (1994), Contrarian Investment, Extrapolation and "
        "Risk, Journal of Finance 49(5), 1541-1578"
    ),
    parent_id=None,
    hypothesis=(
        "Published 1994, so the dev window (ends 2015) can show an edge only after the crowd had "
        "twenty years to trade it. LSV found cash-flow-to-price sorts US stocks about as well as "
        "book-to-market. Rank F4-screened index members ($5, $20M/day, size >= $500M, one listing "
        "per company) on the latest fiscal year's net operating cash flow (SEC filings, usable only "
        "from each filing date) over company size, highest first; hold 20 equal slots monthly in "
        "fractional shares at Gotrade's real fees, incumbents kept within the best 40, behind the "
        "SPY 200-day switch (cash while SPY is under its mean). Assumption: the spec's trailing "
        "four quarters is replaced by the latest fiscal year, because the filing panel does not "
        "difference year-to-date cash-flow facts. Filings begin 2009-04, so every arm holds SPY "
        "until the panel scores 150 companies (about 2010); the book trades roughly six dev years, "
        "2010-2015, and the early stretch is SPY's own curve: not promotable by construction, run "
        "as evidence under --allow-coverage (as M0277 and M0279). Closest recorded: M0574 and "
        "M0369 (accruals, never run: blocked on coverage) and M0569 (gross profitability on the "
        "same chassis, no 200-day switch, rejected). No arm repeats a recorded book: the switch "
        "plus a cash-flow score is new. Arms: CFY20 (the idea), LO20 (the mirror, lowest yield), "
        "RANDOM20 (no opinion: pool in a yearly-redrawn hash order, same switch), CFY20-NOSW "
        "and RANDOM20-NOSW (the same two without the switch, so the 2x2 prices the switch habit "
        "apart from the signal). Predictions, judged first on 2010-2015 against recorded SPY: (1) "
        "CFY20 beats LO20 by at least 3 points a year; (2) CFY20 beats RANDOM20 by at least 2 "
        "points a year; (3) CFY20 beats SPY. Success is (1) and (2) together on the dev store and "
        "the survivorship-check store."
    ),
    expected_failure=(
        "Most likely first. (1) The era: 2010-2015 rewarded large growth names and punished cheap, "
        "cash-rich ones, so CFY20 can beat LO20 and RANDOM20 without beating SPY. (2) Cash-flow "
        "yield among index members is dominated by financials and energy, where operating cash "
        "flow is lumpy or odd (bank working capital swings, commodity cycles), so the top 20 is "
        "a sector bet. (3) The 200-day switch spends time in cash during a rising decade, costing "
        "points the signal cannot repay (insight 462); the NOSW arms price that. (4) A yearly "
        "numerator plus six years is thin: a few points a year between two 20-name books is within "
        "luck. The whole-window row will fail the walk-forward gate by construction."
    ),
    candidates=(
        _v("CFY20", CfyParams(20, "hi", True), "The idea: top 20 by operating cash flow over size, behind the 200-day switch"),
        _v("LO20", CfyParams(20, "lo", True), "The mirror: the 20 lowest-yield names, same switch"),
        _v("RANDOM20", CfyParams(20, "random", True, seed=1),
           "No opinion: 20 names from the whole pool in a yearly-redrawn hash order, same switch"),
        _v("CFY20-NOSW", CfyParams(20, "hi", False), "The idea with no switch: prices the switch habit"),
        _v("RANDOM20-NOSW", CfyParams(20, "random", False, seed=1),
           "No opinion and no switch: the always-invested, opinion-free book"),
    ),
    seen_keys=("concept:cash-flow-yield",),
)
