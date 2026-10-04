"""veto: Strategy C's nightly news check, run after ``nightly`` and before ``paper`` (handover D6).

``python -m seer_engine [--dry-run] [-v] veto [--now ISO8601]``

Flow (plan contract K6):
  1. purge demo data if a demo run exists (own transaction; rolled back under --dry-run)
  2. ``started_at`` = now (UTC): the news cutoff and every row's ``decided_at``.
     rd = run_dates(started_at); the session checked is rd.session_date
  3. the real runs row for that session must be ``success`` (as in ``paper``); otherwise log
     and exit 1 with nothing written and no network call
  3b. ``paper`` has already decided that session (``runs.paper_status = 'success'``): log "too
     late", exit 0, nothing written, no network call. A verdict written after Paper decided would
     make paper_check replay a trade Paper never placed (reproducible replay, handover §2)
  4. verdicts already stored for (C, session): log "already checked", exit 0, no network call
  5. A's ranked candidates for the session, capped at C's ``max_candidates``: the windowed bars
     cut at rd.data_date (exactly what ``decide_bracket`` hands the strategy), point-in-time
     members on rd.data_date. Read and rolled back before any network call. No candidates:
     exit 0, nothing written
  6. one verdict per candidate, in rank order. ``failed`` (no trade, design §8) when
     FINNHUB_API_KEY is unset, LLM_* is unset, LLM_MODEL is not C's frozen model, a Finnhub or
     LLM call fails, the reply is unparsable, or MAX_CONSECUTIVE_FAILURES network failures in a
     row stopped the night's calls. Otherwise the LLM's ``allow`` or ``veto``
  7. ONE transaction: re-check steps 3b and 4 (Paper may have decided, or another run may have
     won, while the checks ran), write every verdict. --dry-run rolls it back

Exit 0 whenever verdicts were written or nothing was needed; 1 only for step 3 or a database
error. No secret reaches a log line or a stored reason: every error text passes through
``llm.scrub`` with both keys. News items dated at or after ``started_at`` are never sent to the
LLM nor stored (``strategies.c.select_headlines``).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Sequence
from datetime import date, datetime, timezone
from typing import Any, Protocol

import psycopg

from seer_engine import dates, db, demo, runs
from seer_engine import finnhub as finnhub_api
from seer_engine import llm as llm_api
from seer_engine.commands.nightly import _parse_now
from seer_engine.paper import roster, store
from seer_engine.paper.store import NewsVerdict
from seer_engine.sim.sizing import Pick
from seer_engine.strategies import c

log = logging.getLogger(__name__)

HELP = "Strategy C's news check: ask the LLM about A's candidates for the next session (never fails the night)"

STRATEGY_ID = "C"
MAX_CONSECUTIVE_FAILURES = 3
MAX_REASON_LEN = 300
LLM_TIMEOUT_S = 30.0
LLM_RETRIES = 1


class NewsSource(Protocol):
    """What ``veto`` needs from Finnhub (``finnhub.Client``)."""

    def company_news(self, symbol: str, start: date, end: date) -> list[c.Headline]: ...

    def earnings(self, symbol: str, start: date, end: date) -> date | None: ...


class Completer(Protocol):
    """What ``veto`` needs from the LLM (``llm.Client``)."""

    def complete(
        self,
        system: str,
        prompt: str,
        *,
        temperature: float | None = None,
        thinking: str | None = None,
        max_tokens: int | None = None,
    ) -> str: ...


NewsFactory = Callable[[str], NewsSource]
LlmFactory = Callable[[llm_api.LlmConfig], Completer]


def default_finnhub(key: str) -> NewsSource:
    """The real Finnhub client (rate-limited, key in a header only)."""
    return finnhub_api.Client(key)


def default_llm(cfg: llm_api.LlmConfig) -> Completer:
    """The real LLM client with C's call budget: 30 s timeout, one retry."""
    return llm_api.Client(cfg, timeout=LLM_TIMEOUT_S, retries=LLM_RETRIES)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--now",
        type=_parse_now,
        default=None,
        metavar="ISO8601",
        help="pretend the current time is this (UTC if no offset); for tests and replays",
    )


def run(args: argparse.Namespace) -> int:
    now = getattr(args, "now", None) or datetime.now(timezone.utc)
    conn = db.connect()
    try:
        return execute(conn, now=now, dry_run=bool(args.dry_run))
    finally:
        conn.close()


# ---- pure helpers ------------------------------------------------------------------------------


def scrub(text: str, secrets: Sequence[str | None]) -> str:
    """``text`` with key/token query parameters and every secret redacted, whitespace collapsed,
    cut to MAX_REASON_LEN characters."""
    out = llm_api.scrub(str(text), None)
    for secret in secrets:
        out = llm_api.scrub(out, secret)
    return " ".join(out.split())[:MAX_REASON_LEN]


