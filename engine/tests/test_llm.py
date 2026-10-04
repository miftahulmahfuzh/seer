"""The Anthropic-compatible Messages client: request shape, retries, timeouts, redaction (no network)."""

from __future__ import annotations

import json

import pytest
import requests

from seer_engine import llm

KEY = "sk-test-SECRET-123"
CFG = llm.LlmConfig(base_url="https://llm.test/api/anthropic", api_key=KEY, model="glm-test")


class _Resp:
    def __init__(self, status: int, body=None, text: str | None = None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else ("" if body is None else str(body))
        self.headers: dict[str, str] = {}

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeTransport:
    def __init__(self, *items):
        self.queue = list(items)
        self.calls: list[dict] = []

    def post(self, url, *, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        item = self.queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def ok(text: str = "A paper note.") -> _Resp:
    return _Resp(200, {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn"})


def make(transport: FakeTransport, sleeps: list[float] | None = None, **kw) -> llm.Client:
    return llm.Client(CFG, transport=transport, sleep=(sleeps if sleeps is not None else []).append, **kw)


def test_messages_url_forms():
    assert llm.messages_url("https://api.z.ai/api/anthropic") == "https://api.z.ai/api/anthropic/v1/messages"
    assert llm.messages_url("https://api.z.ai/api/anthropic/") == "https://api.z.ai/api/anthropic/v1/messages"
    assert llm.messages_url("https://api.anthropic.com/v1") == "https://api.anthropic.com/v1/messages"
    assert llm.messages_url("https://h.test/v1/messages") == "https://h.test/v1/messages"


def test_load_config_needs_all_three(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.test")
    monkeypatch.setenv("LLM_API_KEY", KEY)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert llm.load_config() is None
    monkeypatch.setenv("LLM_MODEL", "   ")
    assert llm.load_config() is None
    monkeypatch.setenv("LLM_MODEL", "glm-test")
    assert llm.load_config() == llm.LlmConfig("https://llm.test", KEY, "glm-test")


def test_key_never_in_repr():
    assert KEY not in repr(CFG)
    assert KEY not in repr(make(FakeTransport()))


def test_complete_posts_one_messages_request():
    t = FakeTransport(ok("Hello there."))
    assert make(t).complete("sys text", "user text") == "Hello there."
    [call] = t.calls
    assert call["url"] == "https://llm.test/api/anthropic/v1/messages"
    assert call["headers"]["x-api-key"] == KEY
    assert call["headers"]["authorization"] == f"Bearer {KEY}"
    assert call["headers"]["anthropic-version"] == llm.ANTHROPIC_VERSION
    assert call["headers"]["content-type"] == "application/json"
    assert call["timeout"] == llm.DEFAULT_TIMEOUT_S
    assert call["json"] == {
        "model": "glm-test",
        "max_tokens": llm.DEFAULT_MAX_TOKENS,
        "system": "sys text",
        "messages": [{"role": "user", "content": "user text"}],
    }


def test_joins_text_blocks_and_ignores_others():
    body = {
        "content": [
            {"type": "thinking", "thinking": "hidden"},
            {"type": "text", "text": " First. "},
            {"type": "text", "text": "Second."},
        ]
    }
    assert make(FakeTransport(_Resp(200, body))).complete("s", "p") == "First. Second."


def test_reply_without_text_raises():
    t = FakeTransport(_Resp(200, {"content": [], "stop_reason": "max_tokens"}))
    with pytest.raises(llm.LlmError, match="no text"):
        make(t).complete("s", "p")


def test_non_json_reply_raises():
    with pytest.raises(llm.LlmError, match="non-JSON"):
        make(FakeTransport(_Resp(200, None, text="<html>"))).complete("s", "p")


def test_retries_5xx_and_429_then_succeeds():
    sleeps: list[float] = []
    t = FakeTransport(_Resp(503, text="busy"), ok("Done."))
    assert make(t, sleeps).complete("s", "p") == "Done."
    assert len(t.calls) == 2 and sleeps == [llm.DEFAULT_BACKOFF_S]

    sleeps2: list[float] = []
    t2 = FakeTransport(_Resp(429, text="slow down"), _Resp(429, text="slow down"), ok("Done."))
    assert make(t2, sleeps2, retries=2).complete("s", "p") == "Done."
    assert sleeps2 == [llm.DEFAULT_BACKOFF_S, llm.DEFAULT_BACKOFF_S * 2]


def test_timeout_is_retried_then_raises():
    sleeps: list[float] = []
    t = FakeTransport(requests.Timeout("read timed out"), requests.Timeout("read timed out"))
    with pytest.raises(llm.LlmError, match="Timeout") as exc:
        make(t, sleeps, timeout=1.5).complete("s", "p")
    assert exc.value.status is None
    assert len(t.calls) == 2 and all(c["timeout"] == 1.5 for c in t.calls)
    assert sleeps == [llm.DEFAULT_BACKOFF_S]


def test_4xx_is_not_retried_and_the_key_is_redacted():
    sleeps: list[float] = []
    t = FakeTransport(_Resp(401, text=f'{{"error": "invalid key {KEY}"}}'))
    with pytest.raises(llm.LlmError) as exc:
        make(t, sleeps).complete("s", "p")
    assert exc.value.status == 401
    assert KEY not in str(exc.value) and "REDACTED" in str(exc.value)
    assert len(t.calls) == 1 and sleeps == []


def test_connection_error_text_is_redacted(caplog):
    t = FakeTransport(
        requests.ConnectionError(f"https://llm.test/x?api_key={KEY} refused"),
        requests.ConnectionError(f"failed with {KEY}"),
    )
    with pytest.raises(llm.LlmError) as exc:
        make(t).complete("s", "p")
    assert KEY not in str(exc.value)
    assert KEY not in caplog.text


def test_scrub():
    assert llm.scrub(f"a {KEY} b ?token=xyz", KEY) == "a REDACTED b ?token=REDACTED"
    assert llm.scrub("plain", None) == "plain"


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
