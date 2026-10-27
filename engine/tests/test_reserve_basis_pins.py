"""``TradeRules.reserve_basis``: how much of one night's budget an order holds, and the pins that
say adding the lever moved nothing.

``sim.book.step_book`` sizes a night's buys against ``available = book.cash + planned`` and runs a
``committed`` tally down the rank-ordered targets. That tally counted RESERVATIONS priced at the
order's limit while ``cash`` counted FILLS priced at ``min(open, limit)``, and nothing reconciled
them. Two leaks sat in that one line, and they are not equally defensible:

- an order rejected "no_bar" was never placed at all, one rejected "unfilled" never traded, and the
  part of one the cash clamp shrank away was never bought -- yet each kept a full reservation
  against every pick ranked below it. That is accounting error with no live-book defence;
- an order that filled under its limit kept the difference reserved. Reserving at the limit is what
  a live book HAS to do: the owner places the whole night's orders in the morning and cannot know an
  early fill price before sizing a later one, so handing that slack back inside one session reads
  the night with hindsight.

Both are repaired together behind ``reserve_basis="fill"``, because a book that opts in opts into
one rule -- a reservation is what the night actually commits -- and because splitting them would
cost a second field on a value every config digest reads.

It is a lever added after the P7a registry, the lab trials and the paper roster were pinned, so it
sits in ``sim.rules.LEVERS_SINCE_PINS`` at "order" and drops out of every canonical text while it is
there. These tests are the proof, in the shape ``test_resize_basis_pins.py`` set, plus a golden
ledger: a seeded unequal-weight tape stepped at the default and captured from the engine BEFORE the
lever existed, so any default-path change in the buy loop goes red with a readable diff.

The tape exercises entries, adds, trims, signal sells and the "no_bar" leak (17 of them). The
"unfilled", "too_small" and cash-clamp leaks are covered one at a time in ``test_sim_book.py``.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from seer_engine import dates, sim
from seer_engine.backtest.registry import REGISTRY, candidate_digest, candidate_text
from seer_engine.lab.method import config_digest, config_text, discover
from seer_engine.paper import roster
from seer_engine.prices import Bar
from seer_engine.sim import Target, new_book, step_book
from seer_engine.sim.rules import (
    DESIGN_V0,
    DESIGN_V0_GOTRADE,
    LEVERS_SINCE_PINS,
    MONTHLY_HOLD,
    PRESETS,
    V0_BOOK,
    TradeRules,
    describe_rules,
    is_pinned_default,
)

W = Decimal

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "sim_book_reserve_order_golden.txt"

# The golden tape. Six names, an unequal weight ladder summing to 1, and a resizing open_limit book,
# so entries, adds, trims, signal sells and missing bars all occur. The market generator mirrors
# ``test_sim_book._market`` exactly -- the same 0.25 price grid and the same 5% missing-bar rate --
# so the two tapes stay comparable, and like it this relies on ``random.Random.gauss`` being stable
# across CPython versions, which the §5 parity test has relied on since P7a.
GOLDEN_RULES = TradeRules(id="gold-unequal", engine="book", entry="open_limit", resize=True)
GOLDEN_SYMBOLS: dict[str, float] = {
    "AAA": 50.0,
    "BBB": 120.0,
    "CCC": 20.0,
    "DDD": 300.0,
    "EEE": 75.0,
    "FFF": 8.0,
}
GOLDEN_WEIGHTS: tuple[Decimal, ...] = (W("0.30"), W("0.25"), W("0.18"), W("0.12"), W("0.09"), W("0.06"))
GOLDEN_SEED = 7
GOLDEN_START = date(2026, 6, 1)
GOLDEN_END = date(2026, 9, 30)
GOLDEN_CASH = W("10000")


def _tick(x: float | Decimal) -> Decimal:
    """``x`` on a 0.25 price grid, so exact ties (low == limit) occur."""
    d = W(repr(x)) if isinstance(x, float) else x
    return sim.q((d * 4).to_integral_value() / 4)


def _golden_market(sessions: list[date]) -> dict[date, dict[str, Bar]]:
    rng = random.Random(GOLDEN_SEED)
    closes = dict(GOLDEN_SYMBOLS)
    out: dict[date, dict[str, Bar]] = {}
    for i, s in enumerate(sessions):
        bars: dict[str, Bar] = {}
        for sym in sorted(GOLDEN_SYMBOLS):
            prev = closes[sym]
            o = prev * (1 + rng.gauss(0, 0.012))
            c = prev * (1 + rng.gauss(0.0005, 0.018))
            h = max(o, c) * (1 + abs(rng.gauss(0, 0.008)))
            lo = min(o, c) * (1 - abs(rng.gauss(0, 0.008)))
            closes[sym] = c
            if i > 0 and rng.random() < 0.05:
                continue  # a missing bar
            bars[sym] = Bar(sym, s, _tick(o), _tick(h), _tick(lo), _tick(c), 1_000_000)
        out[s] = bars
    return out


def golden_ledger(rules: TradeRules) -> str:
    """One line per session -- fills, rejections, cash, equity -- as text a human can diff.

    Also the capture function: run it at HEAD and write the result to ``GOLDEN_PATH`` before the
    lever exists, so the fixture pins the engine the lab recorded and not the repaired one.
    """
    sessions = dates.sessions(GOLDEN_START, GOLDEN_END)
    market = _golden_market(sessions)
    rng = random.Random(GOLDEN_SEED + 500)
    bk = new_book(GOLDEN_CASH)
    data = market[sessions[0]]
    lines: list[str] = []
    for s in sessions[1:]:
        order = sorted(data)
        rng.shuffle(order)
        targets = tuple(Target(sym, w, data[sym].close) for sym, w in zip(order, GOLDEN_WEIGHTS))
        out = step_book(bk, s, market[s], targets, rules)
        bk = out.book
        lines.append(
            "|".join(
                (
                    s.isoformat(),
                    ";".join(
                        f"{f.symbol},{f.side},{f.shares},{f.price},{f.cash_usd},{f.reason}"
                        for f in out.fills
                    ),
                    ";".join(f"{sym},{why}" for sym, why in out.rejected),
                    str(out.snapshot.cash_usd),
                    str(out.snapshot.equity_usd),
                )
            )
        )
        data = market[s]
    return "\n".join(lines) + "\n"


# ============================================================== the default is the old engine


def test_the_default_basis_replays_the_engine_the_lab_recorded():
    """The golden tape, captured before the lever existed. A readable diff on failure."""
    want = GOLDEN_PATH.read_text(encoding="utf-8")
    got = golden_ledger(GOLDEN_RULES)
    assert got == want


def test_the_fill_basis_is_not_inert_on_the_same_tape():
    """If this passed, the lever would be doing nothing and the test above would prove nothing."""
    other = golden_ledger(replace(GOLDEN_RULES, reserve_basis="fill"))
    assert other != GOLDEN_PATH.read_text(encoding="utf-8")


def test_every_rule_set_the_repo_ships_is_on_the_old_basis():
    assert TradeRules(id="x", engine="book").reserve_basis == "order"
    assert DESIGN_V0.reserve_basis == "order" and V0_BOOK.reserve_basis == "order"
    assert [r.id for r in PRESETS if r.reserve_basis != "order"] == []


# ============================================================== validation


def test_reserve_basis_validation():
    with pytest.raises(TypeError, match="reserve_basis"):
        replace(MONTHLY_HOLD, id="x", reserve_basis=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown reserve_basis"):
        replace(MONTHLY_HOLD, id="x", reserve_basis="limit")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="book-engine lever"):
        replace(DESIGN_V0_GOTRADE, id="x", reserve_basis="fill")
    with pytest.raises(ValueError, match="book-engine lever"):
        replace(DESIGN_V0, reserve_basis="fill")
    assert replace(MONTHLY_HOLD, id="x", reserve_basis="fill").reserve_basis == "fill"


# ============================================================== it moved nothing that was pinned


def test_reserve_basis_is_a_lever_since_the_pins():
    assert LEVERS_SINCE_PINS["reserve_basis"] == "order"
    assert is_pinned_default("reserve_basis", "order") is True
    assert is_pinned_default("reserve_basis", "fill") is False
    # Append only: an insertion would re-order nothing, but the habit is the point.
    assert list(LEVERS_SINCE_PINS)[-1] == "reserve_basis"


def _all_candidates():
    """Every registry candidate and every lab variant, amendments included (``all_candidates``)."""
    out = list(REGISTRY)
    for m, _ in discover().values():
        out += list(m.all_candidates())
    return out


def _asserts_reserve_basis(text: str, c) -> None:
    """"order" is left out of a canonical form; "fill" names itself, so it digests apart.

    Conditional on purpose: a later method built on the repaired budget must name the lever, and
    asserting absence unconditionally would pin the lab to the leak forever.
    """
    if c.rules.reserve_basis == "order":
        assert "reserve_basis" not in text, c.id
    else:
        assert f"reserve_basis='{c.rules.reserve_basis}'" in text, c.id


def test_order_is_absent_from_every_canonical_form():
    for c in REGISTRY:
        _asserts_reserve_basis(candidate_text(c), c)
    for c in _all_candidates():
        _asserts_reserve_basis(config_text(c), c)
    for r in (*PRESETS, V0_BOOK):
        if r.reserve_basis == "order":
            assert "reserve_basis" not in roster.rules_dict(r), r.id
        else:
            assert roster.rules_dict(r)["reserve_basis"] == r.reserve_basis, r.id


def test_fill_digests_differently():
    book_candidates = [c for c in _all_candidates() if c.rules.engine == "book"]
    assert book_candidates
    for c in book_candidates[:25]:
        # The rules id is kept, so the only thing that moves in the text is the lever itself.
        f = replace(c, rules=replace(c.rules, reserve_basis="fill"))
        assert "reserve_basis='fill'" in config_text(f), c.id
        assert config_digest(f) != config_digest(c), c.id
        assert candidate_digest(f) != candidate_digest(c), c.id
    g = replace(MONTHLY_HOLD, id="monthly-hold-fill", reserve_basis="fill")
    assert roster.rules_dict(g)["reserve_basis"] == "fill"
    assert "reserve_basis" not in roster.rules_dict(MONTHLY_HOLD)


# ============================================================== the plain-English description


def test_describe_rules_names_the_lever_only_when_it_is_used():
    plain = describe_rules(MONTHLY_HOLD)
    assert len(plain) == 12
    assert not any(line.startswith("Buy budget:") for line in plain)
    used = describe_rules(replace(MONTHLY_HOLD, id="monthly-hold-fill", reserve_basis="fill"))
    assert len(used) == 13
    assert used[1:12] == plain[1:12]  # index 0 is the rule-set id, which differs by construction
    assert used[12].startswith("Buy budget:")
    assert "hindsight" in used[12]
