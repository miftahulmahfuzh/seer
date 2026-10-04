# Phase 3: Finnhub client and LLM call options

**Plan set:** `STRATEGY_C_NEWS_VETO_PLAN.md`
**Analysis:** `20261004-171449-C5V8_code_analyzer.md`
**Spec:** `docs/handover/2026-10-04-strategy-c-news-veto.md`
**Satisfies:** R2 — the impure edge C's veto needs: a rate-limited, redacting Finnhub client (company news + earnings calendar) and per-call LLM options (temperature 0, thinking disabled, max_tokens 1024)
**Depends on:** Phase 1 (`seer_engine.strategies.c.Headline`, K1)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine`

---

## Goal

After this phase `seer_engine.finnhub.Client` can fetch a symbol's company news as K1 `Headline`s
(tz-aware UTC, malformed items dropped) and the earliest earnings date inside a window, never
faster than one request per second, with exactly one retry on connection error/timeout/429/5xx and
the key travelling only in the `X-Finnhub-Token` header and scrubbed from every error and log.
`llm.Client.complete` accepts keyword-only `temperature`, `thinking`, `max_tokens`; without them
its request body is byte-identical to today's, so `explain` is unchanged. Nothing calls either new
surface yet — phase 4 (`veto`) does.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates (all in `engine/src/seer_engine/finnhub.py`, new file):**
- constants `BASE_URL = "https://finnhub.io/api/v1"`, `MIN_INTERVAL = 1.0`, `DEFAULT_TIMEOUT_S = 15.0`,
  `RETRIES = 1`, `BACKOFF_S = 2.0`, `MAX_RETRY_AFTER_S = 60.0`, `MAX_ERROR_BODY = 200`,
  `TOKEN_HEADER = "X-Finnhub-Token"`
- `class FinnhubError(RuntimeError)` with `__init__(message: str, status: int | None = None)` and `.status`
- `class Transport(Protocol)`: `get(url, *, params, headers, timeout) -> response` (`requests.Session` satisfies it)
- `def load_key() -> str | None` (`config.get("FINNHUB_API_KEY")`, stripped; blank -> None)
- `def scrub(text: str, key: str | None) -> str` (`http.redact` + literal key -> `REDACTED`)
- `class Client(key: str, *, transport=None, base_url=BASE_URL, min_interval=MIN_INTERVAL,
  timeout=DEFAULT_TIMEOUT_S, retries=RETRIES, backoff=BACKOFF_S, clock=time.monotonic,
  sleep=time.sleep)`; empty/blank key -> `ValueError`; attribute `calls: int` (attempts made)
  - `company_news(symbol: str, start: date, end: date) -> list[Headline]`
  - `earnings(symbol: str, start: date, end: date) -> date | None`
- `engine/tests/test_finnhub.py` (new)

**Signature changes:**
`llm.Client.complete(self, system: str, prompt: str) -> str`
-> `llm.Client.complete(self, system: str, prompt: str, *, temperature: float | None = None, thinking: str | None = None, max_tokens: int | None = None) -> str`.
Body gains `"temperature": temperature` when not None, `"thinking": {"type": thinking}` when not None
(both appended after `"messages"`), and `"max_tokens"` is the per-call value when given. Invalid
`max_tokens < 1` or blank `thinking` raise `ValueError` **before** any request (not `LlmError`).

**Requires (from earlier phases):** `seer_engine.strategies.c.Headline` (Phase 1, K1): a frozen,
slotted dataclass constructible by keyword as `Headline(id: int, published: datetime, source: str,
headline: str, summary: str)`, with value equality. `strategies/c.py` must be importable without
side effects (it is pure, so it is).

**Provides to later phases:**
- Phase 4 constructs `finnhub.Client(key)` (key from `finnhub.load_key()`), calls
  `company_news(symbol, from_et, to_et)` and `earnings(symbol, s, s5)`, catches `FinnhubError`
  (its `str()` is already scrubbed; phase 4 still caps to 300 chars). Phase 4 constructs
  `llm.Client(cfg, timeout=30.0, retries=1)` and calls `complete(SYSTEM_PROMPT, prompt,
  temperature=float(params.temperature), thinking=params.thinking, max_tokens=params.max_tokens)`
  (0.0, "disabled", 1024). Note `CParams.temperature` is the **string** `"0"` and `thinking` the string
  `"disabled"` (K1 `as_dict` needs strings); phase 4 converts with `float(...)` and never passes the
  string (reconciliation: settled as `float(params.temperature)`, the phase 7 smoke does the same).
- Phase 7's live smoke uses the same two clients.
- `company_news` applies **no** cutoff: phase 4 (via K1 `select_headlines`) drops items at/after
  `started_at`. `company_news` keeps Finnhub's order; K1 sorts newest first.

**Leaves alone (owned by others):** `strategies/c.py` (Phase 1); `db/**`, `paper/roster.py`,
`paper/store.py`, `demo.py` (Phase 2); `commands/**` incl. `commands/explain.py` (keeps calling
`complete(SYSTEM, prompt)` unchanged) and `commands/veto.py` (Phase 4/5); `web/**` (Phase 6);
`.github/**`, `engine/package_readme.md`, `docs/**`, `.env.example` (Phase 7); `http.py`, `config.py`,
`massive.py` (unchanged, reused).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/finnhub.py` | create | whole Finnhub client (K5) |
| `engine/src/seer_engine/llm.py:10-12` | modify | module docstring mentions the call options |
| `engine/src/seer_engine/llm.py:153-167` | modify | `complete` keyword options; body built conditionally |
| `engine/tests/test_finnhub.py` | create | fake transport + fake clock tests, no network |
| `engine/tests/test_llm.py:5` and append after `:156` | modify | `import json`; option tests incl. byte-identical legacy body |

## Implementation Steps

### Step 1: Create the Finnhub client
**File:** `engine/src/seer_engine/finnhub.py` (new)
**Change:** New module modelled on `massive.py` (injectable `clock`/`sleep`, spacing measured from
the end of the previous attempt, `calls` counter, debug "waiting" log) and on `llm.py` (injectable
transport with a `requests.Session` default, `scrub` = `http.redact` + literal key, retry loop with
`backoff * 2**(attempt-1)` widened by a numeric `Retry-After`). Design points:

- Pacing runs before **every attempt**, retries included, so no two requests are < 1.0 s apart
  (60/min). `_last_call` is set in a `finally` after each attempt (success, error or exception).
- The key is put only into the `X-Finnhub-Token` header dict; `params` holds only `symbol`, `from`,
  `to`; the info log prints the path and those params. `__repr__` omits the key.
- `Retry-After` is capped at `MAX_RETRY_AFTER_S = 60` so a hostile header cannot stall the nightly
  veto step (whose own budget is 10 min, phase 7). Retry delay = `max(backoff, retry_after)`.
- Unix-second `datetime` -> `datetime.fromtimestamp(stamp, tz=timezone.utc)` (tz-aware UTC). This
  module is impure and outside the purity glob (`strategies/`, `backtest/`, `paper/`), so
  `fromtimestamp` is allowed here.
- Items are dropped when `datetime` or `id` is not a real `int` (bools rejected), or `headline` is
  missing/blank. The `id` check goes slightly beyond K5's wording ("missing/non-int datetime or empty
  headline") because K1's `Headline.id` is `int` and K2 stores it; flagged for the reconciler.
  `source`/`summary` default to `""` when not strings; strings are stripped.
- A JSON object instead of a list for `/company-news` (Finnhub's `{"error": ...}` shape) raises
  `FinnhubError` with the scrubbed error text. An empty list is valid "no news".
- `earnings`: accept **any** row returned for the queried symbol (BRK.B -> BRK.A row, verified);
  unparsable dates skipped; earliest date in `[start, end]` inclusive, else `None`. Missing
  `earningsCalendar` key, a non-list value, or a non-object body -> `FinnhubError`; `null` or `[]` -> `None`.

**Code:**
```python
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
```
**Impact:** New module only; nothing imports it yet. It imports `seer_engine.strategies.c`, so it
requires Phase 1. It is not under the purity glob, so `test_strategy_purity.py` is unaffected.

### Step 2: Module docstring of `llm.py`
**File:** `engine/src/seer_engine/llm.py:10-11`
**Change:** Replace the two lines

```text
``Client.complete(system, prompt)`` POSTs one non-streaming Messages request to
``messages_url(LLM_BASE_URL)`` and returns the reply's text. Connection errors, timeouts, 429
```
with
```text
``Client.complete(system, prompt)`` POSTs one non-streaming Messages request to
``messages_url(LLM_BASE_URL)`` and returns the reply's text. Optional keywords
``temperature``, ``thinking`` and ``max_tokens`` add ``"temperature"`` and
``"thinking": {"type": ...}`` to the body and override the client's ``max_tokens`` for that call
(Strategy C's veto); without them the body is exactly ``{model, max_tokens, system, messages}``
(``explain``). Connection errors, timeouts, 429
```
(the following line `and 5xx are retried ...` stays as is).
**Impact:** docs only.

### Step 3: Keyword options on `Client.complete`
**File:** `engine/src/seer_engine/llm.py:153` (whole method, through end of file at `:191`)
**Change:** Replace the method `complete` with the version below. The body dict keeps its exact key
order (`model`, `max_tokens`, `system`, `messages`) and values when no keyword is given, so
`json.dumps(body)` is byte-identical to today's; options are appended after `messages`. Validation
happens before headers/body are built and before any request.
**Code:**
```python
    def complete(
        self,
        system: str,
        prompt: str,
        *,
        temperature: float | None = None,
        thinking: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send one user ``prompt`` under ``system`` and return the reply's text.

        ``temperature`` adds ``"temperature"`` to the body, ``thinking`` adds
        ``"thinking": {"type": thinking}`` (e.g. ``"disabled"``), and ``max_tokens`` replaces the
        client's default for this call. With none of them the body is byte-identical to the
        keyword-less call ``explain`` makes.
        """
        if max_tokens is not None and max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {max_tokens}")
        if thinking is not None and not thinking.strip():
            raise ValueError("thinking must be a non-empty type such as 'disabled'")
        headers = {
            "x-api-key": self._cfg.api_key,
            "authorization": f"Bearer {self._cfg.api_key}",
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
            "user-agent": f"seer-engine/{__version__}",
        }
        body: dict[str, Any] = {
            "model": self._cfg.model,
            "max_tokens": self._max_tokens if max_tokens is None else max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            body["temperature"] = temperature
        if thinking is not None:
            body["thinking"] = {"type": thinking}
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
```
**Impact:** Backward compatible: the only caller (`commands/explain.py:241`,
`client.complete(SYSTEM, prompt_for(entry))`) is untouched and sends the same bytes. Existing
`test_llm.py::test_complete_posts_one_messages_request` stays green unchanged.

### Step 4: `test_llm.py` additions
**File:** `engine/tests/test_llm.py:5` — insert `import json` and a blank line above `import pytest`, so
the imports read:
```python
from __future__ import annotations

import json

import pytest
import requests

from seer_engine import llm
```
**File:** `engine/tests/test_llm.py` — append after the last line (`:156`, end of `test_scrub`):
**Code:**
```python
# --- Call options for Strategy C's veto (P6 phase 3) -------------------------------------------

LEGACY_BODY_JSON = (
    '{"model": "glm-test", "max_tokens": 400, "system": "sys text", '
    '"messages": [{"role": "user", "content": "user text"}]}'
)


def test_no_keywords_keeps_the_body_byte_identical():
    t = FakeTransport(ok())
    make(t).complete("sys text", "user text")
    [call] = t.calls
    assert json.dumps(call["json"]) == LEGACY_BODY_JSON
    assert list(call["json"]) == ["model", "max_tokens", "system", "messages"]


def test_explicit_none_keywords_equal_no_keywords():
    t = FakeTransport(ok())
    make(t).complete("sys text", "user text", temperature=None, thinking=None, max_tokens=None)
    assert json.dumps(t.calls[0]["json"]) == LEGACY_BODY_JSON


def test_veto_options_reach_the_body():
    t = FakeTransport(ok('{"verdict": "allow", "reason": "No company news."}'))
    text = make(t).complete("sys", "user", temperature=0.0, thinking="disabled", max_tokens=1024)
    assert text == '{"verdict": "allow", "reason": "No company news."}'
    [call] = t.calls
    assert call["json"] == {
        "model": "glm-test",
        "max_tokens": 1024,
        "system": "sys",
        "messages": [{"role": "user", "content": "user"}],
        "temperature": 0.0,
        "thinking": {"type": "disabled"},
    }


def test_each_option_is_independent():
    t = FakeTransport(ok(), ok(), ok())
    c = make(t, max_tokens=300)
    c.complete("s", "p", temperature=0.0)
    c.complete("s", "p", thinking="disabled")
    c.complete("s", "p", max_tokens=50)
    first, second, third = (call["json"] for call in t.calls)
    assert first["temperature"] == 0.0 and "thinking" not in first and first["max_tokens"] == 300
    assert second["thinking"] == {"type": "disabled"} and "temperature" not in second
    assert third["max_tokens"] == 50 and "temperature" not in third and "thinking" not in third


def test_max_tokens_override_is_per_call():
    t = FakeTransport(ok(), ok())
    c = make(t)
    c.complete("s", "p", max_tokens=1024)
    c.complete("s", "p")
    assert [call["json"]["max_tokens"] for call in t.calls] == [1024, llm.DEFAULT_MAX_TOKENS]


def test_options_survive_a_retry():
    sleeps: list[float] = []
    t = FakeTransport(_Resp(503, text="busy"), ok())
    make(t, sleeps).complete("s", "p", temperature=0.0, thinking="disabled", max_tokens=1024)
    assert len(t.calls) == 2 and t.calls[0]["json"] == t.calls[1]["json"]
    assert t.calls[1]["json"]["thinking"] == {"type": "disabled"}


def test_thinking_block_beside_text_still_returns_the_text():
    body = {
        "content": [
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": '{"verdict": "veto", "reason": "Guidance cut."}'},
        ],
        "stop_reason": "end_turn",
    }
    t = FakeTransport(_Resp(200, body))
    assert make(t).complete("s", "p", thinking="disabled") == '{"verdict": "veto", "reason": "Guidance cut."}'


@pytest.mark.parametrize("kw", [{"max_tokens": 0}, {"max_tokens": -5}, {"thinking": ""}, {"thinking": "  "}])
def test_invalid_options_raise_before_any_request(kw):
    t = FakeTransport()
    with pytest.raises(ValueError):
        make(t).complete("s", "p", **kw)
    assert t.calls == []
```
**Impact:** test-only. `LEGACY_BODY_JSON` pins the exact serialized body explain sends today.

### Step 5: `test_finnhub.py`
**File:** `engine/tests/test_finnhub.py` (new)
**Change:** Fake transport (records `url`, `params`, `headers`, `timeout`; can advance the fake
clock per request) and fake clock (from `test_massive.py`). Covers: `load_key`; empty key refused;
key only in the header (never in URL/params/repr/logs); request shapes for both endpoints; pacing
(first call no wait, `MIN_INTERVAL` gaps, spacing from end of previous call, gap between any two
request starts >= 1.0 s); retries (5xx once after `BACKOFF_S`, 429 honouring longer `Retry-After`,
shorter `Retry-After` -> backoff, cap at 60 s, second 5xx raises with status, timeout retried then
raises with `status is None`, connection error then success, 4xx not retried and key scrubbed,
connection-error text scrubbed in error and caplog, non-JSON 200); parsing (UTC conversion and
stripping, malformed items dropped, empty list, `{"error"}` object, non-list); earnings (earliest
in window, inclusive bounds, outside -> None, BRK.B -> BRK.A row accepted, `[]`/`null` -> None,
unparsable rows skipped, unusable shapes raise).
**Code:**
```python
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
```
**Impact:** test-only, no network, no Postgres (never skipped by `PG_TEST_URL`).

## Verification

**Build:** `cd engine && .venv/bin/python -c "import seer_engine.finnhub, seer_engine.llm"` (the worktree
needs its own `engine/.venv`; main's venv tests the wrong tree)
**Lint:** `.venv/bin/python -m ruff check engine` (from repo root, as CI does)
**Tests:** `cd engine && .venv/bin/python -m pytest tests/test_finnhub.py tests/test_llm.py tests/test_strategy_purity.py tests/test_massive.py tests/test_http.py -q`
then the whole suite `python -m pytest engine/tests -q` (with `PG_TEST_URL` set so `test_explain.py` runs:
it must pass unchanged, proving explain's call is untouched).
**Verified this session:** in a scratch copy of `engine/` with a stub `strategies/c.py` holding only
K1's `Headline`, the steps above produced 85 passed across `test_finnhub.py` (37), `test_llm.py`
(23 incl. 11 new), purity, massive, http; `ruff check` clean.
**Manual check:** none (phase 7 runs the live smoke against real Finnhub/z.ai).
**Exit criteria:** spacing >= 1.0 s between any two Finnhub requests (retries included); the key appears
only in the `X-Finnhub-Token` header and in no error, log or repr; one retry on connection
error/timeout/429/5xx honouring a longer `Retry-After` (capped 60 s), no retry on other 4xx;
`earnings` returns the earliest date in the inclusive window; `complete()` with no keywords sends
the byte-identical legacy body and with keywords carries `temperature`, `thinking`, `max_tokens`;
all tests green.

## Handoffs

- **Phase 1 (K1):** `Headline` must be keyword-constructible with fields exactly
  `id, published, source, headline, summary`. If phase 1 renames a field, `finnhub._headline` and
  `test_finnhub.py::test_company_news_converts_items_to_utc_headlines` follow it.
- **Phase 4 (veto, R2):** pass `temperature` as a float (`0.0`), not `CParams.temperature` (the string
  `"0"`); `complete` would serialize a string `"0"` and the provider may reject it. `ValueError` from
  `complete` (bad `max_tokens`/`thinking`) is a programming error, not a network failure — phase 4
  should not count it toward `MAX_CONSECUTIVE_FAILURES` (it cannot happen with the frozen params).
  `FinnhubError`/`LlmError` messages are already scrubbed; phase 4 still truncates to 300 chars and
  may re-`scrub` defensively. `company_news` does not apply the `started_at` cutoff; `select_headlines`
  must. Each candidate costs two Finnhub requests (>= 1 s apart) plus retries; with one shared
  `finnhub.Client` across candidates the pacing holds across the whole run — phase 4 should build one
  client per run, not per candidate.
- **K5 deviation for the reconciler:** items with a non-int `id` are dropped too (K5 lists only
  `datetime`/headline). `Retry-After` is capped at 60 s (K5 says "honouring"). `Client` also takes
  `base_url`, `retries`, `backoff` keywords (superset of K5's list; defaults match K5).
- **Phase 7 (docs, R2/ship):** `engine/package_readme.md` gains a `finnhub` section (constants,
  pacing, retry, redaction, BRK.B -> BRK.A note) and the `llm` section the `complete` keywords.
  `.env.example:19` comment for `FINNHUB_API_KEY`. Not done here.

## Rollback

`git rm engine/src/seer_engine/finnhub.py engine/tests/test_finnhub.py` and
`git checkout <base> -- engine/src/seer_engine/llm.py engine/tests/test_llm.py`. Nothing else in the
tree references the new surface until phase 4 lands; if phase 4 has landed, roll it back first.
