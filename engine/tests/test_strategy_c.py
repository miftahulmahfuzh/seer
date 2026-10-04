"""Strategy C, pure part (strategy-c-news-veto phase 1, contract K1): the NewsVeto strategy object,
its frozen params, the c-veto-v1 prompt and the verdict parser."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from simkit import D, bar

from seer_engine import dates
from seer_engine.backtest.book_runner import run_rules
from seer_engine.backtest.market import Market, Membership
from seer_engine.sim.rules import DESIGN_V0
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS, AParams
from seer_engine.strategies.base import Strategy, history_from_bars
from seer_engine.strategies.c import (
    FROZEN_MODEL,
    PROMPT_VERSION,
    STRATEGY_C,
    STRATEGY_C_ID,
    STRATEGY_C_PARAMS,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
    VERDICTS,
    CParams,
    Headline,
    NewsVeto,
    allowed_map,
    candidates,
    candidates_prepared,
    earnings_window,
    news_dates,
    parse_verdict,
    select_headlines,
    user_prompt,
)

UTC = timezone.utc

# --------------------------------------------------------------------------- synthetic markets


def _smoke_bars(symbol: str, sessions: list[date], phase: int, base: float = 100.0):
    """An uptrend (+0.4 % a session) with two -3 % sessions every 20 (shifted by ``phase``) and a
    deep intraday low the session after, so A's setup fires and its limit fills (the market of
    tests/test_backtest_runner.py::test_strategy_a_smoke_prepared_equals_plain)."""
    out = []
    prev = base + phase
    for t, d in enumerate(sessions):
        k = (t + phase) % 20
        c = prev * 0.97 if k in (17, 18) else prev * 1.004
        o = prev
        lo = min(o, c) * (0.97 if k == 19 else 0.995)
        hi = max(o, c) * 1.005
        out.append(bar(symbol, d, f"{o:.4f}", f"{hi:.4f}", f"{lo:.4f}", f"{c:.4f}", 1_000_000))
        prev = float(f"{c:.4f}")
    return out


SESSIONS = dates.sessions(D("2024-01-02"), D("2025-03-31"))


def _market(spec: tuple[tuple[str, int, float], ...]) -> Market:
    history = {s: history_from_bars(s, _smoke_bars(s, SESSIONS, phase, base)) for s, phase, base in spec}
    return Market(
        history=history,
        membership=Membership(tuple((s, D("2020-01-02"), None) for s in sorted(history))),
        fx=((D("2023-12-29"), Decimal("16000")),),
    )


# A never ranks more than three symbols here, so C with every candidate allowed is A.
SMALL = _market((("UPA", 0, 100.0), ("UPB", 7, 100.0), ("UPC", 13, 100.0)))
# Twelve symbols that dip on the same sessions: A ranks all twelve, C checks only the first ten.
WIDE = _market(tuple((f"W{k:02d}", 0, 100.0 + 3.0 * k) for k in range(12)))
START, END = SESSIONS[200], SESSIONS[-1]  # data_date SESSIONS[199] has exactly 200 bars


def _members(market: Market, d: date) -> frozenset[str]:
    return market.membership.members_on(d)


def _cut(market: Market, d: date):
    return {s: h.upto(d) for s, h in market.history.items()}


def _a_picks(market: Market, d: date):
    return STRATEGY_A.picks(_cut(market, d), _members(market, d), d, STRATEGY_A_PARAMS)


def _wide_day() -> date:
    """A data_date on which A ranks more than ten WIDE symbols."""
    for d in SESSIONS[199:]:
        if len(_a_picks(WIDE, d)) > 10:
            return d
    raise AssertionError("WIDE never ranks more than ten symbols")


def _all_allowed(market: Market, start: date, end: date) -> dict[date, frozenset[str]]:
    everyone = frozenset(market.history)
    return {s: everyone for s in dates.sessions(start, dates.next_session(end))}


# --------------------------------------------------------------------------- params and constants


def test_constants():
    assert PROMPT_VERSION == "c-veto-v1"
    assert FROZEN_MODEL == "glm-5.3"
    assert STRATEGY_C_ID == "C-news-veto"
    assert VERDICTS == ("allow", "veto", "failed")


def test_params_defaults_and_as_dict():
    p = STRATEGY_C_PARAMS
    assert p == CParams()
    assert p.a is STRATEGY_A_PARAMS
    assert (p.max_candidates, p.news_days, p.max_headlines, p.max_summary_chars, p.earnings_sessions) == (
        10, 3, 20, 280, 5
    )
    assert p.earnings_sessions == DESIGN_V0.time_stop
    d = p.as_dict()
    assert list(d) == [
        "a.rsi_max",
        "a.limit_atr",
        "a.tp_atr",
        "a.sl_atr",
        "a.min_dollar_volume",
        "a_object",
        "a_object_id",
        "max_candidates",
        "news_days",
        "max_headlines",
        "max_summary_chars",
        "earnings_sessions",
        "model",
        "prompt_version",
        "temperature",
        "thinking",
        "max_tokens",
        "system_prompt",
        "user_template",
    ]
    assert all(isinstance(v, str) for v in d.values())
    assert {k[2:]: v for k, v in d.items() if k.startswith("a.")} == STRATEGY_A_PARAMS.as_dict()
    assert d["a_object"] == "STRATEGY_A"
    assert d["a_object_id"] == "A"
    assert d["max_candidates"] == "10"
    assert d["news_days"] == "3"
    assert d["max_headlines"] == "20"
    assert d["max_summary_chars"] == "280"
    assert d["earnings_sessions"] == "5"
    assert d["model"] == "glm-5.3"
    assert d["prompt_version"] == "c-veto-v1"
    assert d["temperature"] == "0"
    assert d["thinking"] == "disabled"
    assert d["max_tokens"] == "1024"
    assert d["system_prompt"] == SYSTEM_PROMPT
    assert d["user_template"] == USER_TEMPLATE
    json.dumps(d, sort_keys=True)  # canonical-JSON-able, as the roster's spec_text needs


def test_as_dict_moves_with_every_frozen_input():
    base = STRATEGY_C_PARAMS.as_dict()
    for changed in (
        CParams(a=AParams(rsi_max=5.0)),
        CParams(max_candidates=9),
        CParams(news_days=2),
        CParams(max_headlines=10),
        CParams(max_summary_chars=200),
        CParams(earnings_sessions=4),
        CParams(model="glm-9"),
        CParams(prompt_version="c-veto-v2"),
        CParams(temperature="0.2"),
        CParams(thinking="enabled"),
        CParams(max_tokens=512),
    ):
        assert changed.as_dict() != base


@pytest.mark.parametrize(
    "kwargs, exc",
    [
        ({"a": "A"}, TypeError),
        ({"max_candidates": 0}, ValueError),
        ({"max_candidates": True}, TypeError),
        ({"news_days": 1.5}, TypeError),
        ({"max_headlines": -1}, ValueError),
        ({"earnings_sessions": 0}, ValueError),
        ({"model": ""}, ValueError),
        ({"temperature": 0}, TypeError),
    ],
)
def test_params_validate(kwargs, exc):
    with pytest.raises(exc):
        CParams(**kwargs)


def test_frozen_prompt_texts_verbatim():
    assert SYSTEM_PROMPT.startswith("You are the news check of a paper-trading research app. ")
    assert SYSTEM_PROMPT.endswith('{"verdict": "allow" or "veto", "reason": "<one sentence, at most 25 words>"}')
    assert SYSTEM_PROMPT.count("\n- ") == 8
    assert "- the departure of the CEO or CFO.\n\nAnswer \"allow\" otherwise:" in SYSTEM_PROMPT
    assert USER_TEMPLATE == (
        "Symbol: {symbol}\n"
        "Entry: the open of {session}\n"
        "Holding window: {session} to {window_end} ({sessions} sessions)\n"
        "Scheduled earnings inside the window: {earnings}\n"
        "Headlines published before {cutoff} UTC, newest first ({count} shown, at most {cap}):\n"
        "{headline_lines}"
    )


# --------------------------------------------------------------------------- candidates and NewsVeto


def test_news_veto_is_a_strategy_and_the_roster_object_never_buys():
    assert isinstance(STRATEGY_C, Strategy)
    assert STRATEGY_C.id == STRATEGY_C_ID
    assert STRATEGY_C.lookback == STRATEGY_A.lookback
    assert dict(STRATEGY_C.allowed) == {}
    d = _wide_day()
    assert STRATEGY_C.picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS) == []
    with pytest.raises(FrozenInstanceError):
        STRATEGY_C.id = "X"  # type: ignore[misc]


def test_candidates_are_a_first_ten_and_all_allowed_c_equals_them():
    d = _wide_day()
    a = _a_picks(WIDE, d)
    assert len(a) > 10
    cands = candidates(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS)
    assert cands == a[:10]
    c = STRATEGY_C.with_allowed({dates.next_session(d): frozenset(WIDE.history)})
    assert c.picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS) == cands
    # ranks 11 and 12 are never returned, even when allowed
    assert {p.symbol for p in a[10:]}.isdisjoint(
        p.symbol for p in c.picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS)
    )


def test_vetoed_failed_and_missing_symbols_are_dropped_in_rank_order():
    d = _wide_day()
    cands = candidates(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS)
    rows = []
    for rank, p in enumerate(cands, start=1):
        if rank in (2, 5):
            rows.append((dates.next_session(d), p.symbol, "veto"))
        elif rank == 7:
            rows.append((dates.next_session(d), p.symbol, "failed"))
        elif rank == 9:
            continue  # no stored verdict = failed
        else:
            rows.append((dates.next_session(d), p.symbol, "allow"))
    c = STRATEGY_C.with_allowed(allowed_map(rows))
    got = c.picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS)
    assert got == [p for k, p in enumerate(cands, start=1) if k not in (2, 5, 7, 9)]


def test_verdicts_are_keyed_by_the_session_bought_for():
    d = _wide_day()
    everyone = frozenset(WIDE.history)
    # a map keyed by data_date (the wrong key) buys nothing
    assert STRATEGY_C.with_allowed({d: everyone}).picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS) == []
    # another session's verdicts do not leak
    other = dates.next_session(dates.next_session(d))
    assert STRATEGY_C.with_allowed({other: everyone}).picks(
        _cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS
    ) == []


def test_with_allowed_keeps_id_and_lookback_and_freezes_the_map():
    src = {D("2025-01-02"): {"AAA", "BBB"}}
    c = STRATEGY_C.with_allowed(src)
    assert isinstance(c, NewsVeto)
    assert (c.id, c.lookback) == (STRATEGY_C.id, STRATEGY_C.lookback)
    assert c.allowed[D("2025-01-02")] == frozenset({"AAA", "BBB"})
    src[D("2025-01-02")].add("CCC")
    src[D("2025-01-03")] = {"DDD"}
    assert c.allowed == {D("2025-01-02"): frozenset({"AAA", "BBB"})}
    with pytest.raises(TypeError):
        c.allowed[D("2025-01-06")] = frozenset()  # type: ignore[index]
    assert dict(STRATEGY_C.allowed) == {}


@pytest.mark.parametrize(
    "allowed, exc",
    [
        ([("2025-01-02", "AAA")], TypeError),
        ({datetime(2025, 1, 2): {"AAA"}}, TypeError),
        ({D("2025-01-02"): "AAA"}, TypeError),
        ({D("2025-01-02"): {1}}, TypeError),
    ],
)
def test_allowed_map_shape_is_validated(allowed, exc):
    with pytest.raises(exc):
        NewsVeto(allowed=allowed)


def test_params_must_be_c_params():
    d = _wide_day()
    with pytest.raises(TypeError):
        STRATEGY_C.picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_A_PARAMS)
    with pytest.raises(TypeError):
        candidates(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_A_PARAMS)
    with pytest.raises(TypeError):
        candidates_prepared(STRATEGY_A.prepare(WIDE.history), _members(WIDE, d), d, STRATEGY_A_PARAMS)


def test_picks_prepared_equals_picks_on_the_cut_history():
    c = STRATEGY_C.with_allowed(_all_allowed(WIDE, START, END))
    partial = STRATEGY_C.with_allowed(
        {s: frozenset({"W00", "W03", "W07", "W11"}) for s in dates.sessions(START, dates.next_session(END))}
    )
    prepared = c.prepare(WIDE.history)
    for d in SESSIONS[199:]:
        members = _members(WIDE, d)
        assert candidates_prepared(prepared, members, d, STRATEGY_C_PARAMS) == candidates(
            _cut(WIDE, d), members, d, STRATEGY_C_PARAMS
        )
        for strat in (c, partial, STRATEGY_C):
            assert strat.picks_prepared(prepared, members, d, STRATEGY_C_PARAMS) == strat.picks(
                _cut(WIDE, d), members, d, STRATEGY_C_PARAMS
            )


def test_bars_after_data_date_never_change_candidates():
    d = _wide_day()
    full = candidates(WIDE.history, _members(WIDE, d), d, STRATEGY_C_PARAMS)
    assert full == candidates(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS)


def test_run_rules_all_allowed_c_equals_a_when_a_never_needs_rank_eleven():
    for d in SESSIONS[199:]:
        assert len(_a_picks(SMALL, d)) <= 10
    c = STRATEGY_C.with_allowed(_all_allowed(SMALL, START, END))
    a_run = run_rules(SMALL, STRATEGY_A, STRATEGY_A_PARAMS, DESIGN_V0, START, END)
    c_run = run_rules(SMALL, c, STRATEGY_C_PARAMS, DESIGN_V0, START, END)
    assert c_run.strategy_id == STRATEGY_C_ID
    assert any(e.kind == "fill" for e in a_run.events)
    assert replace(c_run, strategy_id="A", params=STRATEGY_A_PARAMS) == a_run
    prepped = run_rules(SMALL, c, STRATEGY_C_PARAMS, DESIGN_V0, START, END, prepared=c.prepare(SMALL.history))
    assert prepped == c_run


def test_run_rules_with_no_verdicts_never_trades_and_a_veto_changes_the_run():
    none = run_rules(SMALL, STRATEGY_C, STRATEGY_C_PARAMS, DESIGN_V0, START, END)
    assert none.events == ()
    assert {s.equity_usd for s in none.snapshots} == {none.initial_cash}
    allowed = _all_allowed(SMALL, START, END)
    no_upa = STRATEGY_C.with_allowed({s: v - {"UPA"} for s, v in allowed.items()})
    run = run_rules(SMALL, no_upa, STRATEGY_C_PARAMS, DESIGN_V0, START, END)
    assert all(e.order.symbol != "UPA" for e in run.events)
    assert any(e.kind == "fill" for e in run.events)


# --------------------------------------------------------------------------- news window, earnings window


def test_news_dates_are_et_calendar_dates():
    # 2026-10-05 23:00 UTC is 19:00 ET the same day
    assert news_dates(datetime(2026, 10, 5, 23, 0, tzinfo=UTC), 3) == (D("2026-10-02"), D("2026-10-05"))
    # 2026-10-06 01:00 UTC (the retry cron) is still 2026-10-05 in New York
    assert news_dates(datetime(2026, 10, 6, 1, 0, tzinfo=UTC), 3) == (D("2026-10-02"), D("2026-10-05"))
    # winter: UTC-5
    assert news_dates(datetime(2026, 1, 6, 4, 59, tzinfo=UTC), 3) == (D("2026-01-02"), D("2026-01-05"))
    assert news_dates(datetime(2026, 1, 6, 5, 0, tzinfo=UTC), 3) == (D("2026-01-03"), D("2026-01-06"))
    with pytest.raises(ValueError):
        news_dates(datetime(2026, 10, 5, 23, 0), 3)
    with pytest.raises(ValueError):
        news_dates(datetime(2026, 10, 5, 23, 0, tzinfo=UTC), 0)


def test_earnings_window_counts_sessions_from_the_entry_session():
    assert earnings_window(D("2026-10-06"), 5) == (D("2026-10-06"), D("2026-10-12"))
    assert earnings_window(D("2026-10-06"), 1) == (D("2026-10-06"), D("2026-10-06"))
    # Thanksgiving 2026-11-26 is skipped
    assert earnings_window(D("2026-11-23"), 5) == (D("2026-11-23"), D("2026-11-30"))
    with pytest.raises(ValueError):
        earnings_window(D("2026-10-10"), 5)  # a Saturday
    with pytest.raises(ValueError):
        earnings_window(D("2026-10-06"), 0)
    with pytest.raises(TypeError):
        earnings_window(datetime(2026, 10, 6), 5)


# --------------------------------------------------------------------------- headlines


def _h(i: int, when: datetime, headline: str = "", summary: str = "", source: str = "Reuters") -> Headline:
    return Headline(i, when, source, headline or f"Headline {i}", summary)


CUTOFF = datetime(2026, 10, 5, 23, 0, 7, tzinfo=UTC)


def test_headline_validates_and_normalizes_to_utc():
    est = timezone(timedelta(hours=-4))
    h = Headline(1, datetime(2026, 10, 5, 9, 30, tzinfo=est), "CNBC", "x", "")
    assert h.published == datetime(2026, 10, 5, 13, 30, tzinfo=UTC)
    assert h.published.tzinfo is UTC
    with pytest.raises(ValueError):
        Headline(1, datetime(2026, 10, 5, 9, 30), "CNBC", "x", "")
    with pytest.raises(TypeError):
        Headline(True, CUTOFF, "CNBC", "x", "")
    with pytest.raises(TypeError):
        Headline(1, CUTOFF, None, "x", "")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Headline(1, CUTOFF, "CNBC", "   ", "")


def test_select_headlines_drops_items_at_or_after_the_cutoff_newest_first():
    items = [
        _h(1, CUTOFF - timedelta(hours=30)),
        _h(2, CUTOFF),  # at the cutoff: dropped
        _h(3, CUTOFF + timedelta(seconds=1)),  # after: dropped
        _h(4, CUTOFF - timedelta(seconds=1)),
        _h(5, CUTOFF - timedelta(hours=2)),
        _h(6, CUTOFF - timedelta(hours=2)),  # tie with 5: higher id first
    ]
    got = select_headlines(items, CUTOFF, 20)
    assert [h.id for h in got] == [4, 6, 5, 1]
    assert [h.id for h in select_headlines(items, CUTOFF, 2)] == [4, 6]
    assert select_headlines(items, CUTOFF, 0) == ()
    assert select_headlines([], CUTOFF, 20) == ()
    assert select_headlines(iter(items), CUTOFF, 20) == got
    with pytest.raises(ValueError):
        select_headlines(items, CUTOFF.replace(tzinfo=None), 20)
    with pytest.raises(ValueError):
        select_headlines(items, CUTOFF, -1)
    with pytest.raises(TypeError):
        select_headlines([{"id": 1}], CUTOFF, 20)  # type: ignore[list-item]


# --------------------------------------------------------------------------- the user prompt (golden)


def test_user_prompt_golden():
    heads = (
        _h(
            7,
            datetime(2026, 10, 5, 20, 15, 59, tzinfo=UTC),
            "Acme  beats\nestimates",
            "Acme Corp reported third-quarter revenue above expectations.",
            "Reuters",
        ),
        _h(3, datetime(2026, 10, 3, 9, 1, tzinfo=UTC), "Acme names new CFO", "", "MarketWatch"),
    )
    got = user_prompt(
        "ACME", D("2026-10-06"), D("2026-10-12"), D("2026-10-08"), CUTOFF, heads, STRATEGY_C_PARAMS
    )
    assert got == (
        "Symbol: ACME\n"
        "Entry: the open of 2026-10-06\n"
        "Holding window: 2026-10-06 to 2026-10-12 (5 sessions)\n"
        "Scheduled earnings inside the window: 2026-10-08\n"
        "Headlines published before 2026-10-05 23:00 UTC, newest first (2 shown, at most 20):\n"
        "1. 2026-10-05 20:15Z | Reuters | Acme beats estimates | "
        "Acme Corp reported third-quarter revenue above expectations.\n"
        "2. 2026-10-03 09:01Z | MarketWatch | Acme names new CFO |"
    )


def test_user_prompt_with_no_headlines_and_no_earnings():
    got = user_prompt("BRK.B", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (), STRATEGY_C_PARAMS)
    assert got == (
        "Symbol: BRK.B\n"
        "Entry: the open of 2026-10-06\n"
        "Holding window: 2026-10-06 to 2026-10-12 (5 sessions)\n"
        "Scheduled earnings inside the window: none found\n"
        "Headlines published before 2026-10-05 23:00 UTC, newest first (0 shown, at most 20):\n"
        "No headlines."
    )


def test_user_prompt_cuts_summaries_at_a_word_boundary():
    words = " ".join(["alpha"] * 100)  # 599 chars
    p = CParams(max_summary_chars=20)
    got = user_prompt("X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (_h(1, CUTOFF - timedelta(1), "H", words),), p)
    assert got.splitlines()[-1] == "1. 2026-10-04 23:00Z | Reuters | H | alpha alpha alpha"
    exact = "abcde fghij"
    got = user_prompt(
        "X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (_h(1, CUTOFF - timedelta(1), "H", exact),), CParams(max_summary_chars=11)
    )
    assert got.splitlines()[-1].endswith("| H | abcde fghij")
    one_word = "x" * 40
    got = user_prompt(
        "X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (_h(1, CUTOFF - timedelta(1), "H", one_word),), p
    )
    assert got.splitlines()[-1].endswith("| H | " + "x" * 20)
    long = STRATEGY_C_PARAMS.max_summary_chars
    got = user_prompt(
        "X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (_h(1, CUTOFF - timedelta(1), "H", words),), STRATEGY_C_PARAMS
    )
    assert len(got.splitlines()[-1].split(" | ")[-1]) <= long


def test_user_prompt_validates():
    args = ("X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (), STRATEGY_C_PARAMS)
    user_prompt(*args)
    with pytest.raises(ValueError):
        user_prompt("", *args[1:])
    with pytest.raises(ValueError):
        user_prompt("X", D("2026-10-12"), D("2026-10-06"), None, CUTOFF, (), STRATEGY_C_PARAMS)
    with pytest.raises(ValueError):
        user_prompt("X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF.replace(tzinfo=None), (), STRATEGY_C_PARAMS)
    too_many = tuple(_h(i, CUTOFF - timedelta(minutes=i)) for i in range(1, 22))
    with pytest.raises(ValueError):
        user_prompt("X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, too_many, STRATEGY_C_PARAMS)
    with pytest.raises(TypeError):
        user_prompt("X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (), STRATEGY_A_PARAMS)


# --------------------------------------------------------------------------- the verdict parser


@pytest.mark.parametrize(
    "text, expected",
    [
        ('{"verdict": "allow", "reason": "Only routine product news."}', ("allow", "Only routine product news.")),
        ('{"verdict": "veto", "reason": "Earnings on 2026-10-08."}', ("veto", "Earnings on 2026-10-08.")),
        ('  \n{"verdict": " VETO ", "reason": "  Lawsuit\n filed   today. "}\n ', ("veto", "Lawsuit filed today.")),
        ('```json\n{"verdict": "Allow", "reason": "No news."}\n```', ("allow", "No news.")),
        ('Here you go: {"verdict": "allow", "reason": "No news."} Thanks!', ("allow", "No news.")),
        ('{"reason": "Has {braces} inside.", "verdict": "allow"}', ("allow", "Has {braces} inside.")),
        ('{"verdict": "allow", "reason": "a"} {"verdict": "veto", "reason": "b"}', ("allow", "a")),
        ('{"verdict": "allow", "reason": "ok", "extra": 1}', ("allow", "ok")),
    ],
)
def test_parse_verdict_accepts(text, expected):
    assert parse_verdict(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "allow",
        "I think you should veto this one.",
        '{"verdict": "allow"}',
        '{"verdict": "allow", "reason": ""}',
        '{"verdict": "allow", "reason": "   "}',
        '{"verdict": "maybe", "reason": "Unsure."}',
        '{"verdict": "failed", "reason": "x"}',
        '{"verdict": true, "reason": "x"}',
        '{"verdict": "allow", "reason": 5}',
        '{"verdict": "allow", "reason": "x"',
        "[1, 2]",
        "{not json}",
    ],
)
def test_parse_verdict_rejects(text):
    verdict, reason = parse_verdict(text)
    assert verdict == "failed"
    assert reason.startswith("unparsable reply: ")
    assert len(reason) <= len("unparsable reply: ") + 120


def test_parse_verdict_failure_reason_quotes_the_first_120_chars_on_one_line():
    text = "nope\n" + "z" * 300
    assert parse_verdict(text) == ("failed", "unparsable reply: " + ("nope " + "z" * 300)[:120])
    assert parse_verdict("") == ("failed", "unparsable reply: empty")
    assert parse_verdict(None) == ("failed", "unparsable reply: empty")  # type: ignore[arg-type]


def test_parse_verdict_caps_the_reason_at_300_chars():
    reason = "word " * 100
    verdict, got = parse_verdict(json.dumps({"verdict": "veto", "reason": reason}))
    assert verdict == "veto"
    assert len(got) <= 300
    assert got == reason.strip()[:300].rstrip()


# --------------------------------------------------------------------------- allowed_map


def test_allowed_map():
    s1, s2, s3 = D("2026-10-06"), D("2026-10-07"), D("2026-10-08")
    rows = [
        (s2, "BBB", "allow"),
        (s1, "AAA", "allow"),
        (s1, "CCC", "veto"),
        (s1, "DDD", "failed"),
        (s1, "EEE", "allow"),
        (s3, "AAA", "veto"),
    ]
    assert allowed_map(rows) == {s1: frozenset({"AAA", "EEE"}), s2: frozenset({"BBB"}), s3: frozenset()}
    assert allowed_map([]) == {}
    with pytest.raises(ValueError):
        allowed_map([(s1, "AAA", "maybe")])
    with pytest.raises(ValueError):
        allowed_map([(s1, "AAA", "allow"), (s1, "AAA", "veto")])
    with pytest.raises(TypeError):
        allowed_map([(datetime(2026, 10, 6), "AAA", "allow")])
