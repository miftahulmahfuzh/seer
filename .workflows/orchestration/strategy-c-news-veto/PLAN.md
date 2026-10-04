# Plan: Strategy C — A's candidates with a news + LLM veto, on paper (roadmap P6, v0.2.0)

**Slug:** strategy-c-news-veto
**Date:** 2026-10-04
**Analysis:** `20261004-171449-C5V8_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/strategy-c-news-veto`
**Branch:** `feature/strategy-c-news-veto` (base: `HEAD` = local `main` @ `d9cecce`)
**Phases:** 7
**Status:** phase 3/7 complete
**Coordinator:** —

---

## Why

The specification is `docs/handover/2026-10-04-strategy-c-news-veto.md` (committed at `d9cecce`);
every phase reads all of it. Its own words:

> C is A with a second opinion: every night it takes the stocks A would buy for the next session,
> reads the latest news about each one (Finnhub), and asks the LLM whether the news says "don't
> touch this right now" (an earnings miss, fraud, a lawsuit, a buyout, a guidance cut...). C buys
> only what the LLM lets through. If the news or the LLM can't be reached, C does **not** buy
> (design §8: "a failed veto check is no trade").
>
> C can only be tested going forward: an LLM has read the news of the past, so a backtest of C would
> be contaminated (design §4). So C joins the paper roster next to A, and the app shows, month by
> month, whether the veto made A better or worse. Nothing here moves real money.