def config_failure(key: str | None, cfg: llm_api.LlmConfig | None, params: c.CParams) -> str | None:
    """Why no candidate can be checked tonight, or None when Finnhub and the LLM are configured
    and the configured model is C's frozen one (handover D5, D12)."""
    reasons: list[str] = []
    if key is None:
        reasons.append("FINNHUB_API_KEY is not set")
    if cfg is None:
        reasons.append("LLM_BASE_URL, LLM_API_KEY and LLM_MODEL are not all set")
    elif cfg.model != params.model:
        reasons.append(f"LLM_MODEL {cfg.model} is not C's frozen model {params.model}")
    return "; ".join(reasons) if reasons else None


def lean(h: c.Headline) -> dict[str, Any]:
    """The stored form of a headline the LLM saw (handover D7: no summary)."""
    return {
        "id": h.id,
        "datetime": h.published.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": h.source,
        "headline": h.headline,
    }


def _verdict(
    rank: int,
    symbol: str,
    verdict: str,
    reason: str,
    *,
    model: str | None,
    params: c.CParams,
    started_at: datetime,
    headlines: Sequence[c.Headline] = (),
    earnings: date | None = None,
) -> NewsVerdict:
    return NewsVerdict(
        rank=rank,
        symbol=symbol,
        verdict=verdict,
        reason=reason,
        model=model,
        prompt_version=params.prompt_version,
        headlines=tuple(lean(h) for h in headlines),
        earnings_date=earnings,
        decided_at=started_at,
    )


def check_candidate(
    rank: int,
    symbol: str,
    *,
    session: date,
    started_at: datetime,
    params: c.CParams,
    news: NewsSource,
    ask: Completer,
    model: str | None,
    secrets: Sequence[str | None],
) -> tuple[NewsVerdict, bool]:
    """One candidate's verdict, and whether a network call failed (for the consecutive stop).

    News from ``news_dates(started_at)`` filtered to items strictly before ``started_at``; the
    earnings calendar over the holding window; one LLM call; ``parse_verdict``. Any exception is
    a ``failed`` verdict whose reason is scrubbed of both keys.
    """
    window_start, window_end = c.earnings_window(session, params.earnings_sessions)
    headlines: tuple[c.Headline, ...] = ()
    earnings: date | None = None
    stage = "Finnhub company-news"
    try:
        items = news.company_news(symbol, *c.news_dates(started_at, params.news_days))
        headlines = c.select_headlines(items, started_at, params.max_headlines)
        stage = "Finnhub earnings calendar"
        earnings = news.earnings(symbol, window_start, window_end)
        stage = "LLM"
        prompt = c.user_prompt(symbol, session, window_end, earnings, started_at, headlines, params)
        reply = ask.complete(
            c.SYSTEM_PROMPT,
            prompt,
            temperature=float(params.temperature),
            thinking=params.thinking,
            max_tokens=params.max_tokens,
        )
    except Exception as exc:  # noqa: BLE001 - a failed check is no trade, never a failed night
        reason = scrub(f"{stage} failed: {type(exc).__name__}: {exc}", secrets)
        failed = _verdict(
            rank, symbol, "failed", reason,
            model=model, params=params, started_at=started_at, headlines=headlines, earnings=earnings,
        )
        return failed, True
    verdict, reason = c.parse_verdict(reply)
    checked = _verdict(
        rank, symbol, verdict, scrub(reason, secrets),
        model=model, params=params, started_at=started_at, headlines=headlines, earnings=earnings,
    )
    return checked, False


def check_all(
    cands: Sequence[Pick],
    *,
    session: date,
    started_at: datetime,
    params: c.CParams,
    news: NewsSource,
    ask: Completer,
    model: str | None,
    secrets: Sequence[str | None],
) -> list[NewsVerdict]:
    """Every candidate's verdict in rank order (rank 1 = A's best). After
    MAX_CONSECUTIVE_FAILURES network failures in a row the rest are ``failed`` without a call."""
    out: list[NewsVerdict] = []
    in_row = 0
    for rank, pick in enumerate(cands, start=1):
        if in_row >= MAX_CONSECUTIVE_FAILURES:
            out.append(
                _verdict(
                    rank, pick.symbol, "failed",
                    f"skipped after {MAX_CONSECUTIVE_FAILURES} consecutive failures",
                    model=model, params=params, started_at=started_at,
                )
            )
            continue
        verdict, network_failed = check_candidate(
            rank, pick.symbol,
            session=session, started_at=started_at, params=params,
            news=news, ask=ask, model=model, secrets=secrets,
        )
        in_row = in_row + 1 if network_failed else 0
        if in_row == MAX_CONSECUTIVE_FAILURES:
            log.warning("veto: %d failures in a row; no more calls tonight, the rest are failed", in_row)
        out.append(verdict)
    return out


def _all_failed(
    cands: Sequence[Pick], reason: str, *, model: str | None, params: c.CParams, started_at: datetime
) -> list[NewsVerdict]:
    return [
        _verdict(rank, pick.symbol, "failed", reason, model=model, params=params, started_at=started_at)
        for rank, pick in enumerate(cands, start=1)
    ]


# ---- the command -------------------------------------------------------------------------------


