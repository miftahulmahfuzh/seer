import logging
from datetime import date
from decimal import Decimal

import pytest

from seer_engine import massive
from seer_engine.massive import Client, MassiveError

KEY = "sekret-key-123"
D = date(2026, 10, 1)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, url, params=None, **kwargs):
        self.requests.append((url, dict(params or {}), kwargs))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


GROUPED_OK = {
    "status": "OK",
    "adjusted": True,
    "resultsCount": 3,
    "results": [
        {"T": "SPY", "o": 764.36, "h": 765.65, "l": 758.7901, "c": 763.99, "v": 47708058.813089,
         "vw": 762.1, "t": 1790798400000, "n": 512345},
        {"T": "BRK.B", "o": 480.1, "h": 482.0, "l": 478.5, "c": 481.25, "v": 3100200.0},
        {"T": "BAD", "o": 1.0},
    ],
}


def make_client(http_, clock=None):
    clock = clock or FakeClock()
    return Client(KEY, get_json=http_, clock=clock.now, sleep=clock.sleep), clock


def test_grouped_parses_bars_and_keeps_dot_tickers():
    http_ = FakeHttp([GROUPED_OK])
    c, _ = make_client(http_)
    out = c.grouped(D)
    assert set(out) == {"SPY", "BRK.B"}
    spy = out["SPY"]
    assert spy.date == D
    assert spy.open == Decimal("764.36")
    assert spy.low == Decimal("758.7901")
    assert spy.close == Decimal("763.99")
    assert isinstance(spy.volume, int)
    assert abs(spy.volume - 47708058) <= 1


def test_grouped_request_shape_and_retry_settings():
    http_ = FakeHttp([GROUPED_OK])
    c, _ = make_client(http_)
    c.grouped(D)
    url, params, kwargs = http_.requests[0]
    assert url == "https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/2026-10-01"
    assert params == {"adjusted": "true", "apiKey": KEY}
    assert kwargs == {"retries": massive.RETRIES, "backoff": massive.BACKOFF}
    assert massive.BACKOFF >= massive.MIN_INTERVAL


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "OK", "adjusted": True, "resultsCount": 0},
        {"status": "OK", "adjusted": True, "resultsCount": 0, "results": []},
        {"status": "NOT_AUTHORIZED", "message": "plan doesn't include this data timeframe"},
        {"status": "OK", "adjusted": False, "results": GROUPED_OK["results"]},
    ],
)
def test_grouped_unusable_responses_raise(payload):
    c, _ = make_client(FakeHttp([payload]))
    with pytest.raises(MassiveError):
        c.grouped(D)


def test_grouped_accepts_delayed_status():
    c, _ = make_client(FakeHttp([{**GROUPED_OK, "status": "DELAYED"}]))
    assert "SPY" in c.grouped(D)


def test_calls_are_spaced_by_min_interval():
    clock = FakeClock()
    c, _ = make_client(FakeHttp([GROUPED_OK, GROUPED_OK, GROUPED_OK]), clock)
    c.grouped(D)
    c.grouped(D)
    clock.t += 20.0
    c.grouped(D)
    assert clock.sleeps == [pytest.approx(massive.MIN_INTERVAL)]
    assert c.calls == 3


def test_http_error_propagates_and_still_counts_for_spacing():
    clock = FakeClock()
    c, _ = make_client(FakeHttp([RuntimeError("HTTP 503"), GROUPED_OK]), clock)
    with pytest.raises(RuntimeError):
        c.grouped(D)
    c.grouped(D)
    assert clock.sleeps == [pytest.approx(massive.MIN_INTERVAL)]


def test_splits_parses_and_follows_next_url():
    page1 = {
        "status": "OK",
        "results": [{"ticker": "NVDA", "execution_date": "2024-06-10", "split_from": 1, "split_to": 10}],
        "next_url": "https://api.massive.com/v3/reference/splits?cursor=abc",
    }
    page2 = {
        "status": "OK",
        "results": [
            {"ticker": "XYZ", "execution_date": "2024-06-10", "split_from": 32, "split_to": 1},
            {"ticker": "BROKEN", "execution_date": "2024-06-10", "split_from": 0, "split_to": 1},
            {"ticker": "OTHER", "execution_date": "2024-06-11", "split_from": 1, "split_to": 2},
        ],
    }
    http_ = FakeHttp([page1, page2])
    c, clock = make_client(http_)
    out = c.splits(date(2024, 6, 10))
    assert [(s.symbol, s.split_from, s.split_to) for s in out] == [
        ("NVDA", Decimal("1"), Decimal("10")),
        ("XYZ", Decimal("32"), Decimal("1")),
    ]
    assert out[0].factor == Decimal(10)
    assert http_.requests[0][1] == {"execution_date": "2024-06-10", "limit": 1000, "apiKey": KEY}
    assert http_.requests[1][0] == "https://api.massive.com/v3/reference/splits?cursor=abc"
    assert http_.requests[1][1] == {"apiKey": KEY}
    assert clock.sleeps == [pytest.approx(massive.MIN_INTERVAL)]


def test_key_never_logged(caplog):
    caplog.set_level(logging.DEBUG)
    c, _ = make_client(FakeHttp([GROUPED_OK, {"status": "OK", "results": []}]))
    c.grouped(D)
    c.splits(D)
    assert KEY not in caplog.text
    assert "massive GET" in caplog.text


def test_empty_key_rejected():
    with pytest.raises(ValueError):
        Client("")