Design §1 stays law. C never presents anything as a real-money buy; Today keeps "SPY buy-and-hold is
the champion; Seer recommends no buys".

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Engine, pure: C strategy object, roster entry `C` with frozen spec (D5), prompt + JSON verdict parser | 1, 2 |
| R2 | Engine, impure: Finnhub client, `veto` command (D6), migration `004` (D7), verdict store, `paper` deciding C, `paper_check` replaying C (D8), `explain` covering C | 2, 3, 4, 5 |
| R3 | Workflow: `Veto` step between `Nightly` and `Paper`, inside the 45-minute job | 7 |
| R4 | Web: C in every roster view, "Vetoed tonight" on Positions, D9 checklist row, demo seed | 6 |
| R5 | Docs: engine readme, paper runbook (veto step, failures, owner steps, C's clock), ROADMAP P6 (D11) | 7 |

Phase 2 serves R1 and R2 on purpose: the roster entry's display fields must equal the row migration
`004` inserts (a test checks it against a migrated database), so the two cannot land apart green.

## Scope

**In scope:** handover §4 items 1–5.
**Out of scope:** handover §4 "Out of scope" (real money; design §1; B; new quant strategies or
registry appends; changing A, F4, F1 or SPY; the `v0.1.0` release; notifications; the trade journal;
backtesting C). Also: writing to Neon from any phase (the nightly `Migrate` step applies `004` on the
first scheduled run after the merge), and setting GitHub secrets (owner steps, D12).

## Invariants

1. At the end of every phase: `docker start seer-pg`, then
   `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
   passes with **0 skipped**, `engine/.venv/bin/ruff check engine` is clean, and
   `cd web && npx vitest run && npx tsc --noEmit` passes. The worktree has its own `engine/.venv`
   (already created); never test with main's venv.
2. **Frozen roster.** `SPY`, `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M`: ids, display fields, specs
   and digests byte for byte (`tests/test_paper_roster.py::PINS` values for those four never change);
   their paper rows are never touched by `004` or by C.
3. **Closed records.** Not edited: `backtest/registry.py`, `backtest/runner.py`,
   `backtest/book_runner.py`, `backtest/benchmark.py`, `docs/backtests/*`, `strategies/a.py`
   (`STRATEGY_A`, `STRATEGY_A_PARAMS`), `strategies/a2.py`, `STRATEGY_B_FROZEN`, `sim/*`,
   `paper/bracket.py`, `paper/book.py`, `paper/benchmark.py`, `paper/replay.py`, `db/migrations/00[1-3]_*.sql`.
4. **Same code path.** C's trades come only from `paper.bracket.decide_bracket`/`settle_bracket`
   (live) and `replay.expected_bracket` → `run_rules(DESIGN_V0)` (check), fed a `NewsVeto` object
   that carries stored verdicts. No new fill, sizing or exit logic anywhere.
5. **Pure means pure.** `strategies/c.py` imports no psycopg, requests, yfinance, `time`, `random`,
   `logging`, `urllib`, `socket`; calls no `now/utcnow/today/fromtimestamp/print/open/input`
   (`tests/test_strategy_purity.py` covers it automatically). Converting a unix timestamp is
   `datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=ts)`, never `fromtimestamp`.
6. **No look-ahead.** C's decision for session S uses bars through `prev_session(S)` and news items
   whose `datetime` is strictly before the veto run's start (`decided_at`); the earnings calendar is
   the schedule as known at that start.
7. **Failure = no trade, never a failed night.** Any missing key, network error, timeout, HTTP
   error, unparsable reply, model mismatch or missing verdict row ⇒ verdict `failed` (or no row) ⇒ that
   candidate is not bought. `veto` never raises out to the workflow on such a failure; `paper` never
   fails because of C's verdicts.
8. **UI law.** Seer v2 design (`docs/design/Seer v2.dc.html`); every button icon-only (Lucide) with
   `aria-label` and `data-tip`; 414 pt and desktop; light and dark. Nothing reads as a real-money
   recommendation; Today unchanged.
9. **File ownership.** `engine/src/seer_engine/paper/store.py`, `paper/roster.py`, `demo.py`:
   phase 2 only. The one-line `"C"` edits in `engine/tests/test_paper_check.py:51` and
   `engine/tests/test_paper_store.py:58`: phase 2 only (so phase 2 is green alone). `llm.py`: phase 3
   only. `commands/paper.py`, `commands/paper_check.py`: phase 5 only. `web/**` (including
   `web/package_readme.md`): phase 6 only. `.github/workflows/nightly.yml`, `engine/package_readme.md`,
   `docs/runbooks/*`, `docs/ROADMAP.md`, `.env.example`: phase 7 only. `tests/test_paper_command.py`:
   no phase edits it (phase 4 imports its `synthetic_bars`, `fx_rate`, `_sessions`, `STOCKS`).
10. No secret is logged, committed, stored in `news_vetoes.reason` or printed. Every error text stored
    or logged passes through `http.redact` / `llm.scrub`.

## Contracts every phase codes against

### K1 — `engine/src/seer_engine/strategies/c.py` (phase 1, pure)

```python
PROMPT_VERSION = "c-veto-v1"
FROZEN_MODEL = "glm-5.3"          # the model C's verdicts are frozen to (Decisions: "model in the spec")
STRATEGY_C_ID = "C-news-veto"     # NewsVeto.id (the spec's object_id)

Verdict = Literal["allow", "veto", "failed"]
VERDICTS: tuple[str, ...] = ("allow", "veto", "failed")

@dataclass(frozen=True, slots=True)
class Headline:            # one Finnhub company-news item, as C reads it
    id: int
    published: datetime    # tz-aware UTC
    source: str
    headline: str
    summary: str

@dataclass(frozen=True, slots=True)
class CParams:
    a: AParams = STRATEGY_A_PARAMS
    max_candidates: int = 10          # D2
    news_days: int = 3                # D3: from = run date (ET) - 3 days, to = run date (ET)
    max_headlines: int = 20           # D3
    max_summary_chars: int = 280      # summaries are sent to the LLM, never stored
    earnings_sessions: int = 5        # earnings window = S .. the 5th session from S (DESIGN_V0.time_stop)
    model: str = FROZEN_MODEL
    prompt_version: str = PROMPT_VERSION
    temperature: str = "0"
    thinking: str = "disabled"
    max_tokens: int = 1024
    def as_dict(self) -> dict[str, str]: ...
        # every key a plain string: "a.<k>" for each item of self.a.as_dict(), "a_object": "STRATEGY_A",
        # "a_object_id": STRATEGY_A.id, the other fields by name, "system_prompt": SYSTEM_PROMPT,
        # "user_template": USER_TEMPLATE (the full frozen texts, handover D5)

STRATEGY_C_PARAMS = CParams()

SYSTEM_PROMPT: str   # the c-veto-v1 system text below, verbatim
USER_TEMPLATE: str   # the c-veto-v1 user template below, verbatim (str.format fields)

def candidates(history, members, data_date, params: CParams) -> list[Pick]:
    """STRATEGY_A.picks(history, members, data_date, params.a)[: params.max_candidates]"""

def candidates_prepared(prepared, members, data_date, params: CParams) -> list[Pick]:
    """STRATEGY_A.picks_prepared(prepared, members, data_date, params.a)[: params.max_candidates]"""

@dataclass(frozen=True, slots=True, eq=False)
class NewsVeto:                       # satisfies strategies.base.Strategy
    allowed: Mapping[date, frozenset[str]]   # session S -> symbols whose stored verdict is "allow"
    id: str = STRATEGY_C_ID
    lookback: int = STRATEGY_A.lookback
    def picks(self, history, members, data_date, params: CParams) -> list[Pick]:
        """[p for p in candidates(...) if p.symbol in self.allowed.get(next_session(data_date), frozenset())]"""
    def prepare(self, history): return STRATEGY_A.prepare(history)
    def picks_prepared(self, prepared, members, data_date, params): ...  # same filter over candidates_prepared
    def with_allowed(self, allowed: Mapping[date, frozenset[str]]) -> "NewsVeto": ...

STRATEGY_C = NewsVeto(allowed={})     # the roster object: with no verdicts it never buys

def news_dates(started_at: datetime, days: int) -> tuple[date, date]:
    """(from, to) ET calendar dates for Finnhub: to = started_at in America/New_York, from = to - days."""

def earnings_window(session: date, n: int) -> tuple[date, date]:
    """(session, the n-th session counting session as 1)."""

def select_headlines(items: Iterable[Headline], cutoff: datetime, cap: int) -> tuple[Headline, ...]:
    """items with published < cutoff, newest first (ties: higher id first), at most cap."""

def user_prompt(symbol: str, session: date, window_end: date, earnings: date | None,
                cutoff: datetime, headlines: Sequence[Headline], params: CParams) -> str: ...

def parse_verdict(text: str) -> tuple[Verdict, str]:
    """("allow"|"veto", reason) from the reply; ("failed", "unparsable reply: <first 120 chars>") otherwise.
    Accepts surrounding whitespace and a ```json fence; takes the first {...} object; verdict must be
    exactly "allow" or "veto" (case-insensitive, stripped); reason a non-empty string, whitespace
    collapsed, capped at 300 chars."""

def allowed_map(rows: Iterable[tuple[date, str, str]]) -> dict[date, frozenset[str]]:
    """(session, symbol, verdict) rows -> {session: symbols with verdict == "allow"}."""
    # every session with a row gets a key (empty set when nothing allowed); callers still use .get(S, frozenset())
```
Phase 1 also exports `headline_line(i, h, max_summary_chars)`, `NEWS_TZ`, `MAX_REASON_CHARS = 300`,
`UNPARSABLE_SNIPPET_CHARS = 120`, `NO_HEADLINES`, `NO_EARNINGS`; `CParams.as_dict()` key order is
`a.rsi_max, a.limit_atr, a.tp_atr, a.sl_atr, a.min_dollar_volume, a_object, a_object_id, max_candidates,
news_days, max_headlines, max_summary_chars, earnings_sessions, model, prompt_version, temperature,
thinking, max_tokens, system_prompt, user_template` (C's pinned digest `6cea6cb8…b762` depends on it).

#### The frozen prompt `c-veto-v1` (verbatim; part of C's digest)

`SYSTEM_PROMPT`:

```text
You are the news check of a paper-trading research app. A price rule has already chosen a US stock to buy at the next market open and to hold for at most 5 trading sessions. Your only job is to say whether recent news about this company shows a specific event risk inside that window.

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
{"verdict": "allow" or "veto", "reason": "<one sentence, at most 25 words>"}
```

`USER_TEMPLATE` (`str.format` fields; `{headline_lines}` is one line per headline as
`{i}. {YYYY-MM-DD HH:MM}Z | {source} | {headline} | {summary}` with the summary cut to
`max_summary_chars` at a word boundary, or the single line `No headlines.`):

```text
Symbol: {symbol}
Entry: the open of {session}
Holding window: {session} to {window_end} ({sessions} sessions)
Scheduled earnings inside the window: {earnings}
Headlines published before {cutoff} UTC, newest first ({count} shown, at most {cap}):
{headline_lines}
```

`{earnings}` is the ISO date or `none found`; `{cutoff}` is `YYYY-MM-DD HH:MM`.

### K2 — Migration `db/migrations/004_news_veto.sql` (phase 2)

```sql
-- Strategy C (handover D1, D7). 003 deleted the unreferenced 'C' row; this puts the roster row back.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id) VALUES
  ('C', 'C · News veto', 'A''s picks, LLM can veto on news', 'gavel', false, false, 5, 'bracket', 'design-v0')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, sub = EXCLUDED.sub, icon = EXCLUDED.icon,
  is_champion = EXCLUDED.is_champion, is_benchmark = EXCLUDED.is_benchmark, sort = EXCLUDED.sort,
  engine = EXCLUDED.engine, rules_id = EXCLUDED.rules_id;

-- One row per (strategy, session, candidate): the news check `veto` ran the night before the session.
-- Replay (paper_check) reads these; the LLM is never re-asked (handover §2, D8).
CREATE TABLE IF NOT EXISTS news_vetoes (
  strategy_id     text NOT NULL REFERENCES strategies(id),
  session_date    date NOT NULL,                 -- the session the candidate would be bought for
  rank            int NOT NULL CHECK (rank >= 1),-- rank in A's list (1..max_candidates)
  symbol          text NOT NULL,
  verdict         text NOT NULL CHECK (verdict IN ('allow', 'veto', 'failed')),
  reason          text NOT NULL,                 -- the LLM's sentence, or why the check failed (redacted)
  model           text,                          -- LLM_MODEL as configured that night; NULL when unset
  prompt_version  text NOT NULL,                 -- 'c-veto-v1'
  headlines       jsonb NOT NULL DEFAULT '[]',   -- [{id, datetime (ISO UTC), source, headline}], newest first
  earnings_date   date,                          -- earnings found inside the holding window, if any
  decided_at      timestamptz NOT NULL,          -- the veto run's start: the news cutoff
  PRIMARY KEY (strategy_id, session_date, symbol),
  UNIQUE (strategy_id, session_date, rank)
);
```

### K3 — Store API in `paper/store.py` (phase 2; impure; nothing commits)

```python
@dataclass(frozen=True, slots=True)
class NewsVerdict:
    rank: int
    symbol: str
    verdict: str                          # one of strategies.c.VERDICTS
    reason: str
    model: str | None
    prompt_version: str
    headlines: tuple[Mapping[str, Any], ...]   # {"id": int, "datetime": "YYYY-MM-DDTHH:MM:SSZ", "source": str, "headline": str}
    earnings_date: date | None
    decided_at: datetime                  # tz-aware

def has_vetoes(conn, strategy_id: str, session: date) -> bool
def write_vetoes(conn, strategy_id: str, session: date, verdicts: Sequence[NewsVerdict]) -> int
    # plain INSERTs (a duplicate is a database error: the caller checks has_vetoes first, in the same txn);
    # validates ranks 1..n unique, symbols unique, verdict in VERDICTS, decided_at tz-aware, session an
    # NYSE session; nothing written on a bad input; empty -> 0; returns rows written
def read_vetoes(conn, strategy_id: str, session: date) -> tuple[NewsVerdict, ...]        # by rank
def allowed_between(conn, strategy_id: str, start: date, end: date) -> dict[date, frozenset[str]]
    # sessions start..end inclusive; only verdict = 'allow'; via strategies.c.allowed_map
```

`demo.DEMO_TABLES` gains `news_vetoes` (demo-owned, truncated by `purge_demo`).
`paper._PAPER_ROWS_SQL` does **not** gain it (verdicts exist before C starts).

### K4 — Roster entry `C` (phase 2)

```python
RosterEntry(
    id="C", name="C · News veto", sub="A's picks, LLM can veto on news", icon="gavel",
    is_champion=False, is_benchmark=False, sort=5, engine="bracket", rules=DESIGN_V0,
    obj=STRATEGY_C, object_name="STRATEGY_C", params=STRATEGY_C_PARAMS, registry_id=None,
    lookback=STRATEGY_C.lookback,
    gate_note="Backtest gate: not applicable (LLM strategy, design §1 item 5)",
    gate_applicable=False,
)
```
`RosterEntry` gains `gate_applicable: bool = True` (last field, default). `backtest_gate(e)` returns
`{"passed": False, "note": e.gate_note}` for applicable entries (unchanged bytes) and
`{"passed": False, "applicable": False, "note": e.gate_note}` for C. `spec(e)` needs no change: C's
`params` comes from `CParams.as_dict()`, `object_id` from `STRATEGY_C.id`. `PINS` gains `"C"`.

### K5 — Clients (phase 3)

- `engine/src/seer_engine/finnhub.py`: `BASE_URL = "https://finnhub.io/api/v1"`, `MIN_INTERVAL = 1.0`
  (60/min), `DEFAULT_TIMEOUT_S = 15.0`; `FinnhubError(message, status)`; `load_key() -> str | None`
  (`config.get("FINNHUB_API_KEY")`); `class Client(key, *, transport=None, min_interval, timeout,
  clock=time.monotonic, sleep=time.sleep)` with
  `company_news(symbol, start: date, end: date) -> list[Headline]` (`GET /company-news`, items with a
  missing/non-int `datetime` or empty headline dropped; `Headline` from K1) and
  `earnings(symbol, start: date, end: date) -> date | None` (`GET /calendar/earnings`; earliest
  `date` in `earningsCalendar` within [start, end], else None; every returned row counts, e.g. BRK.B →
  the BRK.A row). The key travels **only** in the `X-Finnhub-Token` header; error texts are scrubbed of
  it. Retries: one retry on connection error/timeout/429/5xx (honouring a longer numeric `Retry-After`,
  capped at `MAX_RETRY_AFTER_S = 60`), else `FinnhubError`. As planned in phase 3 (reconciled superset):
  items with a non-int `id` are dropped too; `Client` also takes `base_url`, `retries=1`, `backoff=2.0`;
  `scrub(text, key)`, `TOKEN_HEADER`; spacing counts from the end of the previous attempt, retries included.
- `llm.Client.complete(system, prompt, *, temperature: float | None = None,
  thinking: str | None = None, max_tokens: int | None = None)`: the body gains `"temperature"` when
  given, `"thinking": {"type": thinking}` when given, and `max_tokens` overrides the client default
  for that call. With no keyword arguments the request body is byte-identical to today's (explain
  unchanged). `max_tokens < 1` or a blank `thinking` raise `ValueError` before any request.

### K6 — `veto` command (phase 4)

`python -m seer_engine [--dry-run] [-v] veto [--now ISO8601]` (`commands/veto.py`, auto-discovered):

1. `demo.purge_demo_if_needed(conn, dry_run)`.
2. `started_at = now` (tz-aware UTC; `--now` for tests) — the news cutoff and `decided_at`.
   `rd = dates.run_dates(now)`; `session = rd.session_date`.
3. The real `runs` row for `session` must be `success` (as in `paper`), else log error, exit 1.
3b. **(H1, reconciliation)** that row's `paper_status == "success"` (`runs.real_run(...).paper_status`):
   Paper already decided the session → log "too late", exit 0, **no network call, nothing written**.
   A verdict written after Paper decided would make `paper_check` replay a trade Paper never placed.
4. `store.has_vetoes(conn, "C", session)` → log "already checked", exit 0, **no network call**.
5. Read, then roll back, before any network call: `store.load_market_window(conn,
   store.market_window_since(rd.data_date))`; `cands = c.candidates(market.history,
   market.membership.members_on(rd.data_date), rd.data_date, roster.entry("C").params)`.
   No candidates → log, exit 0, nothing written.
6. Per candidate in rank order → one `NewsVerdict`, verdict `failed` with a plain reason when:
   `FINNHUB_API_KEY` unset; `LLM_*` unset (`llm.load_config() is None`); configured model ≠
   `params.model` ("LLM_MODEL <x> is not C's frozen model <y>"); a Finnhub or LLM error (redacted,
   ≤ 300 chars); `parse_verdict` → failed; or `MAX_CONSECUTIVE_FAILURES = 3` network failures in a row
   ("skipped after 3 consecutive failures"). Otherwise: news `company_news(symbol, *news_dates(started_at,
   params.news_days))` → `select_headlines(..., cutoff=started_at, cap=params.max_headlines)`;
   `earnings(symbol, *earnings_window(session, params.earnings_sessions))`; `llm.Client(cfg,
   timeout=30.0, retries=1).complete(SYSTEM_PROMPT, user_prompt(...),
   temperature=float(params.temperature), thinking=params.thinking, max_tokens=params.max_tokens)`
   (0.0, "disabled", 1024) → `parse_verdict`. Stored headlines are the
   selected ones (lean: id, datetime, source, headline).
7. One transaction: re-check step 3b (exit 0 if Paper decided meanwhile) and `has_vetoes` (exit 0 if
   another run won), `write_vetoes`. `--dry-run` rolls back.
8. Exit 0 whenever rows were written or nothing was needed; 1 only for step 3 or a database error.
   The workflow step is `continue-on-error: true` anyway.

### K7 — `paper` and `paper_check` (phase 5)

- `paper`: a helper `_bracket_strategy(conn, e, first: date, last: date)` returns `e.obj` unchanged
  unless `isinstance(e.obj, NewsVeto)`, in which case it returns
  `e.obj.with_allowed(store.allowed_between(conn, e.id, first, last))`. `_start` uses it with
  `first = last = rd.session_date`; `_step_bracket` with `first = next_session(sessions[0])`,
  `last = next_session(sessions[-1])`. Nothing else in the night changes.
- `paper_check`: inside the existing read-only transaction, for a `NewsVeto` entry, the strategy
  passed to `replay.expected_bracket` is `entry.obj.with_allowed(store.allowed_between(conn,
  entry.id, head.paper_start, next_session(head.last_session)))`.
- `explain`: unchanged code; a test proves C's pending orders get explanations like A's.

### K8 — Web (phase 6)

- `Gate = { passed: boolean; applicable: boolean; note: string | null }`; `parseGate` reads
  `applicable !== false`.
- `checklist(m, spy, gate)` row 6: applicable → as today; not applicable → `{ label: 'Backtest gate',
  val: 'Not applicable', ok: false, note }`.
- `scoreOf(items, gate)` (signature takes the `Gate`): not applicable → lines
  `['Paper only. No backtest gate.', 'Real money needs an owner decision']`.
- `data.ts`: `type Veto = { rank: number; symbol: string; verdict: 'allow' | 'veto' | 'failed';
  reason: string; headlineCount: number; earningsDate: string | null; decidedAt: string }` and
  `vetoes(strategyId: string, sessionDate: string): Promise<Veto[]>` (by rank, all verdicts).
- Positions: for a strategy whose rows exist in `news_vetoes` (or `strategy.id === 'C'` when none
  exist for the pending session), a "Vetoed tonight" sheet under the paper orders: `veto` and
  `failed` rows (symbol, verdict chip, reason via `WhyToggle`, headline count), a line "`n` checked ·
  `k` allowed", and the empty/failed states. No rows (reconciliation: `veto` writes none when A had no
  candidates, so the app cannot tell that from a check that did not run) → `noCheckLine`: "No news
  check for {date}: A had no candidates, or the check did not run. C buys nothing this session."; every
  row failed with one reason → "News check failed for {date}: C sits this session out." + the shared
  reason. Today unchanged.
- `web/lib/vetoes.ts` (pure): `Verdict`, `Veto`, `parseVerdict`, `VetoSheet`, `vetoSheet`, `checkedLine`,
  `headlinesLabel`, `noCheckLine(day, short)`. `Strategy.checksNews` via `checksNews(id, specObject)`
  (`specObject === 'STRATEGY_C' || id === 'C'`). Leaderboard: C's look is the 4th pair (`bg-butter` /
  `var(--coral)`), `monthsBg` (butter → stone), up to 5 desktop card columns.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Pure C: strategy object, prompt, parser | R1 | `engine/strategies` | 2 | — | NORMAL | `.workflows/plan/strategy-c-news-veto/phase-1.md` | P1-ENG-KIBJ | — |
| 2 | Migration 004, roster entry C, verdict store | R1, R2 | `db`, `engine/paper` | 10 | 1 | NORMAL | `.workflows/plan/strategy-c-news-veto/phase-2.md` | P1-ENG-4I4B | — |
| 3 | Finnhub client and LLM call options | R2 | `engine` | 4 | 1 | NORMAL | `.workflows/plan/strategy-c-news-veto/phase-3.md` | P1-ENG-2548 | — |
| 4 | `veto` command | R2 | `engine/commands` | 2 | 2, 3 | HARD | `.workflows/plan/strategy-c-news-veto/phase-4.md` | P1-ENG-QRXI | — |
| 5 | `paper`, `paper_check`, `explain` decide and replay C | R2 | `engine/commands` | 3 | 2 | HARD | `.workflows/plan/strategy-c-news-veto/phase-5.md` | P1-ENG-IIZE | — |
| 6 | Web: C everywhere, Vetoed tonight, D9 row, demo seed | R4 | `web` | 17 | 2 | HARD | `.workflows/plan/strategy-c-news-veto/phase-6.md` | P1-WEB-8YO3 | — |
| 7 | Ship: Veto workflow step, live smoke, docs | R3, R5 | repo | 5 | 4, 5, 6 | NORMAL | `.workflows/plan/strategy-c-news-veto/phase-7.md` | P1-ROOT-ZEOM | — |

Phases 3, 5 and 6 can run in parallel after their dependencies; 4 needs 2 and 3. Every dependency points
backward. File counts are each plan's Files table (phase 7's uncommitted scratch smoke script excluded).

### Phase 1 — Pure C: strategy object, prompt, parser
**Satisfies:** R1
**Owns:** `engine/src/seer_engine/strategies/c.py` (K1, entire); `engine/tests/test_strategy_c.py`.
**Does not touch:** `strategies/a.py`, `strategies/__init__.py` (no re-export), roster, store, any command, web.
**Exit criteria:** with every candidate allowed, `NewsVeto.picks == candidates == STRATEGY_A.picks[:10]`; vetoed/failed/missing symbols removed, order kept; ranks > 10 never returned; `picks_prepared(prepare(H)) == picks(H cut)`; `run_rules(DESIGN_V0)` over a synthetic market with an all-allow map equals A's run where A never needs rank > 10; `select_headlines` drops items at/after the cutoff; `parse_verdict` table of cases; `user_prompt` golden text; purity green; prompt texts have no trailing newline and `as_dict` has exactly the 19 keys K1 lists (C's pin depends on them).

### Phase 2 — Migration 004, roster entry C, verdict store
**Satisfies:** R1, R2
**Owns:** `db/migrations/004_news_veto.sql` (K2, byte for byte); `paper/roster.py` (K4); `paper/store.py` (K3); `demo.py` (`news_vetoes` in `DEMO_TABLES`); tests `test_migrate.py` (003 tests pinned to a schema at 003; 004 fresh, post-003, restyle, idempotent, keys), `test_paper_roster.py` (C pin `6cea6cb8…b762`, display fields equal 004's row, the four pins unchanged, C's gate dict), `test_demo.py`, new `test_paper_store_vetoes.py`, and the one-line `"C"` edits in `test_paper_store.py:58` and `test_paper_check.py:51` (owned here so the phase is green alone).
**Does not touch:** commands, workflows, web, docs.
**Exit criteria:** full engine suite green with 0 skipped; the four existing digests and gate dicts unchanged; `004` applies on a schema at 003 and is a no-op twice; C's pin passes (if it fails for C only, re-pin from the printed digest: C has never been frozen).

### Phase 3 — Finnhub client and LLM call options
**Satisfies:** R2
**Owns:** `engine/src/seer_engine/finnhub.py` (K5) + `engine/tests/test_finnhub.py` (fake transport/clock); `llm.py` keyword options (K5) + `test_llm.py` additions (body byte-identical without keywords; with them `temperature`, `thinking`, `max_tokens` present).
**Does not touch:** commands (`explain` keeps calling `complete(system, prompt)`), store, web.
**Exit criteria:** spacing ≥ 1.0 s between any two requests, retries included; key only in a header and scrubbed from errors, logs and repr; one retry on connection error/timeout/429/5xx (Retry-After capped at 60 s), none on other 4xx; earnings earliest-in-window; tests green.

### Phase 4 — `veto` command
**Satisfies:** R2
**Owns:** `engine/src/seer_engine/commands/veto.py` (K6, incl. the H1 guard) + `engine/tests/test_veto_command.py` (27 tests; PG + fake Finnhub/LLM injected through `execute(conn, *, now, dry_run, finnhub=..., llm=...)` factories).
**Does not touch:** `paper.py`, `paper_check.py`, store (calls K3 only), `test_paper_command.py` (imports its helpers), workflow, docs.
**Exit criteria:** tests for each acceptance-3 failure (no LLM config, timeout/HTTP error, unparsable, Finnhub error, no Finnhub key, model mismatch, consecutive-failure stop); look-ahead (news at/after start never in the prompt or stored; bars dated ≥ session never change candidates); idempotent re-run makes zero client calls and writes nothing; **after Paper decided the session (late-verdict retry) no client call, no row, and C's `paper_check` stays ok; Paper deciding during the checks → the write transaction writes nothing**; failed/missing bars run → exit 1, nothing written; `--dry-run` writes nothing; no secret in rows or logs; LLM options are `float(params.temperature)`, `params.thinking`, `params.max_tokens`.

### Phase 5 — `paper`, `paper_check`, `explain` decide and replay C
**Satisfies:** R2
**Owns:** `commands/paper.py` (K7: `_bracket_strategy`, `_start`, `_step_bracket`), `commands/paper_check.py` (K7: `_expected(conn, ...)`); new `engine/tests/test_paper_c.py` (14 tests, verdict rows via `store.write_vetoes`).
**Does not touch:** `paper/*` cores, `replay.py`, store, `veto.py`, `explain.py`, `test_paper_command.py`, `test_paper_check.py` / `test_paper_store.py` (phase 2's edits stand), web.
**Exit criteria:** C starts on its first night with its own `paper_start` while the other four keep theirs; ≥ 5 synthetic nights → `paper_check` ok for all five; the replay really reads stored verdicts (flipping one → C mismatch); all-allow C orders == A orders; veto/failed/missing → no C order for that symbol and `paper` exit 0; catch-up night with verdicts only for the newest session; re-run writes nothing; the four existing strategies' rows identical with and without C; explain fills C's pending orders.

### Phase 6 — Web: C everywhere, Vetoed tonight, D9 row, demo seed
**Satisfies:** R4
**Owns:** `web/lib/strategy.ts` (+test), `web/lib/metrics.ts` (+test), new `web/lib/vetoes.ts` (+test, incl. `noCheckLine`), `web/lib/data.ts` (`checksNews`, `vetoes()`), `web/app/(app)/leaderboard/view.ts` (+test) + `page.tsx` (butter/coral 4th look, `monthsBg`, `scoreOf(items, gate)`, 5 card columns), `web/app/(app)/positions/page.tsx` + `positions.module.css` ("Vetoed tonight"), `web/components/WhyToggle.tsx` (optional `label`/`missing`), `web/components/roster.ts` (comment) + `roster.test.ts`, `web/scripts/seed-demo.mjs` (C row with `applicable: false`, C portfolio on its own clock, six verdict rows, `news_vetoes` in the TRUNCATE), `web/package_readme.md` (Step 16).
**Does not touch:** engine, Today (`app/(app)/page.tsx`).
**Exit criteria:** vitest (10 files, 83 tests) + `tsc --noEmit` green; seed applies onto 001–004 locally; screens render on demo data at 414 pt and desktop, light and dark; the no-rows state reads the neutral `noCheckLine`; Today still shows no buys.

### Phase 7 — Ship: Veto workflow step, live smoke, docs
**Satisfies:** R3, R5
**Owns:** `.github/workflows/nightly.yml` (`Veto` step after `Nightly`, before `Paper`; `continue-on-error: true`; `timeout-minutes: 10`; env `FINNHUB_API_KEY`, `LLM_*` from secrets; job stays 45 min); a live smoke (local, scratchpad, never committed, no database) of the phase-3 clients + K1 prompt/parser for 10 liquid symbols with timings recorded in the runbook; `engine/package_readme.md` (`veto` incl. H1, `finnhub`, `strategies.c`, store additions, migration 004); `docs/runbooks/paper-trading.md` (the veto step, failure states quoting phase 6's exact strings, owner steps for `FINNHUB_API_KEY` and `LLM_*`, C's clock, `--require-sessions` counting C, reset procedures that keep `news_vetoes`); `docs/ROADMAP.md` (P6 with D11's wording); `.env.example` comment.
**Does not touch:** source behaviour; `web/**` (incl. `web/package_readme.md`, phase 6's); Neon; GitHub secrets.
**Exit criteria:** `actionlint`-clean YAML (or the YAML assertion), CI commands pass locally, smoke timings recorded, no `‹` left in the docs, docs updated, diff limited to the five files and free of secrets.

## Reconciliation Log

Round 1 (2026-10-04). Composed scratch build: phases 1–5 code blocks applied to a copy of the worktree (no
stubs), worktree venv, local PG: **full engine suite 2159 passed, 0 skipped, 0 failed (5 min 28 s)**, ruff clean, `004` byte-identical to K2, C's
digest `6cea6cb8…b762` reproduced. Phase 6 applied to a copy of `web/`: vitest 10 files / 83 tests, `tsc
--noEmit` clean, seed `--dry-run` ok.

| # | Conflict | Class | Phases | Resolution |
|---|---|---|---|---|
| 1 | A retry Veto (01:00, or a manual run) after the 23:00 Veto wrote nothing and Paper already decided S would store late verdicts; `paper_check` would replay buys Paper never made: permanently red | Unmet assumption (phase 7 H1) | 4, 7 | Phase 4: exit 0 with no client call and nothing written when `runs.real_run(conn, S).paper_status == "success"`, checked before any network call and re-checked in the write transaction (`_paper_decided`); two tests (late-verdict retry → no rows and C's `paper_check` ok; Paper deciding mid-check → nothing written), both proven to fail without the guard. K6 step 3b. Phase 7 H1 alternative text removed |
| 2 | `test_paper_check.py:51` `ROSTER_IDS` edited by phase 2 and (conditionally) by phase 5 Step 4 | Duplicate work | 2, 5 | Phase 2 owns it (and `test_paper_store.py:58`); phase 5 Step 4 removed, its Files table/Requires/Handoffs/Rollback quote the post-phase-2 lines |
| 3 | Phase 5 quoted `test_paper_check.py:51` in its pre-phase-2 state | File collision | 2, 5 | Phase 5 now quotes both lines as phase 2 leaves them |
| 4 | `web/package_readme.md` exists but no phase owned it (phase 6 deferred it, phase 7 does not touch `web/**`) | Gap | 6 | Phase 6 Step 16 (layout, `lib/strategy.ts`, `lib/metrics.ts`, new `lib/vetoes.ts` section, `data.ts`, roster icon, `view.ts`, seed, gotchas); Files 16 → 17 |
| 5 | "News check did not run for {date}: C sits this session out." is also shown on zero-candidate nights, when the check did run | Contract drift (K8, phases 6, 7) | 6, 7 | Coordinator decision: no marker table; `noCheckLine` in `lib/vetoes.ts` ("No news check for {date}: A had no candidates, or the check did not run. C buys nothing this session.") with a unit test; Positions' `noOrders` says "buys nothing this session" for that state; phase 7 runbook rows quote it; K8 updated |
| 6 | Phase 7's reset procedures delete `news_vetoes`; phase 5's reset (test code) keeps verdicts and its handoff says the reset must not need to delete them; phase 7 also says "never delete a verdict to hide" | Behavior fork | 5, 7 | Keep verdicts on both resets (Decisions); phase 7 3.13 SQL edited, a bullet explains why it is safe |
| 7 | Phase 3's client drops non-int `id` items, caps `Retry-After` at 60 s, takes `base_url`/`retries`/`backoff`, raises `ValueError` on bad `complete` options; K5 did not say so | Contract drift | 3, index | K5 updated to phase 3's code; phase 7 readme `finnhub` bullets aligned |
| 8 | Phase 7 readme said `commands.veto` imports `config`; phase 4's module does not (it imports `commands.nightly`, `sim.sizing`) | Contract drift | 4, 7 | Phase 7 dependency line rewritten from phase 4's imports |
| 9 | Phase 7's smoke passed the literal `temperature=0.0`; phase 4 derives it from `float(params.temperature)` (coordinator decision 4) | Contract drift | 4, 7 | Smoke uses `float(params.temperature)`; K6 text states the derivation. Phase 4's code already matched phase 3's `complete()` keywords |
| 10 | C's pin in phase 2 was computed from a K1 stub; phase 1's real bytes could differ | Unmet assumption | 1, 2 | Verified equal in the scratch build (digest reproduced); phase 2 gained the "re-pin C only if only C fails" rule |
| 11 | Phase 7's runbook rows held `‹date›` / `‹x›`, which its own "no `‹` remains" check would reject though they are not smoke-filled values | Contract drift | 7 | Replaced with `{date}` / `<x>` |
| 12 | Phase 6's `noOrders` said "sits this session out" for the no-rows state too | Contract drift (with #5) | 6 | Split: `missing` → "No orders. C buys nothing this session.", `failed` → "sits this session out" |

Checked and found consistent (no edit): `test_paper_command.py` helpers (`synthetic_bars`, `fx_rate`, `_sessions`,
`STOCKS`) and `test_paper_check.py` world names are renamed by no phase; phase 1's `allowed_map` keeps empty sessions
and every caller uses `.get(S, frozenset())`; phase 4's candidate computation equals phase 5's test mirror; phase 6's
`checksNews(id, specObject)` reads `params->'spec'->>'object'`, which K4's `object_name` fills with `STRATEGY_C`;
dependencies all point backward; nothing is deleted by any phase.

Round 2: no interface contract moved between phases (no deletion, creation or rename changed owner; the H1 guard
lives inside phase 4's own module and phase 7 was already written against it), so no second round was needed.

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| D5 "the LLM model name it was started with" vs a code-computed digest that `paper` checks every night | The model is a code constant `FROZEN_MODEL = "glm-5.3"` in `CParams` (part of the digest); `veto` marks every verdict `failed` when `LLM_MODEL` differs. Changing models = a new id, as D5 intends | 1: invariant 2 + `plan_night`'s `check_digest` (stored digest must equal the code's) |
| §6 earnings dates | Included as a fact: Finnhub `calendar/earnings` per symbol over S..5th session (verified on the free key: JPM 2026-10-13, AAPL 2026-10-29); window length frozen in the spec; a calendar error makes the verdict `failed` | 5: handover §6 + measurement |
| §6 the prompt | `c-veto-v1` as written in K1, frozen into the digest (system text + user template) | 5: handover §6 |
| LLM call shape | `temperature: 0`, `thinking: {"type": "disabled"}`, `max_tokens: 1024`, timeout 30 s, 1 retry. Measured: default body with `max_tokens` 200 failed 2/3 on reasoning tokens; this body answered 3/3 in 1.6–1.7 s | 6: measurement |
| §6 time budget | ≈ 1 min nominal; worst case bounded by 3 consecutive failures and `timeout-minutes: 10` on the step; job stays 45 min | 6: measurement |
| §6 candidate count | Cap 10 kept: median 15, > 10 on 61.6 % of nights, ≈ 7.8 candidates/night after the cap | 6: measurement |
| §6 where candidates are computed | `strategies.c.candidates` is the one function; `veto` calls it on the windowed market at `rd.data_date`, `NewsVeto.picks` calls it inside `decide_bracket`/`run_rules` | 1: invariant 4 (same code path) |
| §6 catch-up nights | `veto` writes verdicts only for `rd.session_date`; `paper` uses any stored verdicts for earlier sessions and treats missing as `failed` | 5: handover §6 recommendation |
| §6 storage | ≈ 0.55 MB/month (163 rows × ≈ 3.4 KB); no retention needed | 6: measurement |
| Verdict map key | By session S (the session bought for), matching `news_vetoes.session_date`; `NewsVeto` looks up `next_session(data_date)` | 1: K2 column semantics |
| D9 checklist encoding | `backtest_gate.applicable = false` for C only (not part of the spec, so no digest moves); web `Gate.applicable` | 1: invariant 2 |
| `explain` for C | No code change (its SQL is engine-driven); covered by a test | 6: surrounding convention |
| Zero candidates | `veto` writes nothing; `paper` decides an empty list | 6: surrounding convention (`book_targets`: an empty decision writes no row) |
| `--require-sessions 5` and C's younger clock | Semantics unchanged (every roster strategy counts); the runbook says the v0.1.0 check therefore also waits for C's 5th session | 1: invariant 3 (`paper_check` semantics are the shipped contract); handover §1 keeps v0.1.0 out of scope |
| Neon | No phase writes to Neon; the nightly `Migrate` step applies `004` on the first scheduled run after the merge, and C's clock starts that night | 5: handover §4 "Out of scope" + D1 |
| Late verdicts (H1): may `veto` write after Paper decided the session? | No: exit 0, no network call, nothing written when the session's real runs row has `paper_status = 'success'`; re-checked in the write transaction. `running` / `failed` / NULL do not block (a failed Paper rolled back and its retry reads the verdicts) | 1: "reproducible replay" invariant (handover §2) — coordinator decision |
| Who owns `test_paper_check.py:51` / `test_paper_store.py:58` | Phase 2; phase 5 starts from them | 1: invariant 1 (every phase green on its own) — coordinator decision |
| Zero-candidate nights vs a check that did not run | No marker table. One neutral line: "No news check for {date}: A had no candidates, or the check did not run. C buys nothing this session." (`noCheckLine`), quoted by the runbook | 1: honest-reporting law (handover §2) + the "Zero candidates" decision below — coordinator decision |
| LLM call options in `veto` | `temperature=float(params.temperature)` (0.0), `thinking=params.thinking`, `max_tokens=params.max_tokens`, from `CParams`; the smoke uses the same | 3: phase 3's `complete()` signature (float) and phase 4's code — coordinator decision |
| `web/package_readme.md` | Phase 6 updates it (Step 16); phase 7 does not touch it | 1: invariant 9 (`web/**` is phase 6's) — coordinator decision |
| C's web look and C detection | `bg-butter` sheet + `var(--coral)` line (4th look), months sheet stone, up to 5 desktop card columns, `checksNews(id, specObject)` | 3: phase 6's code blocks; no other phase conflicts — coordinator decision |
| C's digest pin | `6cea6cb8…b762` stands (reproduced from phase 1's real code); if only C's pin fails, re-pin C from the printed digest | 3: phase 1/2 code blocks; legal because C has never been frozen — coordinator decision |
| Do the paper-clock resets delete `news_vetoes`? | No. Verdicts are inputs and a record; Paper and the replay read only sessions from the (new) `paper_start` on | 1: honest-reporting / closed-records law (handover §2), backed by phase 5's `reset()` code block (rung 3) |
| Finnhub client details beyond K5 (non-int `id` dropped, `Retry-After` cap 60 s, extra keywords) | Phase 3's code; K5 updated | 3: phase 3 code blocks |
| A `ValueError` from `complete()` counts toward the consecutive-failure stop in `veto` | Kept as phase 4 codes it (any exception is a network failure); unreachable with the frozen params | 3: phase 4 code block |
| Positions' "No orders" line for the no-rows state | "No orders. C buys nothing this session." (the failed state keeps "sits this session out") | 1: honest-reporting law (handover §2) |
| `timeout-minutes` on the Explain step (phase 7 suggestion) | Not adopted; Explain unchanged | 4: R3 scopes the workflow change to the Veto step |

## Open Questions

(none)

## Rollback

Per phase: revert its commit; phases 1–3 are additive modules/tests; phase 2's migration is additive
(drop `news_vetoes`, delete the `C` row only when nothing references it). As a whole: revert the merge;
if `004` already ran on Neon, C's rows can stay (unreferenced by code) or be removed with
`DELETE FROM news_vetoes WHERE strategy_id = 'C'` plus the paper-clock reset procedure for `C` in the
runbook. The four existing strategies are never affected.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f STRATEGY_C_NEWS_VETO_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f STRATEGY_C_NEWS_VETO_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan STRATEGY_C_NEWS_VETO_PLAN.md
