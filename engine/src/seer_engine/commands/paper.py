"""paper: paper-trade every roster strategy through each new session, after a successful bars run.

``python -m seer_engine [--dry-run] [-v] paper [--now ISO8601]``

Flow (handover D10, design §8, plan index C4):
  1. purge demo data if a demo run exists (own transaction; rolled back under --dry-run)
  2. rd = run_dates(now). The real runs row for rd.session_date must be ``success``; otherwise log
     and exit 1 with no paper writes (no paper step after a failed or missing bars run)
  3. read the roster rows (``store.read_roster_rows``) and resolve them into roster entries
     (``roster.from_rows``); a
     row whose object cannot be resolved stops the night with a named error and writes nothing
     (plan invariant 9). A ``status='retired'`` entry is then skipped deliberately: no orders, no
     equity snapshot, no ``paper_state`` step, and its ``paper_end`` is stamped with the last
     session it actually traded if it has none. For every **active** entry, a set paper_start
     under a different spec digest is refused (``store.check_digest``: a changed strategy needs a
     new id, handover D4). An active entry with no ``paper_start`` -- one just added to the
     roster -- starts tonight exactly as any new entry does (step 6).
  4. every active roster strategy already stepped through rd.data_date and every retirement
     already stamped: no-op, exit 0, nothing written (a re-run, a weekend or a holiday lands here)
  5. runs.paper_status = running (own transaction)
  6. ONE transaction: load the bars window; start new strategies (frozen spec + paper_start =
     rd.session_date, USD/IDR = the latest fx row on or before rd.data_date, day-0 snapshot at
     rd.data_date = prev_session(paper_start), the decision for paper_start); then for every
     session S after a strategy's last_session through rd.data_date, in order: splits applied on
     S, settle S (dividends, force-close), persist, decide next_session(S), persist; finally
     paper_status = success
  7. any exception in 3-6: rollback, paper_status = failed (own transaction), exit 1

Every session is computed on ``night_view(market, S, ...)``, the market as it stood on the night
of S:
- bars and FX dated after S are invisible;
- splits that executed after S are undone on the stored history, and on the stored dividends.

So catching up several sessions in one night takes the decisions the missed nights would have
taken. Undoing a split is exact only up to the 4-dp (bars) / 6-dp (dividends) rounding of the
stored rewrite; such sessions are inside the replay check's split-affected scope anyway.

Strategy C (``strategies.c.NewsVeto``) is decided like A, by ``decide_bracket``, on a copy of
its roster object that carries the verdicts ``veto`` stored for the sessions being decided
(``store.allowed_between``): only a symbol whose stored verdict is ``allow`` can be bought; a
``veto``, a ``failed`` verdict or no row at all is no trade (design §8). ``paper`` never calls the
network and never fails because of C's verdicts.

Evidence (migration 009, ``strategies.evidence``): every decision written tonight -- a bracket
entry's pending orders, a book entry's targets and its "would pick now" preview -- stores, per
symbol, the facts its method's formula read on that night's view (``_evidence``). The idle
instrument gets none. Evidence never changes a decision and never fails the night: an evidence
function that raises leaves that strategy's evidence NULL for the night and logs a warning.

Trade logic lives in ``paper.bracket``, ``paper.book`` and ``paper.benchmark`` (pure), and all
persistence in ``paper.store``; this module only sequences them.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

import psycopg

from seer_engine import dates, db, demo, http, runs
from seer_engine.backtest.market import Market
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.commands.nightly import _parse_now
from seer_engine.paper import roster, store
from seer_engine.paper.benchmark import SPY, step_benchmark
from seer_engine.paper.book import decide_book, needs_kickoff, settle_book
from seer_engine.paper.bracket import decide_bracket, settle_bracket
from seer_engine.paper.roster import RosterEntry
from seer_engine.paper.store import PaperState, StrategyRow
from seer_engine.sim import initial_cash_usd, new_portfolio
from seer_engine.strategies import evidence
from seer_engine.strategies.base import History, Strategy
from seer_engine.strategies.c import NewsVeto

log = logging.getLogger(__name__)

HELP = "Paper-trade the roster through every new session (runs after a successful bars run)"

MAX_ERROR_LEN = 2000

Splits = tuple[tuple[str, Decimal], ...]
Dividends = dict[str, dict[date, Decimal]]  # backtest.book_runner.DividendMap shape


class PaperError(RuntimeError):
    """A precondition of the paper step failed; the step is marked failed."""


@dataclass(frozen=True)
class Retired:
    """A ``status='retired'`` roster entry: tonight it takes no decisions at all.

    No orders, no equity snapshot, no ``paper_state`` step, and no row of its history is touched
    (plan invariant 4) -- it keeps every snapshot, order, book row and trade it ever wrote.

    ``paper_end`` is the last session it actually traded (``paper_state.last_session``), or None
    when it never started. ``stamp`` is True when the stored ``strategies.paper_end`` is still
    NULL and tonight must write it: that is the repair for a retirement taken by hand SQL, since
    ``store.retire`` stamps it at retirement time.
    """

    entry: RosterEntry
    paper_end: date | None
    stamp: bool


@dataclass(frozen=True)
class NightPlan:
    """What tonight does.

    ``start``: active roster entries with no paper state yet (they start tonight).
    ``step``: (entry, its state) for active entries whose last session is before rd.data_date.
    ``retired``: every retired entry, with the ``paper_end`` it has or needs. They trade nothing.
    """

    start: tuple[RosterEntry, ...]
    step: tuple[tuple[RosterEntry, PaperState], ...]
    retired: tuple[Retired, ...] = ()

    def empty(self) -> bool:
        """Nothing to write tonight.

        A retired entry keeps the night awake only while its ``paper_end`` is unstamped: once
        stamped it costs nothing every night thereafter, so a roster that is all-retired settles
        into the ordinary no-op.
        """
        return not self.start and not self.step and not any(r.stamp for r in self.retired)


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


def _error_text(e: BaseException) -> str:
    return http.redact(f"{type(e).__name__}: {e}")[:MAX_ERROR_LEN]


def execute(conn: psycopg.Connection, *, now: datetime, dry_run: bool = False) -> int:
    """Run one paper night against ``conn``. Returns the exit code (0 ok or no-op, 1 failed)."""
    demo.purge_demo_if_needed(conn, dry_run)

    rd = dates.run_dates(now)
    log.info("now %s -> data_date %s, session_date %s", now.isoformat(), rd.data_date, rd.session_date)

    try:
        bars_run = runs.real_run(conn, rd.session_date)
    finally:
        conn.rollback()
    if bars_run is None or bars_run.status != "success":
        found = "missing" if bars_run is None else bars_run.status
        log.error(
            "the bars run for session %s is %s; no paper step after a failed or missing bars run",
            rd.session_date,
            found,
        )
        return 1
    run_id = bars_run.id

    try:
        try:
            strategy_rows = store.read_roster_rows(conn)
            # The roster is data (phase 1). An entry whose object cannot be resolved raises here,
            # by name, and the whole night stops (plan invariant 9) -- that is NOT the deliberate
            # skip a retired entry gets below, and the two never share a code path or a log line.
            entries = roster.from_rows(strategy_rows)
            rows = {row.id: row for row in strategy_rows}
            states: dict[str, PaperState] = {}
            for e in entries:
                state = store.read_paper_state(conn, e.id)
                if state is not None:
                    states[e.id] = state
        finally:
            conn.rollback()
        plan = plan_night(entries, rows, states, rd)
        for r in plan.retired:
            log.info(
                "%s: retired; no orders, no equity snapshot, no paper_state step. paper_end %s%s",
                r.entry.id,
                "-" if r.paper_end is None else r.paper_end,
                " (stamped tonight)" if r.stamp else "",
            )
        if plan.empty():
            log.info(
                "every active roster strategy is stepped through %s; nothing to do", rd.data_date
            )
            return 0

        with db.transaction(conn, dry_run):
            runs.start_paper(conn, run_id)
        with db.transaction(conn, dry_run):
            _night(conn, rd, plan, run_id)
    except Exception as e:  # noqa: BLE001 - every failure must become a failed paper step
        message = _error_text(e)
        conn.rollback()
        log.error("paper failed for session %s: %s", rd.session_date, message)
        if dry_run:
            log.info("dry-run: would mark the paper step failed")
            return 1
        with db.transaction(conn, False):
            runs.fail_paper(conn, run_id, message)
        return 1
    if dry_run:
        log.info("dry-run: rolled back; nothing written")
    return 0


def plan_night(
    entries: Sequence[RosterEntry],
    rows: Mapping[str, StrategyRow],
    states: Mapping[str, PaperState],
    rd: dates.RunDates,
) -> NightPlan:
    """Which entries start tonight, which step, and which are retired, after the frozen-spec checks.

    A ``status='retired'`` entry is a **deliberate skip**: it is collected into ``NightPlan.retired``
    and takes no decision, no snapshot and no ``paper_state`` step. It is not an error, and it is
    not the same thing as an entry whose object cannot be resolved -- that one never reaches this
    function, because ``roster.from_rows`` raises before the plan exists and the night stops
    (plan invariant 9).

    Raises ``store.SpecMismatch`` when an **active** entry's set ``paper_start`` holds a spec
    digest other than the code's (handover D4: a changed strategy needs a new id). Raises
    PaperError when an entry has no ``strategies`` row, carries a status this night does not
    understand, has ``paper_start`` but no paper state (its clock must be reset first), has paper
    state but no ``paper_start``, or when the stored pending session is not the session after the
    last one stepped.
    """
    start: list[RosterEntry] = []
    step: list[tuple[RosterEntry, PaperState]] = []
    retired: list[Retired] = []
    for e in entries:
        row = rows.get(e.id)
        if row is None:
            raise PaperError(f"strategies row {e.id!r} is missing; run `migrate` (003) first")
        if row.status not in ("active", "retired"):
            raise PaperError(
                f"strategy {e.id!r} has status {row.status!r}; the paper night understands only "
                f"'active' and 'retired'"
            )
        state = states.get(e.id)
        if row.status == "retired":
            last_traded = None if state is None else state.last_session
            retired.append(
                Retired(
                    entry=e,
                    paper_end=row.paper_end if row.paper_end is not None else last_traded,
                    stamp=row.paper_end is None and last_traded is not None,
                )
            )
            continue
        store.check_digest(row, roster.strategy_params(e)["digest"])
        if state is None:
            if row.paper_start is not None:
                raise PaperError(
                    f"strategy {e.id!r} has paper_start {row.paper_start} but no paper_state; reset its "
                    f"paper clock (paper runbook) before it can start"
                )
            start.append(e)
            continue
        if row.paper_start is None:
            raise PaperError(f"strategy {e.id!r} has paper state but no paper_start")
        if state.last_session >= rd.data_date:
            continue
        expected = dates.next_session(state.last_session)
        if state.pending_session != expected:
            raise PaperError(
                f"strategy {e.id!r}: pending session {state.pending_session} is not the session "
                f"after its last one ({state.last_session} -> {expected})"
            )
        step.append((e, state))
    return NightPlan(start=tuple(start), step=tuple(step), retired=tuple(retired))


# ---- the market as it stood on the night of a session ------------------------------------------


def later_factors(
    splits_by_session: Mapping[date, Sequence[tuple[str, Decimal]]], session: date
) -> dict[str, Decimal]:
    """``{symbol: product of factors}`` over the applied splits that executed after ``session``."""
    out: dict[str, Decimal] = {}
    for executed, items in splits_by_session.items():
        if executed <= session:
            continue
        for symbol, factor in items:
            out[symbol] = out.get(symbol, Decimal(1)) * factor
    return out


def _undo_split(h: History, factor: Decimal) -> History:
    """``h`` in pre-split units: prices x factor, volume / factor (the inverse of the stored rewrite)."""
    f = float(factor)
    return History(h.symbol, h.dates, h.open * f, h.high * f, h.low * f, h.close * f, h.volume / f)


def night_view(market: Market, session: date, later: Mapping[str, Decimal]) -> Market:
    """``market`` as it stood on the night of ``session``.

    It keeps the bars and FX dated on or before ``session``. For each ``symbol: factor`` in
    ``later`` (splits that executed after ``session``), the symbol's history is put back in the
    units it had that night. Membership is point in time already and is shared.
    """
    history: dict[str, History] = {}
    for symbol, h in market.history.items():
        cut = h.upto(session)
        factor = later.get(symbol)
        if factor is not None and len(cut):
            cut = _undo_split(cut, factor)
        history[symbol] = cut
    fx = tuple(row for row in market.fx if row[0] <= session)
    return replace(market, history=history, fx=fx)


@dataclass
class _Tonight:
    """Everything tonight reads: the bars window, splits and dividends by session, cached views."""

    market: Market
    splits: Mapping[date, Splits]
    dividends: Mapping[str, Mapping[date, Decimal]]  # store.dividends_between over the window
    views: dict[date, Market] = field(default_factory=dict)

    def view(self, session: date) -> Market:
        v = self.views.get(session)
        if v is None:
            v = night_view(self.market, session, later_factors(self.splits, session))
            self.views[session] = v
        return v

    def splits_on(self, session: date) -> Splits:
        return tuple(self.splits.get(session, ()))

    def dividends_on(self, session: date) -> Dividends:
        """The dividends going ex on ``session`` as a DividendMap, in that night's units (a later
        applied split's rewrite of the stored amount undone, 6 dp)."""
        later = later_factors(self.splits, session)
        out: Dividends = {}
        for symbol, by_date in self.dividends.items():
            amount = by_date.get(session)
            if amount is None:
                continue
            factor = later.get(symbol)
            if factor is not None:
                amount = (amount * factor).quantize(store.DIVIDEND_QUANTUM, rounding=ROUND_HALF_UP)
            out[symbol] = {session: amount}
        return out


