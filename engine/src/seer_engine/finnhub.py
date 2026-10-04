"""Finnhub REST client: company news and the earnings calendar, for Strategy C's veto (P6).

Free tier allows 60 calls/min, so calls are spaced >= MIN_INTERVAL seconds apart (measured from
the end of the previous attempt, retries included). One retry on a connection error, a timeout,
HTTP 429 or 5xx, after BACKOFF_S seconds or the response's numeric Retry-After when longer
(capped at MAX_RETRY_AFTER_S); any other failure raises FinnhubError at once.

The API key travels **only** in the ``X-Finnhub-Token`` request header: never in a query
parameter, a log line or an exception message. Every error text built here passes through
``scrub`` (``http.redact`` plus the key itself), so a provider that echoes the key cannot leak it.

The transport is injectable (anything with ``get(url, *, params, headers, timeout)`` returning a
requests-like response, as ``requests.Session`` does), and so are ``clock`` and ``sleep``, so tests
never touch the network or wait.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any, Protocol

import requests

from seer_engine import __version__, config, http
from seer_engine.strategies.c import Headline

log = logging.getLogger(__name__)

BASE_URL = "https://finnhub.io/api/v1"
MIN_INTERVAL = 1.0
DEFAULT_TIMEOUT_S = 15.0
RETRIES = 1
BACKOFF_S = 2.0
MAX_RETRY_AFTER_S = 60.0
MAX_ERROR_BODY = 200
TOKEN_HEADER = "X-Finnhub-Token"


class FinnhubError(RuntimeError):
    """A Finnhub request failed (after the retry), or answered with something unusable."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class Transport(Protocol):
    def get(self, url: str, *, params: dict[str, Any], headers: dict[str, str], timeout: float) -> Any: ...


def load_key() -> str | None:
    """FINNHUB_API_KEY, or None when it is unset or blank."""
    key = config.get("FINNHUB_API_KEY")
    if key is None:
        return None
    key = key.strip()
    return key or None


def scrub(text: str, key: str | None) -> str:
    """``text`` with key/token query parameters and every occurrence of ``key`` redacted."""
    out = http.redact(text)
    if key:
        out = out.replace(key, "REDACTED")
    return out


def _retry_after(resp: Any) -> float | None:
    headers = getattr(resp, "headers", None) or {}
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        return min(MAX_RETRY_AFTER_S, max(0.0, float(value)))
    except (TypeError, ValueError):
        return None


def _default_transport() -> Transport:
    session = requests.Session()
    session.headers["User-Agent"] = f"seer-engine/{__version__}"
    return session


