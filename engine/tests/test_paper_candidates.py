"""Seer Adversarial (027): the list each reviewable decision is written down with.

- ``paper.candidates`` (pure): a bracket method's own top 10 before any veto, a book's rank targets
  without the idle instrument, ranked by weight; the next session a book ranks.
- ``paper.store``: ``save_candidates`` validates, replaces, and writes nothing when nothing changed;
  ``read_candidates`` gives it back.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

import test_paper_command as tp
from seer_engine.paper import store
from seer_engine.paper.candidates import (
    CANDIDATE_TOP,
    Candidate,
    book_candidates,
    bracket_candidates,
    next_rank_session,
)
from seer_engine.sim import Pick
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC, MONTHLY_RANK_WEEKLY_RESIZE_FRAC
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.base import history_from_bars
from seer_engine.strategies.c import STRATEGY_C, STRATEGY_C_PARAMS

SESSION = date(2026, 11, 4)
NIGHT = date(2026, 11, 3)  # prev_session(SESSION)


def pick(symbol: str) -> Pick:
    return Pick(symbol, Decimal("10"), Decimal("10"), Decimal("11"), Decimal("9"))


@dataclass(frozen=True, eq=False)
class Ranked:
    """A bracket strategy that ranks fixed symbols, in order, whatever the history."""

    symbols: tuple[str, ...]
    id: str = "RANKED"
    lookback: int = 1

    def picks(self, history, members, data_date, params):
        return [pick(s) for s in self.symbols]

    def prepare(self, history):
        return history

    def picks_prepared(self, prepared, members, data_date, params):
        return self.picks(prepared, members, data_date, params)


def synthetic_history():
    by_symbol = defaultdict(list)
    for b in tp.synthetic_bars():
        by_symbol[b.symbol].append(b)
    return {s: history_from_bars(s, sorted(v, key=lambda b: b.date)) for s, v in by_symbol.items()}


def target(symbol: str, weight: str) -> Target:
    return Target(symbol=symbol, weight=Decimal(weight), last=Decimal("10.0000"))


# ---- pure ----------------------------------------------------------------------------------------


def test_a_bracket_list_is_the_methods_own_ranking_cut_to_ten():
    symbols = tuple(f"S{i:02d}" for i in range(1, 13))
    found = bracket_candidates(Ranked(symbols), None, {}, frozenset(symbols), NIGHT)
    assert CANDIDATE_TOP == 10
    assert found == tuple(Candidate(rank=i, symbol=s) for i, s in enumerate(symbols[:10], start=1))
    assert all(c.weight is None for c in found)


def test_a_symbol_ranked_twice_is_listed_once_at_its_first_rank():
    found = bracket_candidates(Ranked(("X", "Y", "X", "Z")), None, {}, frozenset(), NIGHT)
    assert [(c.rank, c.symbol) for c in found] == [(1, "X"), (2, "Y"), (3, "Z")]


def test_c_lists_a_ranking_before_its_veto_and_a_lists_the_same():
    """On the synthetic world's first night A ranks COST then NVDA (measured 2026-11-05).
    C carries no verdict, so it would buy nothing, yet its list is A's ranking, not the allowed set."""
    history = synthetic_history()
    members = frozenset(tp.STOCKS)
    a = bracket_candidates(STRATEGY_A, STRATEGY_A_PARAMS, history, members, tp.N0)
    c = bracket_candidates(STRATEGY_C, STRATEGY_C_PARAMS, history, members, tp.N0)
    assert [x.symbol for x in a] == ["COST", "NVDA"]
    assert c == a
    assert STRATEGY_C.picks(history, members, tp.N0, STRATEGY_C_PARAMS) == []  # what C itself would buy


def test_a_bracket_list_reads_nothing_after_its_night():
    history = synthetic_history()
    members = frozenset(tp.STOCKS)
    cut = {s: h.upto(tp.N0) for s, h in history.items()}
    assert bracket_candidates(STRATEGY_A, STRATEGY_A_PARAMS, history, members, tp.N0) == bracket_candidates(
        STRATEGY_A, STRATEGY_A_PARAMS, cut, members, tp.N0
    )


def test_a_book_list_drops_the_idle_row_and_ranks_by_weight_then_symbol():
    found = book_candidates(
        [target("MSFT", "0.200000"), target("AAPL", "0.200000"), target("XOM", "0.400000"), target("BIL", "0.200000")],
        "BIL",
    )
    assert found == (
        Candidate(rank=1, symbol="XOM", weight=Decimal("0.400000")),
        Candidate(rank=2, symbol="AAPL", weight=Decimal("0.200000")),
        Candidate(rank=3, symbol="MSFT", weight=Decimal("0.200000")),
    )
    assert book_candidates([target("BIL", "1.000000")], "BIL") == ()
    assert book_candidates([], None) == ()
    with pytest.raises(ValueError, match="targeted twice"):
        book_candidates([target("X", "0.500000"), target("X", "0.500000")], None)


def test_the_next_rank_session_skips_resize_only_sessions_and_honours_a_kickoff():
    # monthly: the first session of October, then of November (2026-11-01 is a Sunday)
    assert next_rank_session(MONTHLY_HOLD_FRAC, date(2026, 9, 24), kickoff=False) == date(2026, 10, 1)
    assert next_rank_session(MONTHLY_HOLD_FRAC, date(2026, 9, 30), kickoff=False) == date(2026, 10, 1)
    assert next_rank_session(MONTHLY_HOLD_FRAC, date(2026, 10, 1), kickoff=False) == date(2026, 11, 2)
    # tonight's decision is the kickoff: that session ranks, off the cadence
    assert next_rank_session(MONTHLY_HOLD_FRAC, date(2026, 9, 23), kickoff=True) == date(2026, 9, 24)
    # monthly rank, weekly resize: Monday 2026-09-28 only re-scales, so it is not the answer
    assert next_rank_session(MONTHLY_RANK_WEEKLY_RESIZE_FRAC, date(2026, 9, 25), kickoff=False) == date(2026, 10, 1)


