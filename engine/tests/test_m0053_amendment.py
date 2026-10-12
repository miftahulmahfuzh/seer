"""M0053's 2026-10-12 amendment: the brake-off allocator, and what must not have moved.

The amendment adds a second params type and a second allocator to a method file whose five
original configurations the lab has already recorded. Two things have to be true at once and
neither is checked anywhere else:

- the five recorded candidates still digest to the exact ``config_digest`` the committed
  ``lab/lab.sqlite`` holds for them (``registry._canon`` enumerates every ``compare=True``
  field, so a field added to ``WeeklyOnParams`` would have rewritten all five silently); and
- ``FULLON`` is ``WEEKLYON`` with the brake's scalar removed and **nothing else** -- same monthly
  basket, same weekly refresh -- which is what makes the amendment's arm the exposure
  diagnostic's ``-FULL`` arm rather than a different book that resembles it.

``test_lab_methods`` drives every lab candidate generically; this module pins the two facts that
are specific to this amendment, so a future edit to either params type fails here by name.
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
from seer_engine.backtest.dev import DEV_END, run_candidate
from seer_engine.lab import store
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import _scaled, basket_scale
from seer_engine.lab.methods.m0050_overnight_momentum import OnParams
from seer_engine.lab.methods.m0053_overnight_winners_weekly_brake import (
    FULLON,
    METHOD,
    NOGATE20,
    TOTON20,
    WEEKLYON,
    NoBrakeOnParams,
    WeeklyOnParams,
)

# Measured 2026-10-12 against the committed lab/lab.sqlite (md5 4a34ddb823ec88a5e86afeb5d7e1b7c9),
# read through a read-only sqlite3 URI so no lab command migrated it.
RECORDED: dict[str, str] = {
    "M0053-TOTON20-TV14": "3cd337abbd6c2a614e5c3f426844cde8e4f7eb78c1cc3865b8a456cc5c2a73da",
    "M0053-TOTON20-TV16": "5a5b4828aa2d79acd0c796e1c4f776a455ef44c0d80beadc37eaffe83b26d5f0",
    "M0053-TOTON20-TV18": "104311d5dc64a877edd6742d437a4c451a224423dae897f53b8bce3c5014587e",
    "M0053-TOTON30-TV16": "cc2510f542be9ebac011262812fdb04e795ab27bf5d3afcaf60bd84e03a18e1f",
    "M0053-RESON20-TV16": "f25490aec16eb1d6c69baed0e4d5598b919fb26fa8b91ba640f14888232f3356",
}

# Free in the committed database on 2026-10-12: no trials row claims any of them. Phase 5's
# `lab run --amend M0053` is what records them, and it refuses a digest that is not free.
AMENDED_DIGESTS: dict[str, str] = {
    "M0053-TOTON20-NOBRAKE": "d8e94b628e3fa7a7cc27260e357f70a562686b15649bbfc7dce2eb4cd78e77b6",
    "M0053-RESON20-NOBRAKE": "150eb2516cbcb122529736c2e4c966d7fbcd6f516df6f3911488c55fd8149de1",
    "M0053-RESON20-TV16-NOGATE": "76de74aab1781b28f9494d66ead5f7e7d7d4bf4f73fe4663e51b64558bd65089",
}

NOBRAKE_PARAMS = [NoBrakeOnParams(TOTON20), NoBrakeOnParams(TOTON20, pool_by="residual")]

# (no-brake params, the braked params whose only difference is the scalar)
PAIRS = [
    (NoBrakeOnParams(TOTON20), WeeklyOnParams(TOTON20, Decimal("0.16"), 21)),
    (NoBrakeOnParams(TOTON20, pool_by="residual"),
     WeeklyOnParams(TOTON20, Decimal("0.16"), 21, pool_by="residual")),
]


@pytest.fixture(scope="module")
def market():
    return smoke_market(set(FULLON.symbols(NOBRAKE_PARAMS[0])))


def _by_id() -> dict[str, object]:
    return {c.id: c for c in METHOD.all_candidates()}


def test_the_five_recorded_candidates_still_digest_to_what_the_lab_holds():
    found = _by_id()
    for cid, digest in RECORDED.items():
        assert cid in found, f"{cid} is gone from METHOD"
        assert config_digest(found[cid]) == digest, (
            f"{cid}'s configuration moved; the lab has a trial on the old digest and "
            "prereg.check_digest, remeasure and `lab costs` all read it"
        )


def test_the_recorded_digests_match_the_committed_database():
    """The constants above are a copy of the record; this proves the copy is still true."""
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT candidate_id, config_digest FROM trials WHERE method_id = 'M0053'"
        ).fetchall()
    finally:
        conn.close()
    assert {cid: d for cid, d in rows} == RECORDED


def test_the_amendment_carries_the_three_pre_registered_configurations():
    found = _by_id()
    assert len(METHOD.candidates) == 5
    assert len(METHOD.all_candidates()) == 8
    for cid, digest in AMENDED_DIGESTS.items():
        assert cid in found, f"{cid} is missing from the amendment"
        assert config_digest(found[cid]) == digest, (
            f"{cid}'s configuration is not the one that was checked free against the committed "
            "database; re-check it before phase 5 commits"
        )
    assert found["M0053-RESON20-TV16-NOGATE"].params == WeeklyOnParams(
        NOGATE20, Decimal("0.16"), 21, pool_by="residual"
    )
    assert NOGATE20.inner.trend is None, "the NOGATE arm must have no SPY-200 gate"
    assert TOTON20.inner.trend == ("SPY", 200), "the NOBRAKE arms keep the gate"


def test_the_brake_is_the_only_difference(market):
    """WEEKLYON's targets are exactly FULLON's, scaled by the basket's own brake."""
    members = everyone({s: market.history[s] for s in MEMBER_STOCKS})
    nonempty = 0
    for d in dates.sessions(date(2013, 1, 1), DEV_END)[::17]:
        for nb, wk in PAIRS:
            full = FULLON.targets(market.history, members(d), d, frozenset(), nb)
            braked = WEEKLYON.targets(market.history, members(d), d, frozenset(), wk)
            scale = basket_scale(market.history, full, d, wk.n, wk.target_vol)
            assert braked == _scaled(full, scale), f"{d}: the two allocators chose different baskets"
            nonempty += 1 if full else 0
    assert nonempty > 0, "every probe returned no targets, so this proved nothing"


