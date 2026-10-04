"""`veto`: Strategy C's news check on Postgres with synthetic bars and fake Finnhub/LLM clients.

The world is `test_paper_command`'s synthetic market (bars through 2026-10-09, so a look-ahead on
bars would be visible). On the night of 2026-08-06 A ranks five candidates for 2026-08-07, so
every failure path, the consecutive-failure stop and the rank order are exercised. The clients
are fakes handed to `veto.execute` through its factories; nothing touches the network.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import psycopg
import pytest
from psycopg.rows import tuple_row

import test_paper_command as tp
from seer_engine import bars, cli, dates, db, fx, llm, runs
from seer_engine.commands import paper, paper_check, veto
from seer_engine.finnhub import FinnhubError
from seer_engine.paper import store
from seer_engine.strategies import c
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.base import history_from_bars

UTC = timezone.utc
NIGHT = date(2026, 8, 6)  # a Thursday; A ranks five candidates on the synthetic market
NOW = datetime(2026, 8, 6, 23, tzinfo=UTC)
SESSION = date(2026, 8, 7)
NEWS_FROM, NEWS_TO = date(2026, 8, 3), date(2026, 8, 6)  # ET run date - 3 days .. ET run date
WINDOW_END = date(2026, 8, 13)  # the 5th session counting 2026-08-07 as 1

FH_KEY = "fh-sekret-0123456789"
LLM_KEY = "llm-sekret-9876543210"
LLM_ENV = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")

ALLOW = '{"verdict": "allow", "reason": "Only routine product news."}'
VETO = '```json\n{"verdict": "veto", "reason": "Earnings are due inside the window."}\n```'


# ---- the synthetic world -----------------------------------------------------------------------


@pytest.fixture
def world(pg):
    """`test_paper_command`'s bars, FX and universe (no dividends: `veto` never reads them)."""
    with db.transaction(pg, False):
        bars.upsert_bars(pg, tp.synthetic_bars())
        fx.upsert_fx(pg, [(d, tp.fx_rate(d)) for d in tp._sessions()])
        for s in tp.STOCKS:
            pg.execute(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, 'SP500', '2020-01-02', NULL, %s)",
                (s, s),
            )
    return pg


@lru_cache(maxsize=1)
def expected_symbols() -> tuple[str, ...]:
    """A's ranked picks for SESSION, computed without the database (full history cut at NIGHT)."""
    by_symbol = defaultdict(list)
    for b in tp.synthetic_bars():
        by_symbol[b.symbol].append(b)
    history = {s: history_from_bars(s, bs).upto(NIGHT) for s, bs in by_symbol.items()}
    picks = STRATEGY_A.picks(history, frozenset(tp.STOCKS), NIGHT, STRATEGY_A_PARAMS)
    return tuple(p.symbol for p in picks)[: c.STRATEGY_C_PARAMS.max_candidates]


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    """Every test starts with no Finnhub key and no LLM config (the developer's shell may have them)."""
    for name in ("FINNHUB_API_KEY", *LLM_ENV):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", FH_KEY)
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.invalid/api/anthropic")
    monkeypatch.setenv("LLM_API_KEY", LLM_KEY)
    monkeypatch.setenv("LLM_MODEL", c.FROZEN_MODEL)


# ---- fakes -------------------------------------------------------------------------------------


def headline(i: int, published: datetime, text: str) -> c.Headline:
    return c.Headline(id=i, published=published, source="Wire", headline=text, summary=f"Summary of {text}.")