# ---- the night -------------------------------------------------------------------------------


def _check_window(since: date, earliest: date, entries: Sequence[RosterEntry]) -> None:
    need = max((e.lookback for e in entries), default=0)
    have = len(dates.sessions(since, earliest))
    if have < need:
        raise PaperError(
            f"the bars window {since}..{earliest} holds {have} sessions, fewer than the roster's "
            f"longest lookback ({need}); raise store.MARKET_WINDOW_DAYS"
        )


def _night(conn: psycopg.Connection, rd: dates.RunDates, plan: NightPlan, run_id: int) -> None:
    """The single paper transaction's body (the caller's db.transaction commits or rolls back).

    Retirements are settled first and cost nothing: a retired strategy keeps every history row it
    ever wrote, and the only column tonight may write for it is ``paper_end`` (invariant 4). The
    market window is loaded only when something actually trades, so an all-retired roster is a
    cheap night, not a crash.
    """
    for r in plan.retired:
        if not r.stamp or r.paper_end is None:
            continue
        store.set_paper_end(conn, r.entry.id, r.paper_end)
        log.info(
            "%s: paper_end %s, the last session it traded; its history is kept",
            r.entry.id,
            r.paper_end,
        )
    if plan.start or plan.step:
        _trade(conn, rd, plan)
    runs.finish_paper(conn, run_id)


