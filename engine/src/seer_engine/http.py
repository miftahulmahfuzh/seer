"""JSON-over-HTTP with retries, and URL redaction for logs and errors."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests

from seer_engine import __version__

log = logging.getLogger(__name__)

USER_AGENT = f"seer-engine/{__version__}"

_SECRET_PARAM = re.compile(r"(?i)\b((?:api_?key|apikey|access_token|token|key)=)[^&#\s]+")

# Module-level so tests can replace them.
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_sleep = time.sleep


class HttpError(RuntimeError):
    """A request failed after all retries, or returned a non-retryable status."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def redact(url: str) -> str:
    """``url`` with the value of any key/token query parameter replaced by REDACTED."""
    return _SECRET_PARAM.sub(r"\1REDACTED", url)


def _retry_after(resp: requests.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    retries: int = 3,
    backoff: float = 5.0,
    timeout: float = 30,
) -> dict:
    """GET ``url`` and return the decoded JSON object.

    Connection errors, timeouts, HTTP 429 and 5xx are retried up to ``retries`` times with
    exponential backoff (``backoff``, 2x, 4x ... seconds; a numeric Retry-After header wins
    when it is longer). Any other non-200 status raises HttpError at once. Every URL that
    reaches a log line or an exception message is redacted.
    """
    attempt = 0
    while True:
        attempt += 1
        retry_after: float | None = None
        status: int | None = None
        try:
            resp = _session.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            message = redact(f"{type(exc).__name__}: {exc}")
            retryable = True
        else:
            status = resp.status_code
            if status == 200:
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise HttpError(f"non-JSON response from {redact(resp.url)}", status) from exc
                if not isinstance(data, dict):
                    raise HttpError(f"expected a JSON object from {redact(resp.url)}", status)
                return data
            message = redact(f"HTTP {status} from {resp.url}: {resp.text[:300]}")
            retryable = status == 429 or status >= 500
            retry_after = _retry_after(resp)
        if not retryable or attempt > retries:
            raise HttpError(message, status)
        delay = backoff * (2 ** (attempt - 1))
        if retry_after is not None:
            delay = max(delay, retry_after)
        log.warning("%s; retry %d/%d in %.1fs", message, attempt, retries, delay)
        _sleep(delay)
