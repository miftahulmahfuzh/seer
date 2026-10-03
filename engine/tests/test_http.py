"""Retry policy and redaction of the shared HTTP helper (no network)."""

from __future__ import annotations

import pytest
import requests

from seer_engine import http


class _Resp:
    def __init__(self, status: int, body=None, headers=None, url="https://x.test/a?apiKey=SECRET"):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.url = url
        self.text = "" if body is None else str(body)

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


@pytest.fixture
def fake(monkeypatch):
    queue: list = []
    sleeps: list[float] = []

    class _Session:
        def get(self, url, params=None, timeout=None):
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    monkeypatch.setattr(http, "_session", _Session())
    monkeypatch.setattr(http, "_sleep", sleeps.append)
    return queue, sleeps


def test_redact():
    assert http.redact("https://api.massive.com/v2/x?adjusted=true&apiKey=abc123") == (
        "https://api.massive.com/v2/x?adjusted=true&apiKey=REDACTED"
    )
    assert http.redact("https://h/x?api_key=a&token=b") == "https://h/x?api_key=REDACTED&token=REDACTED"
    assert http.redact("https://api.frankfurter.dev/v1/latest?base=USD") == (
        "https://api.frankfurter.dev/v1/latest?base=USD"
    )


def test_returns_json(fake):
    queue, sleeps = fake
    queue.append(_Resp(200, {"ok": True}))
    assert http.get_json("https://x.test/a") == {"ok": True}
    assert sleeps == []


def test_retries_429_5xx_and_connection_errors(fake):
    queue, sleeps = fake
    queue.extend([_Resp(429), requests.ConnectionError("down"), _Resp(503), _Resp(200, {"ok": 1})])
    assert http.get_json("https://x.test/a", backoff=1.0) == {"ok": 1}
    assert sleeps == [1.0, 2.0, 4.0]


def test_retry_after_header_wins_when_longer(fake):
    queue, sleeps = fake
    queue.extend([_Resp(429, headers={"Retry-After": "61"}), _Resp(200, {"ok": 1})])
    http.get_json("https://x.test/a", backoff=5.0)
    assert sleeps == [61.0]


def test_gives_up_after_retries_and_redacts(fake):
    queue, _ = fake
    queue.extend([_Resp(500)] * 4)
    with pytest.raises(http.HttpError) as exc:
        http.get_json("https://x.test/a", retries=3, backoff=0)
    assert exc.value.status == 500
    assert "SECRET" not in str(exc.value)


def test_4xx_is_not_retried(fake):
    queue, sleeps = fake
    queue.append(_Resp(403, {"status": "NOT_AUTHORIZED"}))
    with pytest.raises(http.HttpError):
        http.get_json("https://x.test/a")
    assert sleeps == []