def _trade(conn: psycopg.Connection, rd: dates.RunDates, plan: NightPlan) -> None:
    """Start and step every active entry on tonight's bars window. Never called with nothing to do."""
    lasts = [state.last_session for _, state in plan.step]
    if plan.start:
        lasts.append(rd.data_date)
    earliest = min(lasts)
    since = store.market_window_since(earliest)  # earliest - store.MARKET_WINDOW_DAYS (550) days
    _check_window(since, earliest, list(plan.start) + [e for e, _ in plan.step])

    market = store.load_market_window(conn, since)
    window = dates.sessions(dates.next_session(earliest), rd.data_date)
    tonight = _Tonight(
        market=market,
        splits={s: store.applied_splits_on(conn, s) for s in window},
        dividends=store.dividends_between(conn, window[0], window[-1]) if window else {},
    )
    log.info(
        "bars window since %s; %d session(s) to step (%s..%s)",
        since,
        len(window),
        window[0] if window else "-",
        window[-1] if window else "-",
    )

    for e in plan.start:
        _start(conn, e, rd, tonight)
    starts = {row.id: row.paper_start for row in store.read_strategies(conn)}
    for e, state in plan.step:
        sessions = dates.sessions(dates.next_session(state.last_session), rd.data_date)
        if e.engine == "bracket":
            _step_bracket(conn, e, sessions, tonight)
        elif e.engine == "book":
            _step_book(conn, e, sessions, tonight, state, starts[e.id])
        elif e.engine == "benchmark":
            _step_benchmark(conn, e, sessions, tonight)
        else:
            raise PaperError(f"strategy {e.id!r} has unknown engine {e.engine!r}")


