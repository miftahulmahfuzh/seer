"""M0254's floor dial: the claims the generic kit cannot check.

``test_lab_methods`` drives every lab allocator through ``allocatorkit`` and runs every candidate
on a smoke window, but a market-aware allocator is driven there WITHOUT its panel, so the kit never
sees this book choose a weight. These are the properties specific to a dose-response ladder whose
only dial is how much of the account must stay invested:

1. **The rungs are evenly spaced, so the floor is a true dose.** The middle rung is the midpoint of
   1.0 and the floor at every arm. If it were not, the four floors would not lie on one line and
   the curve across them would be a shape comparison rather than a dose curve.
2. **The six arms are exactly the documented rung triples.** This is the pre-registration in
   executable form: FLOOR70 is 1.00/0.85/0.70 and nothing else.
3. **HOLD is a genuine always-invested control.** At floor 1.0 every reading, including no reading
   at all, returns full weight -- so it can differ from buy-and-hold only through the chassis, and
   the subtraction against it is the lean alone.
4. **MIRROR50 is an EXACT reflection of FLOOR50.** The same three weights, in the same months,
   assigned the opposite way round. That is what makes it the one control in this method matched on
   the weighting arrangement, the exposure distribution and the fee bill at once; a mirror at any
   other floor is matched on none of them, which is why the mirror arm sits at 0.5 and not at the
   floor that happens to win.
5. **The lookback is the SAME at every arm.** An allocator's lookback sets its start date, so an
   arm with its own lookback would be scored over a different window against a different SPY
   benchmark -- which is exactly why M0251's own HOLD arm could not be reused here.
6. **No reading is full weight, never the floor.** A stale fear index must not read as a bearish
   signal, or the early window differs arm by arm and the paired difference is a coverage artefact.
7. **The signal is M0251's, untouched.** The cut-offs this module asserts against are read off
   M0251's frozen module, so a future edit there would fail here rather than silently redefine what
   "the top third" means.
8. **Only floor 0.0 can ever hold cash.** Every raised floor stays in the market on every reading,
   which is the whole method; it is also why those arms record no closed round trips.
9. **The params validate and every arm digests apart.** ``config_text`` reads the rules, the
   allocator id and the params only, so a dropped field would make two arms share one digest and
   the second would be refused as already run.
10. **The market-aware contract holds**: driven with no panel, every arm targets nothing.

A dedicated module rather than more cases inside the shared lab tests: the smoke fixture's 473
sessions are a fixed budget every lab method is measured against, and a new method must fit it
rather than stretch it.
"""

from __future__ import annotations

import math
from datetime import date

import pytest
from labkit import SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0251_variance_risk_premium_timing import VrpParams, rung
from seer_engine.lab.methods.m0254_premium_floor_ladder import (
    METHOD,
    SIGNAL,
    FloorParams,
    weight_for,
)

ARMS = {c.id: c for c in METHOD.all_candidates()}

#: The rung triples the method file documents, (top third, middle third, bottom third).
EXPECTED_RUNGS = {
    "M0254-FLOOR70": (1.00, 0.850, 0.70),
    "M0254-FLOOR50": (1.00, 0.750, 0.50),
    "M0254-FLOOR25": (1.00, 0.625, 0.25),
    "M0254-FLOOR00": (1.00, 0.500, 0.00),
    "M0254-HOLD": (1.00, 1.000, 1.00),
    "M0254-MIRROR50": (0.50, 0.750, 1.00),  # the reflection
}

# A reading in each third, and one just inside each cut-off.
TOP, MID, BOTTOM = 0.95, 0.5, 0.05


def _thirds(p: FloorParams) -> tuple[float, float, float]:
    return (weight_for(TOP, p), weight_for(MID, p), weight_for(BOTTOM, p))


def test_the_six_arms_are_the_documented_rung_triples():
    assert set(ARMS) == set(EXPECTED_RUNGS)
    for arm, want in EXPECTED_RUNGS.items():
        got = _thirds(ARMS[arm].params)
        assert got == pytest.approx(want), f"{arm}: rungs {got}, expected {want}"


@pytest.mark.parametrize("floor", [0.0, 0.25, 0.5, 0.7, 1.0, 0.123456])
def test_the_middle_rung_is_always_the_midpoint(floor):
    """Evenly spaced rungs are what make the floor a dose rather than a shape."""
    p = FloorParams(floor)
    top, mid, bottom = _thirds(p)
    assert bottom == pytest.approx(floor)
    assert top == pytest.approx(1.0)
    assert mid == pytest.approx((top + bottom) / 2.0)
    assert (top - mid) == pytest.approx(mid - bottom)


def test_hold_is_fully_invested_on_every_reading_including_none():
    p = ARMS["M0254-HOLD"].params
    for q in (None, 0.0, 0.01, TOP, MID, BOTTOM, SIGNAL.lo, SIGNAL.hi, 1.0):
        assert weight_for(q, p) == 1.0, q


def test_mirror50_is_an_exact_reflection_of_floor50():
    straight = ARMS["M0254-FLOOR50"].params
    flipped = ARMS["M0254-MIRROR50"].params
    assert straight.floor == flipped.floor and flipped.mirror and not straight.mirror
    a, b = _thirds(straight), _thirds(flipped)
    assert sorted(a) == pytest.approx(sorted(b))  # the same weights...
    assert b == pytest.approx(tuple(reversed(a)))  # ...in the opposite months
    # and the pair really differs, or it would be a duplicate trial wearing a control's name
    assert a != b


def test_no_reading_is_full_weight_never_the_floor():
    """Including the mirror: reversing the thirds must not reverse the no-reading default."""
    for arm, c in ARMS.items():
        assert weight_for(None, c.params) == 1.0, arm


