# Phase 1: Pure C: strategy object, prompt, parser

**Plan set:** `STRATEGY_C_NEWS_VETO_PLAN.md`
**Analysis:** `20261004-171449-C5V8_code_analyzer.md`
**Satisfies:** R1 (the pure engine half: C strategy object + frozen params + prompt + JSON verdict parser; the roster entry half of R1 is phase 2)
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

After this phase `seer_engine.strategies.c` exists and implements contract K1 in full: `CParams`
(C's frozen spec input, prompt texts included), `NewsVeto` (A's first 10 ranked picks minus every
symbol whose stored verdict for the session bought is not `allow`), the `c-veto-v1` prompt and its
user-message builder, the news/earnings window helpers, `select_headlines`, `parse_verdict` and
`allowed_map`. Nothing calls it yet; it is pure (covered automatically by
`tests/test_strategy_purity.py`), and `tests/test_strategy_c.py` proves the K1 exit criteria.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates** (all in `engine/src/seer_engine/strategies/c.py`, new file):
- Constants: `PROMPT_VERSION = "c-veto-v1"`, `FROZEN_MODEL = "glm-5.3"`, `STRATEGY_C_ID = "C-news-veto"`,
  `Verdict = Literal["allow", "veto", "failed"]`, `VERDICTS = ("allow", "veto", "failed")`,
  `SYSTEM_PROMPT`, `USER_TEMPLATE` (K1 texts verbatim, no trailing newline),
  `NEWS_TZ = ZoneInfo("America/New_York")`, `MAX_REASON_CHARS = 300`, `UNPARSABLE_SNIPPET_CHARS = 120`,
  `NO_HEADLINES = "No headlines."`, `NO_EARNINGS = "none found"`.
- `Headline(id: int, published: datetime, source: str, headline: str, summary: str)` — frozen, slots;
  `published` must be tz-aware and is normalized to UTC; `id` an int (not bool); empty/blank
  `headline` raises `ValueError`.
- `CParams` (fields/defaults exactly K1) with validation and `as_dict() -> dict[str, str]`; key order:
  `a.rsi_max, a.limit_atr, a.tp_atr, a.sl_atr, a.min_dollar_volume, a_object, a_object_id,
  max_candidates, news_days, max_headlines, max_summary_chars, earnings_sessions, model,
  prompt_version, temperature, thinking, max_tokens, system_prompt, user_template`.
- `STRATEGY_C_PARAMS = CParams()`.
- `candidates(history, members, data_date, params: CParams) -> list[Pick]`,
  `candidates_prepared(prepared, members, data_date, params: CParams) -> list[Pick]` (TypeError when
  `params` is not `CParams`).
- `NewsVeto(allowed, id=STRATEGY_C_ID, lookback=STRATEGY_A.lookback)` — frozen, slots, `eq=False`;
  `allowed` is normalized to a read-only `MappingProxyType[date, frozenset[str]]` (a copy; any
  `Mapping[date, Iterable[str]]` accepted); methods `picks`, `prepare`, `picks_prepared`,
  `with_allowed(allowed) -> NewsVeto`. Lookup key: `dates.next_session(data_date)`.
- `STRATEGY_C = NewsVeto(allowed={})`.
- `news_dates(started_at: datetime, days: int) -> tuple[date, date]` (tz-aware `started_at`, `days >= 1`).
- `earnings_window(session: date, n: int) -> tuple[date, date]` (`session` must be an NYSE session,
  `n >= 1`).
- `select_headlines(items, cutoff, cap) -> tuple[Headline, ...]` (tz-aware cutoff, `cap >= 0`).
- `headline_line(i: int, h: Headline, max_summary_chars: int) -> str` (public helper used by
  `user_prompt`; one prompt line; an empty summary leaves the line ending in `|`).
- `user_prompt(symbol, session, window_end, earnings, cutoff, headlines, params) -> str`
  (raises `ValueError` when more than `params.max_headlines` headlines are passed, or `window_end < session`).
- `parse_verdict(text) -> tuple[Verdict, str]` (never raises; non-`str` input → `failed`; raw control
  characters inside JSON strings tolerated via `JSONDecoder(strict=False)`; failure reason is
  `"unparsable reply: " + first 120 chars of the reply with whitespace collapsed`, or
  `"unparsable reply: empty"`).
- `allowed_map(rows) -> dict[date, frozenset[str]]` (every session with a row gets a key, an empty set
  when nothing was allowed; unknown verdict or a duplicate (session, symbol) raises `ValueError`;
  keys sorted ascending).

**Creates** (tests): `engine/tests/test_strategy_c.py`.
**Signature changes:** none.
**Requires (from earlier phases):** none.
**Leaves alone (owned by others):** `strategies/a.py` and `strategies/__init__.py` (no re-export of C;
callers import `seer_engine.strategies.c` directly); `paper/roster.py`, `paper/store.py`, `demo.py`,
`db/migrations/*` (phase 2); `finnhub.py`, `llm.py` (phase 3); `commands/veto.py` (phase 4);
`commands/paper.py`, `commands/paper_check.py` (phase 5); `web/**` (phase 6); workflow and docs (phase 7).

### Notes for the phases that consume K1

- **Phase 2 (roster/store):** `STRATEGY_C.id == "C-news-veto"`, `STRATEGY_C.lookback == 200`;
  `STRATEGY_C_PARAMS.as_dict()` holds the full prompt texts, so C's digest is long-input but stable.
  `allowed_map` validates verdicts against `VERDICTS` and rejects duplicates, so `allowed_between`
  can feed it rows straight from `news_vetoes`.
- **Phase 3 (Finnhub):** build `Headline(id, published, source, headline, summary)`; `published` must
  be tz-aware (convert unix seconds as `datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=ts)`).
  `Headline` raises `ValueError` on a blank headline and `TypeError` on a non-int id / non-str text,
  so the client must drop such items **before** constructing (K5 already says it drops them).
- **Phase 4 (veto):** `user_prompt(...)` wants the output of `select_headlines(..., cap=params.max_headlines)`;
  passing more raises. `window_end` is `earnings_window(session, params.earnings_sessions)[1]`.
  `parse_verdict` never raises. The stored lean headline dict (`id`, `datetime` as
  `YYYY-MM-DDTHH:MM:SSZ`, `source`, `headline`) is built by phase 4/2 from `Headline` fields; K1 has
  no helper for it.