class FakeNews:
    """Finnhub stand-in: per-symbol headlines and earnings dates, per-symbol failures."""

    def __init__(self, *, news=None, earnings=None, fail_news=(), fail_earnings=()):
        self.news = dict(news or {})
        self.earnings_dates = dict(earnings or {})
        self.fail_news = set(fail_news)
        self.fail_earnings = set(fail_earnings)
        self.calls: list[tuple[str, str, date, date]] = []

    def company_news(self, symbol, start, end):
        self.calls.append(("news", symbol, start, end))
        if symbol in self.fail_news:
            raise FinnhubError(f"HTTP 500 from https://finnhub.io/api/v1/company-news?token={FH_KEY} ({FH_KEY})", 500)
        return list(self.news.get(symbol, ()))

    def earnings(self, symbol, start, end):
        self.calls.append(("earnings", symbol, start, end))
        if symbol in self.fail_earnings:
            raise FinnhubError(f"HTTP 429 from Finnhub, key {FH_KEY}", 429)
        return self.earnings_dates.get(symbol)


class FakeLlm:
    """LLM stand-in: a reply per symbol (read from the prompt's first line), per-symbol failures."""

    def __init__(self, *, replies=None, default=ALLOW, fail=(), fail_all=False):
        self.replies = dict(replies or {})
        self.default = default
        self.fail = set(fail)
        self.fail_all = fail_all
        self.calls: list[dict] = []

    def complete(self, system, prompt, *, temperature=None, thinking=None, max_tokens=None):
        symbol = prompt.splitlines()[0].removeprefix("Symbol: ").strip()
        self.calls.append(
            {
                "symbol": symbol,
                "system": system,
                "prompt": prompt,
                "temperature": temperature,
                "thinking": thinking,
                "max_tokens": max_tokens,
            }
        )
        if self.fail_all or symbol in self.fail:
            raise llm.LlmError(f"ReadTimeout: read timed out (x-api-key {LLM_KEY})", None)
        return self.replies.get(symbol, self.default)


class Harness:
    """The factories `veto.execute` takes, recording what they were built with."""

    def __init__(self, news: FakeNews | None = None, ask: FakeLlm | None = None):
        self.news = news if news is not None else FakeNews()
        self.ask = ask if ask is not None else FakeLlm()
        self.keys: list[str] = []
        self.cfgs: list[llm.LlmConfig] = []

    def finnhub(self, key):
        self.keys.append(key)
        return self.news

    def llm(self, cfg):
        self.cfgs.append(cfg)
        return self.ask

    def run(self, conn, *, now: datetime = NOW, dry_run: bool = False) -> int:
        return veto.execute(conn, now=now, dry_run=dry_run, finnhub=self.finnhub, llm=self.llm)

    def network(self) -> int:
        """Client constructions plus calls: zero means nothing reached for the network."""
        return len(self.keys) + len(self.cfgs) + len(self.news.calls) + len(self.ask.calls)


# ---- helpers -----------------------------------------------------------------------------------


def q(conn, sql, params=()):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(sql, params)
        out = cur.fetchall()
    conn.rollback()
    return out


def bars_run(conn, status: str = "success") -> None:
    """The real runs row `nightly` writes for NIGHT (session SESSION)."""
    with db.transaction(conn, False):
        conn.execute(
            """
            INSERT INTO runs (status, data_date, session_date, is_demo, finished_at)
            VALUES (%s, %s, %s, false, now())
            ON CONFLICT (session_date) WHERE NOT is_demo DO NOTHING
            """,
            (status, NIGHT, SESSION),
        )


def rows(conn):
    return q(
        conn,
        "SELECT rank, symbol, verdict, reason, model, prompt_version, headlines, earnings_date, decided_at "
        "FROM news_vetoes WHERE strategy_id = 'C' AND session_date = %s ORDER BY rank",
        (SESSION,),
    )


def verdicts(conn):
    return [(r[1], r[2]) for r in rows(conn)]


def reasons(conn):
    return [r[3] for r in rows(conn)]


EVERYTHING = ("news_vetoes", "runs", "strategies", "paper_state", "orders", "equity_snapshots")


def everything(conn):
    return {t: q(conn, f"SELECT x::text FROM {t} x ORDER BY 1") for t in EVERYTHING}


def lean(h: c.Headline) -> dict:
    return {
        "id": h.id,
        "datetime": h.published.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": h.source,
        "headline": h.headline,
    }


# ---- the command -------------------------------------------------------------------------------