_PAPER_ROWS_SQL = """
    SELECT EXISTS (SELECT 1 FROM orders WHERE strategy_id = %(id)s)
        OR EXISTS (SELECT 1 FROM equity_snapshots WHERE strategy_id = %(id)s)
        OR EXISTS (SELECT 1 FROM book_positions WHERE strategy_id = %(id)s)
        OR EXISTS (SELECT 1 FROM book_targets WHERE strategy_id = %(id)s)
        OR EXISTS (SELECT 1 FROM book_fills WHERE strategy_id = %(id)s)
        OR EXISTS (SELECT 1 FROM book_trades WHERE strategy_id = %(id)s)
"""


def _has_paper_rows(conn: psycopg.Connection, strategy_id: str) -> bool:
    return bool(conn.execute(_PAPER_ROWS_SQL, {"id": strategy_id}).fetchone()[0])


def _bracket_strategy(conn: psycopg.Connection, e: RosterEntry, first: date, last: date) -> Strategy:
    """The strategy object ``decide_bracket`` gets for ``e`` when it decides sessions ``first`` ..
    ``last`` (inclusive).

    Every bracket entry but C: ``e.obj`` unchanged. C (a ``NewsVeto``): ``e.obj`` carrying the
    ``allow`` verdicts stored for those sessions (``store.allowed_between``), so a candidate with
    a ``veto`` or ``failed`` verdict, or with no verdict row, is not bought (handover D6, D8).
    """
    if not isinstance(e.obj, NewsVeto):
        return e.obj
    return e.obj.with_allowed(store.allowed_between(conn, e.id, first, last))