- **Phase 5 (paper/check):** `NewsVeto.with_allowed(mapping)` accepts the `dict[date, frozenset[str]]`
  from `store.allowed_between`; an `isinstance(e.obj, NewsVeto)` test is the dispatch K7 describes.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/c.py` | create (whole file, line 1) | K1: params, strategy object, prompt, parser |
| `engine/tests/test_strategy_c.py` | create (whole file, line 1) | K1 exit criteria |

`tests/test_strategy_purity.py` needs no edit: its glob picks up `strategies/c.py` (verified: the
purity tests pass with the file present; `c.py` imports only `json`, `collections.abc`,
`dataclasses`, `datetime`, `types`, `typing`, `zoneinfo`, `seer_engine.dates` (already imported by
`strategies/f_index.py`), `seer_engine.sim`, `strategies.a`, `strategies.base`).

## Implementation Steps

### Step 1: Create `strategies/c.py`
**File:** `engine/src/seer_engine/strategies/c.py:1` (new file)
**Change:** the whole module below. `SYSTEM_PROMPT` and `USER_TEMPLATE` are the K1 texts verbatim,
without a trailing newline (lines are long on purpose; ruff in this repo selects only `E9`/`F`, so
`E501` does not apply).
**Code:**
```python
"""Strategy C: Strategy A's candidates with a news + LLM veto (design §4, roadmap P6).

Every night the impure ``veto`` command takes A's ranked picks for the next session S, cut to the
first ``max_candidates`` (``candidates``), reads each company's recent news (Finnhub), asks the LLM
under the frozen prompt ``c-veto-v1`` (``SYSTEM_PROMPT`` + ``user_prompt``) and stores one verdict
per candidate (``parse_verdict``). ``NewsVeto`` then decides S from the stored verdicts only: it
keeps a candidate when its verdict for S is ``allow`` and drops it when the verdict is ``veto`` or
``failed`` or missing (design §8: a failed veto check is no trade). The LLM is never asked here,
so ``paper`` and ``paper_check`` replay C exactly from what was stored.

Everything C's frozen spec depends on is a code constant in ``CParams`` (A's params, the caps, the
news window, the model, the prompt version and texts), so ``CParams.as_dict`` is C's digest input.

Pure: no database, network, clock, randomness or logging (tests/test_strategy_purity.py). Times
come in as arguments (``started_at``, ``cutoff``); ``zoneinfo`` only converts them.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence, Set
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Literal
from zoneinfo import ZoneInfo

from seer_engine import dates
from seer_engine.sim import Pick
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS, AParams
from seer_engine.strategies.base import History

PROMPT_VERSION = "c-veto-v1"
FROZEN_MODEL = "glm-5.3"  # the model C's verdicts are frozen to; a different LLM_MODEL = every verdict failed
STRATEGY_C_ID = "C-news-veto"  # NewsVeto.id, the spec's object_id

Verdict = Literal["allow", "veto", "failed"]
VERDICTS: tuple[str, ...] = ("allow", "veto", "failed")

NEWS_TZ = ZoneInfo("America/New_York")  # Finnhub's from/to are calendar dates; C reads them in ET
MAX_REASON_CHARS = 300
UNPARSABLE_SNIPPET_CHARS = 120

SYSTEM_PROMPT = """You are the news check of a paper-trading research app. A price rule has already chosen a US stock to buy at the next market open and to hold for at most 5 trading sessions. Your only job is to say whether recent news about this company shows a specific event risk inside that window.

Answer "veto" when the facts or headlines show any of these for this company:
- an earnings report scheduled inside the holding window, or released in the last 3 days;
- a guidance cut, profit warning, or a large miss;
- accounting problems, a restatement, fraud allegations, or an auditor change;
- a new lawsuit, regulatory or government action, investigation, or recall;
- merger, acquisition, buyout, spin-off, or tender-offer news;
- a trading halt, delisting notice, bankruptcy, or going-concern doubt;
- a major analyst downgrade or a credit-rating downgrade;
- the departure of the CEO or CFO.

Answer "allow" otherwise: when there are no headlines, or the news is general market or sector commentary, a recap of price moves, routine product news, or opinion.

Use only the facts and headlines given. Reply with one JSON object and nothing else:
{"verdict": "allow" or "veto", "reason": "<one sentence, at most 25 words>"}"""

USER_TEMPLATE = """Symbol: {symbol}
Entry: the open of {session}
Holding window: {session} to {window_end} ({sessions} sessions)
Scheduled earnings inside the window: {earnings}
Headlines published before {cutoff} UTC, newest first ({count} shown, at most {cap}):
{headline_lines}"""

NO_HEADLINES = "No headlines."
NO_EARNINGS = "none found"


def _positive_int(name: str, v: object) -> None:
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < 1:
        raise ValueError(f"{name} must be >= 1, got {v}")


def _aware(name: str, v: object) -> datetime:
    if not isinstance(v, datetime):
        raise TypeError(f"{name} must be a datetime, got {type(v).__name__}")
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware, got {v!r}")
    return v.astimezone(timezone.utc)


def _day(name: str, v: object) -> date:
    if isinstance(v, datetime) or not isinstance(v, date):
        raise TypeError(f"{name} must be a date, got {type(v).__name__}")
    return v


def _one_line(text: str) -> str:
    """``text`` with every run of whitespace (newlines included) collapsed to one space, stripped."""
    return " ".join(text.split())


@dataclass(frozen=True, slots=True)
class Headline:
    """One Finnhub company-news item, as C reads it. ``published`` is stored in UTC."""

    id: int
    published: datetime
    source: str
    headline: str
    summary: str

    def __post_init__(self) -> None:
        if isinstance(self.id, bool) or not isinstance(self.id, int):
            raise TypeError(f"id must be an int, got {type(self.id).__name__}")
        object.__setattr__(self, "published", _aware("published", self.published))
        for name in ("source", "headline", "summary"):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"{name} must be a str, got {type(getattr(self, name)).__name__}")
        if not self.headline.strip():
            raise ValueError(f"headline {self.id} is empty")


@dataclass(frozen=True, slots=True)
class CParams:
    """Strategy C's frozen parameters. Every field is part of C's spec digest (handover D5)."""

    a: AParams = STRATEGY_A_PARAMS
    max_candidates: int = 10  # D2: A's first 10 ranked picks are checked; lower ranks never bought
    news_days: int = 3  # D3: from = run date (ET) - 3 days, to = run date (ET)
    max_headlines: int = 20  # D3
    max_summary_chars: int = 280  # summaries are sent to the LLM, never stored
    earnings_sessions: int = 5  # earnings window = S .. the 5th session from S (DESIGN_V0.time_stop)
    model: str = FROZEN_MODEL
    prompt_version: str = PROMPT_VERSION
    temperature: str = "0"
    thinking: str = "disabled"
    max_tokens: int = 1024

    def __post_init__(self) -> None:
        if not isinstance(self.a, AParams):
            raise TypeError(f"a must be AParams, got {type(self.a).__name__}")
        for name in ("max_candidates", "news_days", "max_headlines", "max_summary_chars", "earnings_sessions", "max_tokens"):
            _positive_int(name, getattr(self, name))
        for name in ("model", "prompt_version", "temperature", "thinking"):
            v = getattr(self, name)
            if not isinstance(v, str):
                raise TypeError(f"{name} must be a str, got {type(v).__name__}")
            if not v:
                raise ValueError(f"{name} must be non-empty")

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (C's frozen spec ``params``).

        A's params come first as ``a.<key>``, then the object they run on, C's own fields by name,
        and the full frozen prompt texts, so any change to the prompt moves C's digest.
        """
        out = {f"a.{k}": v for k, v in self.a.as_dict().items()}
        out["a_object"] = "STRATEGY_A"
        out["a_object_id"] = STRATEGY_A.id
        out["max_candidates"] = str(self.max_candidates)
        out["news_days"] = str(self.news_days)
        out["max_headlines"] = str(self.max_headlines)
        out["max_summary_chars"] = str(self.max_summary_chars)
        out["earnings_sessions"] = str(self.earnings_sessions)
        out["model"] = self.model
        out["prompt_version"] = self.prompt_version
        out["temperature"] = self.temperature
        out["thinking"] = self.thinking
        out["max_tokens"] = str(self.max_tokens)
        out["system_prompt"] = SYSTEM_PROMPT
        out["user_template"] = USER_TEMPLATE
        return out