def test_only_floor_zero_can_ever_hold_cash():
    for arm, c in ARMS.items():
        weights = [weight_for(q, c.params) for q in (None, 0.0, 0.2, 0.5, 0.8, 1.0)]
        if c.params.floor == 0.0:
            assert min(weights) == 0.0, arm
        else:
            assert min(weights) > 0.0, f"{arm} reached cash at floor {c.params.floor}"


def test_the_cutoffs_are_m0251s_own_and_the_mapping_agrees_with_it():
    """FLOOR00 must step where M0251's ladder steps, or it is not a fourth rung of one curve."""
    assert (SIGNAL.rv_n, SIGNAL.rank_n) == (22, 252)
    assert SIGNAL.lo == pytest.approx(1.0 / 3.0) and SIGNAL.hi == pytest.approx(2.0 / 3.0)
    ladder = VrpParams("ladder")
    floor00 = FloorParams(0.0)
    mirror50 = FloorParams(0.5, mirror=True)
    for i in range(0, 101):
        q = i / 100.0
        step = rung(q, ladder)  # 0 cash, 1 half, 2 full -- M0251's own mapping
        assert weight_for(q, floor00) == pytest.approx((0.0, 0.5, 1.0)[step]), q
        # the mirror arm reverses the same step, exactly as M0251's mirror mode does
        assert weight_for(q, mirror50) == pytest.approx((1.0, 0.75, 0.5)[step]), q


def test_the_lookback_is_identical_at_every_arm():
    alloc = ARMS["M0254-FLOOR50"].allocator
    seen = {alloc.lookback(c.params) for c in ARMS.values()}
    assert seen == {SIGNAL.rank_n + SIGNAL.rv_n} == {274}


def test_every_arm_digests_apart():
    digests = {arm: config_digest(c) for arm, c in ARMS.items()}
    assert len(set(digests.values())) == len(ARMS), digests


def test_params_validate():
    for bad in (-0.001, 1.001, 2.0, -1.0):
        with pytest.raises(ValueError):
            FloorParams(bad)
    for wrong in (0, 1, True, "0.5", None):
        with pytest.raises(TypeError):
            FloorParams(wrong)
    with pytest.raises(TypeError):
        FloorParams(0.5, mirror="yes")
    p = FloorParams(0.25)
    assert p.as_dict() == {"floor": "0.25", "mirror": "False"}


def test_params_round_trip_through_as_dict():
    for c in ARMS.values():
        d = c.params.as_dict()
        back = FloorParams(float(d["floor"]), d["mirror"] == "True")
        assert back == c.params


def _series_market():
    """The smoke market plus a fear index with a readable shape, so the live path really decides."""
    days = dates.sessions(SMOKE_FIRST, DEV_END)
    rows = [(d, 14.0 + 10.0 * math.sin(i / 11.0)) for i, d in enumerate(days)]
    return smoke_market().with_series(MarketSeries({"VIX": rows})), days


def test_with_no_panel_every_arm_targets_nothing():
    market = smoke_market()
    alloc = ARMS["M0254-FLOOR50"].allocator
    prepared = alloc.prepare(market.history)
    assert len(EMPTY_SERIES) == 0
    for d in dates.sessions(date(2015, 1, 2), DEV_END)[::40]:
        for c in ARMS.values():
            assert alloc.targets_prepared(prepared, frozenset(), d, frozenset(), c.params) == ()


def test_with_a_panel_a_raised_floor_never_leaves_the_market():
    """The whole method: a floor above zero holds SPY on every decision, at some weight."""
    market, days = _series_market()
    alloc = ARMS["M0254-FLOOR50"].allocator
    prepared = alloc.prepare_market(market)
    probe = [d for d in days if d >= days[SIGNAL.rank_n + SIGNAL.rv_n]][::10]
    assert len(probe) >= 10
    for arm in ("M0254-FLOOR70", "M0254-FLOOR50", "M0254-FLOOR25", "M0254-HOLD", "M0254-MIRROR50"):
        p = ARMS[arm].params
        weights = set()
        for d in probe:
            out = alloc.targets_prepared(prepared, frozenset(), d, frozenset({"SPY"}), p)
            assert len(out) == 1 and out[0].symbol == "SPY", (arm, d)
            weights.add(float(out[0].weight))
        assert min(weights) >= p.floor - 1e-9, (arm, weights)
        assert max(weights) <= 1.0, (arm, weights)


def test_with_a_panel_the_arms_really_differ():
    """Two floors that produced identical weight paths would be duplicate trials."""
    market, days = _series_market()
    alloc = ARMS["M0254-FLOOR50"].allocator
    prepared = alloc.prepare_market(market)
    probe = [d for d in days if d >= days[SIGNAL.rank_n + SIGNAL.rv_n]][::10]

    def path(arm: str) -> tuple[float, ...]:
        out = []
        for d in probe:
            ts = alloc.targets_prepared(prepared, frozenset(), d, frozenset({"SPY"}), ARMS[arm].params)
            out.append(float(ts[0].weight) if ts else 0.0)
        return tuple(out)

    hold = path("M0254-HOLD")
    assert set(hold) == {1.0}, "HOLD must sit at full weight on every decision"
    for arm in ("M0254-FLOOR70", "M0254-FLOOR50", "M0254-FLOOR25", "M0254-FLOOR00"):
        assert path(arm) != hold, f"{arm} never leaned: the dial is not wired in"
    assert path("M0254-FLOOR50") != path("M0254-MIRROR50")
    # the dose really is ordered: a deeper floor is never above a shallower one on any date
    deep, shallow = path("M0254-FLOOR25"), path("M0254-FLOOR70")
    assert all(a <= b + 1e-9 for a, b in zip(deep, shallow, strict=True))
