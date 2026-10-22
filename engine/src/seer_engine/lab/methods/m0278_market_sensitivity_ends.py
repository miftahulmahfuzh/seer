"""M0278 — Jumpy versus calm index members: is "both ends of a ranking win" just market sensitivity?

Source: Black, Jensen & Scholes (1972), "The Capital Asset Pricing Model: Some Empirical Tests";
Frazzini & Pedersen (2014), "Betting Against Beta", J. Financial Economics 111(1); Ang, Hodrick,
Xing & Zhang (2006) on idiosyncratic volatility. Reserved by Sera batch 20261022-1954 as an
``idea`` row with M0275 as its parent; this file refines it and keeps its id.

WHY. In M0275 (asset growth) the 30 lowest and the 30 highest growers both beat a matched blind
draw from the same pool by 3-4 points a year over 2010-2015 and finished 0.6 points apart. When the
two ends of a ranking both beat the middle, the ranking is not what paid: what the two ends share
is that they are *unusual* names, and unusual names in a rising market are often the jumpier ones.
This method asks that question directly, on the whole dev window rather than five rising years:
rank index members on how hard they move with the market (beta) and, as a second lens, on how much
they move at all (volatility), and hold each end beside a blind draw of the jumpy end's size and
churn. Beta is the oldest anomaly in the book -- high-beta stocks earn about what low-beta stocks
earn, not the extra the textbook says they should -- so the prediction is that the jumpy end wins
the rising stretches and gives it all back in the falls.

THE SIGNAL, POINT IN TIME. On each monthly check, for every index member with a bar dated
``data_date``: take SPY's last ``WINDOW + 1`` sessions ending at ``data_date``, keep the dates on
which the member also printed a bar, and read daily close-to-close returns over consecutive kept
dates for both (a gap makes a two-day return on both sides, so the pair stays matched). A member
with fewer than ``MIN_RETURNS`` paired returns is not scored. Beta is cov(member, SPY) / var(SPY);
volatility is the standard deviation of the member's own returns. Two members answering the
identical beta and volatility are one company listed twice (GOOG/GOOGL before 2014): the one with
the larger 60-session trading value is kept.

ARMS, one scored pool, equal slots, fully invested, monthly, no switch:

    HB30      the 30 members with the HIGHEST beta -- the jumpy end
    LB30      the 30 with the LOWEST beta -- the calm end (betting against beta, long side only)
    HB30-PLC  placebo: HB30's size and monthly entry count drawn blind from the same pool
              (``lab.control_draw``'s matched draw): the no-opinion arm, same fees, no signal
    HV30      the 30 with the HIGHEST volatility -- jumpy by its own moves, not the market's
    LV30      the 30 with the LOWEST volatility

HB30 against LB30 says whether sensitivity is a signal; HB30 against HB30-PLC prices acting on it
(the third arm the lab's mirror rule asks for). The placebo is drawn against HB30 because the
question is whether the jumpy end's lead over "a random 30" is real. No arm steps aside, so there
is no gate habit to price with a 2x2.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly top-up. Pure: reads only bars dated on or before ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED

ADDED = date(2026, 10, 22)
BENCH = "SPY"
WINDOW = 252  # sessions of SPY returns the beta and volatility are read over
MIN_RETURNS = 200  # paired daily returns a member needs to be scored
DV_N = 60  # sessions of trading value that decide which listing of one company stays
SIGNALS = ("beta", "vol")
SIDES = ("high", "low", "control")


@dataclass(frozen=True, slots=True)
class SensitivityParams:
    """``top`` names held; ``signal`` beta or vol; ``side`` high, low or control (the matched-draw
    placebo of the high book on ``signal``); ``seed`` the placebo's hash seed."""

    top: int
    signal: str = "beta"
    side: str = "high"
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"top": str(self.top), "signal": self.signal, "side": self.side,
               "seed": str(self.seed), "window": str(WINDOW), "min_returns": str(MIN_RETURNS),
               "dv_n": str(DV_N), "class_rule": "identical-beta-and-vol"}
        if self.side == "control":
            out["control_rule"] = control_draw.RULE_ID
        return out