def test_the_new_allocator_passes_the_contract(market):
    sessions = dates.sessions(date(2014, 12, 1), DEV_END)
    probe = sessions[::40]
    held_sets = [frozenset(), frozenset(MEMBER_STOCKS[:2]) & frozenset(market.history)]
    members = everyone({s: market.history[s] for s in MEMBER_STOCKS})
    nonempty = assert_p4_identity(FULLON, market.history, members,
                                  [dates.prev_session(s) for s in probe], held_sets, NOBRAKE_PARAMS)
    nonempty += assert_no_lookahead(FULLON, market.history, members, probe, held_sets, NOBRAKE_PARAMS)
    assert nonempty > 0, "every probe returned no targets, so the contract check proved nothing"


def test_every_amended_candidate_runs_a_smoke_window(market):
    amount = Decimal("1.0300")
    amended = {c.id for c in METHOD.all_candidates()} - {c.id for c in METHOD.candidates}
    assert amended == set(AMENDED_DIGESTS)
    found = _by_id()
    for cid in sorted(amended):
        result, row = run_candidate(market, {"SPY": {SPY_EX_DATE: amount}},
                                    (Dividend(SPY_EX_DATE, amount),), found[cid])
        assert row.end == DEV_END
        assert len(result.snapshots) >= 2


def test_the_new_params_type_refuses_what_it_cannot_run():
    with pytest.raises(TypeError):
        NoBrakeOnParams(TOTON20.inner)              # a FactorParams where an OnParams belongs
    with pytest.raises(ValueError):
        NoBrakeOnParams(OnParams(TOTON20.inner, rank="overnight", pool=40))
    with pytest.raises(ValueError):
        NoBrakeOnParams(TOTON20, pool_by="whatever")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        FULLON.lookback(WeeklyOnParams(TOTON20, Decimal("0.16"), 21))