Facts = tuple[str, ...]


def _evidence(e: RosterEntry, market: Market, data_date: date, symbols: Iterable[str]) -> dict[str, Facts]:
    """``{symbol: facts}`` for the symbols ``e`` just decided on ``market`` (the decision's own
    night view) and ``data_date``, through ``strategies.evidence.evidence_for``.

    The idle instrument (``e.rules.idle_symbol``) is never asked for and never gets evidence.
    A symbol the method cannot explain is absent (stored NULL). Never raises (plan invariant 5):
    any exception -- an unknown object name, a bug in an evidence function, a malformed result --
    logs one warning and returns ``{}``, so the decision is stored with NULL evidence and the
    night goes on. Nothing here feeds back into a decision.
    """
    idle = None if e.rules is None else e.rules.idle_symbol
    wanted = tuple(dict.fromkeys(s for s in symbols if s != idle))
    if not wanted:
        return {}
    try:
        found = evidence.evidence_for(e.object_name, market, e.params, data_date, wanted)
        if not isinstance(found, Mapping):
            raise TypeError(f"evidence_for returned {type(found).__name__}, not a mapping")
        out: dict[str, Facts] = {}
        for symbol in wanted:
            facts = found.get(symbol)
            if facts is None:
                continue
            if isinstance(facts, str):
                raise TypeError(f"{symbol}: facts must be a sequence of strings, got a str")
            items = tuple(facts)
            for f in items:
                if not isinstance(f, str) or not f.strip():
                    raise TypeError(f"{symbol}: every fact must be a non-empty string, got {f!r}")
            if items:
                out[symbol] = items
        return out
    except Exception as exc:  # noqa: BLE001 - evidence must never fail the night (invariant 5)
        log.warning(
            "%s %s: no evidence stored tonight (%s); the decision is unchanged",
            e.id,
            data_date,
            _error_text(exc),
        )
        return {}


