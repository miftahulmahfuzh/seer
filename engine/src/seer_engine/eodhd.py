"""EODHD REST client: dividends (with declaration dates), daily prices and splits per code.

Bought for one month to fill the research store's ``dividend_announcements.csv`` (insight 109:
the lab only sees the ex-date, weeks after a dividend is announced). The token travels only as
the ``api_token`` query parameter EODHD requires; every URL that reaches a log line or an
exception goes through ``scrub`` (``http.redact`` plus the token itself).
The by-code endpoints (``eod``, ``splits``, ``dividends_by_code``) take a vendor code from the
symbol lists verbatim (``exchange_code``); the alias fill in ``survivorship_alias`` is their only
caller.

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
EOD_FROM = date(1993, 1, 1)  # the original eod/ pull's start (handover §2)


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


def exchange_code(code: str) -> str:
    """An EODHD symbol-list ``Code`` with the US suffix, verbatim: ``DELL_old`` -> ``DELL_old.US``.

    The store's symbols go through ``ticker`` (``BRK.B`` -> ``BRK-B.US``); a vendor code from
    ``symbols-US-*.json`` is already in EODHD's spelling and must keep its case (``_old``)."""
    if not code or not code.strip():
        raise ValueError("code is empty")
    code = code.strip()
    if "." in code:
        raise ValueError(f"{code!r} is not an EODHD code (has a '.'); store symbols go through ticker()")
    return code + ".US"


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
        return self._get_list("div", ticker(symbol), start, what="dividend list")

    def dividends_by_code(self, code: str, *, start: date = HISTORY_FROM) -> list[Any] | None:
        """``/div`` for an EODHD code from its symbol lists (``DELL_old``); None on 404."""
        return self._get_list("div", exchange_code(code), start, what="dividend list")

    def eod(self, code: str, *, start: date = EOD_FROM) -> list[Any] | None:
        """The raw daily ``/eod`` list for an EODHD code since ``start``; None on 404.

        Rows are ``{date, open, high, low, close, adjusted_close, volume}`` with RAW (not
        split-adjusted) OHLC, exactly like ``engine/.cache/eodhd/eod/``."""
        return self._get_list("eod", exchange_code(code), start, what="price list", extra={"period": "d"})

    def splits(self, code: str, *, start: date = HISTORY_FROM) -> list[Any] | None:
        """The raw ``/splits`` list (``[{date, split: "2.000000/1.000000"}]``) for a code; None on 404."""
        return self._get_list("splits", exchange_code(code), start, what="split list")

    def _get_list(
        self,
        endpoint: str,
        target: str,
        start: date,
        *,
        what: str,
        extra: dict[str, str] | None = None,
    ) -> list[Any] | None:
        """GET ``<base>/<endpoint>/<target>`` expecting a JSON list; None on 404.

        Paced by ``min_interval``; 429, 5xx and connection errors retry with exponential
        backoff up to ``retries`` times. Every message that can reach a log line or an
        exception goes through ``scrub`` so the token never leaves this object."""
        url = f"{self.base_url}/{endpoint}/{target}"
        params: dict[str, Any] = {"fmt": "json", "from": start.isoformat()}
        params.update(extra or {})
        params["api_token"] = self._token
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
                        raise EodhdError(f"non-JSON answer for {target}") from exc
                    if not isinstance(data, list):
                        raise EodhdError(
                            f"expected a {what} for {target}, got "
                            f"{scrub(str(data)[:MAX_ERROR_BODY], self._token)}"
                        )
                    return data
                if status == 404:
                    self._last_call = self._clock()
                    return None
                body = scrub(str(getattr(resp, "text", ""))[:MAX_ERROR_BODY], self._token)
                message = f"HTTP {status} for {target}: {body}"
                retryable = status == 429 or status >= 500
            self._last_call = self._clock()
            if not retryable or attempt > self.retries:
                raise EodhdError(message)
            delay = self.backoff * (2 ** (attempt - 1))
            log.warning("eodhd: %s; retry %d/%d in %.1fs", message, attempt, self.retries, delay)
            self._sleep(delay)
