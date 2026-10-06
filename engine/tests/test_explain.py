"""explain: notes for the newest paper entries, from their stored evidence only; every reply is
vetted, and the night never fails (PG for the step, pure for the checks)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from psycopg.types.json import Jsonb

from seer_engine import cli, llm
from seer_engine.commands import explain

LAST = date(2026, 10, 30)
NEXT = date(2026, 11, 2)
OLD = date(2026, 10, 1)
F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"

AAPL_FACTS = [
    "AAPL closed at $190.00, 6.1% above its 200-day average.",
    "Its 2-day strength score was 4 out of 100; below 10 counts as a sharp short drop.",
    "It came 1st of 2 stocks that qualified tonight.",
]
JNJ_FACTS = [
    "JNJ closed at $151.20, 2.4% above its 200-day average.",
    "Its 2-day strength score was 7 out of 100; below 10 counts as a sharp short drop.",
    "It came 2nd of 2 stocks that qualified tonight.",
]
NVDA_FACTS = [  # phase 1's exact FACTOR wording
    "Its price rose 48.2% from 12 months ago to 1 month ago.",
    "It ranked 3rd of 412 stocks checked on that move, strongest first.",
    "SPY closed 4.1% above its 200-day average, so the method is allowed to hold stocks.",
]
SPY_FACTS = ["SPY closed at $671.20, 8.3% above its 200-day average of $619.80, so the rule says hold."]

Reply = Callable[[str, str], str]


def paper_note(symbol: str, prompt: str) -> str:
    return f"  Paper note\n for {symbol}.  "


class FakeClient:
    """Records every call; replies ``reply(symbol, prompt)`` (default: "Paper note for X.")."""

    def __init__(self, fail_on: set[str] | None = None, fail_all: bool = False, reply: Reply = paper_note):
        self.fail_on = fail_on or set()
        self.fail_all = fail_all
        self.reply = reply
        self.prompts: list[str] = []
        self.systems: list[str] = []
        self.kwargs: list[dict[str, object]] = []

    def complete(
        self,
        system: str,
        prompt: str,
        *,
        temperature: float | None = None,
        thinking: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.prompts.append(prompt)
        self.systems.append(system)
        self.kwargs.append({"temperature": temperature, "thinking": thinking, "max_tokens": max_tokens})
        symbol = next(line for line in prompt.splitlines() if line.startswith("Stock: "))[len("Stock: "):]
        if self.fail_all or symbol in self.fail_on:
            raise llm.LlmError("HTTP 503 from the LLM endpoint: busy", 503)
        return self.reply(symbol, prompt)


def seed(pg) -> None:
    """Rows as `paper` (with phase 2's evidence) would leave them after deciding session NEXT."""
    for sid in ("SPY", "A", F4, F1):
        pg.execute(
            "INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd,"
            " usd_idr, pending_session, pending_decision) VALUES (%s, %s, 1000, 1000, 1200, 16500, %s, %s)",
            (sid, LAST, NEXT, sid in (F4, F1)),
        )
    order_sql = (
        "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price,"
        " tp_price, sl_price, shares, explanation, status, evidence)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    pg.execute(order_sql, ("A", NEXT, 1, "AAPL", "Apple Inc.", 190, 185, 195, 180, 10, None, "pending", Jsonb(AAPL_FACTS)))
    pg.execute(order_sql, ("A", NEXT, 2, "JNJ", "Johnson & Johnson", 151, 148, 155, 145, 3, None, "pending", Jsonb(JNJ_FACTS)))
    pg.execute(order_sql, ("A", NEXT, 3, "MSFT", "Microsoft", 400, 390, 410, 380, 2, "kept", "pending", Jsonb(AAPL_FACTS)))
    pg.execute(order_sql, ("A", NEXT, 4, "PFE", "Pfizer", 27, 27, 28, 26, 30, None, "pending", None))  # no evidence
    pg.execute(order_sql, ("A", LAST, 1, "KO", "Coca-Cola", 60, 59, 61, 58, 30, None, "open", Jsonb(AAPL_FACTS)))
    target_sql = (
        "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price, limit_price, evidence)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    pg.execute(target_sql, (F4, NEXT, 1, "NVDA", Decimal("0.05"), 120, Decimal("122.40"), Jsonb(NVDA_FACTS)))
    pg.execute(target_sql, (F4, NEXT, 2, "AAPL", Decimal("0.05"), 190, Decimal("193.80"), Jsonb(NVDA_FACTS)))
    pg.execute(target_sql, (F4, NEXT, 3, "META", Decimal("0.05"), 700, Decimal("714.00"), Jsonb([])))  # empty
    pg.execute(target_sql, (F4, OLD, 1, "AMD", Decimal("0.05"), 150, Decimal("153.00"), Jsonb(NVDA_FACTS)))
    pg.execute(target_sql, (F1, NEXT, 1, "SPY", Decimal("1"), 660, Decimal("673.20"), Jsonb(SPY_FACTS)))
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
    assert order_notes(pg) == {"AAPL": None, "JNJ": None, "MSFT": "kept", "PFE": None, "KO": None}
    assert set(target_notes(pg).values()) == {None}


# ---- the step (PG) ---------------------------------------------------------------------------


def test_fills_only_the_newest_entries_that_have_evidence(pg):
    seed(pg)
    client = FakeClient()
    assert explain.execute(pg, client=client) == 0
    assert order_notes(pg) == {
        "AAPL": "Paper note for AAPL.",
        "JNJ": "Paper note for JNJ.",
        "MSFT": "kept",
        "PFE": None,  # no evidence: skipped, never sent
        "KO": None,  # an older, open order
    }
    assert target_notes(pg) == {
        (F4, NEXT, "NVDA"): "Paper note for NVDA.",
        (F4, NEXT, "AAPL"): None,  # already held: a re-weight, not a new entry
        (F4, NEXT, "META"): None,  # evidence is an empty array: skipped
        (F4, OLD, "AMD"): None,  # an older decision
        (F1, NEXT, "SPY"): "Paper note for SPY.",  # SPY held by the benchmark, not by F1
    }
    assert len(client.prompts) == 4
    assert not any("Stock: PFE" in p or "Stock: META" in p for p in client.prompts)


def test_prompt_is_the_plain_name_the_stock_and_its_facts_only(pg):
    seed(pg)
    client = FakeClient()
    explain.execute(pg, client=client)
    aapl, jnj, nvda, spy = client.prompts
    assert aapl.splitlines()[:2] == ["Method: Quant, a research method followed on paper.", "Stock: AAPL"]
    for fact in AAPL_FACTS:
        assert f"- {fact}" in aapl
    assert "- " + JNJ_FACTS[0] in jnj and AAPL_FACTS[0] not in jnj
    assert "Method: Momentum," in nvda and "Method: Trend," in spy
    for fact in NVDA_FACTS:
        assert f"- {fact}" in nvda
    for p in client.prompts:
        assert "at most 2 short plain sentences" in p and "using only these facts" in p
        assert "No advice, no predictions." in p
        # no order mechanics, no roster codes, no paper boilerplate (R4, R8)
        for gone in ("PAPER", "paper trade", "Take-profit", "Stop-loss", "limit", "shares", "Rule set",
                     "A · Quant", "F4", "F1", "Apple Inc.", "$185.00", "Target weight"):
            assert gone not in p


def test_call_disables_thinking_at_temperature_zero(pg):
    seed(pg)
    client = FakeClient()
    explain.execute(pg, client=client)
    assert client.kwargs == [
        {"temperature": 0.0, "thinking": "disabled", "max_tokens": explain.EXPLAIN_MAX_TOKENS}
    ] * 4
    assert set(client.systems) == {explain.SYSTEM}
    assert "Never recommend buying or selling, never predict prices" in explain.SYSTEM


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


def test_rejected_replies_stay_null_and_never_stop_the_night(pg, monkeypatch, caplog):
    seed(pg)
    monkeypatch.setattr(explain, "MAX_CONSECUTIVE_FAILURES", 2)
    client = FakeClient(reply=lambda symbol, prompt: f"{symbol} rose 99% in a week.")
    assert explain.execute(pg, client=client) == 0
    assert len(client.prompts) == 4  # a rejection is not an outage: every entry was still asked
    all_null_except_kept(pg)
    assert "explanation rejected for A AAPL: number not in the facts: 99" in caplog.text


def test_a_rejection_resets_the_failure_count(pg, monkeypatch):
    seed(pg)
    monkeypatch.setattr(explain, "MAX_CONSECUTIVE_FAILURES", 2)
    # AAPL fails, JNJ answers (rejected: a buy word), NVDA fails, SPY answers well. Without the reset
    # the second failure would stop the night before SPY.
    client = FakeClient(
        fail_on={"AAPL", "NVDA"},
        reply=lambda symbol, prompt: "A buy." if symbol == "JNJ" else f"Paper note for {symbol}.",
    )
    assert explain.execute(pg, client=client) == 0
    assert len(client.prompts) == 4
    assert target_notes(pg)[(F1, NEXT, "SPY")] == "Paper note for SPY."
    assert order_notes(pg)["JNJ"] is None


def test_the_same_note_twice_in_one_strategy_is_kept_once(pg):
    seed(pg)
    same = FakeClient(reply=lambda symbol, prompt: "The method picked this stock on its own numbers.")
    assert explain.execute(pg, client=same) == 0
    notes = order_notes(pg)
    assert notes["AAPL"] == "The method picked this stock on its own numbers."
    assert notes["JNJ"] is None  # a copy of AAPL's note in the same strategy
    # another strategy's batch is judged on its own
    assert target_notes(pg)[(F4, NEXT, "NVDA")] == "The method picked this stock on its own numbers."


def test_client_bug_never_raises(pg):
    seed(pg)

    class Broken:
        def complete(self, system, prompt, **kwargs):
            raise KeyError("unexpected")

    assert explain.execute(pg, client=Broken()) == 0
    all_null_except_kept(pg)


def test_empty_reply_counts_as_unavailable(pg):
    seed(pg)

    class Blank:
        def complete(self, system, prompt, **kwargs):
            return "   \n "

    assert explain.execute(pg, client=Blank()) == 0
    all_null_except_kept(pg)


def test_dry_run_writes_nothing(pg):
    seed(pg)
    client = FakeClient()
    assert explain.execute(pg, client=client, dry_run=True) == 0
    assert len(client.prompts) == 4
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


# ---- the checks (pure) -----------------------------------------------------------------------

FACTS = (
    "NVDA rose 48.2% over the 12 months up to a month ago.",
    "That ranked 3rd of 412 eligible stocks.",
    "SPY closed at $671.20, 8.3% above its 200-day average of $1,619.80.",
)


@pytest.mark.parametrize(
    ("reply", "want"),
    [
        ("NVDA rose 48.2% over the past 12 months, the 3rd best of 412 stocks.",
         "NVDA rose 48.2% over the past 12 months, the 3rd best of 412 stocks."),
        ('  **"NVDA rose 48.20% over 12 months."**  ', "NVDA rose 48.20% over 12 months."),  # markup, quotes, zeros
        ("- NVDA rose 48.2% over 12 months.", "NVDA rose 48.2% over 12 months."),  # a bullet
        ("SPY was 8.3% above its 1619.8 average.", "SPY was 8.3% above its 1619.8 average."),  # $ , and zeros
        ("NVDA rose 48.2% over 12 months. That ranked 3rd of 412 stocks.",
         "NVDA rose 48.2% over 12 months. That ranked 3rd of 412 stocks."),  # two sentences
        ("NVDA ranked 3rd of 412 stocks, ahead of the buyback names.",
         "NVDA ranked 3rd of 412 stocks, ahead of the buyback names."),  # "buyback" is not "buy"
        ("S01 ranked 3rd of 412 stocks.", "S01 ranked 3rd of 412 stocks."),  # a symbol's digits are no number
    ],
)
def test_vet_accepts(reply, want):
    assert explain.vet(reply, FACTS) == want
    assert explain.accept(reply, FACTS) == want


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        ("", "empty"),
        ("  \n ", "empty"),
        ("NVDA rose 50% over 12 months.", "number not in the facts: 50"),
        ("NVDA rose 48.2% over 12 months and ranked", "not a complete sentence"),
        ("NVDA rose 48.2%…", "ellipsis"),
        ("NVDA rose 48.2%...", "ellipsis"),
        ("NVDA rose 48.2%. It ranked 3rd. Of 412 stocks.", "3 sentences"),
        ("NVDA rose 48.2% over 12 months " + "and kept its place " * 20 + ".", "characters"),
        ("You should look at NVDA, which rose 48.2%.", "should"),
        ("NVDA shouldn't fall.", "should"),
        ("NVDA is a buy after rising 48.2%.", "buy"),
        ("NVDA hit a sell signal.", "sell"),
        ("Analysts recommend NVDA.", "recommend"),
        ("NVDA will rise after its 48.2% gain.", "a price move"),  # match= is a regex: no "+"
        ("NVDA is going to climb.", "going to"),
        ("We expect NVDA to keep its place.", "expect"),
        ("Returns are not guaranteed.", "guarantee"),
    ],
)
def test_vet_rejects(reply, reason):
    with pytest.raises(explain.Rejected, match=reason):
        explain.vet(reply, FACTS)
    assert explain.accept(reply, FACTS) is None


def test_vet_rejects_a_copy_of_an_earlier_note():
    with pytest.raises(explain.Rejected, match="same as an earlier note"):
        explain.vet("NVDA rose 48.2% over 12 months.", FACTS, ["  nvda rose 48.2% over 12 months. "])
    assert explain.vet("NVDA rose 48.2% over 12 months.", FACTS, ["NVDA ranked 3rd of 412 stocks."])


def test_a_past_tense_phrase_the_facts_use_is_allowed():
    facts = ("Its last earnings came in above what was expected.",)
    assert explain.vet("Its last earnings came in above what was expected.", facts)
    with pytest.raises(explain.Rejected, match="expect"):
        explain.vet("Its last earnings came in above what was expected.", FACTS)


def test_accepted_notes_are_short_and_never_cut():
    assert explain.MAX_CHARS <= 320 and explain.MAX_SENTENCES == 2
    long = "NVDA rose 48.2% over 12 months " + "and kept its place " * 20 + "."
    assert explain.clean(long).endswith(".")  # clean never cuts and never adds an ellipsis
    assert "…" not in explain.clean(long)


def test_numbers_in():
    assert explain.numbers_in("$1,850.00, 6.10%, +3, S01, F4, 12-1, 3rd, 0.50") == {"1850", "6.1", "3", "12", "1", "0.5"}


@pytest.mark.parametrize(
    ("name", "want"),
    [("A · Quant", "Quant"), ("F4 · Momentum", "Momentum"), ("C · News veto", "News veto"), ("SPY", "SPY")],
)
def test_plain_name(name, want):
    assert explain.plain_name(name) == want


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        (None, ()),
        ([], ()),
        (["  a  b ", "", "c"], ("a b", "c")),
        ("a", ()),
        ([1, "a"], ()),
        ({"a": "b"}, ()),
    ],
)
def test_facts_from(raw, want):
    assert explain.facts_from(raw) == want


