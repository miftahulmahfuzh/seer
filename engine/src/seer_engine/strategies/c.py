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
