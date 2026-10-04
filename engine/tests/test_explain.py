"""explain: fills explanations of the newest paper entries only, and never fails the night (PG)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from seer_engine import cli, llm
from seer_engine.commands import explain

LAST = date(2026, 10, 30)
NEXT = date(2026, 11, 2)
OLD = date(2026, 10, 1)
F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"


class FakeClient:
    def __init__(self, fail_on: set[str] | None = None, fail_all: bool = False):
        self.fail_on = fail_on or set()
        self.fail_all = fail_all
        self.prompts: list[str] = []

    def complete(self, system: str, prompt: str) -> str:
        self.prompts.append(prompt)
        symbol = next(line for line in prompt.splitlines() if line.startswith("- Symbol: "))
        if self.fail_all or any(f"- Symbol: {s}" in symbol for s in self.fail_on):
            raise llm.LlmError("HTTP 503 from the LLM endpoint: busy", 503)
        return f"  Paper note\n for {symbol[len('- Symbol: '):].split()[0].rstrip('.')}.  "


def seed(pg) -> None:
    """Rows as `paper` (phase 7) would leave them after deciding session NEXT."""
    for sid in ("SPY", "A", F4, F1):
        pg.execute(
            "INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd,"
            " usd_idr, pending_session, pending_decision) VALUES (%s, %s, 1000, 1000, 1200, 16500, %s, %s)",
            (sid, LAST, NEXT, sid in (F4, F1)),
        )
    order_sql = (
        "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price,"
        " tp_price, sl_price, shares, explanation, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    pg.execute(order_sql, ("A", NEXT, 1, "AAPL", "Apple Inc.", 190, 185, 195, 180, 10, None, "pending"))
    pg.execute(order_sql, ("A", NEXT, 2, "MSFT", "Microsoft", 400, 390, 410, 380, 2, "kept", "pending"))
    pg.execute(order_sql, ("A", LAST, 3, "KO", "Coca-Cola", 60, 59, 61, 58, 30, None, "open"))
    target_sql = (
        "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price, limit_price)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s)"
    )
    pg.execute(target_sql, (F4, NEXT, 1, "NVDA", Decimal("0.05"), 120, Decimal("122.40")))
    pg.execute(target_sql, (F4, NEXT, 2, "AAPL", Decimal("0.05"), 190, Decimal("193.80")))
    pg.execute(target_sql, (F4, OLD, 1, "AMD", Decimal("0.05"), 150, Decimal("153.00")))
    pg.execute(target_sql, (F1, NEXT, 1, "SPY", Decimal("1"), 660, Decimal("673.20")))
    pos_sql = (
        "INSERT INTO book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, days_held,"
        " cost_usd, income_usd) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    pg.execute(pos_sql, (F4, "AAPL", 5, 190, OLD, 180, 20, 1, 0))
    pg.execute(pos_sql, ("SPY", "SPY", 2, 660, OLD, 650, 20, 1, 0))  # the benchmark's holding, not F1's
    pg.commit()


def order_notes(pg) -> dict[str, str | None]:
    rows = pg.execute("SELECT symbol, explanation FROM orders WHERE strategy_id = 'A'").fetchall()
    pg.rollback()
    return dict(rows)


def target_notes(pg) -> dict[tuple[str, date, str], str | None]:
    rows = pg.execute("SELECT strategy_id, session_date, symbol, explanation FROM book_targets").fetchall()
    pg.rollback()
    return {(sid, d, sym): note for sid, d, sym, note in rows}


def all_null_except_kept(pg) -> None:
    assert order_notes(pg) == {"AAPL": None, "MSFT": "kept", "KO": None}
    assert set(target_notes(pg).values()) == {None}


def test_fills_only_the_newest_unexplained_entries(pg):
    seed(pg)
    client = FakeClient()
    assert explain.execute(pg, client=client) == 0
    assert order_notes(pg) == {"AAPL": "Paper note for AAPL.", "MSFT": "kept", "KO": None}
    assert target_notes(pg) == {
        (F4, NEXT, "NVDA"): "Paper note for NVDA.",
        (F4, NEXT, "AAPL"): None,  # already held: a re-weight, not a new entry
        (F4, OLD, "AMD"): None,  # an older decision
        (F1, NEXT, "SPY"): "Paper note for SPY.",  # SPY held by the benchmark, not by F1
    }
    assert len(client.prompts) == 3


def test_prompts_carry_stored_facts_and_paper_label(pg):
    seed(pg)
    client = FakeClient()
    explain.execute(pg, client=client)
    a, nvda, spy = client.prompts
    assert "- Symbol: AAPL (Apple Inc.)." in a
    assert "buy 10 shares with a limit of $185.00 (about $1,850.00)" in a
    assert "Take-profit: $195.00. Stop-loss: $180.00." in a
    assert "Rule set: design-v0." in a and "A · Quant" in a
    assert "Target weight: 5.0% of the paper portfolio." in nvda
    assert "Paper buy limit: $122.40." in nvda and "Rule set: monthly-hold." in nvda
    assert "Target weight: 100.0%" in spy
    for p in client.prompts:
        assert "PAPER trade only" in p and "not a recommendation" in p and "at most 3" in p


def test_rerun_calls_nothing(pg):
    seed(pg)
    explain.execute(pg, client=FakeClient())
    again = FakeClient()
    assert explain.execute(pg, client=again) == 0
    assert again.prompts == []


def test_one_failure_leaves_that_entry_null_and_exits_zero(pg):
    seed(pg)
    assert explain.execute(pg, client=FakeClient(fail_on={"NVDA"})) == 0
    notes = target_notes(pg)
    assert notes[(F4, NEXT, "NVDA")] is None
    assert notes[(F1, NEXT, "SPY")] == "Paper note for SPY."
    assert order_notes(pg)["AAPL"] == "Paper note for AAPL."


def test_llm_down_leaves_everything_null_and_exits_zero(pg, monkeypatch):
    seed(pg)
    monkeypatch.setattr(explain, "MAX_CONSECUTIVE_FAILURES", 2)
    client = FakeClient(fail_all=True)
    assert explain.execute(pg, client=client) == 0
    assert len(client.prompts) == 2  # the circuit breaker stopped the third call
    all_null_except_kept(pg)


def test_client_bug_never_raises(pg):
    seed(pg)

    class Broken:
        def complete(self, system, prompt):
            raise KeyError("unexpected")

    assert explain.execute(pg, client=Broken()) == 0
    all_null_except_kept(pg)


def test_empty_reply_counts_as_unavailable(pg):
    seed(pg)

    class Blank:
        def complete(self, system, prompt):
            return "   \n "

    assert explain.execute(pg, client=Blank()) == 0
    all_null_except_kept(pg)


def test_dry_run_writes_nothing(pg):
    seed(pg)
    client = FakeClient()
    assert explain.execute(pg, client=client, dry_run=True) == 0
    assert len(client.prompts) == 3
    all_null_except_kept(pg)


def test_no_paper_state_is_a_no_op(pg):
    client = FakeClient()
    assert explain.execute(pg, client=client) == 0
    assert client.prompts == []


def test_missing_config_exits_zero_without_touching_the_db(pg, monkeypatch, caplog):
    seed(pg)
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    # DATABASE_URL_UNPOOLED points at an invalid host (conftest): a connection attempt would fail.
    assert cli.main(["explain"]) == 0
    assert "explanations unavailable" in caplog.text
    all_null_except_kept(pg)


def test_cli_end_to_end(pg_schema, pg, monkeypatch):
    seed(pg)
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.test/api/anthropic")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "glm-test")
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", pg_schema.url)
    fake = FakeClient()
    monkeypatch.setattr(llm, "Client", lambda cfg: fake)
    assert cli.main(["explain"]) == 0
    assert target_notes(pg)[(F4, NEXT, "NVDA")] == "Paper note for NVDA."
    assert cli.main(["--dry-run", "explain"]) == 0  # nothing left to explain; still 0


@pytest.mark.parametrize(
    ("raw", "want"),
    [("  a\n b  ", "a b"), ("", None), ("  \n", None)],
)
def test_clean(raw, want):
    assert explain.clean(raw) == want


def test_clean_caps_length():
    out = explain.clean("word " * 400)
    assert out is not None and len(out) <= explain.MAX_CHARS + 1 and out.endswith("…")