def _start(conn: psycopg.Connection, e: RosterEntry, rd: dates.RunDates, tonight: _Tonight) -> None:
    """Start ``e`` tonight.

    ``store.freeze_spec`` writes the frozen spec (C2) and ``paper_start = rd.session_date``;
    ``store.init_paper_state`` writes ``paper_state`` and the day-0 snapshot at
    ``prev_session(paper_start)`` (= ``rd.data_date``); then the decision for ``paper_start`` is
    written and ``paper_state.pending_session`` set to it (every engine, SPY included).
    """
    if _has_paper_rows(conn, e.id):
        raise PaperError(
            f"strategy {e.id!r} has no paper_state but has paper rows; reset its paper clock "
            f"(paper runbook) before it can start"
        )
    view = tonight.view(rd.data_date)
    try:
        usd_idr = view.usd_idr_on(rd.data_date)
    except ValueError as exc:
        raise PaperError(f"no USD/IDR rate on or before {rd.data_date}; cannot start {e.id!r}") from exc
    cash0 = initial_cash_usd(INITIAL_IDR, usd_idr)
    paper_start = rd.session_date

    frozen = roster.strategy_params(e)
    store.freeze_spec(
        conn,
        e.id,
        spec=frozen["spec"],
        digest=frozen["digest"],
        backtest_gate=frozen["backtest_gate"],
        paper_start=paper_start,
    )
    store.init_paper_state(conn, e.id, paper_start=paper_start, cash0=cash0, usd_idr=usd_idr)

    if e.engine == "bracket":
        sized = decide_bracket(
            new_portfolio(cash0),
            _bracket_strategy(conn, e, paper_start, paper_start),
            e.params,
            view.history,
            view.membership.members_on(rd.data_date),
            rd.data_date,
        )
        facts = _evidence(e, view, rd.data_date, (o.symbol for o in sized.placed))
        store.insert_pending_orders(conn, e.id, sized.placed, evidence=facts)
        store.write_pending(conn, e.id, paper_start, decision=False)
    elif e.engine == "book":
        kickoff = needs_kickoff(e.rules, paper_start, paper_start, None)
        targets, _ = decide_book(view, e.obj, e.params, e.rules, rd.data_date, frozenset(), force=kickoff)
        facts = None if targets is None else _evidence(e, view, rd.data_date, (t.symbol for t in targets))
        store.save_book_decision(conn, e.id, paper_start, targets, evidence=facts)
        if kickoff:
            store.write_kickoff(conn, e.id, paper_start)
        store.save_book_preview(conn, e.id, rd.data_date, targets, evidence=facts)
    elif e.engine == "benchmark":
        store.write_pending(conn, e.id, paper_start, decision=False)
    else:
        raise PaperError(f"strategy {e.id!r} has unknown engine {e.engine!r}")
    log.info("%s: paper starts %s with %s USD (USD/IDR %s)", e.id, paper_start, cash0, usd_idr)


