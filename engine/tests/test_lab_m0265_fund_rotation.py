"""M0265's fund switch: the claims the generic kit cannot check.

``test_lab_methods`` drives every lab allocator through ``allocatorkit`` and runs every candidate
on a smoke window, but a market-aware allocator is driven there WITHOUT its panel, so the kit never
sees this book choose between the two funds. These are the properties specific to a method whose
whole argument is that its cost is zero:

1. **Every arm is 100% invested on every reading.** This is the method. M0254 showed the price of
   risk cannot be spent as an exposure dial because the cost of standing aside scales with the
   lean; M0265 escapes that only if the weights always sum to exactly one, on every arm, including
   when the signal cannot be read. A single reading that leaves a sliver in cash would reintroduce
   the very cost the method exists to remove, and no later number would mean what it claims.
2. **The rungs are symmetric about the 50/50 midpoint, so the lean is a true dose.** If they were
   not, the three leans would not lie on one line and the curve across them would be a shape
   comparison rather than a dose curve.
3. **The six arms are exactly the documented rung triples.** The pre-registration in executable
   form: ROTATE is 100/50/0 percent QQQ and nothing else.
4. **BLEND is the genuine zero rung.** At lean 0.0 every reading, including no reading at all, is
   half and half -- so it differs from the leaning arms only through the opinion, and it is both
   the ladder's zero rung and the no-opinion shape placebo.
5. **MIRROR is an EXACT reflection of ROTATE.** The same two weights in the same months, assigned
   the opposite way round, which is what makes it matched on exposure, weighting arrangement and
   (to within the order of the flips) fee bill at once.
6. **Every arm reads BOTH symbols and carries the SAME lookback.** An allocator's symbol list and
   lookback set its start date, so an endpoint that read only its own fund would be scored over a
   longer window against a different SPY benchmark, and the comparison against it would not be a
   paired difference -- the exact mistake M0254 records about M0251's HOLD arm.
7. **No reading is the neutral 50/50, never an extreme.** A stale fear index must not read as
   conviction either way, or the early window differs arm by arm and the gap is a coverage artefact.
8. **The signal is M0251's, untouched.** The cut-offs asserted here are read off M0251's frozen
   module, so a future edit there fails this module rather than silently redefining "the top third".
9. **The fixed endpoints ignore the signal entirely.** SPY-HOLD and QQQ-HOLD must be what the owner
   could have bought and left alone, not a rotation that happens to sit still.
10. **The heavier side is targeted first**, so a partial fill buys the conviction and not the
    ballast.
11. **Every arm digests apart** -- ``config_text`` reads the rules, the allocator id and the params
    only, so a dropped field would make two arms share one digest and the second be refused.
12. **The market-aware contract holds**: driven with no panel, every arm targets nothing.

A dedicated module rather than more cases inside the shared lab tests: the smoke fixture's 473
sessions are a fixed budget every lab method is measured against, and a new method must fit it
rather than stretch it.
"""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest
from labkit import SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0251_variance_risk_premium_timing import VrpParams, rung
from seer_engine.lab.methods.m0265_premium_picks_the_fund import (
    METHOD,
    RISK_OFF,
    RISK_ON,
    SIGNAL,
    RotateParams,
    risk_on_share,
)

ARMS = {c.id: c for c in METHOD.all_candidates()}
ALLOC = ARMS["M0265-ROTATE"].allocator

#: The QQQ share the method file documents, (top third, middle third, bottom third).
EXPECTED_RUNGS = {
    "M0265-ROTATE": (1.00, 0.50, 0.00),
    "M0265-ROTATE-HALF": (0.75, 0.50, 0.25),
    "M0265-BLEND": (0.50, 0.50, 0.50),
    "M0265-MIRROR": (0.00, 0.50, 1.00),  # the reflection
    "M0265-SPY-HOLD": (0.00, 0.00, 0.00),
    "M0265-QQQ-HOLD": (1.00, 1.00, 1.00),
}

# A reading in each third, and the readings at the cut-offs themselves.
TOP, MID, BOTTOM = 0.95, 0.5, 0.05
EVERY_READING = (None, 0.0, 0.05, 0.2, SIGNAL.lo, 0.5, SIGNAL.hi, 0.8, 0.95, 1.0)


def _thirds(p: RotateParams) -> tuple[float, float, float]:
    return (risk_on_share(TOP, p), risk_on_share(MID, p), risk_on_share(BOTTOM, p))


def test_the_six_arms_are_the_documented_rung_triples():
    assert set(ARMS) == set(EXPECTED_RUNGS)
    for arm, want in EXPECTED_RUNGS.items():
        got = _thirds(ARMS[arm].params)
        assert got == pytest.approx(want), f"{arm}: QQQ shares {got}, expected {want}"


