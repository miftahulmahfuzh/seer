"""paper.store's news-veto API on Postgres (strategy-c-news-veto contract K3, migration 004):
round trip, order by rank, validation before any write, has_vetoes, allowed_between."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import psycopg
import pytest

from seer_engine.paper import store
from seer_engine.paper.store import NewsVerdict
from seer_engine.strategies.c import PROMPT_VERSION, VERDICTS

S1, S2, S3, S4 = date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8), date(2026, 10, 9)
DECIDED = datetime(2026, 10, 5, 23, 31, 7, 250000, tzinfo=timezone.utc)
HEADLINES = (
    {"id": 9002, "datetime": "2026-10-05T21:10:00Z", "source": "Reuters", "headline": "NVIDIA ships a new chip"},
    {"id": 9001, "datetime": "2026-10-05T14:02:00Z", "source": "Yahoo", "headline": "Chip stocks rally"},
)


def verdict(rank: int, symbol: str, v: str = "allow", **kw) -> NewsVerdict:
    base = NewsVerdict(
        rank=rank,
        symbol=symbol,
        verdict=v,
        reason=f"{symbol}: no event risk in the window.",
        model="glm-5.3",
        prompt_version=PROMPT_VERSION,
        headlines=(),
        earnings_date=None,
        decided_at=DECIDED,
    )
    return replace(base, **kw)


NIGHT = (
    verdict(1, "NVDA", "allow", headlines=HEADLINES),
    verdict(2, "BRK.B", "veto", reason="Earnings on 2026-10-08, inside the window.", earnings_date=S3),
    verdict(3, "AAPL", "failed", reason="LLM_* is not configured", model=None),
    verdict(4, "MSFT", "allow"),
)


def count(conn) -> int:
    return conn.execute("SELECT count(*) FROM news_vetoes").fetchone()[0]


def test_verdicts_are_the_three_k2_values():
    assert VERDICTS == ("allow", "veto", "failed")


def test_write_then_read_round_trips_by_rank(pg):
    assert store.read_vetoes(pg, "C", S1) == ()
    assert store.write_vetoes(pg, "C", S1, NIGHT) == 4
    back = store.read_vetoes(pg, "C", S1)
    assert back == NIGHT
    assert back[0].headlines == HEADLINES and back[0].decided_at == DECIDED
    assert back[0].decided_at.utcoffset() is not None
    assert back[1].earnings_date == S3 and back[2].model is None


def test_rows_come_back_by_rank_whatever_the_write_order(pg):
    store.write_vetoes(pg, "C", S1, tuple(reversed(NIGHT)))
    assert [v.rank for v in store.read_vetoes(pg, "C", S1)] == [1, 2, 3, 4]
    assert [v.symbol for v in store.read_vetoes(pg, "C", S1)] == ["NVDA", "BRK.B", "AAPL", "MSFT"]


def test_headlines_are_stored_as_a_jsonb_list_newest_first(pg):
    store.write_vetoes(pg, "C", S1, NIGHT[:1])
    stored = pg.execute("SELECT headlines FROM news_vetoes WHERE symbol = 'NVDA'").fetchone()[0]
    assert stored == [dict(h) for h in HEADLINES]


def test_has_vetoes_is_per_strategy_and_session(pg):
    assert store.has_vetoes(pg, "C", S1) is False
    store.write_vetoes(pg, "C", S1, NIGHT[:2])
    assert store.has_vetoes(pg, "C", S1) is True
    assert store.has_vetoes(pg, "C", S2) is False
    assert store.has_vetoes(pg, "A", S1) is False


def test_a_second_write_for_the_session_is_a_database_error(pg):
    store.write_vetoes(pg, "C", S1, NIGHT[:2])
    pg.commit()
    with pytest.raises(psycopg.errors.UniqueViolation):
        store.write_vetoes(pg, "C", S1, NIGHT[:1])
    pg.rollback()
    assert count(pg) == 2


def test_an_empty_night_writes_nothing(pg):
    assert store.write_vetoes(pg, "C", S1, ()) == 0
    assert count(pg) == 0
    assert store.has_vetoes(pg, "C", S1) is False


def test_nothing_commits(pg):
    store.write_vetoes(pg, "C", S1, NIGHT)
    pg.rollback()
    assert count(pg) == 0


BAD = [
    pytest.param((verdict(1, "NVDA"), verdict(3, "AAPL")), ValueError, "ranks must be 1..2", id="rank-gap"),
    pytest.param((verdict(2, "NVDA"),), ValueError, "ranks must be 1..1", id="rank-not-from-1"),
    pytest.param((verdict(1, "NVDA"), verdict(1, "AAPL")), ValueError, "ranks must be 1..2", id="rank-repeat"),
    pytest.param((verdict(1, "NVDA"), verdict(2, "NVDA")), ValueError, "symbols must be unique", id="symbol-repeat"),
    pytest.param((verdict(1, "NVDA", "maybe"),), ValueError, "is not one of", id="verdict"),
    pytest.param((verdict(1, "NVDA", "Allow"),), ValueError, "is not one of", id="verdict-case"),
    pytest.param((verdict(1, ""),), ValueError, "symbol must be a non-empty str", id="symbol-empty"),
    pytest.param(
        (verdict(1, "NVDA", decided_at=datetime(2026, 10, 5, 23, 31)),), ValueError, "tz-aware", id="naive-decided-at"
    ),
    pytest.param((verdict(1, "NVDA", decided_at=S1),), ValueError, "tz-aware", id="date-decided-at"),
    pytest.param((verdict(1, "NVDA", prompt_version=""),), ValueError, "prompt_version", id="prompt-version"),
    pytest.param((verdict(1, "NVDA", reason=None),), TypeError, "reason must be a str", id="reason-none"),
    pytest.param((verdict(1, "NVDA", model=5),), TypeError, "model must be a str or None", id="model-type"),
    pytest.param((replace(verdict(1, "NVDA"), rank=True),), TypeError, "rank must be an int", id="rank-bool"),
    pytest.param((verdict(1, "NVDA", headlines=("x",)),), TypeError, "headline must be a mapping", id="headline"),
    pytest.param(
        (verdict(1, "NVDA", earnings_date=DECIDED),), TypeError, "earnings_date must be a date", id="earnings-datetime"
    ),
    pytest.param(((1, "NVDA", "allow"),), TypeError, "must be NewsVerdict", id="not-a-verdict"),
]


@pytest.mark.parametrize(("verdicts", "error", "message"), BAD)
def test_bad_input_raises_before_any_write(pg, verdicts, error, message):
    with pytest.raises(error, match=message):
        store.write_vetoes(pg, "C", S1, verdicts)
    assert count(pg) == 0


def test_the_session_must_be_an_nyse_session(pg):
    with pytest.raises(ValueError, match="not an NYSE session"):
        store.write_vetoes(pg, "C", date(2026, 10, 10), NIGHT)  # a Saturday
    with pytest.raises(TypeError):
        store.write_vetoes(pg, "C", DECIDED, NIGHT)
    with pytest.raises(TypeError):
        store.has_vetoes(pg, "C", DECIDED)
    with pytest.raises(TypeError):
        store.read_vetoes(pg, "C", DECIDED)
    assert count(pg) == 0


def test_an_unknown_strategy_is_a_database_error(pg):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        store.write_vetoes(pg, "B", S1, NIGHT[:1])
    pg.rollback()


def nonempty(m: dict[date, frozenset[str]]) -> dict[date, frozenset[str]]:
    return {d: s for d, s in m.items() if s}


def test_allowed_between_keeps_only_allow_inclusive_and_per_strategy(pg):
    store.write_vetoes(pg, "C", S1, NIGHT)  # NVDA, MSFT allowed
    store.write_vetoes(pg, "C", S2, (verdict(1, "NVDA", "veto"), verdict(2, "AMD", "failed")))  # none allowed
    store.write_vetoes(pg, "C", S3, (verdict(1, "AMD", "allow"),))
    store.write_vetoes(pg, "C", S4, (verdict(1, "TSLA", "allow"),))
    store.write_vetoes(pg, "A", S3, (verdict(1, "XOM", "allow"),))  # another strategy's rows never leak in
    got = store.allowed_between(pg, "C", S1, S3)
    assert nonempty(got) == {S1: frozenset({"NVDA", "MSFT"}), S3: frozenset({"AMD"})}
    assert got.get(S2, frozenset()) == frozenset()
    assert S4 not in got
    assert nonempty(store.allowed_between(pg, "C", S3, S3)) == {S3: frozenset({"AMD"})}
    assert nonempty(store.allowed_between(pg, "C", S2, S2)) == {}
    assert store.allowed_between(pg, "C", S4, S1) == {}  # start after end
    assert nonempty(store.allowed_between(pg, "C", S1 - timedelta(days=30), S4 + timedelta(days=30))) == {
        S1: frozenset({"NVDA", "MSFT"}),
        S3: frozenset({"AMD"}),
        S4: frozenset({"TSLA"}),
    }


def test_allowed_between_with_no_rows_is_empty(pg):
    assert store.allowed_between(pg, "C", S1, S4) == {}
    with pytest.raises(TypeError):
        store.allowed_between(pg, "C", DECIDED, S4)