def _paper_decided(conn: psycopg.Connection, session: date) -> bool:
    """True when ``paper`` has already decided ``session`` (its real runs row has
    ``paper_status = 'success'``): a verdict written now would never have been traded, and
    paper_check would replay a trade Paper never placed (reconciliation H1)."""
    found = runs.real_run(conn, session)
    return found is not None and found.paper_status == "success"


def execute(
    conn: psycopg.Connection,
    *,
    now: datetime,
    dry_run: bool = False,
    finnhub: NewsFactory = default_finnhub,
    llm: LlmFactory = default_llm,
) -> int:
    """Check C's candidates for the next session against ``conn``. Returns the exit code.

    ``finnhub`` builds the news source from FINNHUB_API_KEY and ``llm`` the completer from the
    LLM config; neither is called when nothing needs checking or the configuration is incomplete.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    started_at = now.astimezone(timezone.utc)
    demo.purge_demo_if_needed(conn, dry_run)

    rd = dates.run_dates(started_at)
    session = rd.session_date
    log.info("veto: started %s -> data_date %s, session_date %s", started_at.isoformat(), rd.data_date, session)

    try:
        try:
            bars_run = runs.real_run(conn, session)
            done = store.has_vetoes(conn, STRATEGY_ID, session)
        finally:
            conn.rollback()
    except psycopg.Error as exc:
        log.error("veto: database error reading session %s: %s", session, scrub(str(exc), ()))
        return 1
    if bars_run is None or bars_run.status != "success":
        found = "missing" if bars_run is None else bars_run.status
        log.error("the bars run for session %s is %s; no news check after a failed or missing bars run", session, found)
        return 1
    if bars_run.paper_status == "success":
        log.info("veto: paper already decided %s; too late for a news check, nothing written", session)
        return 0
    if done:
        log.info("veto: %s already checked for %s; nothing to do", STRATEGY_ID, session)
        return 0

    params: c.CParams = roster.entry(STRATEGY_ID).params
    try:
        try:
            market = store.load_market_window(conn, store.market_window_since(rd.data_date))
        finally:
            conn.rollback()
    except Exception as exc:  # noqa: BLE001 - a database or data error is exit 1, logged
        log.error("veto: could not load the bars window for %s: %s", rd.data_date, scrub(f"{type(exc).__name__}: {exc}", ()))
        return 1
    history = {symbol: h.upto(rd.data_date) for symbol, h in market.history.items()}
    cands = c.candidates(history, market.membership.members_on(rd.data_date), rd.data_date, params)
    if not cands:
        log.info("veto: A has no candidates for %s; nothing to check", session)
        return 0
    log.info("veto: %d candidate(s) for %s: %s", len(cands), session, ", ".join(p.symbol for p in cands))

    key = finnhub_api.load_key()
    cfg = llm_api.load_config()
    secrets = (key, None if cfg is None else cfg.api_key)
    model = None if cfg is None else cfg.model
    blocked = config_failure(key, cfg, params)
    if blocked is not None or key is None or cfg is None:
        reason = scrub(blocked or "news check not configured", secrets)
        log.warning("veto: no news check tonight: %s; every candidate is failed (no trade)", reason)
        verdicts = _all_failed(cands, reason, model=model, params=params, started_at=started_at)
    else:
        try:
            news = finnhub(key)
            ask = llm(cfg)
        except Exception as exc:  # noqa: BLE001 - a client that cannot be built is no trade
            reason = scrub(f"client setup failed: {type(exc).__name__}: {exc}", secrets)
            log.warning("veto: %s; every candidate is failed (no trade)", reason)
            verdicts = _all_failed(cands, reason, model=model, params=params, started_at=started_at)
        else:
            verdicts = check_all(
                cands,
                session=session, started_at=started_at, params=params,
                news=news, ask=ask, model=model, secrets=secrets,
            )

    for v in verdicts:
        log.info(
            "veto: %s %s #%d %s: %s (%d headline(s)%s) %s",
            STRATEGY_ID, session, v.rank, v.symbol, v.verdict, len(v.headlines),
            f", earnings {v.earnings_date}" if v.earnings_date else "", v.reason,
        )

    try:
        with db.transaction(conn, dry_run):
            if _paper_decided(conn, session):
                log.info("veto: paper decided %s while the checks ran; too late, nothing written", session)
                return 0
            if store.has_vetoes(conn, STRATEGY_ID, session):
                log.info("veto: another run checked %s first; nothing written", session)
                return 0
            written = store.write_vetoes(conn, STRATEGY_ID, session, verdicts)
    except Exception as exc:  # noqa: BLE001 - a database error is exit 1, logged without secrets
        log.error("veto: could not write the verdicts for %s: %s", session, scrub(f"{type(exc).__name__}: {exc}", secrets))
        return 1
    counts = {name: sum(1 for v in verdicts if v.verdict == name) for name in c.VERDICTS}
    log.info(
        "veto: %s %s: %d checked, %d allowed, %d vetoed, %d failed%s",
        STRATEGY_ID, session, written, counts["allow"], counts["veto"], counts["failed"],
        " (dry-run: rolled back; nothing written)" if dry_run else "",
    )
    return 0