STRATEGY_C_PARAMS = CParams()


def _params(params: object) -> CParams:
    if not isinstance(params, CParams):
        raise TypeError(f"params must be CParams, got {type(params).__name__}")
    return params


def candidates(
    history: Mapping[str, History],
    members: Set[str],
    data_date: date,
    params: CParams,
) -> list[Pick]:
    """A's ranked picks on ``data_date`` (for ``next_session(data_date)``), cut to ``max_candidates``.

    The one function both ``veto`` (which checks them) and ``NewsVeto.picks`` (which buys the
    allowed ones) call, so the two always see the same list in the same order.
    """
    p = _params(params)
    return STRATEGY_A.picks(history, members, data_date, p.a)[: p.max_candidates]


def candidates_prepared(prepared: Any, members: Set[str], data_date: date, params: CParams) -> list[Pick]:
    """``candidates`` on A's prepared features (``STRATEGY_A.prepare``); equal by A's contract."""
    p = _params(params)
    return STRATEGY_A.picks_prepared(prepared, members, data_date, p.a)[: p.max_candidates]


def _allowed(allowed: Mapping[date, Iterable[str]]) -> Mapping[date, frozenset[str]]:
    if not isinstance(allowed, Mapping):
        raise TypeError(f"allowed must be a Mapping, got {type(allowed).__name__}")
    out: dict[date, frozenset[str]] = {}
    for session, symbols in allowed.items():
        _day("allowed session", session)
        if isinstance(symbols, str):
            raise TypeError(f"allowed[{session}] must be a set of symbols, got a str")
        frozen = frozenset(symbols)
        for s in frozen:
            if not isinstance(s, str) or not s:
                raise TypeError(f"allowed[{session}] holds a non-symbol {s!r}")
        out[session] = frozen
    return MappingProxyType(out)


