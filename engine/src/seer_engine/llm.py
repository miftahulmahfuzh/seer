"""Minimal Anthropic-compatible Messages API client for optional explanations (design §4, D9).

Configured by three environment variables (see ``.env.example``):

    LLM_BASE_URL   the provider's Anthropic-compatible base URL, e.g. https://api.z.ai/api/anthropic
    LLM_API_KEY    sent as both ``x-api-key`` and ``Authorization: Bearer`` (z.ai
                   compatibility), never logged
    LLM_MODEL      the model id passed in the request body

``Client.complete(system, prompt)`` POSTs one non-streaming Messages request to
``messages_url(LLM_BASE_URL)`` and returns the reply's text. Connection errors, timeouts, 429
and 5xx are retried ``retries`` times; any other failure raises ``LlmError`` at once. Every
error message is scrubbed of the API key and of key/token query parameters.

The transport is injectable (anything with ``post(url, *, headers, json, timeout)`` returning a
requests-like response), so tests never touch the network. Callers treat every ``LlmError`` as
"explanation unavailable": nothing in the paper step depends on this module.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import requests

from seer_engine import __version__, config, http

log = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT_S = 20.0
DEFAULT_RETRIES = 1
DEFAULT_BACKOFF_S = 2.0
DEFAULT_MAX_TOKENS = 400
MAX_ERROR_BODY = 200


class LlmError(RuntimeError):
    """An LLM request failed (after retries), or its reply held no text."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    api_key: str = field(repr=False)
    model: str


class Transport(Protocol):
    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float) -> Any: ...


def load_config() -> LlmConfig | None:
    """The LLM settings, or None when any of LLM_BASE_URL, LLM_API_KEY, LLM_MODEL is unset or empty."""
    base_url = config.get("LLM_BASE_URL")
    api_key = config.get("LLM_API_KEY")
    model = config.get("LLM_MODEL")
    if base_url is None or api_key is None or model is None:
        return None
    base_url, api_key, model = base_url.strip(), api_key.strip(), model.strip()
    if not (base_url and api_key and model):
        return None
    return LlmConfig(base_url=base_url, api_key=api_key, model=model)


def messages_url(base_url: str) -> str:
    """The Messages endpoint for ``base_url``.

    ``https://h/api/anthropic`` -> ``https://h/api/anthropic/v1/messages`` (what Anthropic SDKs do
    with a base URL); a base already ending in ``/v1`` gains ``/messages``; one already ending in
    ``/v1/messages`` is used as is.
    """
    base = base_url.strip().rstrip("/")
    if base.endswith("/v1/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def scrub(text: str, secret: str | None) -> str:
    """``text`` with key/token query parameters and every occurrence of ``secret`` redacted."""
    out = http.redact(text)
    if secret:
        out = out.replace(secret, "REDACTED")
    return out


def _reply_text(resp: Any) -> str:
    """The concatenated text blocks of a Messages reply; LlmError when there are none."""
    try:
        data = resp.json()
    except ValueError as exc:
        raise LlmError("non-JSON reply from the LLM endpoint", resp.status_code) from exc
    if not isinstance(data, dict):
        raise LlmError("expected a JSON object from the LLM endpoint", resp.status_code)
    content = data.get("content")
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
    text = " ".join(p.strip() for p in parts if p.strip())
    if not text:
        raise LlmError(f"no text in the LLM reply (stop_reason={data.get('stop_reason')!r})", resp.status_code)
    return text


def _default_transport() -> Transport:
    session = requests.Session()
    session.headers["User-Agent"] = f"seer-engine/{__version__}"
    return session


class Client:
    """One Anthropic-compatible Messages endpoint; ``complete`` is the only call."""

    def __init__(
        self,
        cfg: LlmConfig,
        *,
        transport: Transport | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        retries: int = DEFAULT_RETRIES,
        backoff: float = DEFAULT_BACKOFF_S,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._cfg = cfg
        self._url = messages_url(cfg.base_url)
        self._transport = transport if transport is not None else _default_transport()
        self._timeout = timeout
        self._retries = retries
        self._backoff = backoff
        self._max_tokens = max_tokens
        self._sleep = sleep

    @property
    def model(self) -> str:
        return self._cfg.model

    def __repr__(self) -> str:
        return f"Client(url={self._url!r}, model={self._cfg.model!r})"

    def complete(self, system: str, prompt: str) -> str:
        """Send one user ``prompt`` under ``system`` and return the reply's text."""
        headers = {
            "x-api-key": self._cfg.api_key,
            "authorization": f"Bearer {self._cfg.api_key}",
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
            "user-agent": f"seer-engine/{__version__}",
        }
        body: dict[str, Any] = {
            "model": self._cfg.model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        attempt = 0
        while True:
            attempt += 1
            status: int | None = None
            try:
                resp = self._transport.post(self._url, headers=headers, json=body, timeout=self._timeout)
            except requests.RequestException as exc:
                message = f"{type(exc).__name__}: {exc}"
                retryable = True
            else:
                status = resp.status_code
                if status == 200:
                    try:
                        return _reply_text(resp)
                    except LlmError as exc:
                        raise LlmError(scrub(str(exc), self._cfg.api_key), status) from None
                message = f"HTTP {status} from the LLM endpoint: {str(resp.text)[:MAX_ERROR_BODY]}"
                retryable = status == 429 or status >= 500
            message = scrub(message, self._cfg.api_key)
            if not retryable or attempt > self._retries:
                raise LlmError(message, status)
            delay = self._backoff * (2 ** (attempt - 1))
            log.warning("LLM call failed (%s); retry %d/%d in %.1fs", message, attempt, self._retries, delay)
            self._sleep(delay)