# Phase 1's exact fact shapes (strategies/evidence.py "Fact strings", real prototype output). A faithful
# note that restates them must pass vet: every number is extracted identically from facts and note, and
# no fact carries a BANNED word (the reconciled trend fact says "hold stocks", not "buy").
PHASE_ONE_FACTS = (
    ("It closed at $219.00, 1.9% above its 200-day average of $215.00.",
     "Its 2-day strength score was 1.1 out of 100; below 10 counts as a sharp short drop.",
     "Over the last 2 trading days it fell 2.6%, and over the last 5 it fell 2.4%.",
     "On an average day over the last 20 trading days, $224 million of its shares changed hands.",
     "It ranked 1st of 3 stocks that passed the rule that day, lowest strength score first."),
    ("Its price rose 60% from 12 months ago to 1 month ago.",
     "It ranked 1st of 5 stocks checked on that move, strongest first.",
     "SPY closed 9.8% above its 200-day average, so the method is allowed to hold stocks."),
    ("SPY closed at $1,231.40, 9.8% above its 200-day average of $1,121.50.",
     "The rule holds SPY while SPY closes above its 200-day average, so it holds SPY."),
    ("It ranked 1st of 5 companies checked on a combined score of 4 measures from its financial filings.",
     "Its net worth on its books is 623.4% of its stock-market value, the highest of the 5 companies checked.",
     "It earned 12.5% on its shareholders' money in its last fiscal year, the lowest of the 5 companies checked.",
     "Its latest quarterly earnings beat the same quarter a year earlier by 2.8 times the usual size of its "
     "earnings surprises, higher than 25% of the other companies checked.",
     "Its latest financial filing used here is 252 days old."),
)


@pytest.mark.parametrize("facts", PHASE_ONE_FACTS)
def test_phase_one_fact_shapes_pass_the_checks(facts):
    joined = " ".join(facts)
    assert not [b.label for b in explain.BANNED if b.pattern.search(joined)]
    for fact in facts:  # each fact restated verbatim is an acceptable note
        assert explain.vet(fact, facts) == fact
    assert explain.vet(f"{facts[0]} {facts[1]}", facts)  # and two of them together
    assert explain.numbers_in("$224 million, 3rd of 412, 200-day, $1,231.40, 6.1%") == {
        "224", "3", "412", "200", "1231.4", "6.1"
    }