def test_veto_is_a_command():
    assert "veto" in cli.discover()
    args = cli.build_parser().parse_args(["--dry-run", "veto", "--now", "2026-08-06T23:00:00Z"])
    assert args.now == NOW and args.dry_run is True


def test_session_has_five_candidates():
    """The world this file relies on: SESSION has more candidates than the consecutive stop."""
    assert len(expected_symbols()) == 5


def test_checks_every_candidate_in_rank_order(world, configured):
    syms = expected_symbols()
    first = syms[0]
    news = {first: [headline(2, NOW - timedelta(hours=2), "Newer"), headline(1, NOW - timedelta(days=1), "Older")]}
    h = Harness(FakeNews(news=news, earnings={first: date(2026, 8, 11)}), FakeLlm(replies={syms[1]: VETO}))
    bars_run(world)

    assert h.run(world) == 0

    got = rows(world)
    assert [r[0] for r in got] == list(range(1, len(syms) + 1))
    assert [r[1] for r in got] == list(syms)
    assert [r[2] for r in got] == ["allow", "veto", *["allow"] * (len(syms) - 2)]
    assert got[0][3] == "Only routine product news." and got[1][3] == "Earnings are due inside the window."
    assert {(r[4], r[5], r[8]) for r in got} == {(c.FROZEN_MODEL, c.PROMPT_VERSION, NOW)}
    assert got[0][6] == [lean(x) for x in news[first]] and all(r[6] == [] for r in got[1:])
    assert got[0][7] == date(2026, 8, 11) and all(r[7] is None for r in got[1:])

    assert h.keys == [FH_KEY] and [cfg.model for cfg in h.cfgs] == [c.FROZEN_MODEL]
    assert h.news.calls == [
        call
        for s in syms
        for call in (("news", s, NEWS_FROM, NEWS_TO), ("earnings", s, SESSION, WINDOW_END))
    ]
    assert [call["symbol"] for call in h.ask.calls] == list(syms)
    for call in h.ask.calls:
        assert call["system"] == c.SYSTEM_PROMPT
        assert (call["temperature"], call["thinking"], call["max_tokens"]) == (0.0, "disabled", 1024)
    assert h.ask.calls[0]["prompt"] == c.user_prompt(
        first, SESSION, WINDOW_END, date(2026, 8, 11), NOW, tuple(news[first]), c.STRATEGY_C_PARAMS
    )
    assert h.ask.calls[1]["prompt"] == c.user_prompt(syms[1], SESSION, WINDOW_END, None, NOW, (), c.STRATEGY_C_PARAMS)

    stored = store.read_vetoes(world, "C", SESSION)
    world.rollback()
    assert [v.symbol for v in stored] == list(syms)
    assert q(world, "SELECT count(*) FROM orders") == [(0,)]  # veto never trades
    assert q(world, "SELECT count(*) FROM paper_state") == [(0,)]


def test_news_at_or_after_the_start_is_never_sent_nor_stored(world, configured):
    first = expected_symbols()[0]
    before = headline(1, NOW - timedelta(seconds=1), "Published before the start")
    at = headline(2, NOW, "Published at the start")
    after = headline(3, NOW + timedelta(hours=1), "Published after the start")
    h = Harness(FakeNews(news={first: [after, at, before]}))
    bars_run(world)

    assert h.run(world) == 0

    prompt = h.ask.calls[0]["prompt"]
    assert "Published before the start" in prompt
    assert "Published at the start" not in prompt and "Published after the start" not in prompt
    assert rows(world)[0][6] == [lean(before)]


def test_bars_dated_on_or_after_the_session_never_change_candidates(world, configured):
    bars_run(world)
    h = Harness()
    assert h.run(world) == 0
    expected_rows, expected_prompts = rows(world), [call["prompt"] for call in h.ask.calls]

    with db.transaction(world, False):
        world.execute("DELETE FROM news_vetoes")
        world.execute(
            "UPDATE bars SET open = open * 0.5, high = high * 0.5, low = low * 0.5, close = close * 0.5, "
            "volume = volume * 3 WHERE date >= %s",
            (SESSION,),
        )
    again = Harness()
    assert again.run(world) == 0
    assert rows(world) == expected_rows
    assert [call["prompt"] for call in again.ask.calls] == expected_prompts