@dataclass(frozen=True, slots=True, eq=False)
class NewsVeto:
    """Strategy C behind the ``Strategy`` protocol: ``candidates`` minus every symbol not allowed.

    ``allowed`` maps the session S being bought for to the symbols whose stored verdict for S is
    ``allow``. A session missing from the map, or a symbol missing from its set, is not bought.
    Picks for ``data_date`` are for ``next_session(data_date)``, so that is the key looked up.
    """

    allowed: Mapping[date, frozenset[str]]
    id: str = STRATEGY_C_ID
    lookback: int = STRATEGY_A.lookback

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed", _allowed(self.allowed))
        if not isinstance(self.id, str) or not self.id:
            raise ValueError(f"id must be a non-empty str, got {self.id!r}")
        _positive_int("lookback", self.lookback)

    def _allowed_for(self, data_date: date) -> frozenset[str]:
        return self.allowed.get(dates.next_session(data_date), frozenset())

    def picks(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        p = _params(params)
        allowed = self._allowed_for(data_date)
        if not allowed:
            return []
        return [pick for pick in candidates(history, members, data_date, p) if pick.symbol in allowed]

    def prepare(self, history: Mapping[str, History]) -> Any:
        return STRATEGY_A.prepare(history)

    def picks_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        p = _params(params)
        allowed = self._allowed_for(data_date)
        if not allowed:
            return []
        return [pick for pick in candidates_prepared(prepared, members, data_date, p) if pick.symbol in allowed]

    def with_allowed(self, allowed: Mapping[date, Iterable[str]]) -> NewsVeto:
        """This strategy with ``allowed`` as its verdict map (same id and lookback)."""
        return replace(self, allowed=allowed)


STRATEGY_C = NewsVeto(allowed={})  # the roster object: with no verdicts it never buys


def news_dates(started_at: datetime, days: int) -> tuple[date, date]:
    """``(from, to)`` ET calendar dates for Finnhub's company news: ``to`` is ``started_at``'s date
    in America/New_York, ``from`` is ``days`` calendar days earlier."""
    started = _aware("started_at", started_at)
    _positive_int("days", days)
    to = started.astimezone(NEWS_TZ).date()
    return to - timedelta(days=days), to


def earnings_window(session: date, n: int) -> tuple[date, date]:
    """``(session, the n-th NYSE session counting session as 1)``: the holding window of a buy at
    ``session``'s open under ``DESIGN_V0.time_stop = n``."""
    _day("session", session)
    _positive_int("n", n)
    if not dates.is_session(session):
        raise ValueError(f"{session} is not an NYSE session")
    end = session
    for _ in range(n - 1):
        end = dates.next_session(end)
    return session, end


def select_headlines(items: Iterable[Headline], cutoff: datetime, cap: int) -> tuple[Headline, ...]:
    """The items published strictly before ``cutoff``, newest first (ties: higher id first), at most
    ``cap``. Items at or after ``cutoff`` are never returned (no look-ahead)."""
    cut = _aware("cutoff", cutoff)
    if isinstance(cap, bool) or not isinstance(cap, int):
        raise TypeError(f"cap must be an int, got {type(cap).__name__}")
    if cap < 0:
        raise ValueError(f"cap must be >= 0, got {cap}")
    kept = []
    for h in items:
        if not isinstance(h, Headline):
            raise TypeError(f"expected a Headline, got {type(h).__name__}")
        if h.published < cut:
            kept.append(h)
    kept.sort(key=lambda h: (h.published, h.id), reverse=True)
    return tuple(kept[:cap])


def _cut_words(text: str, n: int) -> str:
    """``text`` (one line) cut to at most ``n`` characters at a word boundary."""
    if len(text) <= n:
        return text
    head = text[: n + 1]
    i = head.rfind(" ")
    return (head[:i] if i > 0 else text[:n]).rstrip()


def _minute(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")


def headline_line(i: int, h: Headline, max_summary_chars: int) -> str:
    """``{i}. {YYYY-MM-DD HH:MM}Z | {source} | {headline} | {summary}``, one line; an empty
    summary leaves the line ending in ``|``."""
    summary = _cut_words(_one_line(h.summary), max_summary_chars)
    line = f"{i}. {_minute(h.published)}Z | {_one_line(h.source)} | {_one_line(h.headline)} | {summary}"
    return line.rstrip()


def user_prompt(
    symbol: str,
    session: date,
    window_end: date,
    earnings: date | None,
    cutoff: datetime,
    headlines: Sequence[Headline],
    params: CParams,
) -> str:
    """The ``c-veto-v1`` user message for one candidate: ``USER_TEMPLATE`` filled in.

    ``headlines`` are the ones ``select_headlines`` kept, in that order (at most ``max_headlines``).
    """
    p = _params(params)
    if not isinstance(symbol, str) or not symbol:
        raise ValueError(f"symbol must be a non-empty str, got {symbol!r}")
    _day("session", session)
    _day("window_end", window_end)
    if window_end < session:
        raise ValueError(f"window_end {window_end} is before session {session}")
    if earnings is not None:
        _day("earnings", earnings)
    cut = _aware("cutoff", cutoff)
    items = tuple(headlines)
    if len(items) > p.max_headlines:
        raise ValueError(f"{len(items)} headlines, at most {p.max_headlines} are sent")
    for h in items:
        if not isinstance(h, Headline):
            raise TypeError(f"expected a Headline, got {type(h).__name__}")
    lines = (
        "\n".join(headline_line(i, h, p.max_summary_chars) for i, h in enumerate(items, start=1))
        if items
        else NO_HEADLINES
    )
    return USER_TEMPLATE.format(
        symbol=symbol,
        session=session.isoformat(),
        window_end=window_end.isoformat(),
        sessions=p.earnings_sessions,
        earnings=earnings.isoformat() if earnings is not None else NO_EARNINGS,
        cutoff=_minute(cut),
        count=len(items),
        cap=p.max_headlines,
        headline_lines=lines,
    )


def _unparsable(text: object) -> tuple[Verdict, str]:
    snippet = _one_line(text)[:UNPARSABLE_SNIPPET_CHARS] if isinstance(text, str) else ""
    return "failed", f"unparsable reply: {snippet or 'empty'}"


def parse_verdict(text: str) -> tuple[Verdict, str]:
    """``("allow" | "veto", reason)`` from an LLM reply; ``("failed", "unparsable reply: ...")``
    otherwise.

    Takes the first ``{...}`` JSON object in ``text`` (surrounding whitespace, a ```json fence or
    other text around it are ignored). ``verdict`` must be "allow" or "veto" (case-insensitive,
    stripped); ``reason`` a non-empty string, whitespace collapsed, capped at 300 characters.
    """
    if not isinstance(text, str):
        return _unparsable(text)
    start = text.find("{")
    if start < 0:
        return _unparsable(text)
    try:
        obj, _ = json.JSONDecoder(strict=False).raw_decode(text, start)
    except ValueError:
        return _unparsable(text)
    if not isinstance(obj, dict):
        return _unparsable(text)
    verdict, reason = obj.get("verdict"), obj.get("reason")
    if not isinstance(verdict, str) or not isinstance(reason, str):
        return _unparsable(text)
    v = verdict.strip().lower()
    r = _one_line(reason)[:MAX_REASON_CHARS].rstrip()
    if v not in ("allow", "veto") or not r:
        return _unparsable(text)
    return ("allow" if v == "allow" else "veto"), r


def allowed_map(rows: Iterable[tuple[date, str, str]]) -> dict[date, frozenset[str]]:
    """``(session, symbol, verdict)`` rows -> ``{session: symbols whose verdict is "allow"}``.

    Every session that has a row gets a key (an empty set when nothing was allowed). A verdict
    outside ``VERDICTS`` or two rows for the same (session, symbol) raise ValueError.
    """
    seen: set[tuple[date, str]] = set()
    out: dict[date, set[str]] = {}
    for session, symbol, verdict in rows:
        _day("session", session)
        if not isinstance(symbol, str) or not symbol:
            raise ValueError(f"symbol must be a non-empty str, got {symbol!r}")
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}, got {verdict!r}")
        if (session, symbol) in seen:
            raise ValueError(f"two verdicts for {symbol} on {session}")
        seen.add((session, symbol))
        bucket = out.setdefault(session, set())
        if verdict == "allow":
            bucket.add(symbol)
    return {s: frozenset(v) for s, v in sorted(out.items())}
```
**Impact:** additive; no existing module imports it. `tests/test_strategy_purity.py` now also checks
`seer_engine.strategies.c` (passes).

Design notes the implementer should keep:
- `NewsVeto.picks`/`picks_prepared` return `[]` before computing candidates when the session has no
  allowed symbol: same output, and a replay of `STRATEGY_C` over a long window stays cheap. The
  `params` type check runs first, so a wrong `params` still raises.
- `allowed` is copied into a `MappingProxyType` in `__post_init__` (also on `with_allowed`, which uses
  `dataclasses.replace`), so a caller mutating its own dict later cannot change a decided night.
- `parse_verdict` uses `json.JSONDecoder(strict=False).raw_decode` from the first `{`: that accepts a
  ```` ```json ```` fence, surrounding text, and raw newlines inside the reason string (seen from LLMs),
  and only ever reads the first object.
- Times: `news_dates` converts with `zoneinfo` (tzdata ships with the venv via pandas; the OS zoneinfo
  on ubuntu CI also works). No `fromtimestamp`, no `now`.

### Step 2: Create `tests/test_strategy_c.py`
**File:** `engine/tests/test_strategy_c.py:1` (new file)
**Change:** the whole test module below. Synthetic markets reuse the bar shape of
`tests/test_backtest_runner.py::_smoke_bars` (copied, not imported: test modules are not a library)
plus `simkit.D`/`simkit.bar`. `SMALL` (3 symbols) never ranks more than 10, so C with every candidate
allowed must equal A under `run_rules(DESIGN_V0)`; `WIDE` (12 symbols dipping together) ranks 12 on
its dip days, so the cap is exercised.
**Code:**
```python
"""Strategy C, pure part (strategy-c-news-veto phase 1, contract K1): the NewsVeto strategy object,
its frozen params, the c-veto-v1 prompt and the verdict parser."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from simkit import D, bar

from seer_engine import dates
from seer_engine.backtest.book_runner import run_rules
from seer_engine.backtest.market import Market, Membership
from seer_engine.sim.rules import DESIGN_V0
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS, AParams
from seer_engine.strategies.base import Strategy, history_from_bars
from seer_engine.strategies.c import (
    FROZEN_MODEL,
    PROMPT_VERSION,
    STRATEGY_C,
    STRATEGY_C_ID,
    STRATEGY_C_PARAMS,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
    VERDICTS,
    CParams,
    Headline,
    NewsVeto,
    allowed_map,
    candidates,
    candidates_prepared,
    earnings_window,
    news_dates,
    parse_verdict,
    select_headlines,
    user_prompt,
)

UTC = timezone.utc

# --------------------------------------------------------------------------- synthetic markets


def _smoke_bars(symbol: str, sessions: list[date], phase: int, base: float = 100.0):
    """An uptrend (+0.4 % a session) with two -3 % sessions every 20 (shifted by ``phase``) and a
    deep intraday low the session after, so A's setup fires and its limit fills (the market of
    tests/test_backtest_runner.py::test_strategy_a_smoke_prepared_equals_plain)."""
    out = []
    prev = base + phase
    for t, d in enumerate(sessions):
        k = (t + phase) % 20
        c = prev * 0.97 if k in (17, 18) else prev * 1.004
        o = prev
        lo = min(o, c) * (0.97 if k == 19 else 0.995)
        hi = max(o, c) * 1.005
        out.append(bar(symbol, d, f"{o:.4f}", f"{hi:.4f}", f"{lo:.4f}", f"{c:.4f}", 1_000_000))
        prev = float(f"{c:.4f}")
    return out


SESSIONS = dates.sessions(D("2024-01-02"), D("2025-03-31"))


def _market(spec: tuple[tuple[str, int, float], ...]) -> Market:
    history = {s: history_from_bars(s, _smoke_bars(s, SESSIONS, phase, base)) for s, phase, base in spec}
    return Market(
        history=history,
        membership=Membership(tuple((s, D("2020-01-02"), None) for s in sorted(history))),
        fx=((D("2023-12-29"), Decimal("16000")),),
    )


# A never ranks more than three symbols here, so C with every candidate allowed is A.
SMALL = _market((("UPA", 0, 100.0), ("UPB", 7, 100.0), ("UPC", 13, 100.0)))
# Twelve symbols that dip on the same sessions: A ranks all twelve, C checks only the first ten.
WIDE = _market(tuple((f"W{k:02d}", 0, 100.0 + 3.0 * k) for k in range(12)))
START, END = SESSIONS[200], SESSIONS[-1]  # data_date SESSIONS[199] has exactly 200 bars


def _members(market: Market, d: date) -> frozenset[str]:
    return market.membership.members_on(d)


def _cut(market: Market, d: date):
    return {s: h.upto(d) for s, h in market.history.items()}


def _a_picks(market: Market, d: date):
    return STRATEGY_A.picks(_cut(market, d), _members(market, d), d, STRATEGY_A_PARAMS)


def _wide_day() -> date:
    """A data_date on which A ranks more than ten WIDE symbols."""
    for d in SESSIONS[199:]:
        if len(_a_picks(WIDE, d)) > 10:
            return d
    raise AssertionError("WIDE never ranks more than ten symbols")


def _all_allowed(market: Market, start: date, end: date) -> dict[date, frozenset[str]]:
    everyone = frozenset(market.history)
    return {s: everyone for s in dates.sessions(start, dates.next_session(end))}


# --------------------------------------------------------------------------- params and constants


def test_constants():
    assert PROMPT_VERSION == "c-veto-v1"
    assert FROZEN_MODEL == "glm-5.3"
    assert STRATEGY_C_ID == "C-news-veto"
    assert VERDICTS == ("allow", "veto", "failed")


def test_params_defaults_and_as_dict():
    p = STRATEGY_C_PARAMS
    assert p == CParams()
    assert p.a is STRATEGY_A_PARAMS
    assert (p.max_candidates, p.news_days, p.max_headlines, p.max_summary_chars, p.earnings_sessions) == (
        10, 3, 20, 280, 5
    )
    assert p.earnings_sessions == DESIGN_V0.time_stop
    d = p.as_dict()
    assert list(d) == [
        "a.rsi_max",
        "a.limit_atr",
        "a.tp_atr",
        "a.sl_atr",
        "a.min_dollar_volume",
        "a_object",
        "a_object_id",
        "max_candidates",
        "news_days",
        "max_headlines",
        "max_summary_chars",
        "earnings_sessions",
        "model",
        "prompt_version",
        "temperature",
        "thinking",
        "max_tokens",
        "system_prompt",
        "user_template",
    ]
    assert all(isinstance(v, str) for v in d.values())
    assert {k[2:]: v for k, v in d.items() if k.startswith("a.")} == STRATEGY_A_PARAMS.as_dict()
    assert d["a_object"] == "STRATEGY_A"
    assert d["a_object_id"] == "A"
    assert d["max_candidates"] == "10"
    assert d["news_days"] == "3"
    assert d["max_headlines"] == "20"
    assert d["max_summary_chars"] == "280"
    assert d["earnings_sessions"] == "5"
    assert d["model"] == "glm-5.3"
    assert d["prompt_version"] == "c-veto-v1"
    assert d["temperature"] == "0"
    assert d["thinking"] == "disabled"
    assert d["max_tokens"] == "1024"
    assert d["system_prompt"] == SYSTEM_PROMPT
    assert d["user_template"] == USER_TEMPLATE
    json.dumps(d, sort_keys=True)  # canonical-JSON-able, as the roster's spec_text needs


def test_as_dict_moves_with_every_frozen_input():
    base = STRATEGY_C_PARAMS.as_dict()
    for changed in (
        CParams(a=AParams(rsi_max=5.0)),
        CParams(max_candidates=9),
        CParams(news_days=2),
        CParams(max_headlines=10),
        CParams(max_summary_chars=200),
        CParams(earnings_sessions=4),
        CParams(model="glm-9"),
        CParams(prompt_version="c-veto-v2"),
        CParams(temperature="0.2"),
        CParams(thinking="enabled"),
        CParams(max_tokens=512),
    ):
        assert changed.as_dict() != base


@pytest.mark.parametrize(
    "kwargs, exc",
    [
        ({"a": "A"}, TypeError),
        ({"max_candidates": 0}, ValueError),
        ({"max_candidates": True}, TypeError),
        ({"news_days": 1.5}, TypeError),
        ({"max_headlines": -1}, ValueError),
        ({"earnings_sessions": 0}, ValueError),
        ({"model": ""}, ValueError),
        ({"temperature": 0}, TypeError),
    ],
)
def test_params_validate(kwargs, exc):
    with pytest.raises(exc):
        CParams(**kwargs)


def test_frozen_prompt_texts_verbatim():
    assert SYSTEM_PROMPT.startswith("You are the news check of a paper-trading research app. ")
    assert SYSTEM_PROMPT.endswith('{"verdict": "allow" or "veto", "reason": "<one sentence, at most 25 words>"}')
    assert SYSTEM_PROMPT.count("\n- ") == 8
    assert "- the departure of the CEO or CFO.\n\nAnswer \"allow\" otherwise:" in SYSTEM_PROMPT
    assert USER_TEMPLATE == (
        "Symbol: {symbol}\n"
        "Entry: the open of {session}\n"
        "Holding window: {session} to {window_end} ({sessions} sessions)\n"
        "Scheduled earnings inside the window: {earnings}\n"
        "Headlines published before {cutoff} UTC, newest first ({count} shown, at most {cap}):\n"
        "{headline_lines}"
    )


# --------------------------------------------------------------------------- candidates and NewsVeto


def test_news_veto_is_a_strategy_and_the_roster_object_never_buys():
    assert isinstance(STRATEGY_C, Strategy)
    assert STRATEGY_C.id == STRATEGY_C_ID
    assert STRATEGY_C.lookback == STRATEGY_A.lookback
    assert dict(STRATEGY_C.allowed) == {}
    d = _wide_day()
    assert STRATEGY_C.picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS) == []
    with pytest.raises(FrozenInstanceError):
        STRATEGY_C.id = "X"  # type: ignore[misc]


def test_candidates_are_a_first_ten_and_all_allowed_c_equals_them():
    d = _wide_day()
    a = _a_picks(WIDE, d)
    assert len(a) > 10
    cands = candidates(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS)
    assert cands == a[:10]
    c = STRATEGY_C.with_allowed({dates.next_session(d): frozenset(WIDE.history)})
    assert c.picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS) == cands
    # ranks 11 and 12 are never returned, even when allowed
    assert {p.symbol for p in a[10:]}.isdisjoint(
        p.symbol for p in c.picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS)
    )


def test_vetoed_failed_and_missing_symbols_are_dropped_in_rank_order():
    d = _wide_day()
    cands = candidates(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS)
    rows = []
    for rank, p in enumerate(cands, start=1):
        if rank in (2, 5):
            rows.append((dates.next_session(d), p.symbol, "veto"))
        elif rank == 7:
            rows.append((dates.next_session(d), p.symbol, "failed"))
        elif rank == 9:
            continue  # no stored verdict = failed
        else:
            rows.append((dates.next_session(d), p.symbol, "allow"))
    c = STRATEGY_C.with_allowed(allowed_map(rows))
    got = c.picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS)
    assert got == [p for k, p in enumerate(cands, start=1) if k not in (2, 5, 7, 9)]


def test_verdicts_are_keyed_by_the_session_bought_for():
    d = _wide_day()
    everyone = frozenset(WIDE.history)
    # a map keyed by data_date (the wrong key) buys nothing
    assert STRATEGY_C.with_allowed({d: everyone}).picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS) == []
    # another session's verdicts do not leak
    other = dates.next_session(dates.next_session(d))
    assert STRATEGY_C.with_allowed({other: everyone}).picks(
        _cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS
    ) == []


def test_with_allowed_keeps_id_and_lookback_and_freezes_the_map():
    src = {D("2025-01-02"): {"AAA", "BBB"}}
    c = STRATEGY_C.with_allowed(src)
    assert isinstance(c, NewsVeto)
    assert (c.id, c.lookback) == (STRATEGY_C.id, STRATEGY_C.lookback)
    assert c.allowed[D("2025-01-02")] == frozenset({"AAA", "BBB"})
    src[D("2025-01-02")].add("CCC")
    src[D("2025-01-03")] = {"DDD"}
    assert c.allowed == {D("2025-01-02"): frozenset({"AAA", "BBB"})}
    with pytest.raises(TypeError):
        c.allowed[D("2025-01-06")] = frozenset()  # type: ignore[index]
    assert dict(STRATEGY_C.allowed) == {}


@pytest.mark.parametrize(
    "allowed, exc",
    [
        ([("2025-01-02", "AAA")], TypeError),
        ({datetime(2025, 1, 2): {"AAA"}}, TypeError),
        ({D("2025-01-02"): "AAA"}, TypeError),
        ({D("2025-01-02"): {1}}, TypeError),
    ],
)
def test_allowed_map_shape_is_validated(allowed, exc):
    with pytest.raises(exc):
        NewsVeto(allowed=allowed)


def test_params_must_be_c_params():
    d = _wide_day()
    with pytest.raises(TypeError):
        STRATEGY_C.picks(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_A_PARAMS)
    with pytest.raises(TypeError):
        candidates(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_A_PARAMS)
    with pytest.raises(TypeError):
        candidates_prepared(STRATEGY_A.prepare(WIDE.history), _members(WIDE, d), d, STRATEGY_A_PARAMS)


def test_picks_prepared_equals_picks_on_the_cut_history():
    c = STRATEGY_C.with_allowed(_all_allowed(WIDE, START, END))
    partial = STRATEGY_C.with_allowed(
        {s: frozenset({"W00", "W03", "W07", "W11"}) for s in dates.sessions(START, dates.next_session(END))}
    )
    prepared = c.prepare(WIDE.history)
    for d in SESSIONS[199:]:
        members = _members(WIDE, d)
        assert candidates_prepared(prepared, members, d, STRATEGY_C_PARAMS) == candidates(
            _cut(WIDE, d), members, d, STRATEGY_C_PARAMS
        )
        for strat in (c, partial, STRATEGY_C):
            assert strat.picks_prepared(prepared, members, d, STRATEGY_C_PARAMS) == strat.picks(
                _cut(WIDE, d), members, d, STRATEGY_C_PARAMS
            )


def test_bars_after_data_date_never_change_candidates():
    d = _wide_day()
    full = candidates(WIDE.history, _members(WIDE, d), d, STRATEGY_C_PARAMS)
    assert full == candidates(_cut(WIDE, d), _members(WIDE, d), d, STRATEGY_C_PARAMS)


def test_run_rules_all_allowed_c_equals_a_when_a_never_needs_rank_eleven():
    for d in SESSIONS[199:]:
        assert len(_a_picks(SMALL, d)) <= 10
    c = STRATEGY_C.with_allowed(_all_allowed(SMALL, START, END))
    a_run = run_rules(SMALL, STRATEGY_A, STRATEGY_A_PARAMS, DESIGN_V0, START, END)
    c_run = run_rules(SMALL, c, STRATEGY_C_PARAMS, DESIGN_V0, START, END)
    assert c_run.strategy_id == STRATEGY_C_ID
    assert any(e.kind == "fill" for e in a_run.events)
    assert replace(c_run, strategy_id="A", params=STRATEGY_A_PARAMS) == a_run
    prepped = run_rules(SMALL, c, STRATEGY_C_PARAMS, DESIGN_V0, START, END, prepared=c.prepare(SMALL.history))
    assert prepped == c_run


def test_run_rules_with_no_verdicts_never_trades_and_a_veto_changes_the_run():
    none = run_rules(SMALL, STRATEGY_C, STRATEGY_C_PARAMS, DESIGN_V0, START, END)
    assert none.events == ()
    assert {s.equity_usd for s in none.snapshots} == {none.initial_cash}
    allowed = _all_allowed(SMALL, START, END)
    no_upa = STRATEGY_C.with_allowed({s: v - {"UPA"} for s, v in allowed.items()})
    run = run_rules(SMALL, no_upa, STRATEGY_C_PARAMS, DESIGN_V0, START, END)
    assert all(e.order.symbol != "UPA" for e in run.events)
    assert any(e.kind == "fill" for e in run.events)


# --------------------------------------------------------------------------- news window, earnings window


def test_news_dates_are_et_calendar_dates():
    # 2026-10-05 23:00 UTC is 19:00 ET the same day
    assert news_dates(datetime(2026, 10, 5, 23, 0, tzinfo=UTC), 3) == (D("2026-10-02"), D("2026-10-05"))
    # 2026-10-06 01:00 UTC (the retry cron) is still 2026-10-05 in New York
    assert news_dates(datetime(2026, 10, 6, 1, 0, tzinfo=UTC), 3) == (D("2026-10-02"), D("2026-10-05"))
    # winter: UTC-5
    assert news_dates(datetime(2026, 1, 6, 4, 59, tzinfo=UTC), 3) == (D("2026-01-02"), D("2026-01-05"))
    assert news_dates(datetime(2026, 1, 6, 5, 0, tzinfo=UTC), 3) == (D("2026-01-03"), D("2026-01-06"))
    with pytest.raises(ValueError):
        news_dates(datetime(2026, 10, 5, 23, 0), 3)
    with pytest.raises(ValueError):
        news_dates(datetime(2026, 10, 5, 23, 0, tzinfo=UTC), 0)


def test_earnings_window_counts_sessions_from_the_entry_session():
    assert earnings_window(D("2026-10-06"), 5) == (D("2026-10-06"), D("2026-10-12"))
    assert earnings_window(D("2026-10-06"), 1) == (D("2026-10-06"), D("2026-10-06"))
    # Thanksgiving 2026-11-26 is skipped
    assert earnings_window(D("2026-11-23"), 5) == (D("2026-11-23"), D("2026-11-30"))
    with pytest.raises(ValueError):
        earnings_window(D("2026-10-10"), 5)  # a Saturday
    with pytest.raises(ValueError):
        earnings_window(D("2026-10-06"), 0)
    with pytest.raises(TypeError):
        earnings_window(datetime(2026, 10, 6), 5)


# --------------------------------------------------------------------------- headlines


def _h(i: int, when: datetime, headline: str = "", summary: str = "", source: str = "Reuters") -> Headline:
    return Headline(i, when, source, headline or f"Headline {i}", summary)


CUTOFF = datetime(2026, 10, 5, 23, 0, 7, tzinfo=UTC)


def test_headline_validates_and_normalizes_to_utc():
    est = timezone(timedelta(hours=-4))
    h = Headline(1, datetime(2026, 10, 5, 9, 30, tzinfo=est), "CNBC", "x", "")
    assert h.published == datetime(2026, 10, 5, 13, 30, tzinfo=UTC)
    assert h.published.tzinfo is UTC
    with pytest.raises(ValueError):
        Headline(1, datetime(2026, 10, 5, 9, 30), "CNBC", "x", "")
    with pytest.raises(TypeError):
        Headline(True, CUTOFF, "CNBC", "x", "")
    with pytest.raises(TypeError):
        Headline(1, CUTOFF, None, "x", "")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Headline(1, CUTOFF, "CNBC", "   ", "")


def test_select_headlines_drops_items_at_or_after_the_cutoff_newest_first():
    items = [
        _h(1, CUTOFF - timedelta(hours=30)),
        _h(2, CUTOFF),  # at the cutoff: dropped
        _h(3, CUTOFF + timedelta(seconds=1)),  # after: dropped
        _h(4, CUTOFF - timedelta(seconds=1)),
        _h(5, CUTOFF - timedelta(hours=2)),
        _h(6, CUTOFF - timedelta(hours=2)),  # tie with 5: higher id first
    ]
    got = select_headlines(items, CUTOFF, 20)
    assert [h.id for h in got] == [4, 6, 5, 1]
    assert [h.id for h in select_headlines(items, CUTOFF, 2)] == [4, 6]
    assert select_headlines(items, CUTOFF, 0) == ()
    assert select_headlines([], CUTOFF, 20) == ()
    assert select_headlines(iter(items), CUTOFF, 20) == got
    with pytest.raises(ValueError):
        select_headlines(items, CUTOFF.replace(tzinfo=None), 20)
    with pytest.raises(ValueError):
        select_headlines(items, CUTOFF, -1)
    with pytest.raises(TypeError):
        select_headlines([{"id": 1}], CUTOFF, 20)  # type: ignore[list-item]


# --------------------------------------------------------------------------- the user prompt (golden)


def test_user_prompt_golden():
    heads = (
        _h(
            7,
            datetime(2026, 10, 5, 20, 15, 59, tzinfo=UTC),
            "Acme  beats\nestimates",
            "Acme Corp reported third-quarter revenue above expectations.",
            "Reuters",
        ),
        _h(3, datetime(2026, 10, 3, 9, 1, tzinfo=UTC), "Acme names new CFO", "", "MarketWatch"),
    )
    got = user_prompt(
        "ACME", D("2026-10-06"), D("2026-10-12"), D("2026-10-08"), CUTOFF, heads, STRATEGY_C_PARAMS
    )
    assert got == (
        "Symbol: ACME\n"
        "Entry: the open of 2026-10-06\n"
        "Holding window: 2026-10-06 to 2026-10-12 (5 sessions)\n"
        "Scheduled earnings inside the window: 2026-10-08\n"
        "Headlines published before 2026-10-05 23:00 UTC, newest first (2 shown, at most 20):\n"
        "1. 2026-10-05 20:15Z | Reuters | Acme beats estimates | "
        "Acme Corp reported third-quarter revenue above expectations.\n"
        "2. 2026-10-03 09:01Z | MarketWatch | Acme names new CFO |"
    )


def test_user_prompt_with_no_headlines_and_no_earnings():
    got = user_prompt("BRK.B", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (), STRATEGY_C_PARAMS)
    assert got == (
        "Symbol: BRK.B\n"
        "Entry: the open of 2026-10-06\n"
        "Holding window: 2026-10-06 to 2026-10-12 (5 sessions)\n"
        "Scheduled earnings inside the window: none found\n"
        "Headlines published before 2026-10-05 23:00 UTC, newest first (0 shown, at most 20):\n"
        "No headlines."
    )


def test_user_prompt_cuts_summaries_at_a_word_boundary():
    words = " ".join(["alpha"] * 100)  # 599 chars
    p = CParams(max_summary_chars=20)
    got = user_prompt("X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (_h(1, CUTOFF - timedelta(1), "H", words),), p)
    assert got.splitlines()[-1] == "1. 2026-10-04 23:00Z | Reuters | H | alpha alpha alpha"
    exact = "abcde fghij"
    got = user_prompt(
        "X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (_h(1, CUTOFF - timedelta(1), "H", exact),), CParams(max_summary_chars=11)
    )
    assert got.splitlines()[-1].endswith("| H | abcde fghij")
    one_word = "x" * 40
    got = user_prompt(
        "X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (_h(1, CUTOFF - timedelta(1), "H", one_word),), p
    )
    assert got.splitlines()[-1].endswith("| H | " + "x" * 20)
    long = STRATEGY_C_PARAMS.max_summary_chars
    got = user_prompt(
        "X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (_h(1, CUTOFF - timedelta(1), "H", words),), STRATEGY_C_PARAMS
    )
    assert len(got.splitlines()[-1].split(" | ")[-1]) <= long


def test_user_prompt_validates():
    args = ("X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (), STRATEGY_C_PARAMS)
    user_prompt(*args)
    with pytest.raises(ValueError):
        user_prompt("", *args[1:])
    with pytest.raises(ValueError):
        user_prompt("X", D("2026-10-12"), D("2026-10-06"), None, CUTOFF, (), STRATEGY_C_PARAMS)
    with pytest.raises(ValueError):
        user_prompt("X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF.replace(tzinfo=None), (), STRATEGY_C_PARAMS)
    too_many = tuple(_h(i, CUTOFF - timedelta(minutes=i)) for i in range(1, 22))
    with pytest.raises(ValueError):
        user_prompt("X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, too_many, STRATEGY_C_PARAMS)
    with pytest.raises(TypeError):
        user_prompt("X", D("2026-10-06"), D("2026-10-12"), None, CUTOFF, (), STRATEGY_A_PARAMS)


# --------------------------------------------------------------------------- the verdict parser


@pytest.mark.parametrize(
    "text, expected",
    [
        ('{"verdict": "allow", "reason": "Only routine product news."}', ("allow", "Only routine product news.")),
        ('{"verdict": "veto", "reason": "Earnings on 2026-10-08."}', ("veto", "Earnings on 2026-10-08.")),
        ('  \n{"verdict": " VETO ", "reason": "  Lawsuit\n filed   today. "}\n ', ("veto", "Lawsuit filed today.")),
        ('```json\n{"verdict": "Allow", "reason": "No news."}\n```', ("allow", "No news.")),
        ('Here you go: {"verdict": "allow", "reason": "No news."} Thanks!', ("allow", "No news.")),
        ('{"reason": "Has {braces} inside.", "verdict": "allow"}', ("allow", "Has {braces} inside.")),
        ('{"verdict": "allow", "reason": "a"} {"verdict": "veto", "reason": "b"}', ("allow", "a")),
        ('{"verdict": "allow", "reason": "ok", "extra": 1}', ("allow", "ok")),
    ],
)
def test_parse_verdict_accepts(text, expected):
    assert parse_verdict(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "allow",
        "I think you should veto this one.",
        '{"verdict": "allow"}',
        '{"verdict": "allow", "reason": ""}',
        '{"verdict": "allow", "reason": "   "}',
        '{"verdict": "maybe", "reason": "Unsure."}',
        '{"verdict": "failed", "reason": "x"}',
        '{"verdict": true, "reason": "x"}',
        '{"verdict": "allow", "reason": 5}',
        '{"verdict": "allow", "reason": "x"',
        "[1, 2]",
        "{not json}",
    ],
)
def test_parse_verdict_rejects(text):
    verdict, reason = parse_verdict(text)
    assert verdict == "failed"
    assert reason.startswith("unparsable reply: ")
    assert len(reason) <= len("unparsable reply: ") + 120


def test_parse_verdict_failure_reason_quotes_the_first_120_chars_on_one_line():
    text = "nope\n" + "z" * 300
    assert parse_verdict(text) == ("failed", "unparsable reply: " + ("nope " + "z" * 300)[:120])
    assert parse_verdict("") == ("failed", "unparsable reply: empty")
    assert parse_verdict(None) == ("failed", "unparsable reply: empty")  # type: ignore[arg-type]


def test_parse_verdict_caps_the_reason_at_300_chars():
    reason = "word " * 100
    verdict, got = parse_verdict(json.dumps({"verdict": "veto", "reason": reason}))
    assert verdict == "veto"
    assert len(got) <= 300
    assert got == reason.strip()[:300].rstrip()


# --------------------------------------------------------------------------- allowed_map


def test_allowed_map():
    s1, s2, s3 = D("2026-10-06"), D("2026-10-07"), D("2026-10-08")
    rows = [
        (s2, "BBB", "allow"),
        (s1, "AAA", "allow"),
        (s1, "CCC", "veto"),
        (s1, "DDD", "failed"),
        (s1, "EEE", "allow"),
        (s3, "AAA", "veto"),
    ]
    assert allowed_map(rows) == {s1: frozenset({"AAA", "EEE"}), s2: frozenset({"BBB"}), s3: frozenset()}
    assert allowed_map([]) == {}
    with pytest.raises(ValueError):
        allowed_map([(s1, "AAA", "maybe")])
    with pytest.raises(ValueError):
        allowed_map([(s1, "AAA", "allow"), (s1, "AAA", "veto")])
    with pytest.raises(TypeError):
        allowed_map([(datetime(2026, 10, 6), "AAA", "allow")])
```
**Impact:** adds 60 test cases (62 with the two purity tests that now include `c.py`); about 3 s.

Exit-criteria map (plan index, phase 1):

| Criterion | Test |
|---|---|
| all allowed: `NewsVeto.picks == candidates == STRATEGY_A.picks[:10]` | `test_candidates_are_a_first_ten_and_all_allowed_c_equals_them` |
| vetoed/failed/missing removed, order kept | `test_vetoed_failed_and_missing_symbols_are_dropped_in_rank_order` |
| ranks > 10 never returned | `test_candidates_are_a_first_ten_and_all_allowed_c_equals_them` |
| `picks_prepared(prepare(H)) == picks(H cut)` | `test_picks_prepared_equals_picks_on_the_cut_history` |
| `run_rules(DESIGN_V0)` all-allow C == A when A never needs rank > 10 | `test_run_rules_all_allowed_c_equals_a_when_a_never_needs_rank_eleven` |
| `select_headlines` drops items at/after the cutoff | `test_select_headlines_drops_items_at_or_after_the_cutoff_newest_first` |
| `parse_verdict` table of cases | `test_parse_verdict_accepts`, `test_parse_verdict_rejects`, `..._failure_reason_...`, `..._caps_the_reason_...` |
| `user_prompt` golden text | `test_user_prompt_golden`, `test_user_prompt_with_no_headlines_and_no_earnings` |
| purity green | `tests/test_strategy_purity.py` (unchanged) |
| verdicts keyed by the session bought (Decisions: "Verdict map key") | `test_verdicts_are_keyed_by_the_session_bought_for` |

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.strategies.c as c; print(c.STRATEGY_C.id, len(c.STRATEGY_C_PARAMS.as_dict()))"` → `C-news-veto 19`
**Tests:**
```
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_strategy_c.py engine/tests/test_strategy_purity.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
engine/.venv/bin/ruff check engine
```
Verified by the planner on a scratch copy of the worktree with the worktree's own venv: the two
files give `62 passed` for the focused run; the full engine suite `2031 passed`, 0 skipped
(5 min 46 s); `ruff check` clean. Web is untouched (vitest/tsc unaffected).
**Manual check:** none.
**Exit criteria:** `strategies/c.py` matches K1; `test_strategy_c.py` and `test_strategy_purity.py`
pass; the full engine suite passes with 0 skipped; ruff clean; no other file changed.

## Handoffs

- **Phase 2 (R1):** roster entry `C` (`obj=STRATEGY_C`, `object_name="STRATEGY_C"`,
  `params=STRATEGY_C_PARAMS`, `lookback=STRATEGY_C.lookback`), its `PINS` digest, `gate_applicable`,
  and `store.allowed_between` built on `c.allowed_map`. Phase 1 deliberately pins no digest: the
  digest is a roster concern (`spec(e)` adds id/engine/rules/initial_idr around `as_dict()`).
- **Phase 3 (R2):** constructing `Headline` from Finnhub JSON (unix seconds → tz-aware UTC, dropping
  items with a non-int `id`/`datetime` or a blank headline before construction). No `from_unix`
  helper was added to `c.py` (outside K1).
- **Phase 4 (R2):** the lean stored-headline dict (`{"id", "datetime": "YYYY-MM-DDTHH:MM:SSZ",
  "source", "headline"}`) is not a K1 symbol; build it in `veto.py` (or `store.py`) from `Headline`.
- **Not done (no phase asked):** re-exporting C from `strategies/__init__.py`. The plan index says
  none is required; consumers import `seer_engine.strategies.c`.

## Rollback

Delete `engine/src/seer_engine/strategies/c.py` and `engine/tests/test_strategy_c.py` (or revert the
phase commit). Nothing else references them until phase 2 lands; after phase 2+, this phase cannot be
rolled back alone.
