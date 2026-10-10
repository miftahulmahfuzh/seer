"""EODHD REST client: one symbol's full cash-dividend history, with declaration dates.

Bought for one month to fill the research store's ``dividend_announcements.csv`` (insight 109:
the lab only sees the ex-date, weeks after a dividend is announced). The token travels only as
the ``api_token`` query parameter EODHD requires; every URL that reaches a log line or an
exception goes through ``scrub`` (``http.redact`` plus the token itself).

The transport is injectable (anything with ``get(url, *, params, timeout)`` returning a
requests-like response), and so are ``clock`` and ``sleep``, so tests never touch the network.
The demo token ``"demo"`` answers for a handful of tickers (AAPL, MSFT, ...) and is enough to
exercise the whole path before paying.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import requests

from seer_engine import __version__, http

log = logging.getLogger(__name__)

BASE_URL = "https://eodhd.com/api"
DEMO_TOKEN = "demo"
TOKEN_ENV = "EODHD_API_TOKEN"
HISTORY_FROM = date(1990, 1, 1)
MIN_INTERVAL = 0.1  # paid plans allow 1000 calls/min
DEFAULT_TIMEOUT_S = 30.0
RETRIES = 3
BACKOFF_S = 5.0
MAX_ERROR_BODY = 200


class EodhdError(RuntimeError):
    """EODHD failed after its retries, or answered with something that is not a dividend list."""


class Transport(Protocol):
    def get(self, url: str, *, params: dict[str, Any], timeout: float) -> Any: ...


@dataclass(frozen=True)
class Declaration:
    """One vendor dividend row: ``declared`` is None when EODHD has no declaration date."""

    ex_date: date
    declared: date | None
    amount: Decimal | None  # split-adjusted ``value``, for diagnostics only


def ticker(symbol: str) -> str:
    """The store's symbol in EODHD form: ``BRK.B`` -> ``BRK-B.US``."""
    if not symbol or not symbol.strip():
        raise ValueError("symbol is empty")
    return symbol.strip().upper().replace(".", "-") + ".US"


def scrub(text: str, token: str | None) -> str:
    out = http.redact(text)
    if token:
        out = out.replace(token, "REDACTED")
    return out


def _date_or_none(raw: Any) -> date | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def parse_dividends(rows: Any) -> list[Declaration]:
    """EODHD's ``/div`` JSON list as ``Declaration`` rows, ascending by ex-date.

    Rows without a parsable ``date`` (the ex-date) are skipped; a missing or malformed
    ``declarationDate`` becomes None, never a guess.
    """
    if not isinstance(rows, list):
        raise EodhdError(f"expected a JSON list of dividends, got {type(rows).__name__}")
    out: list[Declaration] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        ex_date = _date_or_none(raw.get("date"))
        if ex_date is None:
            continue
        try:
            amount = Decimal(str(raw["value"])) if raw.get("value") is not None else None
        except (InvalidOperation, ValueError):
            amount = None
        out.append(Declaration(ex_date, _date_or_none(raw.get("declarationDate")), amount))
    return sorted(out, key=lambda d: d.ex_date)


def _default_transport() -> Transport:
    session = requests.Session()
    session.headers["User-Agent"] = f"seer-engine/{__version__}"
    return session


class Client:
    def __init__(
        self,
        token: str,
        *,
        transport: Transport | None = None,
        base_url: str = BASE_URL,
        min_interval: float = MIN_INTERVAL,
        timeout: float = DEFAULT_TIMEOUT_S,
        retries: int = RETRIES,
        backoff: float = BACKOFF_S,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not token or not token.strip():
            raise ValueError("EODHD token is empty")
        self._token = token.strip()
        self._transport = transport if transport is not None else _default_transport()
        self.base_url = base_url.rstrip("/")
        self.min_interval = min_interval
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self._clock = clock
        self._sleep = sleep
        self._last_call: float | None = None
        self.calls = 0

    def dividends(self, symbol: str, *, start: date = HISTORY_FROM) -> list[Any] | None:
        """The raw ``/div`` list for ``symbol`` since ``start``; None when EODHD has no such ticker."""
        url = f"{self.base_url}/div/{ticker(symbol)}"
        params = {"fmt": "json", "from": start.isoformat(), "api_token": self._token}
        attempt = 0
        while True:
            attempt += 1
            if self._last_call is not None:
                wait = self._last_call + self.min_interval - self._clock()
                if wait > 0:
                    self._sleep(wait)
            self.calls += 1
            retryable = False
            try:
                resp = self._transport.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                message = scrub(f"{type(exc).__name__}: {exc}", self._token)
                retryable = True
            else:
                status = resp.status_code
                if status == 200:
                    self._last_call = self._clock()
                    try:
                        data = resp.json()
                    except ValueError as exc:
                        raise EodhdError(f"non-JSON answer for {ticker(symbol)}") from exc
                    if not isinstance(data, list):
                        raise EodhdError(
                            f"expected a dividend list for {ticker(symbol)}, got "
                            f"{scrub(str(data)[:MAX_ERROR_BODY], self._token)}"
                        )
                    return data
                if status == 404:
                    self._last_call = self._clock()
                    return None
                body = scrub(str(getattr(resp, "text", ""))[:MAX_ERROR_BODY], self._token)
                message = f"HTTP {status} for {ticker(symbol)}: {body}"
                retryable = status == 429 or status >= 500
            self._last_call = self._clock()
            if not retryable or attempt > self.retries:
                raise EodhdError(message)
            delay = self.backoff * (2 ** (attempt - 1))
            log.warning("eodhd: %s; retry %d/%d in %.1fs", message, attempt, self.retries, delay)
            self._sleep(delay)