def test_rerun_makes_no_call_and_writes_nothing(world, configured):
    bars_run(world)
    assert Harness().run(world) == 0
    before = everything(world)

    again = Harness()
    assert again.run(world) == 0
    assert again.network() == 0
    assert everything(world) == before


def test_failed_or_missing_bars_run_exits_1_and_writes_nothing(world, configured):
    h = Harness()
    before = everything(world)
    assert h.run(world) == 1  # no runs row at all
    assert everything(world) == before

    bars_run(world, status="failed")
    before = everything(world)
    assert h.run(world) == 1
    assert everything(world) == before
    assert h.network() == 0


def test_dry_run_writes_nothing(world, configured):
    bars_run(world)
    before = everything(world)
    dry = Harness()
    assert dry.run(world, dry_run=True) == 0
    assert everything(world) == before
    assert len(dry.ask.calls) == len(expected_symbols())  # every check ran, then rolled back

    assert Harness().run(world) == 0
    assert len(rows(world)) == len(expected_symbols())


def test_no_candidates_writes_nothing_and_calls_nothing(world, configured):
    with db.transaction(world, False):
        world.execute("DELETE FROM universe")
    bars_run(world)
    before = everything(world)
    h = Harness()
    assert h.run(world) == 0
    assert everything(world) == before
    assert h.network() == 0


# ---- failure = no trade (acceptance 3) ----------------------------------------------------------