def test_every_arm_is_always_fully_invested():
    """The method's whole argument: the cost M0254 could not escape is absent by construction."""
    for arm, c in ARMS.items():
        for q in EVERY_READING:
            w = risk_on_share(q, c.params)
            assert 0.0 <= w <= 1.0, (arm, q, w)
            assert w + (1.0 - w) == pytest.approx(1.0), (arm, q)


@pytest.mark.parametrize("lean", [0.0, 0.25, 0.5, 0.75, 1.0, 0.123456])
def test_the_rungs_are_symmetric_about_the_midpoint(lean):
    """Symmetric rungs are what make the lean a dose rather than a shape."""
    top, mid, bottom = _thirds(RotateParams(lean))
    assert mid == pytest.approx(0.5)
    assert top == pytest.approx(0.5 + lean / 2.0)
    assert bottom == pytest.approx(0.5 - lean / 2.0)
    assert (top - mid) == pytest.approx(mid - bottom)
    assert (top + bottom) == pytest.approx(1.0)


def test_blend_is_half_and_half_on_every_reading_including_none():
    p = ARMS["M0265-BLEND"].params
    for q in EVERY_READING:
        assert risk_on_share(q, p) == 0.5, q


def test_mirror_is_an_exact_reflection_of_rotate():
    straight = ARMS["M0265-ROTATE"].params
    flipped = ARMS["M0265-MIRROR"].params
    assert straight.lean == flipped.lean and flipped.mirror and not straight.mirror
    a, b = _thirds(straight), _thirds(flipped)
    assert sorted(a) == pytest.approx(sorted(b))  # the same weights...
    assert b == pytest.approx(tuple(reversed(a)))  # ...in the opposite months
    assert a != b  # and the pair really differs, or it is a duplicate wearing a control's name


def test_no_reading_is_the_neutral_blend_never_an_extreme():
    """Including the mirror: reversing the thirds must not reverse the no-reading default."""
    for arm, c in ARMS.items():
        if c.params.fixed is not None:
            continue  # an endpoint has no opinion to suspend
        assert risk_on_share(None, c.params) == 0.5, arm


def test_the_endpoints_ignore_the_signal_entirely():
    for arm, fund in (("M0265-SPY-HOLD", RISK_OFF), ("M0265-QQQ-HOLD", RISK_ON)):
        p = ARMS[arm].params
        shares = {risk_on_share(q, p) for q in EVERY_READING}
        assert shares == {1.0 if fund == RISK_ON else 0.0}, (arm, shares)


def test_the_cutoffs_are_m0251s_own_and_the_mapping_agrees_with_it():
    """ROTATE must step where M0251's ladder steps, or this is not the same signal."""
    assert (SIGNAL.rv_n, SIGNAL.rank_n) == (22, 252)
    assert SIGNAL.lo == pytest.approx(1.0 / 3.0) and SIGNAL.hi == pytest.approx(2.0 / 3.0)
    ladder = VrpParams("ladder")
    rotate = ARMS["M0265-ROTATE"].params
    mirror = ARMS["M0265-MIRROR"].params
    half = ARMS["M0265-ROTATE-HALF"].params
    for i in range(0, 101):
        q = i / 100.0
        step = rung(q, ladder)  # 0 cash, 1 half, 2 full -- M0251's own mapping
        assert risk_on_share(q, rotate) == pytest.approx((0.0, 0.5, 1.0)[step]), q
        assert risk_on_share(q, mirror) == pytest.approx((1.0, 0.5, 0.0)[step]), q
        assert risk_on_share(q, half) == pytest.approx((0.25, 0.5, 0.75)[step]), q


def test_every_arm_reads_both_funds_and_carries_the_same_lookback():
    """The symbol list and the lookback set the start date: all six must share both."""
    assert {ALLOC.lookback(c.params) for c in ARMS.values()} == {SIGNAL.rank_n + SIGNAL.rv_n} == {274}
    for arm, c in ARMS.items():
        assert set(ALLOC.symbols(c.params)) == {RISK_OFF, RISK_ON}, arm
        assert set(ALLOC.holds(c.params)) == {RISK_OFF, RISK_ON}, arm
        assert ALLOC.uses_members(c.params) is False, arm


def test_no_arm_raises_an_owner_input():
    """Both funds are in DEFAULT_ETFS; any other pair could never be eligible."""
    from seer_engine.backtest.dev import candidate_owner_inputs

    for arm, c in ARMS.items():
        assert candidate_owner_inputs(c) == (), arm


