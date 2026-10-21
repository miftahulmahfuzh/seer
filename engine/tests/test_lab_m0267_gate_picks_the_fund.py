"""M0267's gate switch: the claims the generic kit cannot check.

``test_lab_methods`` drives every lab allocator through ``allocatorkit`` and runs every candidate
on the shared smoke window, but it checks a method's contract and not its argument. These are the
properties specific to a method whose whole claim is that the gate's opinion is being spent at
zero cash cost and that the ladder it is spent on is a true dose:

1. **Every arm is 100% invested on every reading.** This is the method. The 200-day gate's known
   price is the time it spends in cash; this method exists to pay that price in shares instead, so
   a single reading that left a sliver uninvested would put back the exact cost it removes and no
   later number would mean what it claims.
2. **The rungs are symmetric about the 50/50 midpoint, so the lean is a true dose.** The
   pre-registration says the GATE-minus-MIRROR gap should halve at half lean; that is only a
   statement about the opinion if the weights themselves lie on a line through the midpoint.
3. **The six arms are exactly the documented (above, below) pairs** -- the pre-registration in
   executable form.
4. **MIRROR is an EXACT reflection of GATE, and MIRROR-HALF of GATE-HALF.** The same two weights
   in the same months assigned the opposite way round, which is what makes each matched on
   exposure, on weighting arrangement and on fee bill at once.
5. **A two-state switch has exactly two flip-calendar-matched sequences.** The method file argues
   that a sticky placebo drawn to the gate's own flip calendar is degenerate -- it can only be
   GATE or MIRROR -- and that this is why there is no re-drawn placebo arm. That is an argument
   the lab will re-read, so it is asserted here against the real gate path rather than left as
   prose.
6. **An unreadable gate is the neutral 50/50, never an extreme.** A stale reading must not read as
   conviction either way, or the early window differs arm by arm and any gap is a coverage
   artefact rather than the opinion.
7. **The gate is the lab's own frozen one** -- ``f_index.above_sma`` on SPY at 200 -- so a future
   edit there fails this module rather than silently redefining what "the gate" means.
8. **The fixed endpoints ignore the gate entirely.** SPY-HOLD and QQQ-HOLD must be what the owner
   could have bought and left alone, not a rotation that happens to sit still. QQQ-HOLD is the
   opponent the pre-registration says decides this method, so it has to be genuinely inert.
9. **Every arm reads BOTH symbols and carries the SAME lookback.** An allocator's symbol list and
   lookback set its start date, so an endpoint reading only its own fund would be scored over a
   longer window against a different SPY benchmark and the comparison against it would not be a
   paired difference.
10. **The heavier side is targeted first**, so a partial fill buys the conviction, not the ballast.
11. **Every arm digests apart** -- ``config_text`` reads the rules, the allocator id and the params
    only, so a dropped field would make two arms share one digest and the second be refused.
12. **The gate really moves inside the smoke window**, or every claim above is vacuously true on a
    path that never flips.

A dedicated module rather than more cases inside the shared lab tests: the smoke fixture's 473
sessions are a fixed budget every lab method is measured against, and a new method must fit it
rather than stretch it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from labkit import SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0267_gate_picks_the_fund import (
    METHOD,
    RISK_OFF,
    RISK_ON,
    TREND_N,
    TREND_SYMBOL,
    GateFundParams,
    risk_on_share,
)
from seer_engine.strategies.f_index import above_sma

ARMS = {c.id: c for c in METHOD.all_candidates()}
ALLOC = ARMS["M0267-GATE"].allocator

#: The QQQ share the method file documents, as (gate above the line, gate below it).
EXPECTED_PAIRS = {
    "M0267-GATE": (1.00, 0.00),
    "M0267-GATE-HALF": (0.75, 0.25),
    "M0267-MIRROR": (0.00, 1.00),  # the reflection
    "M0267-MIRROR-HALF": (0.25, 0.75),
    "M0267-SPY-HOLD": (0.00, 0.00),
    "M0267-QQQ-HOLD": (1.00, 1.00),
}

EVERY_READING = (None, True, False)


def _pair(p: GateFundParams) -> tuple[float, float]:
    return (risk_on_share(True, p), risk_on_share(False, p))


def test_the_six_arms_are_the_documented_pairs():
    assert set(ARMS) == set(EXPECTED_PAIRS)
    for arm, want in EXPECTED_PAIRS.items():
        got = _pair(ARMS[arm].params)
        assert got == pytest.approx(want), f"{arm}: QQQ shares {got}, expected {want}"


def test_every_arm_is_always_fully_invested():
    """The method's whole argument: the gate's cash cost is absent by construction."""
    for arm, c in ARMS.items():
        for on in EVERY_READING:
            w = risk_on_share(on, c.params)
            assert 0.0 <= w <= 1.0, (arm, on, w)
            assert w + (1.0 - w) == pytest.approx(1.0), (arm, on)


@pytest.mark.parametrize("lean", [0.0, 0.25, 0.5, 0.75, 1.0, 0.123456])
def test_the_rungs_are_symmetric_about_the_midpoint(lean):
    """Symmetric rungs are what make the lean a dose rather than a shape."""
    above, below = _pair(GateFundParams(lean))
    assert above == pytest.approx(0.5 + lean / 2.0)
    assert below == pytest.approx(0.5 - lean / 2.0)
    assert (above + below) == pytest.approx(1.0)
    assert risk_on_share(None, GateFundParams(lean)) == pytest.approx(0.5)


@pytest.mark.parametrize(("straight", "flipped"),
                         [("M0267-GATE", "M0267-MIRROR"),
                          ("M0267-GATE-HALF", "M0267-MIRROR-HALF")])
def test_each_mirror_is_an_exact_reflection(straight, flipped):
    a_p, b_p = ARMS[straight].params, ARMS[flipped].params
    assert a_p.lean == b_p.lean and b_p.mirror and not a_p.mirror
    a, b = _pair(a_p), _pair(b_p)
    assert sorted(a) == pytest.approx(sorted(b))  # the same weights...
    assert b == pytest.approx(tuple(reversed(a)))  # ...in the opposite months
    assert a != b  # and the pair really differs, or it is a duplicate wearing a control's name


def test_no_reading_is_the_neutral_blend_never_an_extreme():
    for arm, c in ARMS.items():
        if c.params.fixed is not None:
            continue
        assert risk_on_share(None, c.params) == 0.5, arm


def test_the_endpoints_ignore_the_gate_entirely():
    for arm, want in (("M0267-SPY-HOLD", 0.0), ("M0267-QQQ-HOLD", 1.0)):
        p = ARMS[arm].params
        assert {risk_on_share(on, p) for on in EVERY_READING} == {want}, arm


def test_the_gate_is_the_labs_own_frozen_reading():
    """A future edit to the lab's gate must fail here, not silently redefine this method."""
    assert (TREND_SYMBOL, TREND_N) == ("SPY", 200)
    market = smoke_market()
    h = market.history[TREND_SYMBOL]
    days = dates.sessions(SMOKE_FIRST, DEV_END)
    p = ARMS["M0267-GATE"].params
    for d in days[TREND_N::7]:
        on = above_sma(h, d, TREND_N)
        assert risk_on_share(on, p) == (1.0 if on else 0.0), d


