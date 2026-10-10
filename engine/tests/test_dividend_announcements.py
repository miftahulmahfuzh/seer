"""Dividend declaration dates: the EODHD client, the matcher, the calendar's point-in-time read,
the store's optional ``dividend_announcements.csv`` and the command. No network: the transport
is a fake, and the store is the tiny fixture ``test_research_store`` builds."""

from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal

import pytest
import requests

from seer_engine import dividend_announcements as da
from seer_engine import eodhd, research
from seer_engine.backtest.market import DividendCalendar
from seer_engine.commands import dividend_announcements as cmd
import test_research_store as rs
from test_research_store import D2, FACTS_A, build


@pytest.fixture
def members(tmp_path):
    """``test_research_store``'s membership fixture, under a name that does not shadow it."""
    return rs.members_dir.__wrapped__(tmp_path)

# ---- client --------------------------------------------------------------------------------


class Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeTransport:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, dict(params)))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def client(transport):
    return eodhd.Client("secret-token", transport=transport, clock=lambda: 0.0, sleep=lambda s: None)


def test_ticker_maps_class_shares_to_eodhd_form():
    assert eodhd.ticker("BRK.B") == "BRK-B.US"
    assert eodhd.ticker("aapl") == "AAPL.US"
    with pytest.raises(ValueError):
        eodhd.ticker(" ")


def test_parse_keeps_a_missing_declaration_as_none_and_skips_rows_without_an_ex_date():
    rows = [
        {"date": "2013-08-13", "declarationDate": "2013-06-12", "value": 0.23},
        {"date": "1990-02-16", "declarationDate": None, "value": 0.1},
        {"date": "2001-05-01", "declarationDate": "", "value": "x"},
        {"declarationDate": "2001-01-01"},
        "junk",
    ]
    out = eodhd.parse_dividends(rows)
    assert [d.ex_date for d in out] == [date(1990, 2, 16), date(2001, 5, 1), date(2013, 8, 13)]
    assert [d.declared for d in out] == [None, None, date(2013, 6, 12)]
    assert out[1].amount is None
    with pytest.raises(eodhd.EodhdError):
        eodhd.parse_dividends({"error": "nope"})


def test_client_returns_the_list_and_none_for_an_unknown_ticker():
    t = FakeTransport(Resp(200, [{"date": "2013-08-13"}]), Resp(404, text="Ticker Not Found"))
    c = client(t)
    assert c.dividends("MSFT") == [{"date": "2013-08-13"}]
    assert c.dividends("GONE") is None
    url, params = t.calls[0]
    assert url.endswith("/div/MSFT.US")
    assert params["api_token"] == "secret-token" and params["fmt"] == "json"


def test_client_retries_429_and_connection_errors_then_succeeds():
    t = FakeTransport(Resp(429), requests.ConnectionError("down"), Resp(200, []))
    assert client(t).dividends("KO") == []
    assert len(t.calls) == 3


def test_client_errors_never_carry_the_token():
    t = FakeTransport(Resp(403, text="Forbidden for api_token=secret-token"))
    with pytest.raises(eodhd.EodhdError) as exc:
        client(t).dividends("KO")
    assert "secret-token" not in str(exc.value)
    t = FakeTransport(Resp(200, {"message": "bad secret-token"}))
    with pytest.raises(eodhd.EodhdError) as exc:
        client(t).dividends("KO")
    assert "secret-token" not in str(exc.value)


# ---- matcher -------------------------------------------------------------------------------


def decl(ex, declared):
    return eodhd.Declaration(ex, declared, Decimal("1"))