def _check(params: object) -> SensitivityParams:
    if not isinstance(params, SensitivityParams):
        raise TypeError(f"params must be SensitivityParams, got {type(params).__name__}")
    return params


def _inner(p: SensitivityParams) -> int:
    return max(WINDOW + 1, DV_N)


def sensitivity(h: History, spy: History, data_date: date) -> tuple[float, float] | None:
    """(beta to SPY, daily volatility) over SPY's last ``WINDOW`` sessions to ``data_date``, or None."""
    j = spy.index_of(data_date)
    if j is None or h.index_of(data_date) is None:
        return None
    lo = max(0, j - WINDOW)
    spy_dates = spy.dates[lo : j + 1]
    pos = np.searchsorted(h.dates, spy_dates)
    pos_c = np.minimum(pos, len(h) - 1)
    hit = h.dates[pos_c] == spy_dates
    if int(hit.sum()) < MIN_RETURNS + 1:
        return None
    s_close = h.close[pos_c[hit]]
    m_close = spy.close[lo : j + 1][hit]
    with np.errstate(invalid="ignore", divide="ignore"):
        rs = s_close[1:] / s_close[:-1] - 1.0
        rm = m_close[1:] / m_close[:-1] - 1.0
    ok = np.isfinite(rs) & np.isfinite(rm)
    if int(ok.sum()) < MIN_RETURNS:
        return None
    rs, rm = rs[ok], rm[ok]
    var_m = float(np.var(rm))
    if not np.isfinite(var_m) or var_m <= 0.0:
        return None
    beta = float(np.mean((rs - rs.mean()) * (rm - rm.mean()))) / var_m
    vol = float(np.std(rs))
    if not (np.isfinite(beta) and np.isfinite(vol)):
        return None
    return beta, vol


def scored_pool(history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                signal: str) -> dict[str, float]:
    """The ``signal`` score of every member that can be held on ``data_date``, one per company."""
    spy = history.get(BENCH)
    if spy is None:
        return {}
    by_company: dict[tuple[float, float], tuple[float, str, float]] = {}
    for s in sorted(members):
        if s in EXCLUDED:
            continue
        h = history.get(s)
        if h is None:
            continue
        read = sensitivity(h, spy, data_date)
        if read is None:
            continue
        beta, vol = read
        dv = trading_value(h, data_date, DV_N)
        key = (round(beta, 12), round(vol, 12))
        seen = by_company.get(key)
        score = beta if signal == "beta" else vol
        if seen is None or (dv, s) > (seen[0], seen[1]):
            by_company[key] = (dv, s, score)
    return {s: v for _, s, v in by_company.values()}


def ranked(pool: Mapping[str, float], side: str) -> list[str]:
    """``pool`` highest first (``high``) or lowest first (``low``), ties by symbol."""
    if side == "high":
        return sorted(pool, key=lambda s: (-pool[s], s))
    return sorted(pool, key=lambda s: (pool[s], s))