def test_every_arm_digests_apart():
    digests = {arm: config_digest(c) for arm, c in ARMS.items()}
    assert len(set(digests.values())) == len(ARMS), digests


def test_params_validate():
    for bad in (-0.001, 1.001, 2.0, -1.0):
        with pytest.raises(ValueError):
            RotateParams(bad)
    for wrong in (0, 1, True, "0.5", None):
        with pytest.raises(TypeError):
            RotateParams(wrong)
    with pytest.raises(TypeError):
        RotateParams(0.5, mirror="yes")
    with pytest.raises(ValueError):
        RotateParams(0.0, fixed="IWM")
    p = RotateParams(0.25)
    assert p.as_dict() == {"lean": "0.25", "mirror": "False", "fixed": "None"}


def test_params_round_trip_through_as_dict():
    for c in ARMS.values():
        d = c.params.as_dict()
        back = RotateParams(float(d["lean"]), d["mirror"] == "True",
                            None if d["fixed"] == "None" else d["fixed"].strip("'"))
        assert back == c.params


def _series_market():
    """The smoke market plus a fear index with a readable shape, so the live path really decides."""
    days = dates.sessions(SMOKE_FIRST, DEV_END)
    rows = [(d, 14.0 + 10.0 * math.sin(i / 11.0)) for i, d in enumerate(days)]
    return smoke_market().with_series(MarketSeries({"VIX": rows})), days


def test_with_no_panel_every_arm_targets_nothing():
    prepared = ALLOC.prepare(smoke_market().history)
    assert len(EMPTY_SERIES) == 0
    for d in dates.sessions(date(2015, 1, 2), DEV_END)[::40]:
        for c in ARMS.values():
            assert ALLOC.targets_prepared(prepared, frozenset(), d, frozenset(), c.params) == ()


def _probe(prepared, days):
    return [d for d in days if d >= days[SIGNAL.rank_n + SIGNAL.rv_n]][::10]


def test_with_a_panel_the_targets_always_spend_the_whole_account():
    """Live, through the real target machinery: Σ weight is exactly 1 on every decision."""
    market, days = _series_market()
    prepared = ALLOC.prepare_market(market)
    probe = _probe(prepared, days)
    assert len(probe) >= 10
    held = frozenset({RISK_OFF, RISK_ON})
    for arm, c in ARMS.items():
        for d in probe:
            out = ALLOC.targets_prepared(prepared, frozenset(), d, held, c.params)
            assert out, (arm, d)
            assert sum(t.weight for t in out) == Decimal(1), (arm, d, out)
            assert len({t.symbol for t in out}) == len(out), (arm, d)
            assert {t.symbol for t in out} <= {RISK_OFF, RISK_ON}, (arm, d)
            # the heavier side first, so a partial fill buys the conviction not the ballast
            assert list(out) == sorted(out, key=lambda t: -t.weight), (arm, d)


def test_with_a_panel_the_arms_really_differ_and_the_dose_is_ordered():
    """Two leans that produced identical paths would be duplicate trials wearing two names."""
    market, days = _series_market()
    prepared = ALLOC.prepare_market(market)
    probe = _probe(prepared, days)
    held = frozenset({RISK_OFF, RISK_ON})

    def path(arm: str) -> tuple[float, ...]:
        out = []
        for d in probe:
            ts = ALLOC.targets_prepared(prepared, frozenset(), d, held, ARMS[arm].params)
            qqq = [t for t in ts if t.symbol == RISK_ON]
            out.append(float(qqq[0].weight) if qqq else 0.0)
        return tuple(out)

    blend = path("M0265-BLEND")
    assert set(blend) == {0.5}, "BLEND must sit at half and half on every decision"
    assert set(path("M0265-SPY-HOLD")) == {0.0}
    assert set(path("M0265-QQQ-HOLD")) == {1.0}
    rotate, half, mirror = path("M0265-ROTATE"), path("M0265-ROTATE-HALF"), path("M0265-MIRROR")
    for arm, got in (("ROTATE", rotate), ("ROTATE-HALF", half), ("MIRROR", mirror)):
        assert got != blend, f"{arm} never leaned: the dial is not wired in"
    assert rotate != mirror
    # the dose really is ordered: the half lean never sits outside the full one, and the mirror
    # is the full lean reflected through the blend on every single date
    for a, b, c in zip(rotate, half, blend, strict=True):
        assert min(a, c) - 1e-9 <= b <= max(a, c) + 1e-9
    for a, m in zip(rotate, mirror, strict=True):
        assert a + m == pytest.approx(1.0)