STORE = {
    "AAA": {
        date(2000, 3, 1): Decimal("0.5"),  # exact match
        date(2000, 6, 1): Decimal("0.5"),  # vendor is two days off
        date(2000, 9, 1): Decimal("0.5"),  # vendor declares after the ex-date: refused
        date(2000, 12, 1): Decimal("0.5"),  # vendor has no declaration date
        date(2001, 3, 1): Decimal("0.5"),  # nothing within the gap
    },
    "BBB": {date(2000, 3, 1): Decimal("1")},  # never fetched
    "SPY": {date(2000, 3, 17): Decimal("0.4")},  # an ETF: skipped
}
VENDOR = {
    "AAA": [
        decl(date(2000, 3, 1), date(2000, 2, 10)),
        decl(date(2000, 6, 3), date(2000, 5, 10)),
        decl(date(2000, 9, 1), date(2000, 9, 2)),
        decl(date(2000, 12, 1), None),
        decl(date(2001, 3, 20), date(2001, 3, 1)),
    ],
    "SPY": [decl(date(2000, 3, 17), date(2000, 3, 1))],
}


def test_match_dates_only_what_the_rules_allow():
    result = da.match(STORE, VENDOR, skip={"SPY"}, years=(2000, 2001))
    assert result.rows == (
        ("AAA", date(2000, 3, 1), date(2000, 2, 10)),
        ("AAA", date(2000, 6, 1), date(2000, 5, 10)),  # the store's ex-date, not the vendor's
    )
    assert result.refused_lead == 1
    assert result.undated_by_vendor == 1
    assert result.unmatched == 1
    assert result.no_vendor_rows == ("BBB",)
    assert result.skipped_symbols == ("SPY",)
    y2000 = result.years[0]
    assert (y2000.year, y2000.dividends, y2000.dated) == (2000, 5, 2)  # BBB counts as undated
    assert result.fraction == pytest.approx(2 / 6)
    assert "2 of 6 dividends dated" in da.format_report(result)


def test_match_refuses_a_declaration_too_far_ahead():
    store = {"AAA": {date(2000, 12, 1): Decimal("1")}}
    vendor = {"AAA": [decl(date(2000, 12, 1), date(2000, 1, 2))]}
    assert da.match(store, vendor).rows == ()


# ---- calendar ------------------------------------------------------------------------------


def test_announced_on_knows_a_declared_dividend_from_its_declaration_day():
    rows = {"AAA": {date(2000, 3, 1): Decimal("0.5"), date(2000, 6, 1): Decimal("0.6")}}
    cal = DividendCalendar.from_map(rows, declared={"AAA": {date(2000, 6, 1): date(2000, 5, 10)}})
    assert cal.announced_on("AAA", date(2000, 2, 29)) == ()  # the March one is undated: ex-date
    assert len(cal.announced_on("AAA", date(2000, 5, 9))) == 1  # June's not yet announced
    assert cal.announced_on("AAA", date(2000, 3, 1))[0].declared is False
    seen = cal.announced_on("AAA", date(2000, 5, 10))
    assert [(a.known, a.ex_date, a.declared) for a in seen] == [
        (date(2000, 3, 1), date(2000, 3, 1), False),
        (date(2000, 5, 10), date(2000, 6, 1), True),
    ]
    assert cal.known_on("AAA", date(2000, 5, 10)) == ((date(2000, 3, 1), Decimal("0.5")),)
    assert cal.declared_count() == 1
    assert cal.announced_on("ZZZ", date(2000, 5, 10)) == ()


def test_calendar_refuses_a_declaration_after_the_ex_date_or_for_no_dividend():
    rows = {"AAA": {date(2000, 3, 1): Decimal("0.5")}}
    with pytest.raises(ValueError):
        DividendCalendar.from_map(rows, declared={"AAA": {date(2000, 3, 1): date(2000, 3, 2)}})
    with pytest.raises(ValueError):
        DividendCalendar.from_map(rows, declared={"AAA": {date(2000, 4, 1): date(2000, 3, 2)}})


# ---- store ---------------------------------------------------------------------------------

ROWS = (("AAA", D2, date(1998, 12, 15)),)


