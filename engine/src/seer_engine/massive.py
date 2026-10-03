"""Massive (ex-Polygon) REST client: grouped daily bars and stock splits.

Free tier allows 5 calls/min, so calls are spaced >= MIN_INTERVAL seconds apart (measured from the
end of the previous call). Retries on 429/5xx are delegated to http.get_json with a backoff that is
itself >= MIN_INTERVAL. The API key only ever travels as the `apiKey` query parameter handed to
http.get_json; it is never put in a log line or an exception message built here.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date
from decimal import InvalidOperation
from typing import Any, Protocol

from seer_engine import bars as bars_mod
from seer_engine import http
from seer_engine.bars import Bar
from seer_engine.splits import Split

log = logging.getLogger(__name__)

BASE_URL = "https://api.massive.com"
MIN_INTERVAL = 12.5
RETRIES = 4
BACKOFF = 15.0
MAX_PAGES = 50
OK_STATUSES = frozenset({"OK", "DELAYED"})

GetJson = Callable[..., Any]


class MassiveError(RuntimeError):
    """Massive answered, but not with usable data (not published yet, not authorized, malformed)."""


class MassiveSource(Protocol):
    def grouped(self, d: date) -> dict[str, Bar]: ...

    def splits(self, d: date) -> list[Split]: ...


class Client:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        min_interval: float = MIN_INTERVAL,
        retries: int = RETRIES,
        backoff: float = BACKOFF,
        get_json: GetJson | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("Massive API key is empty")
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.min_interval = min_interval
        self.retries = retries
        self.backoff = backoff
        self._get_json: GetJson = get_json if get_json is not None else http.get_json
        self._clock = clock
        self._sleep = sleep
        self._last_call: float | None = None
        self.calls = 0

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._last_call is not None:
            wait = self._last_call + self.min_interval - self._clock()
            if wait > 0:
                log.debug("massive: waiting %.1fs for the rate limit", wait)
                self._sleep(wait)
        # The path without its query string and the non-secret params only; never the key.
        log.info("massive GET %s %s", url.split("?", 1)[0], params)
        self.calls += 1
        try:
            data = self._get_json(
                url,
                {**params, "apiKey": self._api_key},
                retries=self.retries,
                backoff=self.backoff,
            )
        finally:
            self._last_call = self._clock()
        if not isinstance(data, dict):
            raise MassiveError(f"unexpected response type from {url.split('?', 1)[0]}: {type(data).__name__}")
        return data

    def grouped(self, d: date) -> dict[str, Bar]:
        """Split-adjusted OHLCV for every US ticker on session d, keyed by Massive's (dot-form) ticker."""
        url = f"{self.base_url}/v2/aggs/grouped/locale/us/market/stocks/{d.isoformat()}"
        data = self._get(url, {"adjusted": "true"})
        status = data.get("status")
        if status not in OK_STATUSES:
            detail = data.get("message") or data.get("error") or ""
            raise MassiveError(f"grouped daily {d.isoformat()}: status {status!r} {detail}".strip())
        if data.get("adjusted") is False:
            raise MassiveError(f"grouped daily {d.isoformat()}: response is not split-adjusted")
        results = data.get("results") or []
        if not results:
            raise MassiveError(f"grouped daily {d.isoformat()}: no results (not published yet?)")
        out: dict[str, Bar] = {}
        skipped = 0
        for r in results:
            symbol = r.get("T")
            values = [r.get(k) for k in ("o", "h", "l", "c", "v")]
            if not isinstance(symbol, str) or not symbol or any(v is None for v in values):
                skipped += 1
                continue
            try:
                out[symbol] = bars_mod.make_bar(symbol, d, *values)
            except (ArithmeticError, ValueError, TypeError):
                skipped += 1
        if skipped:
            log.debug("grouped daily %s: skipped %d malformed rows", d.isoformat(), skipped)
        log.info("grouped daily %s: %d tickers", d.isoformat(), len(out))
        return out

    def splits(self, d: date) -> list[Split]:
        """Splits executing on d (follows next_url pagination)."""
        url = f"{self.base_url}/v3/reference/splits"
        params: dict[str, Any] = {"execution_date": d.isoformat(), "limit": 1000}
        out: list[Split] = []
        for _ in range(MAX_PAGES):
            data = self._get(url, params)
            status = data.get("status")
            if status is not None and status not in OK_STATUSES:
                detail = data.get("message") or data.get("error") or ""
                raise MassiveError(f"splits {d.isoformat()}: status {status!r} {detail}".strip())
            for raw in data.get("results") or []:
                try:
                    split = Split.from_massive(raw, d)
                except (KeyError, ValueError, TypeError, InvalidOperation) as e:
                    log.warning("splits %s: skipped malformed row %r (%s)", d.isoformat(), raw, e)
                    continue
                if split.execution_date == d:
                    out.append(split)
            next_url = data.get("next_url")
            if not next_url:
                log.info("splits %s: %d", d.isoformat(), len(out))
                return out
            url, params = next_url, {}
        raise MassiveError(f"splits {d.isoformat()}: more than {MAX_PAGES} pages")
