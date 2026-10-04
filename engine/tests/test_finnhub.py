"""The Finnhub client: request shape, pacing, retries, redaction, parsing (no network)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
import requests

from seer_engine import finnhub
from seer_engine.finnhub import Client, FinnhubError
from seer_engine.strategies.c import Headline

KEY = "fh-test-SECRET-987"
START = date(2026, 10, 1)
END = date(2026, 10, 4)


class FakeClock:
    def __init__(self) -> None:
        self.t = 100.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


class _Resp:
    def __init__(self, status: int, body=None, text: str | None = None, headers: dict[str, str] | None = None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else ("" if body is None else str(body))
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeTransport:
    """Pops one queued response (or raises one queued exception) per GET; ``took`` advances the clock."""

    def __init__(self, *items, clock: FakeClock | None = None, took: float = 0.0):
        self.queue = list(items)
        self.calls: list[dict] = []
        self.clock = clock
        self.took = took

    def get(self, url, *, params, headers, timeout):
        self.calls.append({"url": url, "params": dict(params), "headers": dict(headers), "timeout": timeout})
        if self.clock is not None:
            self.clock.t += self.took
        item = self.queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def make(transport: FakeTransport, clock: FakeClock | None = None, **kw) -> tuple[Client, FakeClock]:
    clock = clock or transport.clock or FakeClock()
    return Client(KEY, transport=transport, clock=clock.now, sleep=clock.sleep, **kw), clock


def news_item(i: int, stamp: int, headline: str = "Headline", **extra) -> dict:
    item = {
        "category": "company",
        "datetime": stamp,
        "headline": headline,
        "id": i,
        "image": "",
        "related": "MSFT",
        "source": "Reuters",
        "summary": "A summary.",
        "url": "https://example.test/n",
    }
    item.update(extra)
    return item


# 2026-10-03T14:00:00Z and 2026-10-02T09:30:00Z
T1 = 1791036000
T2 = 1790933400


# --- configuration -----------------------------------------------------------------------------


def test_load_key(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.setattr(finnhub.config, "_loaded", True)
    assert finnhub.load_key() is None
    monkeypatch.setenv("FINNHUB_API_KEY", "   ")
    assert finnhub.load_key() is None
    monkeypatch.setenv("FINNHUB_API_KEY", f" {KEY} ")
    assert finnhub.load_key() == KEY


def test_empty_key_is_refused():
    with pytest.raises(ValueError):
        Client("", transport=FakeTransport())
    with pytest.raises(ValueError):
        Client("  ", transport=FakeTransport())


def test_key_never_in_repr():
    c, _ = make(FakeTransport())
    assert KEY not in repr(c)


# --- request shape -----------------------------------------------------------------------------


def test_key_travels_only_in_the_header():
    t = FakeTransport(_Resp(200, []))
    c, _ = make(t)
    c.company_news("BRK.B", START, END)
    [call] = t.calls
    assert call["url"] == "https://finnhub.io/api/v1/company-news"
    assert call["params"] == {"symbol": "BRK.B", "from": "2026-10-01", "to": "2026-10-04"}
    assert call["headers"][finnhub.TOKEN_HEADER] == KEY
    assert KEY not in call["url"] and KEY not in repr(call["params"])
    assert call["timeout"] == finnhub.DEFAULT_TIMEOUT_S


def test_earnings_request_shape():
    t = FakeTransport(_Resp(200, {"earningsCalendar": []}))
    c, _ = make(t, timeout=4.0)
    c.earnings("JPM", date(2026, 10, 6), date(2026, 10, 12))
    [call] = t.calls
    assert call["url"] == "https://finnhub.io/api/v1/calendar/earnings"
    assert call["params"] == {"symbol": "JPM", "from": "2026-10-06", "to": "2026-10-12"}
    assert call["headers"][finnhub.TOKEN_HEADER] == KEY
    assert call["timeout"] == 4.0


def test_key_not_in_logs(caplog):
    caplog.set_level("DEBUG", logger="seer_engine.finnhub")
    t = FakeTransport(_Resp(200, []), _Resp(200, {"earningsCalendar": []}))
    c, _ = make(t)
    c.company_news("AAPL", START, END)
    c.earnings("AAPL", START, END)
    assert caplog.text and KEY not in caplog.text


# --- pacing ------------------------------------------------------------------------------------


def test_first_call_does_not_wait_and_calls_are_spaced_by_min_interval():
    t = FakeTransport(_Resp(200, []), _Resp(200, {"earningsCalendar": []}), _Resp(200, []))
    c, clock = make(t)
    c.company_news("AAPL", START, END)
    c.earnings("AAPL", START, END)
    c.company_news("MSFT", START, END)
    assert clock.sleeps == [finnhub.MIN_INTERVAL, finnhub.MIN_INTERVAL]
    assert c.calls == 3


def test_spacing_counts_from_the_end_of_the_previous_call():
    clock = FakeClock()
    t = FakeTransport(_Resp(200, []), _Resp(200, []), clock=clock, took=0.3)
    c, _ = make(t, clock)
    c.company_news("AAPL", START, END)
    clock.t += 0.4  # caller work between calls
    c.company_news("MSFT", START, END)
    assert clock.sleeps == [pytest.approx(0.6)]


def test_no_wait_when_enough_time_has_passed():
    clock = FakeClock()
    t = FakeTransport(_Resp(200, []), _Resp(200, []))
    c, _ = make(t, clock)
    c.company_news("AAPL", START, END)
    clock.t += 5.0
    c.company_news("MSFT", START, END)
    assert clock.sleeps == []


def test_gap_between_any_two_requests_is_at_least_min_interval():
    clock = FakeClock()
    starts: list[float] = []

    class Recording(FakeTransport):
        def get(self, url, *, params, headers, timeout):
            starts.append(clock.t)
            return super().get(url, params=params, headers=headers, timeout=timeout)

    t = Recording(*[_Resp(200, []) for _ in range(6)], clock=clock, took=0.2)
    c, _ = make(t, clock)
    for symbol in ("A", "B", "C", "D", "E", "F"):
        c.company_news(symbol, START, END)
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(g >= finnhub.MIN_INTERVAL - 1e-9 for g in gaps)


# --- retries and errors ------------------------------------------------------------------------


def test_5xx_is_retried_once_after_the_backoff():
    t = FakeTransport(_Resp(503, text="busy"), _Resp(200, []))
    c, clock = make(t)
    assert c.company_news("AAPL", START, END) == []
    assert len(t.calls) == 2
    assert clock.sleeps == [finnhub.BACKOFF_S]


def test_429_honours_a_longer_retry_after():
    t = FakeTransport(_Resp(429, text="limit", headers={"Retry-After": "7"}), _Resp(200, []))
    c, clock = make(t)
    c.company_news("AAPL", START, END)
    assert clock.sleeps == [7.0]


def test_retry_after_shorter_than_backoff_uses_backoff():
    t = FakeTransport(_Resp(429, text="limit", headers={"Retry-After": "0"}), _Resp(200, []))
    c, clock = make(t)
    c.company_news("AAPL", START, END)
    assert clock.sleeps == [finnhub.BACKOFF_S]


def test_retry_after_is_capped():
    t = FakeTransport(_Resp(429, text="limit", headers={"Retry-After": "3600"}), _Resp(200, []))
    c, clock = make(t)
    c.company_news("AAPL", START, END)
    assert clock.sleeps == [finnhub.MAX_RETRY_AFTER_S]


def test_second_5xx_raises_with_status():
    t = FakeTransport(_Resp(502, text="bad gateway"), _Resp(502, text="bad gateway"))
    c, _ = make(t)
    with pytest.raises(FinnhubError) as exc:
        c.company_news("AAPL", START, END)
    assert exc.value.status == 502
    assert len(t.calls) == 2


def test_timeout_is_retried_then_raises():
    t = FakeTransport(requests.Timeout("read timed out"), requests.Timeout("read timed out"))
    c, clock = make(t)
    with pytest.raises(FinnhubError, match="Timeout") as exc:
        c.earnings("AAPL", START, END)
    assert exc.value.status is None
    assert len(t.calls) == 2 and clock.sleeps == [finnhub.BACKOFF_S]


def test_connection_error_then_success():
    t = FakeTransport(requests.ConnectionError("refused"), _Resp(200, {"earningsCalendar": []}))
    c, _ = make(t)
    assert c.earnings("AAPL", START, END) is None
    assert len(t.calls) == 2


def test_4xx_is_not_retried_and_the_key_is_scrubbed():
    t = FakeTransport(_Resp(401, text=f'{{"error": "Invalid API key {KEY}"}}'))
    c, clock = make(t)
    with pytest.raises(FinnhubError) as exc:
        c.company_news("AAPL", START, END)
    assert exc.value.status == 401
    assert KEY not in str(exc.value) and "REDACTED" in str(exc.value)
    assert len(t.calls) == 1 and clock.sleeps == []


def test_connection_error_text_is_scrubbed_in_errors_and_logs(caplog):
    t = FakeTransport(
        requests.ConnectionError(f"https://finnhub.io/api/v1/news?token={KEY} refused"),
        requests.ConnectionError(f"failed with {KEY}"),
    )
    c, _ = make(t)
    with pytest.raises(FinnhubError) as exc:
        c.company_news("AAPL", START, END)
    assert KEY not in str(exc.value)
    assert KEY not in caplog.text


def test_non_json_200_raises():
    t = FakeTransport(_Resp(200, None, text="<html>"))
    c, _ = make(t)
    with pytest.raises(FinnhubError, match="non-JSON"):
        c.company_news("AAPL", START, END)
    assert len(t.calls) == 1


def test_scrub():
    assert finnhub.scrub(f"a {KEY} b ?token=xyz", KEY) == "a REDACTED b ?token=REDACTED"
    assert finnhub.scrub("plain", None) == "plain"


# --- company_news parsing ----------------------------------------------------------------------


def test_company_news_converts_items_to_utc_headlines():
    body = [
        news_item(11, T1, " Microsoft beats estimates ", source="Reuters", summary=" Strong cloud. "),
        news_item(12, T2, "Older story", source="CNBC", summary=""),
    ]
    c, _ = make(FakeTransport(_Resp(200, body)))
    out = c.company_news("MSFT", START, END)
    assert out == [
        Headline(
            id=11,
            published=datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc),
            source="Reuters",
            headline="Microsoft beats estimates",
            summary="Strong cloud.",
        ),
        Headline(
            id=12,
            published=datetime(2026, 10, 2, 9, 30, tzinfo=timezone.utc),
            source="CNBC",
            headline="Older story",
            summary="",
        ),
    ]
    assert all(h.published.tzinfo is not None and h.published.utcoffset().total_seconds() == 0 for h in out)


def test_company_news_drops_malformed_items():
    body = [
        news_item(1, T1, "Kept"),
        news_item(2, T1, ""),
        news_item(3, T1, "   "),
        news_item(4, "1791036000", "String datetime"),
        news_item(5, 1791036000.5, "Float datetime"),
        news_item(6, True, "Bool datetime"),
        {k: v for k, v in news_item(7, T1, "No datetime").items() if k != "datetime"},
        news_item("8", T1, "String id"),
        news_item(9, T1, None),
        "not an object",
        news_item(10, T2, "Also kept", source=None, summary=None),
    ]
    c, _ = make(FakeTransport(_Resp(200, body)))
    out = c.company_news("MSFT", START, END)
    assert [h.id for h in out] == [1, 10]
    assert out[1].source == "" and out[1].summary == ""


def test_company_news_empty_list_is_no_news():
    c, _ = make(FakeTransport(_Resp(200, [])))
    assert c.company_news("MSFT", START, END) == []


def test_company_news_error_object_raises_scrubbed():
    c, _ = make(FakeTransport(_Resp(200, {"error": f"You don't have access. token {KEY}"})))
    with pytest.raises(FinnhubError) as exc:
        c.company_news("MSFT", START, END)
    assert "access" in str(exc.value) and KEY not in str(exc.value)


def test_company_news_non_list_raises():
    c, _ = make(FakeTransport(_Resp(200, "a string")))
    with pytest.raises(FinnhubError):
        c.company_news("MSFT", START, END)


# --- earnings ----------------------------------------------------------------------------------


def test_earnings_returns_the_earliest_date_in_the_window():
    body = {
        "earningsCalendar": [
            {"symbol": "JPM", "date": "2026-10-20", "hour": "bmo"},
            {"symbol": "JPM", "date": "2026-10-13", "hour": "bmo"},
            {"symbol": "JPM", "date": "2026-09-30", "hour": "bmo"},
        ]
    }
    c, _ = make(FakeTransport(_Resp(200, body)))
    assert c.earnings("JPM", date(2026, 10, 6), date(2026, 10, 20)) == date(2026, 10, 13)


def test_earnings_window_bounds_are_inclusive():
    body = {"earningsCalendar": [{"symbol": "X", "date": "2026-10-06"}]}
    c, _ = make(FakeTransport(_Resp(200, body), _Resp(200, {"earningsCalendar": [{"symbol": "X", "date": "2026-10-12"}]})))
    assert c.earnings("X", date(2026, 10, 6), date(2026, 10, 12)) == date(2026, 10, 6)
    assert c.earnings("X", date(2026, 10, 6), date(2026, 10, 12)) == date(2026, 10, 12)


def test_earnings_outside_the_window_is_none():
    body = {"earningsCalendar": [{"symbol": "AAPL", "date": "2026-10-29", "hour": "amc"}]}
    c, _ = make(FakeTransport(_Resp(200, body)))
    assert c.earnings("AAPL", date(2026, 10, 6), date(2026, 10, 12)) is None


def test_earnings_accepts_the_row_finnhub_returns_for_a_share_class():
    body = {"earningsCalendar": [{"symbol": "BRK.A", "date": "2026-10-30", "hour": ""}]}
    c, _ = make(FakeTransport(_Resp(200, body)))
    assert c.earnings("BRK.B", date(2026, 10, 26), date(2026, 10, 30)) == date(2026, 10, 30)


@pytest.mark.parametrize("calendar", [[], None])
def test_earnings_empty_calendar_is_none(calendar):
    c, _ = make(FakeTransport(_Resp(200, {"earningsCalendar": calendar})))
    assert c.earnings("AAPL", START, END) is None


def test_earnings_skips_unparsable_rows():
    body = {
        "earningsCalendar": [
            {"symbol": "X", "date": "soon"},
            {"symbol": "X", "date": None},
            {"symbol": "X"},
            "junk",
            {"symbol": "X", "date": "2026-10-03"},
        ]
    }
    c, _ = make(FakeTransport(_Resp(200, body)))
    assert c.earnings("X", START, END) == date(2026, 10, 3)


@pytest.mark.parametrize(
    "body",
    [
        {"error": "You don't have access to this resource."},
        {"somethingElse": []},
        {"earningsCalendar": "nope"},
        [],
    ],
)
def test_earnings_unusable_shapes_raise(body):
    c, _ = make(FakeTransport(_Resp(200, body)))
    with pytest.raises(FinnhubError):
        c.earnings("AAPL", START, END)