def _headline(raw: Any) -> Headline | None:
    """One company-news item as a Headline, or None when it lacks an int id/datetime or a headline."""
    if not isinstance(raw, dict):
        return None
    stamp = raw.get("datetime")
    item_id = raw.get("id")
    text = raw.get("headline")
    if not isinstance(stamp, int) or isinstance(stamp, bool):
        return None
    if not isinstance(item_id, int) or isinstance(item_id, bool):
        return None
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        published = datetime.fromtimestamp(stamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    source = raw.get("source")
    summary = raw.get("summary")
    return Headline(
        id=item_id,
        published=published,
        source=source.strip() if isinstance(source, str) else "",
        headline=text.strip(),
        summary=summary.strip() if isinstance(summary, str) else "",
    )


class Client:
    """Finnhub's free REST API: ``company_news`` and ``earnings``."""

    def __init__(
        self,
        key: str,
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
        if not key or not key.strip():
            raise ValueError("Finnhub API key is empty")
        self._key = key.strip()
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

    def __repr__(self) -> str:
        return f"Client(base_url={self.base_url!r})"

    def _pace(self) -> None:
        if self._last_call is None:
            return
        wait = self._last_call + self.min_interval - self._clock()
        if wait > 0:
            log.debug("finnhub: waiting %.2fs for the rate limit", wait)
            self._sleep(wait)

    def _get(self, path: str, params: dict[str, str]) -> Any:
        """GET ``path`` with ``params`` (no secret in them) and return the decoded JSON."""
        url = f"{self.base_url}{path}"
        headers = {
            TOKEN_HEADER: self._key,
            "Accept": "application/json",
            "User-Agent": f"seer-engine/{__version__}",
        }
        attempt = 0
        while True:
            attempt += 1
            self._pace()
            log.info("finnhub GET %s %s", path, params)
            self.calls += 1
            status: int | None = None
            retry_after: float | None = None
            try:
                resp = self._transport.get(url, params=params, headers=headers, timeout=self.timeout)
            except requests.RequestException as exc:
                message = f"{type(exc).__name__}: {exc}"
                retryable = True
            else:
                status = resp.status_code
                if status == 200:
                    try:
                        return resp.json()
                    except ValueError:
                        raise FinnhubError(f"non-JSON response from finnhub {path}", status) from None
                message = f"HTTP {status} from finnhub {path}: {str(resp.text)[:MAX_ERROR_BODY]}"
                retryable = status == 429 or status >= 500
                retry_after = _retry_after(resp)
            finally:
                self._last_call = self._clock()
            message = scrub(message, self._key)
            if not retryable or attempt > self.retries:
                raise FinnhubError(message, status)
            delay = self.backoff * (2 ** (attempt - 1))
            if retry_after is not None:
                delay = max(delay, retry_after)
            log.warning("finnhub: %s; retry %d/%d in %.1fs", message, attempt, self.retries, delay)
            self._sleep(delay)

    def company_news(self, symbol: str, start: date, end: date) -> list[Headline]:
        """Company news for ``symbol`` (dot form, e.g. BRK.B) published on ET dates start..end.

        Items without an int ``id``/``datetime`` or with an empty headline are dropped; the rest
        keep Finnhub's order. ``Headline.published`` is tz-aware UTC. No cutoff is applied here:
        the caller filters by its own clock (``strategies.c.select_headlines``).
        """
        path = "/company-news"
        data = self._get(path, {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()})
        if isinstance(data, dict):
            detail = data.get("error") or "an object instead of a list"
            raise FinnhubError(scrub(f"finnhub {path} {symbol}: {detail}", self._key), 200)
        if not isinstance(data, list):
            raise FinnhubError(f"finnhub {path} {symbol}: unexpected {type(data).__name__}", 200)
        out: list[Headline] = []
        dropped = 0
        for raw in data:
            item = _headline(raw)
            if item is None:
                dropped += 1
                continue
            out.append(item)
        log.info("finnhub news %s %s..%s: %d items, %d dropped", symbol, start, end, len(out), dropped)
        return out

    def earnings(self, symbol: str, start: date, end: date) -> date | None:
        """The earliest earnings date for ``symbol`` within [start, end], or None.

        Every row Finnhub returns for the query counts (``BRK.B`` comes back as the ``BRK.A`` row:
        one company, one report date). Rows without a parsable ``YYYY-MM-DD`` date are skipped.
        """
        path = "/calendar/earnings"
        data = self._get(path, {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()})
        if not isinstance(data, dict):
            raise FinnhubError(f"finnhub {path} {symbol}: unexpected {type(data).__name__}", 200)
        if "earningsCalendar" not in data:
            detail = data.get("error") or "no earningsCalendar field"
            raise FinnhubError(scrub(f"finnhub {path} {symbol}: {detail}", self._key), 200)
        rows = data["earningsCalendar"] or []
        if not isinstance(rows, list):
            raise FinnhubError(f"finnhub {path} {symbol}: earningsCalendar is not a list", 200)
        found: list[date] = []
        for row in rows:
            value = row.get("date") if isinstance(row, dict) else None
            if not isinstance(value, str):
                continue
            try:
                day = date.fromisoformat(value)
            except ValueError:
                continue
            if start <= day <= end:
                found.append(day)
        result = min(found) if found else None
        log.info("finnhub earnings %s %s..%s: %s", symbol, start, end, result)
        return result
