"""M0572 — Does less turnover alone explain the plain-beta control's lead?

Variation of M0528. M0528's plain-beta control (REL-PLAIN: ordinary beta alone, lowest 20,
F4-screened, switch on) recorded this family's best DSR so far (0.871 at N=373) while trading
far less often (770 round trips, turnover 3.17/yr) than the downside-specific treatment
(1065 round trips, turnover 5.87/yr) over the same window, both holding the same 20-name book
size, at a similar return. M0528 never separated two explanations: the plain-beta ranking itself
picks a better book, or picking the same names but trading them less often is what raised the DSR.

This method keeps REL-PLAIN's exact ranking -- ordinary beta (M0528's ``_score`` in "plain" mode),
lowest 20, F4-screened, switch on -- and adds no new signal. It adds only the lab's standard
turnover-cutting device, already measured on three other families (M0344 residual momentum, M0413
plain 12-1 momentum, M0163 dividend yield): a held name stays while it ranks inside the top
``exit_rank`` by ordinary beta; only the free slots are filled from the top of the ranking.
``exit_rank`` equal to the book size (20) reproduces REL-PLAIN exactly through this allocator --
the no-opinion control, and the fidelity check in one. Wider bands trade the same 20 names less
often without changing who is eligible, so if DSR rises with the band, less turnover alone
explains the earlier lead; if it does not, the plain-beta ranking's edge is not a turnover
artifact.

Reads only bars dated <= d, via M0528's own ``_score`` function (ordinary-beta regression,
252-session window, >= 40 down days).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0353_daily_return_profile import ProfilePrepared
from seer_engine.lab.methods.m0528_relative_downside_beta import RelBetaParams, _score
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 12)
BENCH = "SPY"
DOWNSIDE_WINDOW = 252


@dataclass(frozen=True, slots=True)
class BetaBufferParams:
    """``rel`` must be M0528's plain-beta, lowest-side ranking; ``exit_rank`` is the rank a held
    name may fall to before it is sold. ``exit_rank == rel.inner.top`` keeps nobody for being
    close, so it reproduces REL-PLAIN's book exactly."""

    rel: RelBetaParams
    exit_rank: int = 20

    def __post_init__(self) -> None:
        if not isinstance(self.rel, RelBetaParams):
            raise TypeError(f"rel must be RelBetaParams, got {type(self.rel).__name__}")
        if self.rel.mode != "plain" or self.rel.side != "low":
            raise ValueError("rel must be the plain-beta, lowest-side ranking (REL-PLAIN)")
        if isinstance(self.exit_rank, bool) or not isinstance(self.exit_rank, int):
            raise TypeError(f"exit_rank must be an int, got {type(self.exit_rank).__name__}")
        if self.exit_rank < self.rel.inner.top:
            raise ValueError(
                f"exit_rank must be >= book size, got {self.exit_rank} < {self.rel.inner.top}"
            )

    @property
    def inner(self) -> FactorParams:
        return self.rel.inner

    def as_dict(self) -> dict[str, str]:
        out = {"exit_rank": str(self.exit_rank)}
        for k, v in self.rel.as_dict().items():
            out[f"rel.{k}"] = v
        return out


def _check(params: object) -> BetaBufferParams:
    if not isinstance(params, BetaBufferParams):
        raise TypeError(f"params must be BetaBufferParams, got {type(params).__name__}")
    return params


def choose_buffered(rows: list[FactorRow], prepared: ProfilePrepared, data_date: date,
                     held: frozenset[str], p: BetaBufferParams) -> list[FactorRow]:
    """Rank by ordinary beta (lowest first). A held name stays while its rank is within
    ``exit_rank``; the free slots, up to the book size, are filled from the top of the ranking."""
    spy = prepared.history.get(BENCH)
    if spy is None:
        return []
    scored: list[tuple[FactorRow, float]] = []
    for r in rows:
        h = prepared.history.get(r.symbol)
        if r.symbol in EXCLUDED or h is None or r.symbol == BENCH:
            continue
        s = _score(h, spy, data_date, p.rel)
        if s is not None:
            scored.append((r, s))
    scored.sort(key=lambda t: (t[1], t[0].symbol))
    ranked = [r for r, _ in scored]
    top = p.rel.inner.top
    keep = {r.symbol for r in ranked[: p.exit_rank] if r.symbol in held}
    kept = [r for r in ranked if r.symbol in keep][:top]
    kept_syms = {r.symbol for r in kept}
    fill = [r for r in ranked if r.symbol not in kept_syms][: top - len(kept)]
    chosen = kept + fill
    order = {r.symbol: i for i, r in enumerate(ranked)}
    return sorted(chosen, key=lambda r: order[r.symbol])