class SensitivityAllocator:
    """The ``top`` members with the highest (or lowest) trailing beta to SPY or volatility, or a
    matched blind draw of the high book from the same pool; equal slots, fully invested."""

    id = "M0278"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        inner = _inner(p)
        return control_draw.lookback_for(inner) if p.side == "control" else inner

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _select(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                p: SensitivityParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the scored pool, the high book) on ``data_date`` -- what the control is matched to."""
        pool = scored_pool(history, members, data_date, p.signal)
        if not pool:
            return (), ()
        return tuple(sorted(pool)), tuple(ranked(pool, "high")[: p.top])

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if p.side == "control":
            names = control_draw.matched_book(
                lambda d: self._select(history, members, d, p),
                data_date, held, tag="M0278", seed=p.seed,
            )
        else:
            names = ranked(scored_pool(history, members, data_date, p.signal), p.side)[: p.top]
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history: Mapping[str, History]) -> Mapping[str, History]:
        return history

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


SENSITIVITY = SensitivityAllocator()


def _v(suffix: str, params: SensitivityParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0278-{suffix}", family="M0278", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SENSITIVITY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0278",
    name=(
        "Jumpy versus calm index members: is 'both ends of a ranking win' just market sensitivity?"
    ),
    family="stock-market-beta",
    source_kind="variation",
    source_ref=(
        "Black, Jensen & Scholes (1972); Frazzini & Pedersen (2014) Betting Against Beta, JFE "
        "111(1); Ang, Hodrick, Xing & Zhang (2006) idiosyncratic volatility; lab M0275"
    ),
    parent_id="M0275",
    hypothesis=(
        "Published 1972 (flat beta-return line) and 2014 (betting against beta), so the dev window "
        "1996-2015 is long after the first and mostly before the second. In M0275 the 30 lowest "
        "and 30 highest asset growers both beat a matched blind draw by 3-4 points a year over "
        "2010-2015 and finished 0.6 points apart: the ranking carried no signal and the lead came, "
        "the hypothesis says, from holding unusual, more market-sensitive names in a rising "
        "market. Signal: each month, for each index member with a bar, beta to SPY and daily "
        "volatility over SPY's last 252 sessions (at least 200 paired daily returns), one listing "
        "per company. Arms: HB30 (30 highest beta), LB30 (30 lowest beta), HB30-PLC (HB30's size "
        "and monthly entry count drawn blind from the same pool: the no-opinion arm), HV30 and "
        "LV30 (30 highest and lowest volatility). Equal slots, monthly, fully invested, no switch, "
        "fractional shares at Gotrade's real fees on the owner's monthly top-up. Predictions "
        "written before any result, on de-funded monthly returns: HB30 beats HB30-PLC in 2003-2007 "
        "and in 2009-2015 and loses to it in 2000-2002 and in 2008, ending within 2 points a year "
        "of it over 1996-2015 with a worst fall at least 15 points deeper; LB30's worst fall is "
        "the shallowest of the five and its twenty-year return is within 2 points a year of HB30's; "
        "the volatility arms tell the same story as the beta arms. If HB30 leads the placebo by "
        "3 points or more in 2009-2015, the lab's near misses that led SPY there are suspect of a "
        "high-beta lean."
    ),
    expected_failure=(
        "Nobody expects an eligible arm here; the method is a diagnostic. Ways the prediction "
        "itself can fail: (1) the jumpy end does not win 2009-2015 at all -- the 2011 and 2015 "
        "sell-offs and the long rally of the calm, dividend-paying names in 2011-2014 favoured low "
        "beta, so the 'unusual names in a rising market' story for M0275 would be wrong and its "
        "both-ends lead needs another explanation; (2) the high-beta book is dominated by the "
        "1999-2000 technology bubble and its collapse, so its twenty-year number is one episode, "
        "not a property; (3) LB30 beats the placebo by a wide margin before 2009 and nothing after "
        "(the low-risk anomaly was crowded once Frazzini-Pedersen and the low-volatility ETFs "
        "arrived in 2011-2014) -- a published anomaly fading; (4) all arms trail SPY on the "
        "owner's deposits through fees on 30 equal slots and the equal-weight lean against the "
        "big-company drift. None is a reason to tune the 252-session window or the book size."
    ),
    candidates=(
        _v("HB30", SensitivityParams(30, signal="beta", side="high"),
           "The 30 members with the highest trailing one-year beta to SPY, monthly, no switch"),
        _v("LB30", SensitivityParams(30, signal="beta", side="low"),
           "The 30 members with the lowest trailing one-year beta to SPY"),
        _v("HB30-PLC", SensitivityParams(30, signal="beta", side="control", seed=1),
           "Placebo: HB30's book size and monthly entry count drawn blind from the same scored "
           "pool in a hash order, the no-opinion arm"),
        _v("HV30", SensitivityParams(30, signal="vol", side="high"),
           "The 30 members with the highest trailing one-year daily volatility"),
        _v("LV30", SensitivityParams(30, signal="vol", side="low"),
           "The 30 members with the lowest trailing one-year daily volatility"),
    ),
    seen_keys=(
        "concept:stock-beta-sort",
        "concept:betting-against-beta-long-only",
        "concept:high-beta-lean-diagnostic",
    ),
)