def _step_bracket(conn: psycopg.Connection, e: RosterEntry, sessions: Sequence[date], tonight: _Tonight) -> None:
    pf = store.load_portfolio(conn, e.id)
    if not sessions:
        return
    strategy = _bracket_strategy(conn, e, dates.next_session(sessions[0]), dates.next_session(sessions[-1]))
    for s in sessions:
        view = tonight.view(s)
        night = settle_bracket(pf, s, view.bars_on(s, pf.held_symbols()), tonight.splits_on(s), view.last_bar_date)
        store.save_bracket_night(conn, e.id, night.portfolio, night.events, night.snapshot)
        sized = decide_bracket(night.portfolio, strategy, e.params, view.history, view.membership.members_on(s), s)
        facts = _evidence(e, view, s, (o.symbol for o in sized.placed))
        store.insert_pending_orders(conn, e.id, sized.placed, evidence=facts)
        store.write_pending(conn, e.id, dates.next_session(s), decision=False)
        pf = sized.portfolio
        log.info("%s %s: equity %s, %d live order(s)", e.id, s, pf.equity, len(pf.orders))


def _step_book(
    conn: psycopg.Connection,
    e: RosterEntry,
    sessions: Sequence[date],
    tonight: _Tonight,
    state: PaperState,
    paper_start: date,
) -> None:
    rules = e.rules
    loaded = store.load_book(conn, e.id, idle_symbol=rules.idle_symbol)
    book, targets, idle_added = loaded.book, loaded.targets, loaded.idle_added
    kicked = state.kickoff_session
    for s in sessions:
        view = tonight.view(s)
        symbols = set(book.held())
        if targets is not None:
            symbols.update(t.symbol for t in targets)
        night = settle_book(
            book,
            s,
            view.bars_on(s, sorted(symbols)),
            targets,
            idle_added,
            rules,
            tonight.dividends_on(s),
            tonight.splits_on(s),
            view.last_bar_date,
        )
        store.save_book_night(
            conn, e.id, night.book, night.fills, night.trades, night.snapshot, executed_targets=night.targets
        )
        book = night.book
        nxt = dates.next_session(s)
        # A book that has never decided ranks on its first session instead of waiting for its
        # cadence (008, paper.book.needs_kickoff); the replay ranks on the stored kickoff too.
        kickoff = needs_kickoff(rules, paper_start, nxt, kicked)
        targets, idle_added = decide_book(view, e.obj, e.params, rules, s, book.held(), force=kickoff)
        facts = None if targets is None else _evidence(e, view, s, (t.symbol for t in targets))
        store.save_book_decision(conn, e.id, nxt, targets, evidence=facts)
        if kickoff:
            store.write_kickoff(conn, e.id, nxt)
            kicked = nxt
        if s == sessions[-1]:
            # What it would pick if it ranked tonight: display only, never traded or replayed.
            preview, preview_facts = targets, facts
            if preview is None:
                preview, _ = decide_book(view, e.obj, e.params, rules, s, book.held(), force=True)
                preview_facts = None if preview is None else _evidence(e, view, s, (t.symbol for t in preview))
            store.save_book_preview(conn, e.id, s, preview, evidence=preview_facts)
        log.info(
            "%s %s: equity %s, %d position(s)%s",
            e.id,
            s,
            book.equity,
            len(book.positions),
            f", {len(targets)} target(s) for {nxt}" if targets is not None else "",
        )


def _step_benchmark(conn: psycopg.Connection, e: RosterEntry, sessions: Sequence[date], tonight: _Tonight) -> None:
    bench = store.load_benchmark(conn, e.id)
    for s in sessions:
        view = tonight.view(s)
        bar = view.bar(SPY, s)
        if bar is None:
            raise PaperError(f"no {SPY} bar on {s}; the benchmark is marked every session")
        split = dict(tonight.splits_on(s)).get(SPY)  # an applied SPY split goes through split_benchmark (C3)
        dividend = tonight.dividends_on(s).get(SPY, {}).get(s)
        bench, snapshot, fills = step_benchmark(bench, s, bar, dividend, split=split)
        store.save_benchmark_night(conn, e.id, bench, snapshot, fills)
        store.write_pending(conn, e.id, dates.next_session(s), decision=False)
        log.info("%s %s: equity %s", e.id, s, snapshot.equity_usd)