def test_refresh_announcements_adds_the_file_and_keeps_every_price_byte(tmp_path, members):
    store = tmp_path / "store"
    before = build(store, members, facts=FACTS_A)
    carried = (*research.DATA_FILES, research.FUNDAMENTALS_FILE)
    before_bytes = {n: (store / n).read_bytes() for n in carried}

    after = research.refresh_announcements(store, ROWS, data_dir=members)

    assert {n: (store / n).read_bytes() for n in carried} == before_bytes
    assert research.ANNOUNCEMENTS_FILE in after["files"]
    assert research.price_fingerprint_of(after["files"]) == research.price_fingerprint_of(before["files"])
    assert after["fingerprint"] != before["fingerprint"]
    data = research.load_store(store, data_dir=members)
    assert data.market.dividends.declared_count() == 1
    assert data.market.dividends.announced_on("AAA", date(1998, 12, 15))[0].ex_date == D2
    assert data.market.fundamentals.names() == ("AAA",)

    # refreshing the panel afterwards keeps the announcements
    research.refresh_fundamentals(store, FACTS_A, data_dir=members)
    assert research.load_store(store, data_dir=members).market.dividends.declared_count() == 1


def test_refresh_announcements_refuses_a_row_for_no_dividend_and_writes_nothing(tmp_path, members):
    store = tmp_path / "store"
    before = build(store, members)
    with pytest.raises(ValueError):
        research.refresh_announcements(store, (("AAA", date(1999, 1, 4), date(1999, 1, 1)),), data_dir=members)
    with pytest.raises(ValueError):
        research.refresh_announcements(store, (("AAA", D2, date(1999, 2, 1)),), data_dir=members)
    assert json.loads((store / research.MANIFEST_FILE).read_text()) == before
    assert not (store / research.ANNOUNCEMENTS_FILE).exists()


def test_a_store_without_the_file_loads_with_no_declarations(tmp_path, members):
    store = tmp_path / "store"
    build(store, members)
    assert research.load_store(store, data_dir=members).market.dividends.declared_count() == 0


# ---- command -------------------------------------------------------------------------------


def args(store, cache, **kw):
    base = dict(
        fetch=False, refetch=False, refresh=False, demo=False, symbols=None,
        store=store, cache=cache, dry_run=False,
    )
    return argparse.Namespace(**{**base, **kw})


def test_command_fetches_reports_and_refreshes(tmp_path, members, monkeypatch, capsys):
    store = tmp_path / "store"
    build(store, members)
    real_load = research.load_store
    monkeypatch.setattr(
        research, "load_store", lambda s, **kw: real_load(s, **{"data_dir": members, **kw})
    )
    answers = {
        "AAA": [{"date": D2.isoformat(), "declarationDate": "1998-12-15", "value": 0.09}],
    }

    class FakeClient:
        def __init__(self, token):
            assert token == eodhd.DEMO_TOKEN

        def dividends(self, symbol):
            return answers.get(symbol)

    monkeypatch.setattr(eodhd, "Client", FakeClient)
    cache = tmp_path / "cache"

    assert cmd.run(args(store, cache, fetch=True, demo=True)) == 0
    assert json.loads((cache / "AAA.json").read_text())["rows"][0]["declarationDate"] == "1998-12-15"
    assert json.loads((cache / "GONE.json").read_text())["rows"] is None  # unserved, unknown
    out = capsys.readouterr().out
    assert "1 of 1 dividends dated" in out  # SPY is an ETF and left out
    assert not (store / research.ANNOUNCEMENTS_FILE).exists()

    assert cmd.run(args(store, cache, refresh=True)) == 0
    assert (store / research.ANNOUNCEMENTS_FILE).read_text() == (
        f"{research.ANNOUNCEMENTS_HEADER}\nAAA,{D2.isoformat()},1998-12-15\n"
    )


def test_command_without_a_token_exits_2(tmp_path, members, monkeypatch, capsys):
    store = tmp_path / "store"
    build(store, members)
    real_load = research.load_store
    monkeypatch.setattr(
        research, "load_store", lambda s, **kw: real_load(s, **{"data_dir": members, **kw})
    )
    monkeypatch.delenv(eodhd.TOKEN_ENV, raising=False)
    monkeypatch.setattr(cmd.config, "get", lambda name: None)
    assert cmd.run(args(store, tmp_path / "cache", fetch=True)) == 2
    assert eodhd.TOKEN_ENV in capsys.readouterr().out