def test_every_arm_reads_both_funds_and_carries_the_same_lookback():
    for arm, c in ARMS.items():
        assert set(c.allocator.symbols(c.params)) == {RISK_OFF, RISK_ON}, arm
        assert set(c.allocator.holds(c.params)) == {RISK_OFF, RISK_ON}, arm
        assert c.allocator.lookback(c.params) == TREND_N, arm
        assert c.allocator.uses_members(c.params) is False, arm


def test_no_arm_raises_an_owner_input():
    """Both funds are in DEFAULT_ETFS; an owner input would make every arm ineligible forever."""
    for arm, c in ARMS.items():
        assert c.owner_inputs == (), arm


def test_every_arm_digests_apart():
    digests = {arm: config_digest(c) for arm, c in ARMS.items()}
    assert len(set(digests.values())) == len(ARMS), digests


def test_params_validate():
    with pytest.raises(TypeError):
        GateFundParams(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        GateFundParams(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        GateFundParams(1.5)
    with pytest.raises(ValueError):
        GateFundParams(-0.1)
    with pytest.raises(TypeError):
        GateFundParams(1.0, mirror="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        GateFundParams(1.0, fixed="IWM")


def test_params_round_trip_through_as_dict():
    for c in ARMS.values():
        d = c.params.as_dict()
        back = GateFundParams(float(d["lean"]), d["mirror"] == "True",
                              None if d["fixed"] == "None" else d["fixed"].strip("'"))
        assert back == c.params


def _probe_days() -> list[date]:
    return [d for d in dates.sessions(SMOKE_FIRST, DEV_END)[TREND_N:]][::5]


def _gate_path() -> tuple[bool, ...]:
    h = smoke_market().history[TREND_SYMBOL]
    return tuple(bool(above_sma(h, d, TREND_N)) for d in _probe_days())


def test_the_gate_really_moves_inside_the_smoke_window():
    """Without a flip every other claim in this module is vacuously true."""
    path = _gate_path()
    assert len(set(path)) == 2, "the smoke SPY never crosses its 200-day line"
    flips = sum(1 for a, b in zip(path, path[1:]) if a != b)
    assert flips >= 1


def test_a_two_state_switch_has_exactly_two_flip_calendar_matched_sequences():
    """The method file's reason for having no re-drawn placebo arm, asserted rather than claimed.

    A sticky control that changes state on exactly the gate's dates is pinned by its starting
    state alone, so the set of such sequences is {the gate, its complement} -- and the complement
    is MIRROR. There is no third shape-matched control to draw.
    """
    gate = _gate_path()
    changes = [i for i in range(1, len(gate)) if gate[i] != gate[i - 1]]
    matched = set()
    for first in (False, True):
        seq, cur = [first], first
        for i in range(1, len(gate)):
            if i in changes:
                cur = not cur
            seq.append(cur)
        matched.add(tuple(seq))
    assert matched == {gate, tuple(not s for s in gate)}


def test_the_targets_always_spend_the_whole_account():
    """Live, through the real target machinery: sum of weights is exactly 1 on every decision."""
    prepared = ALLOC.prepare(smoke_market().history)
    probe = _probe_days()
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


def test_the_arms_really_differ_and_the_dose_is_ordered():
    """Two leans that produced identical paths would be duplicate trials wearing two names."""
    prepared = ALLOC.prepare(smoke_market().history)
    probe = _probe_days()
    held = frozenset({RISK_OFF, RISK_ON})

    def path(arm: str) -> tuple[float, ...]:
        out = []
        for d in probe:
            ts = ALLOC.targets_prepared(prepared, frozenset(), d, held, ARMS[arm].params)
            qqq = [t for t in ts if t.symbol == RISK_ON]
            out.append(float(qqq[0].weight) if qqq else 0.0)
        return tuple(out)

    assert set(path("M0267-SPY-HOLD")) == {0.0}
    assert set(path("M0267-QQQ-HOLD")) == {1.0}
    gate, half = path("M0267-GATE"), path("M0267-GATE-HALF")
    mirror, mirror_half = path("M0267-MIRROR"), path("M0267-MIRROR-HALF")
    midpoint = tuple(0.5 for _ in gate)
    for arm, got in (("GATE", gate), ("GATE-HALF", half), ("MIRROR", mirror),
                     ("MIRROR-HALF", mirror_half)):
        assert got != midpoint, f"{arm} never leaned: the dial is not wired in"
    assert gate != mirror and half != mirror_half and gate != half
    # the dose really is ordered: each half lean sits between its full lean and the midpoint,
    # and each mirror is its arm reflected through the midpoint on every single date
    for g, hf, m in zip(gate, half, midpoint, strict=True):
        assert min(g, m) - 1e-9 <= hf <= max(g, m) + 1e-9
    for g, mi in zip(gate, mirror, strict=True):
        assert g + mi == pytest.approx(1.0)
    for hf, mh in zip(half, mirror_half, strict=True):
        assert hf + mh == pytest.approx(1.0)