def test_no_llm_config_fails_every_candidate_without_a_call(world, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", FH_KEY)
    bars_run(world)
    h = Harness()
    assert h.run(world) == 0
    assert verdicts(world) == [(s, "failed") for s in expected_symbols()]
    assert set(reasons(world)) == {"LLM_BASE_URL, LLM_API_KEY and LLM_MODEL are not all set"}
    assert {r[4] for r in rows(world)} == {None}
    assert h.network() == 0


def test_no_finnhub_key_fails_every_candidate_without_a_call(world, configured, monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY")
    bars_run(world)
    h = Harness()
    assert h.run(world) == 0
    assert verdicts(world) == [(s, "failed") for s in expected_symbols()]
    assert set(reasons(world)) == {"FINNHUB_API_KEY is not set"}
    assert {r[4] for r in rows(world)} == {c.FROZEN_MODEL}
    assert h.network() == 0


def test_nothing_configured_names_both_reasons(world):
    bars_run(world)
    h = Harness()
    assert h.run(world) == 0
    assert set(reasons(world)) == {
        "FINNHUB_API_KEY is not set; LLM_BASE_URL, LLM_API_KEY and LLM_MODEL are not all set"
    }
    assert h.network() == 0


def test_frozen_model_mismatch_fails_every_candidate_without_a_call(world, configured, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "glm-4.6")
    bars_run(world)
    h = Harness()
    assert h.run(world) == 0
    assert verdicts(world) == [(s, "failed") for s in expected_symbols()]
    assert set(reasons(world)) == {f"LLM_MODEL glm-4.6 is not C's frozen model {c.FROZEN_MODEL}"}
    assert {r[4] for r in rows(world)} == {"glm-4.6"}
    assert h.network() == 0


def test_llm_error_fails_only_that_candidate(world, configured):
    syms = expected_symbols()
    news = {syms[1]: [headline(7, NOW - timedelta(hours=3), "Seen before the LLM failed")]}
    h = Harness(FakeNews(news=news), FakeLlm(fail={syms[1]}))
    bars_run(world)
    assert h.run(world) == 0
    got = rows(world)
    assert [(r[1], r[2]) for r in got] == [(s, "failed" if s == syms[1] else "allow") for s in syms]
    assert got[1][3].startswith("LLM failed: LlmError: ReadTimeout")
    assert LLM_KEY not in got[1][3] and "REDACTED" in got[1][3]
    assert got[1][6] == [lean(x) for x in news[syms[1]]]  # the headlines it would have judged


def test_finnhub_errors_fail_only_that_candidate_without_an_llm_call(world, configured):
    syms = expected_symbols()
    h = Harness(FakeNews(fail_news={syms[0]}, fail_earnings={syms[1]}))
    bars_run(world)
    assert h.run(world) == 0
    got = rows(world)
    assert [(r[1], r[2]) for r in got] == [(s, "failed" if s in syms[:2] else "allow") for s in syms]
    assert got[0][3].startswith("Finnhub company-news failed: FinnhubError: HTTP 500")
    assert got[1][3].startswith("Finnhub earnings calendar failed: FinnhubError: HTTP 429")
    assert all(FH_KEY not in r[3] for r in got)
    assert [call["symbol"] for call in h.ask.calls] == list(syms[2:])


def test_unparsable_replies_fail_but_never_stop_the_night(world, configured):
    syms = expected_symbols()
    h = Harness(ask=FakeLlm(default="Looks fine to me."))
    bars_run(world)
    assert h.run(world) == 0
    assert verdicts(world) == [(s, "failed") for s in syms]
    assert all(r.startswith("unparsable reply") for r in reasons(world))
    assert len(h.ask.calls) == len(syms)  # a reply is not a network failure


def test_three_network_failures_in_a_row_stop_the_night(world, configured):
    syms = expected_symbols()
    h = Harness(ask=FakeLlm(fail_all=True))
    bars_run(world)
    assert h.run(world) == 0
    got = reasons(world)
    assert verdicts(world) == [(s, "failed") for s in syms]
    assert all(r.startswith("LLM failed: LlmError") for r in got[:3])
    assert got[3:] == ["skipped after 3 consecutive failures"] * (len(syms) - 3)
    assert len(h.ask.calls) == 3
    assert [call[1] for call in h.news.calls] == [s for s in syms[:3] for _ in range(2)]


def test_a_success_resets_the_failure_count(world, configured):
    syms = expected_symbols()
    h = Harness(ask=FakeLlm(fail={syms[0], syms[1], syms[3], syms[4]}))
    bars_run(world)
    assert h.run(world) == 0
    assert verdicts(world) == [(s, "allow" if s == syms[2] else "failed") for s in syms]
    assert len(h.ask.calls) == len(syms)


def test_a_client_that_cannot_be_built_fails_every_candidate(world, configured):
    def broken(key):
        raise RuntimeError(f"bad key {key}")

    bars_run(world)
    assert veto.execute(world, now=NOW, finnhub=broken, llm=Harness().llm) == 0
    got = reasons(world)
    assert len(got) == len(expected_symbols())
    assert set(got) == {"client setup failed: RuntimeError: bad key REDACTED"}


def test_no_secret_in_rows_or_logs(world, configured, caplog):
    caplog.set_level(logging.DEBUG)
    syms = expected_symbols()
    leaky = f'{{"verdict": "maybe", "reason": "{LLM_KEY}"}} token={FH_KEY}'
    h = Harness(
        FakeNews(fail_news={syms[0]}),
        FakeLlm(fail={syms[1]}, replies={syms[2]: leaky}),
    )
    bars_run(world)
    assert h.run(world) == 0
    stored = q(world, "SELECT x::text FROM news_vetoes x")
    assert len(stored) == len(syms)
    for secret in (FH_KEY, LLM_KEY):
        assert all(secret not in text for (text,) in stored)
        assert secret not in caplog.text


# ---- races and database errors ------------------------------------------------------------------


def test_another_run_winning_the_race_writes_nothing(world, configured, monkeypatch):
    bars_run(world)
    assert Harness(ask=FakeLlm(default=VETO)).run(world) == 0
    before = everything(world)

    real = store.has_vetoes
    seen = []

    def stale_first(conn, strategy_id, session):
        seen.append(session)
        return False if len(seen) == 1 else real(conn, strategy_id, session)

    monkeypatch.setattr(veto.store, "has_vetoes", stale_first)
    late = Harness()
    assert late.run(world) == 0
    assert len(late.ask.calls) == len(expected_symbols())  # it checked, then lost the race
    assert everything(world) == before
    assert {v for _, v in verdicts(world)} == {"veto"}


def test_paper_already_decided_the_session_writes_nothing(world, configured):
    """H1, the late-verdict retry: the 23:00 Veto wrote nothing, the 23:00 Paper decided SESSION for C
    with no verdicts. The 01:00 retry's Veto must not write verdicts now: C's replay would buy what
    Paper never did and paper_check would stay red."""
    bars_run(world)
    assert paper.execute(world, now=NOW) == 0
    assert q(world, "SELECT paper_status FROM runs WHERE session_date = %s AND NOT is_demo", (SESSION,)) == [
        ("success",)
    ]
    before = everything(world)

    retry = Harness()
    assert retry.run(world, now=NOW + timedelta(hours=2)) == 0  # 01:00 UTC: still SESSION
    assert retry.network() == 0
    assert everything(world) == before
    assert rows(world) == []
    found = {r.strategy_id: r for r in paper_check.check(world)}
    assert found["C"].status == "ok"


def test_paper_deciding_during_the_checks_writes_nothing(world, configured, monkeypatch):
    """H1, re-checked inside the write transaction: Paper finished between the first read and the write."""
    bars_run(world)
    assert paper.execute(world, now=NOW) == 0
    before = everything(world)
    real = runs.real_run
    seen = []

    def stale_first(conn, session):
        seen.append(session)
        found = real(conn, session)
        return replace(found, paper_status=None) if len(seen) == 1 else found

    monkeypatch.setattr(veto.runs, "real_run", stale_first)
    late = Harness()
    assert late.run(world) == 0
    assert len(late.ask.calls) == len(expected_symbols())  # it checked, then saw Paper had decided
    assert everything(world) == before


def test_database_error_on_write_exits_1(world, configured, monkeypatch, caplog):
    def boom(conn, strategy_id, session, verdicts):
        raise psycopg.OperationalError(f"server closed the connection (password={LLM_KEY})")

    monkeypatch.setattr(veto.store, "write_vetoes", boom)
    bars_run(world)
    assert Harness().run(world) == 1
    assert rows(world) == []
    assert LLM_KEY not in caplog.text


# ---- pure helpers ------------------------------------------------------------------------------


def test_config_failure_reasons():
    cfg = llm.LlmConfig(base_url="https://x.invalid", api_key=LLM_KEY, model=c.FROZEN_MODEL)
    p = c.STRATEGY_C_PARAMS
    assert veto.config_failure(FH_KEY, cfg, p) is None
    assert veto.config_failure(None, cfg, p) == "FINNHUB_API_KEY is not set"
    other = llm.LlmConfig(base_url="https://x.invalid", api_key=LLM_KEY, model="glm-4.6")
    assert veto.config_failure(FH_KEY, other, p) == f"LLM_MODEL glm-4.6 is not C's frozen model {c.FROZEN_MODEL}"


def test_scrub_redacts_both_keys_and_caps_length():
    text = f"token={FH_KEY} and {LLM_KEY}\n" + "x" * 400
    out = veto.scrub(text, (FH_KEY, LLM_KEY))
    assert FH_KEY not in out and LLM_KEY not in out and "\n" not in out
    assert len(out) == veto.MAX_REASON_LEN
    assert veto.scrub("plain", (None, None)) == "plain"


def test_session_dates_used_by_this_file():
    assert dates.run_dates(NOW) == dates.RunDates(data_date=NIGHT, session_date=SESSION)
    assert c.news_dates(NOW, 3) == (NEWS_FROM, NEWS_TO)
    assert c.earnings_window(SESSION, 5) == (SESSION, WINDOW_END)