class BufferedBetaAllocator:
    """REL-PLAIN's ordinary-beta book, with held names kept while they stay inside ``exit_rank``."""

    id = "M0572"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), DOWNSIDE_WINDOW + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def prepare(self, history: Mapping[str, History]) -> ProfilePrepared:
        return ProfilePrepared(history, prepare_factor(history))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        prepared = ProfilePrepared(history, prepare_factor(history))
        return targets_from_rows(choose_buffered(rows, prepared, data_date, held, p), p)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ProfilePrepared):
            raise TypeError(f"prepared must be ProfilePrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose_buffered(rows, prepared, data_date, held, p), p)


BUFFERED = BufferedBetaAllocator()
REL_PLAIN_LO = RelBetaParams(N20, "low", "plain")


def _v(suffix: str, params: BetaBufferParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0572-{suffix}", family="M0572", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BUFFERED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0572",
    name="Does less turnover alone explain the plain-beta control's lead?",
    family="stock-downside-beta",
    source_kind="variation",
    source_ref="variation of M0528 (REL-PLAIN); rank-band hysteresis as measured in M0344, M0413, M0163",
    parent_id="M0528",
    hypothesis=(
        "M0528's plain-beta control (ordinary beta alone, lowest 20, F4-screened, switch on) "
        "recorded this family's best DSR so far (0.871 at N=373) while trading far less often "
        "(770 round trips, turnover 3.17/yr) than the downside-specific treatment (1065 round "
        "trips, turnover 5.87/yr) over the same window, both holding the same 20-name book size, "
        "at a similar return. This registers a variation that keeps the same ordinary-beta "
        "ranking but requires a larger rank gap before replacing a held name, cutting churn "
        "without changing the signal, to test whether less turnover alone -- not the beta "
        "definition -- is what raised this arm's DSR. BUF20 holds a name until it falls out of "
        "the top 20 (exit_rank == book size): this reproduces REL-PLAIN's book exactly through "
        "this allocator, so it is the no-opinion control and the fidelity check in one. BUF30 and "
        "BUF40 widen the band to the top 30 and top 40, the same rank-buffer device M0344 priced "
        "on residual momentum (0.3 points a year, deeper fall), M0413 on plain 12-1 momentum, and "
        "M0163 on yearly dividend yield (1.7 points): in all three, less turnover bought little or "
        "nothing. Frame unchanged throughout: F4's screen, SPY-200 trend gate, equal weights, "
        "monthly, fractional shares at Gotrade's real fees (MONTHLY_HOLD_FRAC_GOTRADE). To count, "
        "a buffered arm must raise the dev-window DSR above REL-PLAIN's 0.871 while keeping the "
        "drawdown and 2009-2015 record REL-PLAIN already cleared; if none does, the earlier DSR "
        "lead was the plain-beta ranking itself, not its lower turnover."
    ),
    expected_failure=(
        "By the pattern in M0344, M0413 and M0163, expect the buffer to cut round trips "
        "noticeably (REL-PLAIN already trades at about 3.17/yr, among the lowest in this family, "
        "so there may be little further to cut) while leaving CAGR and DSR within a point of "
        "BUF20 -- turnover-reduction devices have not yet raised a DSR in this lab, only lowered "
        "fees paid on names that would have been held anyway. If that holds here too, REL-PLAIN's "
        "lead over the downside treatment was never about trading less; it was a better-ranked "
        "book that happens to also turn over less, and this variation is rejected on 'buys no DSR'"
        " even if it is not rejected on return."
    ),
    candidates=(
        _v("BUF20", BetaBufferParams(REL_PLAIN_LO, exit_rank=20),
           "Control: reproduces REL-PLAIN's book exactly (exit_rank == book size), first recorded "
           "in M0528 -- the no-opinion arm and the fidelity check"),
        _v("BUF30", BetaBufferParams(REL_PLAIN_LO, exit_rank=30),
           "Hold a name until it falls below rank 30 by ordinary beta"),
        _v("BUF40", BetaBufferParams(REL_PLAIN_LO, exit_rank=40),
           "Hold a name until it falls below rank 40 by ordinary beta"),
    ),
    seen_keys=(
        "concept:plain-beta-turnover-buffer",
        "concept:rank-buffer-hysteresis-downside-beta",
    ),
)