def test_a_candidate_refuses_a_bad_rank_symbol_or_weight():
    with pytest.raises(ValueError):
        Candidate(rank=0, symbol="X")
    with pytest.raises(TypeError):
        Candidate(rank=True, symbol="X")
    with pytest.raises(ValueError):
        Candidate(rank=1, symbol="")
    with pytest.raises(TypeError):
        Candidate(rank=1, symbol="X", weight=0.5)
    with pytest.raises(ValueError):
        Candidate(rank=1, symbol="X", weight=Decimal("0"))


# ---- store (027) -----------------------------------------------------------------------------------


def stored(pg, sid, session):
    return pg.execute(
        "SELECT kind, data_date, rank, symbol, weight, evidence, created_at FROM strategy_candidates "
        "WHERE strategy_id = %s AND session_date = %s ORDER BY rank",
        (sid, session),
    ).fetchall()


def test_save_candidates_round_trips_and_stores_evidence(pg):
    items = (Candidate(1, "NVDA"), Candidate(2, "COST"))
    facts = {"NVDA": ("It closed at $180.00.",)}
    assert store.save_candidates(pg, "A-GT", SESSION, NIGHT, "bracket", items, evidence=facts) is True
    assert store.read_candidates(pg, "A-GT", SESSION) == items
    rows = stored(pg, "A-GT", SESSION)
    assert [r[:6] for r in rows] == [
        ("bracket", NIGHT, 1, "NVDA", None, ["It closed at $180.00."]),
        ("bracket", NIGHT, 2, "COST", None, None),
    ]
    book = (Candidate(1, "XOM", Decimal("0.050000")), Candidate(2, "CVX", Decimal("0.050000")))
    assert store.save_candidates(pg, "COSK-FR-GT", SESSION, NIGHT, "book", book) is True
    assert store.read_candidates(pg, "COSK-FR-GT", SESSION) == book
    pg.rollback()


def test_an_unchanged_list_is_not_rewritten_and_a_changed_one_is_replaced(pg):
    items = (Candidate(1, "NVDA"), Candidate(2, "COST"))
    assert store.save_candidates(pg, "A-GT", SESSION, NIGHT, "bracket", items) is True
    pg.commit()
    first = stored(pg, "A-GT", SESSION)
    assert store.save_candidates(pg, "A-GT", SESSION, NIGHT, "bracket", items) is False
    pg.commit()
    assert stored(pg, "A-GT", SESSION) == first  # created_at included: nothing was touched
    assert store.save_candidates(pg, "A-GT", SESSION, NIGHT, "bracket", (Candidate(1, "COST"),)) is True
    assert store.read_candidates(pg, "A-GT", SESSION) == (Candidate(1, "COST"),)
    assert store.save_candidates(pg, "A-GT", SESSION, NIGHT, "bracket", ()) is True
    assert store.read_candidates(pg, "A-GT", SESSION) == ()
    pg.rollback()


def test_save_candidates_refuses_a_malformed_list_before_writing(pg):
    ok = (Candidate(1, "NVDA"),)
    with pytest.raises(ValueError, match="night of"):
        store.save_candidates(pg, "A-GT", SESSION, date(2026, 11, 2), "bracket", ok)
    with pytest.raises(ValueError, match="kind"):
        store.save_candidates(pg, "A-GT", SESSION, NIGHT, "veto", ok)
    with pytest.raises(ValueError, match="1..n"):
        store.save_candidates(pg, "A-GT", SESSION, NIGHT, "bracket", (Candidate(2, "NVDA"),))
    with pytest.raises(ValueError, match="twice"):
        store.save_candidates(pg, "A-GT", SESSION, NIGHT, "bracket", (Candidate(1, "X"), Candidate(2, "X")))
    with pytest.raises(ValueError, match="no weight"):
        store.save_candidates(pg, "A-GT", SESSION, NIGHT, "bracket", (Candidate(1, "X", Decimal("0.5")),))
    with pytest.raises(ValueError, match="target weight"):
        store.save_candidates(pg, "COSK-FR-GT", SESSION, NIGHT, "book", ok)
    with pytest.raises(ValueError, match="decimals"):
        store.save_candidates(pg, "COSK-FR-GT", SESSION, NIGHT, "book", (Candidate(1, "X", Decimal("0.1234567")),))
    assert pg.execute("SELECT count(*) FROM strategy_candidates").fetchone()[0] == 0
    pg.rollback()


def test_a_preview_stores_its_next_rank_session(pg):
    store.save_book_preview(
        pg, "COSK-FR-GT", NIGHT, [target("XOM", "0.050000")], next_decision_session=date(2026, 12, 1)
    )
    assert pg.execute(
        "SELECT data_date, symbol, next_decision_session FROM book_previews WHERE strategy_id = 'COSK-FR-GT'"
    ).fetchall() == [(NIGHT, "XOM", date(2026, 12, 1))]
    store.save_book_preview(pg, "COSK-FR-GT", NIGHT, [target("XOM", "0.050000")])
    assert pg.execute("SELECT next_decision_session FROM book_previews").fetchall() == [(None,)]
    with pytest.raises(ValueError, match="not after"):
        store.save_book_preview(pg, "COSK-FR-GT", NIGHT, [target("XOM", "0.050000")], next_decision_session=NIGHT)
    pg.rollback()
