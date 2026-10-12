"""M0030's 2026-10-12 amendment: the three pre-registered candidates, and what must not move.

The amendment adds candidates to a method that has already run (trials #126-#128). Two things
have to be true at once for that to be honest, and this module checks both:

- the three configurations the amendment pre-registers are **free** -- no recorded trial, in any
  window, already claims their ``config_digest`` -- so running them is a new measurement and not
  a silent re-run;
- the three configurations the lab already recorded still digest to exactly the values it holds
  on file. ``registry._canon`` enumerates every ``compare=True`` field of a params dataclass, so
  one added field would rewrite the digest of every recorded candidate that uses it and break
  ``prereg.check_digest``, ``remeasure`` and ``lab costs`` at once (plan invariant 3).

The digests below are pinned as literals on purpose. They are the plan's interface contract, and
a test that recomputed both sides from the same code would pass while the history changed under
it. The committed database is read through a read-only URI and never through a lab command,
because a lab command migrates ``lab/lab.sqlite`` on connect even for a read.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, everyone
from labkit import MEMBER_STOCKS, SPY_EX_DATE, smoke_market

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, candidate_owner_inputs, run_candidate
from seer_engine.lab import store
from seer_engine.lab.method import MAX_VARIANTS, config_digest
from seer_engine.lab.methods.m0007_residual_momentum import N20_NOTREND, RESIDMOM
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0030_spy_core_momentum_satellite import (
    AMENDED,
    AMENDMENT_2026_10_12,
    METHOD,
    SAT_NOGATE,
)
from seer_engine.lab.real_costs import real_cost_problem, requires_real_cost
from seer_engine.strategies.allocator import Allocator

# What the committed lab database holds for M0030 (trials #126, #127, #128), verified
# 2026-10-12 against lab/lab.sqlite md5 4a34ddb823ec88a5e86afeb5d7e1b7c9.
RECORDED: dict[str, str] = {
    "M0030-C70T": "ca034400129d92f04a08cfd2160af56cce13194e05b6f3c10d6e5804838793ad",
    "M0030-C50T": "4508e558e3e859be096d8f8f1c4b861e27ae0af5fd25298c0faff617464c7d3a",
    "M0030-C50A": "acbab0edfca44c9256428d2c3df51bccc9ed509977a2b2ca6c42b26f252a97ed",
}

# The amendment's pre-registration, computed in the same session against the same database.
AMENDMENT: dict[str, str] = {
    "M0030-SAT100": "542c1b9e439affc6b8faf45413c284bfbbfba8dafe67c060522288baa4a2c313",
    "M0030-SAT100-NOGATE": "5d00ec7cafc022d5cdf734ba2f357ba21b2134f3a38ac9304c91e33ac97a7136",
    "M0030-C50A-NOGATE": "b7cdc1211336dc8f137ba7beced6eb12f17b441c89a6aec1e52e9acc4ed74495",
}

NEW = AMENDMENT_2026_10_12.candidates


def _recorded_digests() -> set[str] | None:
    """Every config_digest the committed database holds, or None when it is not in this tree."""
    if not store.COMMITTED_DB.exists():
        return None
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    try:
        return {str(r[0]) for r in conn.execute("SELECT config_digest FROM trials")}
    finally:
        conn.close()


@pytest.fixture(scope="module")
def market():
    return smoke_market({"SPY"})


# --------------------------------------------------------------------------- the freeze


def test_the_recorded_candidates_still_digest_to_their_recorded_values():
    got = {c.id: config_digest(c) for c in METHOD.candidates}
    assert got == RECORDED


def test_the_recorded_digests_are_the_ones_the_lab_holds():
    digests = _recorded_digests()
    if digests is None:
        pytest.skip("no lab database")
    for cid, digest in RECORDED.items():
        assert digest in digests, f"{cid}: the lab no longer holds {digest}"


# --------------------------------------------------------------------------- the amendment


def test_the_amendment_is_dated_and_carries_exactly_three_candidates():
    assert AMENDED == date(2026, 10, 12)
    assert AMENDMENT_2026_10_12.added == AMENDED          # phase 1's field name (reconciler, C3)
    assert AMENDMENT_2026_10_12.why.strip()               # the one-line reason, non-empty
    assert AMENDMENT_2026_10_12.hypothesis.strip()
    assert AMENDMENT_2026_10_12.expected_failure.strip()
    assert len(NEW) == 3
    assert len(NEW) <= MAX_VARIANTS
    assert [c.id for c in NEW] == ["M0030-SAT100", "M0030-SAT100-NOGATE", "M0030-C50A-NOGATE"]
    for c in NEW:
        assert c.family == "M0030"
        assert c.added == AMENDED
        assert c.rules.id == "monthly-hold-frac"
        assert c.owner_inputs == () == candidate_owner_inputs(c)


def test_the_amendment_digests_are_the_preregistered_ones():
    assert {c.id: config_digest(c) for c in NEW} == AMENDMENT


def test_the_amendment_digests_are_free_in_the_committed_lab():
    digests = _recorded_digests()
    if digests is None:
        pytest.skip("no lab database")
    for cid, digest in AMENDMENT.items():
        assert digest not in digests, (
            f"{cid} repeats a configuration the lab has already run; an amendment must be a new "
            "measurement, not a re-run under a new name"
        )


def test_no_two_of_the_six_configurations_collide():
    everything = list(METHOD.candidates) + list(NEW)
    digests = [config_digest(c) for c in everything]
    assert len(set(digests)) == len(digests)
    assert len({c.id for c in everything}) == len(everything)


def test_the_two_satellite_arms_differ_only_by_the_gate():
    # RAW20 is M0007-N20-RAW's params; SAT_NOGATE is the same with FactorParams.trend removed.
    assert RAW20.inner.trend == ("SPY", 200)
    assert SAT_NOGATE.inner is N20_NOTREND
    assert SAT_NOGATE.inner.trend is None
    assert SAT_NOGATE.scaled is RAW20.scaled is False
    for name in ("beta_n", "mom_n", "skip", "market"):
        assert getattr(SAT_NOGATE, name) == getattr(RAW20, name)
    for name in ("rank", "top", "mom_n", "mom_skip", "vol_n", "pool", "sizing",
                 "min_dollar_volume", "min_price"):
        assert getattr(SAT_NOGATE.inner, name) == getattr(RAW20.inner, name)


def test_the_blend_arm_turns_the_gate_off_on_both_legs():
    blend = {c.id: c for c in NEW}["M0030-C50A-NOGATE"].params
    core, satellite = blend.parts
    assert core.allocator.id == "F1" and core.params.rule == "always"
    assert satellite.allocator is RESIDMOM and satellite.params is SAT_NOGATE
    assert core.share == satellite.share == Decimal("0.5")


# --------------------------------------------------------------------------- the lab's rules


def test_the_amendment_stays_at_the_lab_s_flat_cost():
    # real_costs.requires_real_cost is keyed on the METHOD ID and exempts <= M0030, so
    # runner.preflight will not refuse monthly-hold-frac here, and the new candidates stay
    # comparable with the three the lab recorded at the same flat 0.1% (Decision D7).
    assert requires_real_cost("M0030") is False
    assert requires_real_cost("M0031") is True
    assert real_cost_problem(METHOD) is None


# --------------------------------------------------------------------------- the contracts


@pytest.mark.parametrize("c", NEW, ids=[c.id for c in NEW])
def test_an_amendment_candidate_runs_a_smoke_window(market, c):
    amount = Decimal("1.0300")
    result, row = run_candidate(
        market, {"SPY": {SPY_EX_DATE: amount}}, (Dividend(SPY_EX_DATE, amount),), c
    )
    assert row.end == DEV_END
    assert len(result.snapshots) >= 2


@pytest.mark.parametrize("c", NEW, ids=[c.id for c in NEW])
def test_an_amendment_candidate_passes_the_allocator_contract(market, c):
    assert isinstance(c.allocator, Allocator)
    sessions = dates.sessions(date(2014, 12, 1), DEV_END)
    probe = sessions[::40]
    held_sets = [frozenset(), frozenset(MEMBER_STOCKS[:2]) & frozenset(market.history)]
    members = everyone({s: market.history[s] for s in MEMBER_STOCKS})
    nonempty = assert_p4_identity(
        c.allocator, market.history, members,
        [dates.prev_session(s) for s in probe], held_sets, [c.params],
    )
    nonempty += assert_no_lookahead(
        c.allocator, market.history, members, probe, held_sets, [c.params]
    )
    assert nonempty > 0, f"{c.id}: every probe returned no targets, so the check proved nothing"
