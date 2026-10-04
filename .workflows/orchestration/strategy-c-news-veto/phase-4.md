# Phase 4: `veto` command

**Plan set:** `STRATEGY_C_NEWS_VETO_PLAN.md`
**Analysis:** `20261004-171449-C5V8_code_analyzer.md`
**Satisfies:** R2 — the impure engine side of C: the nightly news check that turns A's candidates into stored `allow`/`veto`/`failed` verdicts
**Depends on:** Phase 2 (migration 004, roster entry `C`, store vetoes API K3), Phase 3 (`finnhub.py`, `llm.Client.complete` keywords K5). Phase 1 (K1) arrives transitively through phase 2.
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/commands`

---

## Goal

`python -m seer_engine [--dry-run] [-v] veto [--now ISO8601]` exists (auto-discovered by `cli.py`).
After a successful bars run it computes A's ranked candidates for `run_dates(now).session_date`
(capped at C's `max_candidates`), asks Finnhub and the LLM about each, and writes one
`news_vetoes` row per candidate in one transaction. Every failure (missing keys, model mismatch,
network/HTTP error, unparsable reply, consecutive-failure stop) becomes a `failed` row, never a
failed night; a re-run for a session that already has verdicts makes no network call and writes
nothing, and once `paper` has decided the session (`runs.paper_status = 'success'`) `veto` writes
nothing either (H1: a late verdict would make C's replay check permanently red).

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `engine/src/seer_engine/commands/veto.py` (new command module, K6):
  - `HELP: str`, `add_arguments(p)`, `run(args) -> int` (cli command contract)
  - `STRATEGY_ID = "C"`, `MAX_CONSECUTIVE_FAILURES = 3`, `MAX_REASON_LEN = 300`, `LLM_TIMEOUT_S = 30.0`, `LLM_RETRIES = 1`
  - `class NewsSource(Protocol)` (`company_news(symbol, start, end) -> list[c.Headline]`, `earnings(symbol, start, end) -> date | None`)
  - `class Completer(Protocol)` (`complete(system, prompt, *, temperature=None, thinking=None, max_tokens=None) -> str`)
  - `NewsFactory = Callable[[str], NewsSource]`, `LlmFactory = Callable[[llm.LlmConfig], Completer]`
  - `default_finnhub(key) -> NewsSource` (= `finnhub.Client(key)`), `default_llm(cfg) -> Completer` (= `llm.Client(cfg, timeout=30.0, retries=1)`)
  - `scrub(text, secrets) -> str`, `config_failure(key, cfg, params) -> str | None`, `lean(h) -> dict`,
    `check_candidate(...) -> tuple[NewsVerdict, bool]`, `check_all(...) -> list[NewsVerdict]`
  - `_paper_decided(conn, session) -> bool` (reconciliation H1: the real runs row for `session` has `paper_status = 'success'`)
  - `execute(conn, *, now: datetime, dry_run: bool = False, finnhub: NewsFactory = default_finnhub, llm: LlmFactory = default_llm) -> int`
- `engine/tests/test_veto_command.py` (new, 27 tests; PG integration + fakes).

**Signature changes:** none to existing code.

**Requires (from earlier phases) — used exactly as named in the index contracts:**
- Phase 1 / K1 (`seer_engine.strategies.c`): `Headline` (fields `id, published, source, headline, summary`),
  `CParams` fields `max_candidates, news_days, max_headlines, earnings_sessions, model, prompt_version,
  temperature (str "0"), thinking (str "disabled"), max_tokens (int 1024)`, `STRATEGY_C_PARAMS`, `FROZEN_MODEL`,
  `PROMPT_VERSION`, `VERDICTS`, `SYSTEM_PROMPT`, `candidates(history, members, data_date, params)`,
  `news_dates(started_at, days)`, `earnings_window(session, n)`, `select_headlines(items, cutoff, cap)`
  (positional), `user_prompt(symbol, session, window_end, earnings, cutoff, headlines, params)` (positional),
  `parse_verdict(text)`. The tests also rely on the K1 user template's first line being
  `Symbol: {symbol}` (the fake LLM reads the symbol from it).
- Phase 2 / K3 (`seer_engine.paper.store`): `NewsVerdict(rank, symbol, verdict, reason, model, prompt_version,
  headlines, earnings_date, decided_at)` (keyword construction), `has_vetoes(conn, strategy_id, session)`,
  `write_vetoes(conn, strategy_id, session, verdicts) -> int`, `read_vetoes(conn, strategy_id, session)`.
  Migration `004` (K2) creates `news_vetoes` and the `strategies` row `C` (FK target).
  `roster.entry("C").params` is `STRATEGY_C_PARAMS` (K4).
- Phase 3 / K5: `seer_engine.finnhub.load_key()`, `finnhub.Client(key)` (all other args defaulted),
  `finnhub.FinnhubError(message, status)`; `llm.Client.complete(system, prompt, *, temperature, thinking, max_tokens)`.
- Existing (unchanged): `commands.nightly._parse_now`, `runs.real_run(conn, session_date) -> RealRun | None`
  (`RealRun.status`, `RealRun.paper_status: str | None`, `'running' | 'success' | 'failed'` or NULL before `paper`
  ran; `engine/src/seer_engine/runs.py`), `dates.run_dates`, `demo.purge_demo_if_needed`,
  `store.load_market_window`, `store.market_window_since`, `llm.load_config`, `llm.scrub`, `llm.LlmConfig`,
  `llm.LlmError`, `db.transaction`, `History.upto`.
- Test-only: `tests/test_paper_command.py` keeps exporting `synthetic_bars`, `fx_rate`, `_sessions`, `STOCKS`
  (no phase edits that file; reconciliation confirmed no phase renames or removes these four).
  `commands.paper.execute(conn, *, now, dry_run=False)` and `commands.paper_check.check(conn)` (existing; used by the
  two H1 tests only, which pass with phase 2 alone and keep passing after phase 5).

**Leaves alone (owned by others):** `strategies/c.py` (Phase 1); `db/migrations/004_news_veto.sql`,
`paper/roster.py`, `paper/store.py`, `demo.py` (Phase 2); `finnhub.py`, `llm.py` (Phase 3);
`commands/paper.py`, `commands/paper_check.py`, `commands/explain.py`, `tests/test_paper_command.py`
(Phase 5); `web/**` (Phase 6); `.github/workflows/nightly.yml`, `engine/package_readme.md`,
`docs/**`, `.env.example` (Phase 7).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/veto.py` | create (line 1) | the whole `veto` command (K6) |
| `engine/tests/test_veto_command.py` | create (line 1) | PG integration tests with fake Finnhub/LLM factories |

No existing file changes. `cli.py` discovers the module by itself (`cli.discover`, `cli.py:32`).

## Design notes (decisions inside K6 this phase makes)

1. **Order of the night** follows K6 literally: purge demo → `run_dates(started_at)` → real runs row
   `success` (else exit 1) → **`paper_status` of that row is not `success`** (else exit 0, "too late",
   no client built; reconciliation H1) → `has_vetoes` (else exit 0, no client built) → market window
   read and rolled back → `c.candidates` → config checks → network → one write transaction that
   re-checks `paper_status` (H1) and `has_vetoes`. Steps 3, 3b and 4 share one read transaction
   (`veto.py` `execute`, the first `try`).
10. **Late verdicts are never written (H1, coordinator decision; rung 1: the "reproducible replay"
    invariant, handover §2).** If the 23:00 Veto wrote nothing (crash, database error, the 10-minute step
    limit) the 23:00 Paper already decided session S for C with no verdicts and committed. The 01:00 retry
    (or any manual re-run) would otherwise check S and write verdicts after the fact; `paper_check` replays
    C with `allowed_between(paper_start, next_session(last_session))`, would buy what Paper did not, and
    stay red forever. So `veto` writes nothing once `runs.real_run(conn, S).paper_status == "success"`:
    checked before any network call, and re-checked inside the write transaction (Paper may finish while
    the checks run, e.g. a manual run racing the job; the `seer-db-writer` concurrency group makes that
    rare, the re-check makes it impossible to commit). `paper_status` `running`/`failed`/NULL does not
    block: a failed Paper rolled back its decisions and its retry will read the verdicts.
2. **Candidates are computed exactly as `decide_bracket` hands them to the strategy**: the windowed
   history cut with `History.upto(rd.data_date)` (`paper/bracket.py:189`), point-in-time
   `membership.members_on(rd.data_date)`, `roster.entry("C").params`. On the newest night `paper`'s
   `night_view(market, data_date, later_factors(...))` has no later splits, so the inputs are identical.
3. **Configuration failures are decided before any client is built** and stop every network call:
   `FINNHUB_API_KEY` unset, `LLM_*` unset, configured model ≠ `params.model`. All applicable reasons
   are joined with `"; "` (D12 on day one shows both: `"FINNHUB_API_KEY is not set; LLM_BASE_URL,
   LLM_API_KEY and LLM_MODEL are not all set"`). Every candidate gets the same reason, which is what
   phase 6's "every row failed → the shared reason" state shows. `model` column = configured
   `LLM_MODEL` or NULL.
4. **Per-candidate failures** carry a stage prefix: `"Finnhub company-news failed: …"`,
   `"Finnhub earnings calendar failed: …"`, `"LLM failed: …"`, `"client setup failed: …"`;
   then `"<ExceptionType>: <message>"`, scrubbed of both keys via `llm.scrub` (which also applies
   `http.redact`), whitespace collapsed, cut to 300 chars. Headlines and an earnings date already
   fetched before the failure are still stored (they are what the check saw).
5. **Consecutive-failure stop counts network failures only** (`check_candidate` returns
   `network_failed=True` for any exception). An unparsable reply is a successful round trip: it is
   `failed` but resets the counter. After 3 in a row, the rest are `"skipped after 3 consecutive
   failures"` with no call, no headlines.
6. **LLM call options come from the frozen params**, not literals: `temperature=float(params.temperature)`
   (`"0"` → `0.0`), `thinking=params.thinking` (`"disabled"`), `max_tokens=params.max_tokens` (1024).
   So the call shape is part of C's digest. `default_llm` builds `llm.Client(cfg, timeout=30.0, retries=1)`.
7. **Exit codes**: 1 for a failed/missing bars run, a database error on the reads, a failure loading the
   bars window, or a failed write; 0 otherwise. Nothing network-related can return 1 or raise.
8. **Factories, not clients, are injected** (`finnhub=`, `llm=` keyword arguments of `execute`) so the
   idempotent re-run test can prove that no client was even constructed. The module imports are aliased
   (`finnhub_api`, `llm_api`) so the parameter names can match the index text.
9. **Look-ahead**: `started_at` is the cutoff for `select_headlines` and `decided_at`; only selected
   headlines go into the prompt and the stored `headlines`. Bars dated ≥ session never matter because the
   history is cut at `rd.data_date`.

## Implementation Steps

### Step 1: Create the `veto` command
**File:** `engine/src/seer_engine/commands/veto.py:1` (new file)
**Change:** the whole module below.
**Code:**
```python
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
```
**Impact:** adds the `veto` subcommand (`python -m seer_engine veto --help` lists it). No existing
behaviour changes; `cli.py` is untouched. Ruff (`E9`, `F`) clean. The module is impure (DB, network),
so it is not under `tests/test_strategy_purity.py`.

### Step 2: Tests
**File:** `engine/tests/test_veto_command.py:1` (new file)
**Change:** the whole module below. It reuses `test_paper_command`'s synthetic world helpers
(`synthetic_bars`, `fx_rate`, `_sessions`, `STOCKS`) by module import, the way
`test_backtest_walkforward.py` imports `test_backtest_runner`; the `world` fixture is re-declared here
(importing a fixture would trip pyflakes F811). The night is 2026-08-06 (Thu), on which A ranks five
candidates for 2026-08-07 (`XOM, HD, PEP, BAC, TSLA` with today's `synthetic_bars`; the test computes
them independently, without the database, and pins only the count, 5). Coverage map:

| Requirement (phase scope / acceptance) | Test |
|---|---|
| happy path, rank order, call shape, stored columns, no trades | `test_checks_every_candidate_in_rank_order` |
| news at/after `started_at` never in prompt nor stored | `test_news_at_or_after_the_start_is_never_sent_nor_stored` |
| bars dated ≥ session never change candidates | `test_bars_dated_on_or_after_the_session_never_change_candidates` |
| idempotent re-run: zero client calls, zero writes | `test_rerun_makes_no_call_and_writes_nothing` |
| failed/missing bars run → exit 1 | `test_failed_or_missing_bars_run_exits_1_and_writes_nothing` |
| `--dry-run` writes nothing | `test_dry_run_writes_nothing` |
| zero candidates | `test_no_candidates_writes_nothing_and_calls_nothing` |
| no LLM config | `test_no_llm_config_fails_every_candidate_without_a_call` |
| no Finnhub key | `test_no_finnhub_key_fails_every_candidate_without_a_call`, `test_nothing_configured_names_both_reasons` |
| frozen-model mismatch | `test_frozen_model_mismatch_fails_every_candidate_without_a_call` |
| LLM timeout/HTTP error | `test_llm_error_fails_only_that_candidate` |
| Finnhub error (news and calendar) | `test_finnhub_errors_fail_only_that_candidate_without_an_llm_call` |
| unparsable reply | `test_unparsable_replies_fail_but_never_stop_the_night` |
| consecutive-failure stop | `test_three_network_failures_in_a_row_stop_the_night`, `test_a_success_resets_the_failure_count` |
| client construction failure | `test_a_client_that_cannot_be_built_fails_every_candidate` |
| no secret in rows or logs (caplog) | `test_no_secret_in_rows_or_logs`, `test_database_error_on_write_exits_1`, `test_scrub_redacts_both_keys_and_caps_length` |
| race: another run wrote first | `test_another_run_winning_the_race_writes_nothing` |
| H1: Paper already decided the session (late-verdict retry) → no rows, no call, C's replay stays ok | `test_paper_already_decided_the_session_writes_nothing` |
| H1: Paper decided while the checks ran → the write transaction's re-check writes nothing | `test_paper_deciding_during_the_checks_writes_nothing` |
| database error → exit 1 | `test_database_error_on_write_exits_1` |
| CLI discovery and `--now` | `test_veto_is_a_command` |

("Missing verdict row" from acceptance 3 is a `paper` behaviour: phase 5.)

**Code:**
```python
"""`veto`: Strategy C's news check on Postgres with synthetic bars and fake Finnhub/LLM clients.

The world is `test_paper_command`'s synthetic market (bars through 2026-10-09, so a look-ahead on
bars would be visible). On the night of 2026-08-06 A ranks five candidates for 2026-08-07, so
every failure path, the consecutive-failure stop and the rank order are exercised. The clients
are fakes handed to `veto.execute` through its factories; nothing touches the network.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import psycopg
import pytest
from psycopg.rows import tuple_row

import test_paper_command as tp
from seer_engine import bars, cli, dates, db, fx, llm, runs
from seer_engine.commands import paper, paper_check, veto
from seer_engine.finnhub import FinnhubError
from seer_engine.paper import store
from seer_engine.strategies import c
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.base import history_from_bars

UTC = timezone.utc
NIGHT = date(2026, 8, 6)  # a Thursday; A ranks five candidates on the synthetic market
NOW = datetime(2026, 8, 6, 23, tzinfo=UTC)
SESSION = date(2026, 8, 7)
NEWS_FROM, NEWS_TO = date(2026, 8, 3), date(2026, 8, 6)  # ET run date - 3 days .. ET run date
WINDOW_END = date(2026, 8, 13)  # the 5th session counting 2026-08-07 as 1

FH_KEY = "fh-sekret-0123456789"
LLM_KEY = "llm-sekret-9876543210"
LLM_ENV = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")

ALLOW = '{"verdict": "allow", "reason": "Only routine product news."}'
VETO = '```json\n{"verdict": "veto", "reason": "Earnings are due inside the window."}\n```'


# ---- the synthetic world -----------------------------------------------------------------------


@pytest.fixture
def world(pg):
    """`test_paper_command`'s bars, FX and universe (no dividends: `veto` never reads them)."""
    with db.transaction(pg, False):
        bars.upsert_bars(pg, tp.synthetic_bars())
        fx.upsert_fx(pg, [(d, tp.fx_rate(d)) for d in tp._sessions()])
        for s in tp.STOCKS:
            pg.execute(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, 'SP500', '2020-01-02', NULL, %s)",
                (s, s),
            )
    return pg


@lru_cache(maxsize=1)
def expected_symbols() -> tuple[str, ...]:
    """A's ranked picks for SESSION, computed without the database (full history cut at NIGHT)."""
    by_symbol = defaultdict(list)
    for b in tp.synthetic_bars():
        by_symbol[b.symbol].append(b)
    history = {s: history_from_bars(s, bs).upto(NIGHT) for s, bs in by_symbol.items()}
    picks = STRATEGY_A.picks(history, frozenset(tp.STOCKS), NIGHT, STRATEGY_A_PARAMS)
    return tuple(p.symbol for p in picks)[: c.STRATEGY_C_PARAMS.max_candidates]


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    """Every test starts with no Finnhub key and no LLM config (the developer's shell may have them)."""
    for name in ("FINNHUB_API_KEY", *LLM_ENV):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", FH_KEY)
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.invalid/api/anthropic")
    monkeypatch.setenv("LLM_API_KEY", LLM_KEY)
    monkeypatch.setenv("LLM_MODEL", c.FROZEN_MODEL)


# ---- fakes -------------------------------------------------------------------------------------


def headline(i: int, published: datetime, text: str) -> c.Headline:
    return c.Headline(id=i, published=published, source="Wire", headline=text, summary=f"Summary of {text}.")


class FakeNews:
    """Finnhub stand-in: per-symbol headlines and earnings dates, per-symbol failures."""

    def __init__(self, *, news=None, earnings=None, fail_news=(), fail_earnings=()):
        self.news = dict(news or {})
        self.earnings_dates = dict(earnings or {})
        self.fail_news = set(fail_news)
        self.fail_earnings = set(fail_earnings)
        self.calls: list[tuple[str, str, date, date]] = []

    def company_news(self, symbol, start, end):
        self.calls.append(("news", symbol, start, end))
        if symbol in self.fail_news:
            raise FinnhubError(f"HTTP 500 from https://finnhub.io/api/v1/company-news?token={FH_KEY} ({FH_KEY})", 500)
        return list(self.news.get(symbol, ()))

    def earnings(self, symbol, start, end):
        self.calls.append(("earnings", symbol, start, end))
        if symbol in self.fail_earnings:
            raise FinnhubError(f"HTTP 429 from Finnhub, key {FH_KEY}", 429)
        return self.earnings_dates.get(symbol)


class FakeLlm:
    """LLM stand-in: a reply per symbol (read from the prompt's first line), per-symbol failures."""

    def __init__(self, *, replies=None, default=ALLOW, fail=(), fail_all=False):
        self.replies = dict(replies or {})
        self.default = default
        self.fail = set(fail)
        self.fail_all = fail_all
        self.calls: list[dict] = []

    def complete(self, system, prompt, *, temperature=None, thinking=None, max_tokens=None):
        symbol = prompt.splitlines()[0].removeprefix("Symbol: ").strip()
        self.calls.append(
            {
                "symbol": symbol,
                "system": system,
                "prompt": prompt,
                "temperature": temperature,
                "thinking": thinking,
                "max_tokens": max_tokens,
            }
        )
        if self.fail_all or symbol in self.fail:
            raise llm.LlmError(f"ReadTimeout: read timed out (x-api-key {LLM_KEY})", None)
        return self.replies.get(symbol, self.default)


class Harness:
    """The factories `veto.execute` takes, recording what they were built with."""

    def __init__(self, news: FakeNews | None = None, ask: FakeLlm | None = None):
        self.news = news if news is not None else FakeNews()
        self.ask = ask if ask is not None else FakeLlm()
        self.keys: list[str] = []
        self.cfgs: list[llm.LlmConfig] = []

    def finnhub(self, key):
        self.keys.append(key)
        return self.news

    def llm(self, cfg):
        self.cfgs.append(cfg)
        return self.ask

    def run(self, conn, *, now: datetime = NOW, dry_run: bool = False) -> int:
        return veto.execute(conn, now=now, dry_run=dry_run, finnhub=self.finnhub, llm=self.llm)

    def network(self) -> int:
        """Client constructions plus calls: zero means nothing reached for the network."""
        return len(self.keys) + len(self.cfgs) + len(self.news.calls) + len(self.ask.calls)


# ---- helpers -----------------------------------------------------------------------------------


def q(conn, sql, params=()):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(sql, params)
        out = cur.fetchall()
    conn.rollback()
    return out


def bars_run(conn, status: str = "success") -> None:
    """The real runs row `nightly` writes for NIGHT (session SESSION)."""
    with db.transaction(conn, False):
        conn.execute(
            """
            INSERT INTO runs (status, data_date, session_date, is_demo, finished_at)
            VALUES (%s, %s, %s, false, now())
            ON CONFLICT (session_date) WHERE NOT is_demo DO NOTHING
            """,
            (status, NIGHT, SESSION),
        )


def rows(conn):
    return q(
        conn,
        "SELECT rank, symbol, verdict, reason, model, prompt_version, headlines, earnings_date, decided_at "
        "FROM news_vetoes WHERE strategy_id = 'C' AND session_date = %s ORDER BY rank",
        (SESSION,),
    )


def verdicts(conn):
    return [(r[1], r[2]) for r in rows(conn)]


def reasons(conn):
    return [r[3] for r in rows(conn)]


EVERYTHING = ("news_vetoes", "runs", "strategies", "paper_state", "orders", "equity_snapshots")


def everything(conn):
    return {t: q(conn, f"SELECT x::text FROM {t} x ORDER BY 1") for t in EVERYTHING}


def lean(h: c.Headline) -> dict:
    return {
        "id": h.id,
        "datetime": h.published.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": h.source,
        "headline": h.headline,
    }


# ---- the command -------------------------------------------------------------------------------


def test_veto_is_a_command():
    assert "veto" in cli.discover()
    args = cli.build_parser().parse_args(["--dry-run", "veto", "--now", "2026-08-06T23:00:00Z"])
    assert args.now == NOW and args.dry_run is True


def test_session_has_five_candidates():
    """The world this file relies on: SESSION has more candidates than the consecutive stop."""
    assert len(expected_symbols()) == 5


def test_checks_every_candidate_in_rank_order(world, configured):
    syms = expected_symbols()
    first = syms[0]
    news = {first: [headline(2, NOW - timedelta(hours=2), "Newer"), headline(1, NOW - timedelta(days=1), "Older")]}
    h = Harness(FakeNews(news=news, earnings={first: date(2026, 8, 11)}), FakeLlm(replies={syms[1]: VETO}))
    bars_run(world)

    assert h.run(world) == 0

    got = rows(world)
    assert [r[0] for r in got] == list(range(1, len(syms) + 1))
    assert [r[1] for r in got] == list(syms)
    assert [r[2] for r in got] == ["allow", "veto", *["allow"] * (len(syms) - 2)]
    assert got[0][3] == "Only routine product news." and got[1][3] == "Earnings are due inside the window."
    assert {(r[4], r[5], r[8]) for r in got} == {(c.FROZEN_MODEL, c.PROMPT_VERSION, NOW)}
    assert got[0][6] == [lean(x) for x in news[first]] and all(r[6] == [] for r in got[1:])
    assert got[0][7] == date(2026, 8, 11) and all(r[7] is None for r in got[1:])

    assert h.keys == [FH_KEY] and [cfg.model for cfg in h.cfgs] == [c.FROZEN_MODEL]
    assert h.news.calls == [
        call
        for s in syms
        for call in (("news", s, NEWS_FROM, NEWS_TO), ("earnings", s, SESSION, WINDOW_END))
    ]
    assert [call["symbol"] for call in h.ask.calls] == list(syms)
    for call in h.ask.calls:
        assert call["system"] == c.SYSTEM_PROMPT
        assert (call["temperature"], call["thinking"], call["max_tokens"]) == (0.0, "disabled", 1024)
    assert h.ask.calls[0]["prompt"] == c.user_prompt(
        first, SESSION, WINDOW_END, date(2026, 8, 11), NOW, tuple(news[first]), c.STRATEGY_C_PARAMS
    )
    assert h.ask.calls[1]["prompt"] == c.user_prompt(syms[1], SESSION, WINDOW_END, None, NOW, (), c.STRATEGY_C_PARAMS)

    stored = store.read_vetoes(world, "C", SESSION)
    world.rollback()
    assert [v.symbol for v in stored] == list(syms)
    assert q(world, "SELECT count(*) FROM orders") == [(0,)]  # veto never trades
    assert q(world, "SELECT count(*) FROM paper_state") == [(0,)]


def test_news_at_or_after_the_start_is_never_sent_nor_stored(world, configured):
    first = expected_symbols()[0]
    before = headline(1, NOW - timedelta(seconds=1), "Published before the start")
    at = headline(2, NOW, "Published at the start")
    after = headline(3, NOW + timedelta(hours=1), "Published after the start")
    h = Harness(FakeNews(news={first: [after, at, before]}))
    bars_run(world)

    assert h.run(world) == 0

    prompt = h.ask.calls[0]["prompt"]
    assert "Published before the start" in prompt
    assert "Published at the start" not in prompt and "Published after the start" not in prompt
    assert rows(world)[0][6] == [lean(before)]


def test_bars_dated_on_or_after_the_session_never_change_candidates(world, configured):
    bars_run(world)
    h = Harness()
    assert h.run(world) == 0
    expected_rows, expected_prompts = rows(world), [call["prompt"] for call in h.ask.calls]

    with db.transaction(world, False):
        world.execute("DELETE FROM news_vetoes")
        world.execute(
            "UPDATE bars SET open = open * 0.5, high = high * 0.5, low = low * 0.5, close = close * 0.5, "
            "volume = volume * 3 WHERE date >= %s",
            (SESSION,),
        )
    again = Harness()
    assert again.run(world) == 0
    assert rows(world) == expected_rows
    assert [call["prompt"] for call in again.ask.calls] == expected_prompts


def test_rerun_makes_no_call_and_writes_nothing(world, configured):
    bars_run(world)
    assert Harness().run(world) == 0
    before = everything(world)

    again = Harness()
    assert again.run(world) == 0
    assert again.network() == 0
    assert everything(world) == before


def test_failed_or_missing_bars_run_exits_1_and_writes_nothing(world, configured):
    h = Harness()
    before = everything(world)
    assert h.run(world) == 1  # no runs row at all
    assert everything(world) == before

    bars_run(world, status="failed")
    before = everything(world)
    assert h.run(world) == 1
    assert everything(world) == before
    assert h.network() == 0


def test_dry_run_writes_nothing(world, configured):
    bars_run(world)
    before = everything(world)
    dry = Harness()
    assert dry.run(world, dry_run=True) == 0
    assert everything(world) == before
    assert len(dry.ask.calls) == len(expected_symbols())  # every check ran, then rolled back

    assert Harness().run(world) == 0
    assert len(rows(world)) == len(expected_symbols())


def test_no_candidates_writes_nothing_and_calls_nothing(world, configured):
    with db.transaction(world, False):
        world.execute("DELETE FROM universe")
    bars_run(world)
    before = everything(world)
    h = Harness()
    assert h.run(world) == 0
    assert everything(world) == before
    assert h.network() == 0


# ---- failure = no trade (acceptance 3) ----------------------------------------------------------


def test_no_llm_config_fails_every_candidate_without_a_call(world, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", FH_KEY)
    bars_run(world)
    h = Harness()
    assert h.run(world) == 0
    assert verdicts(world) == [(s, "failed") for s in expected_symbols()]
    assert set(reasons(world)) == {"LLM_BASE_URL, LLM_API_KEY and LLM_MODEL are not all set"}
    assert {r[4] for r in rows(world)} == {None}
    assert h.network() == 0


def test_no_finnhub_key_fails_every_candidate_without_a_call(world, configured, monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY")
    bars_run(world)
    h = Harness()
    assert h.run(world) == 0
    assert verdicts(world) == [(s, "failed") for s in expected_symbols()]
    assert set(reasons(world)) == {"FINNHUB_API_KEY is not set"}
    assert {r[4] for r in rows(world)} == {c.FROZEN_MODEL}
    assert h.network() == 0


def test_nothing_configured_names_both_reasons(world):
    bars_run(world)
    h = Harness()
    assert h.run(world) == 0
    assert set(reasons(world)) == {
        "FINNHUB_API_KEY is not set; LLM_BASE_URL, LLM_API_KEY and LLM_MODEL are not all set"
    }
    assert h.network() == 0


def test_frozen_model_mismatch_fails_every_candidate_without_a_call(world, configured, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "glm-4.6")
    bars_run(world)
    h = Harness()
    assert h.run(world) == 0
    assert verdicts(world) == [(s, "failed") for s in expected_symbols()]
    assert set(reasons(world)) == {f"LLM_MODEL glm-4.6 is not C's frozen model {c.FROZEN_MODEL}"}
    assert {r[4] for r in rows(world)} == {"glm-4.6"}
    assert h.network() == 0


def test_llm_error_fails_only_that_candidate(world, configured):
    syms = expected_symbols()
    news = {syms[1]: [headline(7, NOW - timedelta(hours=3), "Seen before the LLM failed")]}
    h = Harness(FakeNews(news=news), FakeLlm(fail={syms[1]}))
    bars_run(world)
    assert h.run(world) == 0
    got = rows(world)
    assert [(r[1], r[2]) for r in got] == [(s, "failed" if s == syms[1] else "allow") for s in syms]
    assert got[1][3].startswith("LLM failed: LlmError: ReadTimeout")
    assert LLM_KEY not in got[1][3] and "REDACTED" in got[1][3]
    assert got[1][6] == [lean(x) for x in news[syms[1]]]  # the headlines it would have judged


def test_finnhub_errors_fail_only_that_candidate_without_an_llm_call(world, configured):
    syms = expected_symbols()
    h = Harness(FakeNews(fail_news={syms[0]}, fail_earnings={syms[1]}))
    bars_run(world)
    assert h.run(world) == 0
    got = rows(world)
    assert [(r[1], r[2]) for r in got] == [(s, "failed" if s in syms[:2] else "allow") for s in syms]
    assert got[0][3].startswith("Finnhub company-news failed: FinnhubError: HTTP 500")
    assert got[1][3].startswith("Finnhub earnings calendar failed: FinnhubError: HTTP 429")
    assert all(FH_KEY not in r[3] for r in got)
    assert [call["symbol"] for call in h.ask.calls] == list(syms[2:])


def test_unparsable_replies_fail_but_never_stop_the_night(world, configured):
    syms = expected_symbols()
    h = Harness(ask=FakeLlm(default="Looks fine to me."))
    bars_run(world)
    assert h.run(world) == 0
    assert verdicts(world) == [(s, "failed") for s in syms]
    assert all(r.startswith("unparsable reply") for r in reasons(world))
    assert len(h.ask.calls) == len(syms)  # a reply is not a network failure


def test_three_network_failures_in_a_row_stop_the_night(world, configured):
    syms = expected_symbols()
    h = Harness(ask=FakeLlm(fail_all=True))
    bars_run(world)
    assert h.run(world) == 0
    got = reasons(world)
    assert verdicts(world) == [(s, "failed") for s in syms]
    assert all(r.startswith("LLM failed: LlmError") for r in got[:3])
    assert got[3:] == ["skipped after 3 consecutive failures"] * (len(syms) - 3)
    assert len(h.ask.calls) == 3
    assert [call[1] for call in h.news.calls] == [s for s in syms[:3] for _ in range(2)]


def test_a_success_resets_the_failure_count(world, configured):
    syms = expected_symbols()
    h = Harness(ask=FakeLlm(fail={syms[0], syms[1], syms[3], syms[4]}))
    bars_run(world)
    assert h.run(world) == 0
    assert verdicts(world) == [(s, "allow" if s == syms[2] else "failed") for s in syms]
    assert len(h.ask.calls) == len(syms)


def test_a_client_that_cannot_be_built_fails_every_candidate(world, configured):
    def broken(key):
        raise RuntimeError(f"bad key {key}")

    bars_run(world)
    assert veto.execute(world, now=NOW, finnhub=broken, llm=Harness().llm) == 0
    got = reasons(world)
    assert len(got) == len(expected_symbols())
    assert set(got) == {"client setup failed: RuntimeError: bad key REDACTED"}


def test_no_secret_in_rows_or_logs(world, configured, caplog):
    caplog.set_level(logging.DEBUG)
    syms = expected_symbols()
    leaky = f'{{"verdict": "maybe", "reason": "{LLM_KEY}"}} token={FH_KEY}'
    h = Harness(
        FakeNews(fail_news={syms[0]}),
        FakeLlm(fail={syms[1]}, replies={syms[2]: leaky}),
    )
    bars_run(world)
    assert h.run(world) == 0
    stored = q(world, "SELECT x::text FROM news_vetoes x")
    assert len(stored) == len(syms)
    for secret in (FH_KEY, LLM_KEY):
        assert all(secret not in text for (text,) in stored)
        assert secret not in caplog.text


# ---- races and database errors ------------------------------------------------------------------


def test_another_run_winning_the_race_writes_nothing(world, configured, monkeypatch):
    bars_run(world)
    assert Harness(ask=FakeLlm(default=VETO)).run(world) == 0
    before = everything(world)

    real = store.has_vetoes
    seen = []

    def stale_first(conn, strategy_id, session):
        seen.append(session)
        return False if len(seen) == 1 else real(conn, strategy_id, session)

    monkeypatch.setattr(veto.store, "has_vetoes", stale_first)
    late = Harness()
    assert late.run(world) == 0
    assert len(late.ask.calls) == len(expected_symbols())  # it checked, then lost the race
    assert everything(world) == before
    assert {v for _, v in verdicts(world)} == {"veto"}


def test_paper_already_decided_the_session_writes_nothing(world, configured):
    """H1, the late-verdict retry: the 23:00 Veto wrote nothing, the 23:00 Paper decided SESSION for C
    with no verdicts. The 01:00 retry's Veto must not write verdicts now: C's replay would buy what
    Paper never did and paper_check would stay red."""
    bars_run(world)
    assert paper.execute(world, now=NOW) == 0
    assert q(world, "SELECT paper_status FROM runs WHERE session_date = %s AND NOT is_demo", (SESSION,)) == [
        ("success",)
    ]
    before = everything(world)

    retry = Harness()
    assert retry.run(world, now=NOW + timedelta(hours=2)) == 0  # 01:00 UTC: still SESSION
    assert retry.network() == 0
    assert everything(world) == before
    assert rows(world) == []
    found = {r.strategy_id: r for r in paper_check.check(world)}
    assert found["C"].status == "ok"


def test_paper_deciding_during_the_checks_writes_nothing(world, configured, monkeypatch):
    """H1, re-checked inside the write transaction: Paper finished between the first read and the write."""
    bars_run(world)
    assert paper.execute(world, now=NOW) == 0
    before = everything(world)
    real = runs.real_run
    seen = []

    def stale_first(conn, session):
        seen.append(session)
        found = real(conn, session)
        return replace(found, paper_status=None) if len(seen) == 1 else found

    monkeypatch.setattr(veto.runs, "real_run", stale_first)
    late = Harness()
    assert late.run(world) == 0
    assert len(late.ask.calls) == len(expected_symbols())  # it checked, then saw Paper had decided
    assert everything(world) == before


def test_database_error_on_write_exits_1(world, configured, monkeypatch, caplog):
    def boom(conn, strategy_id, session, verdicts):
        raise psycopg.OperationalError(f"server closed the connection (password={LLM_KEY})")

    monkeypatch.setattr(veto.store, "write_vetoes", boom)
    bars_run(world)
    assert Harness().run(world) == 1
    assert rows(world) == []
    assert LLM_KEY not in caplog.text


# ---- pure helpers ------------------------------------------------------------------------------


def test_config_failure_reasons():
    cfg = llm.LlmConfig(base_url="https://x.invalid", api_key=LLM_KEY, model=c.FROZEN_MODEL)
    p = c.STRATEGY_C_PARAMS
    assert veto.config_failure(FH_KEY, cfg, p) is None
    assert veto.config_failure(None, cfg, p) == "FINNHUB_API_KEY is not set"
    other = llm.LlmConfig(base_url="https://x.invalid", api_key=LLM_KEY, model="glm-4.6")
    assert veto.config_failure(FH_KEY, other, p) == f"LLM_MODEL glm-4.6 is not C's frozen model {c.FROZEN_MODEL}"


def test_scrub_redacts_both_keys_and_caps_length():
    text = f"token={FH_KEY} and {LLM_KEY}\n" + "x" * 400
    out = veto.scrub(text, (FH_KEY, LLM_KEY))
    assert FH_KEY not in out and LLM_KEY not in out and "\n" not in out
    assert len(out) == veto.MAX_REASON_LEN
    assert veto.scrub("plain", (None, None)) == "plain"


def test_session_dates_used_by_this_file():
    assert dates.run_dates(NOW) == dates.RunDates(data_date=NIGHT, session_date=SESSION)
    assert c.news_dates(NOW, 3) == (NEWS_FROM, NEWS_TO)
    assert c.earnings_window(SESSION, 5) == (SESSION, WINDOW_END)
```
**Impact:** +27 tests, all PG-backed ones use the `pg` fixture (0 skipped with `PG_TEST_URL` set).
No fixture or helper in other test files changes.

## Verification

**Build:** `engine/.venv/bin/ruff check engine` (clean) and
`engine/.venv/bin/python -m seer_engine veto --help` (lists `--now`, `--dry-run`, `-v`).
**Tests:** `docker start seer-pg`, then
`PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_veto_command.py -q`
(27 passed), then the full suite
`PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
(0 failed, 0 skipped).
**Manual check (optional, local Postgres only, `DATABASE_URL_UNPOOLED` pointed at it):**
`--dry-run veto --now 2026-08-06T23:00:00Z` with no keys logs "no news check tonight: FINNHUB_API_KEY is
not set; LLM_BASE_URL, …" and rolls back. Never run it against Neon in this phase.
**Exit criteria:** every test in the coverage table passes; a re-run for a checked session constructs no
client; after Paper decided the session `veto` constructs no client and writes nothing, and C's
`paper_check` stays `ok`; no `FH_KEY`/`LLM_KEY` text appears in `news_vetoes` or in captured logs; the full engine suite
and ruff are green.

**Verified in a scratch copy (2026-10-04):** this exact `veto.py` and test file, run against stubs written
from K1/K3/K5 (`c.py` subset, `NewsVerdict`/`has_vetoes`/`write_vetoes`/`read_vetoes`, 004 SQL from K2,
roster `C` with `STRATEGY_C_PARAMS`, `finnhub.FinnhubError`/`load_key`, `llm.complete` keywords):
25 passed on PG; ruff clean. The real phase 1–3 modules must match those contracts; if K1's
`news_dates`/`earnings_window` differ from the index text, `test_session_dates_used_by_this_file` is the
first test to say so.

**Re-verified by the reconciler (2026-10-04)** on a scratch copy with the real phase 1, 2, 3 and 5 plan code
applied (no stubs) and this file's H1 additions: `test_veto_command.py` 27 passed, ruff clean; with both H1
guards disabled, the two H1 tests fail (17 client calls on the retry; rows written after Paper decided).

## Handoffs

- **Phase 5 (R2):** `paper` must treat a missing `news_vetoes` row as `failed` (acceptance 3 "missing verdict
  row"); `veto` only ever writes rows for `rd.session_date` (catch-up sessions get none, per the Decisions table).
  No phase edits `tests/test_paper_command.py`; its `synthetic_bars`, `fx_rate`, `_sessions`, `STOCKS`
  names stay (this file imports them).
- **Phase 6 (R4):** the stored `reason` texts the UI will show are fixed here: config failures
  (`"FINNHUB_API_KEY is not set"`, `"LLM_BASE_URL, LLM_API_KEY and LLM_MODEL are not all set"`,
  `"LLM_MODEL <x> is not C's frozen model <y>"`, joined by `"; "`), stage-prefixed errors
  (`"Finnhub company-news failed: …"`, `"Finnhub earnings calendar failed: …"`, `"LLM failed: …"`,
  `"client setup failed: …"`), `"skipped after 3 consecutive failures"`, and K1's `"unparsable reply: …"`.
  Headlines are stored even on a failed LLM call when they were fetched, so `headlineCount` can be > 0 on
  a `failed` row. A night with zero candidates, a night Veto did not run, and a night Veto came too late
  (H1) all leave no rows; the web shows one neutral line for all three (reconciliation decision).
- **Phase 7 (R3, R5):** the workflow step is `python -m seer_engine veto` with env `DATABASE_URL_UNPOOLED`,
  `FINNHUB_API_KEY`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`; `continue-on-error: true`,
  `timeout-minutes: 10`. Exit 1 means only "bars run not success" or a database error. The runbook should
  list the reason texts above and say that a re-run of the step is safe (no calls once rows exist, and
  nothing written once Paper decided the session: H1; to re-ask, delete that session's `news_vetoes` rows
  before `paper` runs). The package readme gets a `commands/veto` section from this module's docstring.
  Phase 7's runbook and readme text for H1 ("too late, nothing written") matches the code above.
- Not done here (drive-by): `explain` and `paper` both re-declare the `--now` argument; a shared helper
  would be a cleanup outside every phase's scope.

## Rollback

Delete `engine/src/seer_engine/commands/veto.py` and `engine/tests/test_veto_command.py` (or revert this
phase's commit). Nothing else references them until phase 7 adds the workflow step; if phase 7 has landed,
remove its `Veto` step first. Rows already written to `news_vetoes` by a local run can stay or be removed
with `DELETE FROM news_vetoes WHERE strategy_id = 'C'`.
