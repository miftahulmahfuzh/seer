"""M0553 — M0510's fat-tail pick, dealt evenly across volatility thirds, the way M0534 dealt M0530's.

M0553 was queued to answer: once a stock-picking signal is known to be real (it beats its own
mirror and its own blind draws, not just SPY), does volatility balancing -- splitting the ranked
pool into thirds by each name's own volatility and taking an even share from each third, so the
book's risk mix matches the pool's whichever way it ranks -- cut the book's worst fall, and at
what cost in return?

The host is M0510-HIGHK: of the lab's dev-eligible stock-picking signals that are not already
kin-blocked, it is the one whose idea arm (highest 126-session excess kurtosis, i.e. the most
lottery-like, fat-tailed names) actually beat its own mirror (LOWK, the paper's intended pick,
DSR 0.870, failed) and both of its blind draws (R1 DSR 0.898, R2 DSR 0.895, both failed) --
HIGHK alone cleared the luck bar, DSR 0.927. M0530 (the leverage-effect score M0534 balanced)
is not eligible for this role twice over: it is M0534's own parent, and its own idea arm lost to
its mirror, so VN here is a materially different test than M0534's rather than the same balancing
trick run on the same score again.

VN deals the same kurtosis score (M0510's own `scored_names`, which already returns each name's
126-session volatility alongside its kurtosis, so no second volatility window is invented here)
into three volatility thirds and takes an even share from each, M0534's exact mechanism. PLAIN
ranks the identical pool straight through with no thirds split, at the same keep-band and cadence
as VN, so turnover and hysteresis are held fixed and only the dealing differs -- it is a fresh
construction, not a re-run of M0510-HIGHK, which carried no keep-band at all and is quoted only as
background. VN-NOSW is VN with the switch off: the no-opinion arm that prices the switch apart
from the balancing (M0534's NEG-VN). DRAW1-VN/DRAW2-VN replace the kurtosis score with a hash
re-drawn every month, so the draw's turnover tracks the treatment's own monthly re-ranking instead
of the sticky per-symbol hash M0510's R1/R2 used (a draw with no date term barely turns over,
insight: a matched draw needs a date term or it understates turnover against a score that moves
every month).

Reads only bars dated <= data_date. Pure.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0510_realized_kurtosis import NEED, scored_names
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 12)
_MODES = ("highk", "blind")
MARKET = "SPY"
BINS = 3
KEEP_BAND = 10


@dataclass(frozen=True, slots=True)
class KvParams:
    """``inner`` is the host's screen, switch and book size; ``balanced`` deals the ranked pool
    evenly across volatility thirds (M0534's mechanism) instead of ranking it straight through;
    ``mode`` picks M0510's kurtosis score or a monthly hash draw keyed by ``seed``."""

    inner: FactorParams
    balanced: bool = True
    mode: str = "highk"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if self.mode == "blind" and self.seed <= 0:
            raise ValueError("a blind draw needs a positive seed")

    def as_dict(self) -> dict[str, str]:
        out = {"balanced": str(self.balanced), "mode": self.mode, "seed": str(self.seed)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> KvParams:
    if not isinstance(params, KvParams):
        raise TypeError(f"params must be KvParams, got {type(params).__name__}")
    return params


def _monthly_hash(seed: int, symbol: str, data_date: date) -> float:
    """A hash re-drawn every month (unlike M0510's sticky per-symbol draw), so its turnover
    tracks a score that is itself re-ranked every month instead of sitting still."""
    salt = f"{seed}|{symbol}|{data_date.year}-{data_date.month:02d}"
    digest = hashlib.sha256(salt.encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2.0**64


def choose(rows: list[FactorRow], scores: dict[str, tuple[float, float]], held: frozenset[str],
           p: KvParams, data_date: date) -> list[FactorRow]:
    kept = [(r, scores[r.symbol][0], scores[r.symbol][1]) for r in rows
            if r.symbol not in EXCLUDED and r.symbol in scores]
    if p.mode == "blind":
        kept = [(r, _monthly_hash(p.seed, r.symbol, data_date), vol) for r, _kurt, vol in kept]
    if p.balanced:
        # Rank within each volatility third, then deal the thirds out in turn (M0534's mechanism):
        # any prefix of the result holds the thirds as evenly as its length allows.
        by_level = sorted(kept, key=lambda t: (t[2], t[0].symbol))
        n = len(by_level)
        bins: list[list[FactorRow]] = []
        for b in range(BINS):
            part = by_level[b * n // BINS : (b + 1) * n // BINS]
            part.sort(key=lambda t: (-t[1], t[0].symbol))
            bins.append([t[0] for t in part])
        ranked: list[FactorRow] = []
        for k in range(max((len(b) for b in bins), default=0)):
            for b in bins:
                if k < len(b):
                    ranked.append(b[k])
    else:
        ranked = [t[0] for t in sorted(kept, key=lambda t: (-t[1], t[0].symbol))]
    top = p.inner.top
    keep = [r for r in ranked[: top + KEEP_BAND] if r.symbol in held][:top]
    have = {r.symbol for r in keep}
    for r in ranked:
        if len(keep) >= top:
            break
        if r.symbol not in have:
            keep.append(r)
            have.add(r.symbol)
    return keep


@dataclass
class KvPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class KurtosisVolBalancedAllocator:
    """M0510's fat-tail pick, dealt evenly across volatility thirds instead of ranked straight."""

    id = "M0553"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), NEED)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {MARKET}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: KvPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, held: frozenset[str], p: KvParams
             ) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            scores = scored_names(history, syms, data_date)
        else:
            scores = prepared.cache.get(data_date) or scored_names(history, syms, data_date)
            prepared.cache[data_date] = scores
        return targets_from_rows(choose(rows, scores, held, p, data_date), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> KvPrepared:
        return KvPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, KvPrepared):
            raise TypeError(f"prepared must be KvPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, held, _check(params))


KVBAL = KurtosisVolBalancedAllocator()


def _v(suffix: str, params: KvParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0553-{suffix}", family="M0553", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=KVBAL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0553",
    name=(
        "Deal a signal book evenly from calm, middle and jumpy stocks: does volatility balancing "
        "cut the fall of a book that carries a real signal?"
    ),
    family="stock-portfolio-construction",
    source_kind="variation",
    parent_id="M0534",
    source_ref=(
        "Variation of M0534 (itself a variation of M0530); host signal from M0510 (Amaya, "
        "Christoffersen, Jacobs & Vasquez 2015, realized kurtosis)"
    ),
    hypothesis=(
        "M0534 asked whether volatility balancing (ranking within volatility thirds, then dealing "
        "an even share from each third) changes what M0530's leverage-effect score is worth, and "
        "found neither side of that score cleared the luck bar once balanced. This method asks the "
        "same construction question of a host signal that is already known to be real: M0510's "
        "fat-tail pick, HIGHK (highest 126-session excess kurtosis), is the lab's dev-eligible "
        "stock-picking idea arm that beat both its own mirror (LOWK, the paper's intended pick, "
        "DSR 0.870, failed) and its own blind draws (R1 DSR 0.898, R2 DSR 0.895, both failed) -- "
        "HIGHK alone cleared DSR 0.927, and its kin read clean under the hard gate's D14 behaviour "
        "check. Same score as M0510 (excess kurtosis of the last 126 daily returns, computed "
        "alongside each name's own volatility over the identical window, so no second lookback is "
        "invented), same F4 screen, 20-name book, SPY 200-day switch, monthly, fractional shares "
        "at Gotrade's real fees on the owner's top-up (MONTHLY_HOLD_FRAC_GOTRADE). VN deals the "
        "ranked pool into three volatility thirds and takes an even share from each in turn, "
        "M0534's exact mechanism, with a keep band of 10 against monthly churn. PLAIN ranks the "
        "identical pool straight through with no thirds split, same keep band and cadence as VN, "
        "so the dealing is the only thing that differs between the two -- a fresh construction, "
        "not a re-run of M0510-HIGHK, which carried no keep band at all (M0510-HIGHK: funded "
        "+11.8%/yr vs SPY +7.2%, maxDD 29.6%, DSR 0.927, quoted here as background, not repeated). "
        "VN-NOSW is VN with the switch off: the no-opinion arm that prices the switch apart from "
        "the balancing. DRAW1-VN/DRAW2-VN replace the kurtosis score with a hash re-drawn every "
        "month (unlike M0510's own sticky per-symbol draw, which barely turns over against a "
        "score that re-ranks monthly) and are dealt through the identical thirds and band. To "
        "count, VN must shrink the worst fall against PLAIN by more than it gives up in CAGR, beat "
        "both draws, and keep a positive 2009-2015 edge against SPY."
    ),
    expected_failure=(
        "Four ways, in order of likelihood. (1) Balancing pulls toward the pool's calmer third, "
        "which in a book already picking the most lottery-like names may simply dilute the signal: "
        "VN lands between PLAIN and the draws rather than clearly safer than PLAIN, echoing M0534's "
        "finding that neutralising a score mostly erodes it. (2) The fall does shrink, but only by "
        "what the lost return would have paid for anyway -- VN's MAR is no better than PLAIN's, so "
        "the trade is a wash dressed as safety. (3) Published 2015, dev window ends 2015-10-16: "
        "even a clean dev win on HIGHK should be expected to fade out of sample, as this lab has "
        "watched other strong, recently-published dev results invert. (4) HIGHK itself already "
        "trails SPY in 2009-2015 (M0510's own verdict); if VN inherits that, no amount of balancing "
        "makes the book worth building on, whatever it does to the fall."
    ),
    candidates=(
        _v("VN", KvParams(N20, True, "highk"),
           "Highest 126-session kurtosis, dealt 7/7/6 across volatility thirds, behind the switch: the treatment"),
        _v("PLAIN", KvParams(N20, False, "highk"),
           "Same pool, score, keep band and switch, ranked straight through with no thirds split: isolates the dealing"),
        _v("VN-NOSW", KvParams(N20_NOTREND, True, "highk"),
           "VN always invested, no switch: the no-opinion arm that prices the switch apart from the balancing"),
        _v("DRAW1-VN", KvParams(N20, True, "blind", 5531),
           "Control: hash draw re-drawn every month, seed 5531, dealt through the identical thirds and band"),
        _v("DRAW2-VN", KvParams(N20, True, "blind", 5532),
           "Control: hash draw re-drawn every month, seed 5532, measures draw noise"),
    ),
    seen_keys=(
        "concept:volatility-thirds-dealing-on-a-verified-signal",
        "concept:kurtosis-vol-balanced",
    ),
)
