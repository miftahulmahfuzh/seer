"""``promote``: put a lab method's pre-registered variant on the paper roster.

The lab→roster bridge (plan roster-promotion-pipeline, phase 5; Decisions D1, D3, D6)::

    python -m seer_engine promote --method M0005 --candidate M0005-ALL --id FND \\
        --name "FND · Fundamentals" --sub "Top 20 on filed fundamentals, monthly" \\
        --gate-note "..." [--icon book-open] [--sort 6] \\
        [--retire F1-SPY-SMA200-M] [--lab-status-stays] [--dry-run]

**Promotable** means three things, and this command refuses anything that is not all three:

1. the method file exposes the variant as a ``Candidate`` -- a frozen (rules, allocator, params)
   triple. The roster entry is that triple unchanged; nothing here invents a parameter.
2. the variant's allocator is a value ``paper.roster.RESOLVER`` names. A ``strategies`` row
   cannot hold a live Python object, and the object's *name* is part of the frozen spec, so an
   object the resolver cannot name has no roster identity. The refusal says which line to add.
3. that name has an entry in ``strategies.evidence.EVIDENCE``: the plain-English facts behind
   each pick, which the paper night stores and ``explain`` turns into the site's "Why this
   pick". A strategy that cannot say why it picked a stock does not go on the site.

**What it writes.** One ``strategies`` row: the display columns, the definition columns migration
006 added (``object_name``, ``registry_id`` NULL, ``gate_note``, ``gate_applicable``) --
``paper.roster.from_row`` refuses a row without them, so leaving one out would fail the next
paper night for the whole board -- plus ``status='active'``, ``promoted_from=<method id>``,
the full contract-C2 ``params`` (spec, digest, backtest_gate), and **no** ``paper_start``. The row
is read back and rebuilt through ``roster.from_row`` inside the same transaction before it
commits, so a row the paper night would refuse is never written. The
next paper night starts it through ``paper.store.freeze_spec`` exactly as any new entry starts,
which is what keeps the paper record honest: a promoted strategy's track record begins when it
was promoted. With ``--retire`` the outgoing strategy's ``status`` becomes ``'retired'`` **in the
same transaction**, so the board never shows five active horsemen or three.

**What it never writes.** ``backtest.registry.REGISTRY`` (Decisions D1: it is the P7a dev-run
candidate set, *fixed BEFORE the run*, capped at ``dev.MAX_CANDIDATES``, with ``candidate_digest``
pinned; appending would corrupt the multiple-testing count the lab's ``trials`` table exists to
maintain). A promoted method reaches the roster through the roster's own resolver, the same way
``A`` and ``C`` do. Also never: ``paper_start``, any paper history row, any ``trials`` row, any
lab ``source_sha``, and any ``TRANSITIONS`` edge that is not already there.

**Two databases, one promotion.** The roster is Neon, the lab is ``lab/lab.sqlite``; they cannot
share a transaction. So: the lab's rules are checked first and write nothing, then the roster
transaction commits, then the lab record commits. The only possible partial outcome is "roster
written, lab note missing", and re-running the identical command repairs it -- the roster insert
is skipped for a row this promotion already owns, and ``lab.store.record_promotion`` is
idempotent. The reverse order was rejected: a lab note for a promotion that did not happen cannot
be taken back, because the lab is append-only.

Exit 0 on success; 2 when a rule refuses the request; 1 on any other error.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from dataclasses import fields as dc_fields
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from seer_engine import config, dates, db
from seer_engine.lab import store as lab_store
from seer_engine.paper import roster
from seer_engine.paper import store as paper_store
from seer_engine.sim.rules import PRESETS, TradeRules
from seer_engine.strategies import evidence

log = logging.getLogger(__name__)

HELP = "Promote a lab method's variant onto the paper roster (lab -> strategies)"

DEFAULT_ICON = "flask-conical"  # lucide name; the web renders strategies.icon


class PromoteError(RuntimeError):
    """`promote` refused the request (exit 2)."""


class NotPromotable(PromoteError):
    """The named method or variant cannot become a roster entry as it stands."""


class AlreadyStarted(PromoteError):
    """The target roster id has a paper_start: invariant 3, add never mutate."""


class RosterConflict(PromoteError):
    """The target roster id exists and is not this promotion's own unfrozen row."""


# --------------------------------------------------------------------------- the promotable check


def object_name_of(obj: object) -> str:
    """The roster resolver's stable name for ``obj`` (the inverse of ``roster.RESOLVER``).

    ``roster.RESOLVER`` maps a name to a ``roster.Binding``; the live object is ``binding.obj``,
    which is ``None`` for the benchmark and is therefore never matched here.

    NotPromotable when no name maps to it (the message names the entry to add) or when more than
    one does (the name is in the frozen spec, so an object with two names has two digests).
    """
    names = sorted(n for n, b in roster.RESOLVER.items() if b.obj is not None and b.obj is obj)
    if len(names) == 1:
        return names[0]
    module = type(obj).__module__
    where = f"{module}.{type(obj).__qualname__}"
    ident = getattr(obj, "id", "?")
    if not names:
        raise NotPromotable(
            f"the roster resolver has no name for <{ident}> ({where}). A promotable method's "
            f"allocator must be a module-level object that seer_engine/paper/roster.py's RESOLVER "
            f"names, because the name is part of the frozen spec and a database row cannot hold a "
            f"live object. Add one entry to RESOLVER -- \"<A_STABLE_NAME>\": Binding(obj="
            f"{module.rsplit('.', 1)[-1]}.<THE MODULE-LEVEL NAME>, params=<its params>) -- commit "
            f"it, then promote again."
        )
    raise NotPromotable(
        f"the roster resolver gives <{ident}> ({where}) {len(names)} names "
        f"({', '.join(names)}); a roster object must have exactly one, because the name is part "
        f"of the frozen spec digest"
    )


def fractional_twin(rules: TradeRules) -> TradeRules:
    """The ``sim.rules`` preset that is ``rules`` in fractional shares (``--fractional``).

    Gotrade takes fractional limit orders (owner, 2026-10-07), so a book method may trade its lab
    variant in fractional shares: the same rules but for ``fractional`` and the id naming them.
    NotPromotable when no preset is that twin (add one to ``sim.rules.PRESETS`` first).
    """
    if rules.fractional:
        return rules
    same = [f.name for f in dc_fields(rules) if f.name not in ("id", "fractional")]
    for r in PRESETS:
        if r.fractional and all(getattr(r, n) == getattr(rules, n) for n in same):
            return r
    raise NotPromotable(
        f"--fractional: sim.rules has no fractional preset matching {rules.id!r}; add one to PRESETS "
        f"(as monthly-hold-frac is monthly-hold with fractional=True), commit it, then promote again."
    )


def _check_rules(rules: TradeRules) -> None:
    """NotPromotable when ``rules`` is not the ``sim.rules`` preset of its own id.

    ``roster.from_row`` rebuilds a roster entry's rules with ``roster.rules_for(row.rules_id)``,
    which answers out of ``PRESETS``. A candidate carrying a one-off ``TradeRules`` would be
    frozen under its own rules and read back under the preset's, and the difference would surface
    as a ``store.SpecMismatch`` on the strategy's first paper night rather than here.
    """
    preset = roster.rules_for(rules.id)  # raises roster.UnknownRules for an unknown id
    if preset != rules:
        raise NotPromotable(
            f"this variant's rules are id {rules.id!r} but are not the sim.rules preset of that "
            f"id; a roster row carries only the id, so the spec would be frozen under one rule "
            f"set and read back under another. Promote a variant that uses a preset, or add this "
            f"rule set to sim.rules.PRESETS first"
        )


def _check_evidence(object_name: str) -> None:
    """NotPromotable when ``object_name`` has no entry in ``strategies.evidence.EVIDENCE``.

    The paper night stores each pick's evidence and ``explain`` writes the site's "Why this pick"
    from it, using only those facts. A roster object without an evidence function would put picks
    on the site with no reason at all, so the gap is refused here rather than discovered there.
    """
    if not evidence.has_evidence(object_name):
        raise NotPromotable(
            f"{object_name} has no per-pick evidence, so the site could not say why it picked a "
            f"stock. Add an entry \"{object_name}\": <its evidence function> to EVIDENCE in "
            f"seer_engine/strategies/evidence.py (2-6 plain-English facts per pick, numbers "
            f"formatted), commit it, then promote again."
        )


def find_candidate(method_id: str, candidate_id: str | None) -> tuple[Any, Path, Any]:
    """(METHOD, file path, the chosen Candidate) for a committed lab method.

    NotPromotable when there is no method file, when a multi-variant method is named without
    ``--candidate``, or when the named variant is not one of the method's.
    """
    from seer_engine.lab.method import discover

    methods = discover()
    if method_id not in methods:
        raise NotPromotable(
            f"no method file for {method_id} in seer_engine/lab/methods/. A promotable method is a "
            f"committed mNNNN_<slug>.py exporting METHOD = Method(...): the roster entry is built "
            f"from one of its Candidates, so a lab database row alone is not enough. "
            f"Known: {', '.join(methods) or '(none)'}"
        )
    method, path = methods[method_id]
    ids = tuple(c.id for c in method.candidates)
    if candidate_id is None:
        if len(ids) != 1:
            raise NotPromotable(
                f"{method_id} has {len(ids)} variants ({', '.join(ids)}); they are different "
                f"algorithms, so name the one to promote with --candidate"
            )
        return method, path, method.candidates[0]
    found = [c for c in method.candidates if c.id == candidate_id]
    if len(found) != 1:
        raise NotPromotable(
            f"{method_id} has no variant {candidate_id!r}; its variants are {', '.join(ids)}"
        )
    return method, path, found[0]


def check_lookback(lookback: int, data_date: date) -> None:
    """NotPromotable when the night's bar window is shorter than ``lookback``.

    ``commands/paper.py:_check_window`` raises the same refusal at 23:00 on the night this entry
    would first trade. Raising it at promotion time instead means the roster never holds an entry
    the night cannot feed.
    """
    since = paper_store.market_window_since(data_date)
    have = len(dates.sessions(since, data_date))
    if lookback > have:
        raise NotPromotable(
            f"this variant reads {lookback} bars through a data date, but the paper night's bar "
            f"window {since}..{data_date} holds {have} sessions; raise "
            f"paper.store.MARKET_WINDOW_DAYS (now {paper_store.MARKET_WINDOW_DAYS}) before "
            f"promoting it"
        )


# --------------------------------------------------------------------------- the plan


@dataclass(frozen=True)
class Promotion:
    """Everything the two databases will be asked to write, computed before either is touched."""

    entry: roster.RosterEntry
    params: dict[str, Any]  # roster.strategy_params(entry): {spec, digest, backtest_gate}
    method_id: str
    candidate_id: str
    retire_id: str | None
    sort: int

    @property
    def digest(self) -> str:
        return str(self.params["digest"])


def build_promotion(args: argparse.Namespace, data_date: date, sort: int) -> Promotion:
    """The roster entry and its contract-C2 params, from the named method variant. No I/O."""
    _method, _path, candidate = find_candidate(args.method, args.candidate)
    obj = candidate.allocator
    rules = fractional_twin(candidate.rules) if getattr(args, "fractional", False) else candidate.rules
    _check_rules(rules)
    object_name = object_name_of(obj)
    _check_evidence(object_name)
    engine = "bracket" if rules.engine == "bracket_v0" else "book"
    lookback = obj.lookback if engine == "bracket" else obj.lookback(candidate.params)
    check_lookback(int(lookback), data_date)
    entry = roster.RosterEntry(
        id=args.id,
        name=args.name,
        sub=args.sub,
        icon=args.icon,
        is_champion=False,  # the champion is SPY (handover D2); a promotion never takes it
        is_benchmark=False,
        sort=sort,
        engine=engine,
        rules=rules,
        obj=obj,
        object_name=object_name,
        params=candidate.params,
        registry_id=None,  # D1: a promoted entry is never a REGISTRY entry
        lookback=int(lookback),
        gate_note=args.gate_note,
        gate_applicable=not args.gate_not_applicable,
    )
    return Promotion(
        entry=entry,
        params=roster.strategy_params(entry),
        method_id=args.method,
        candidate_id=candidate.id,
        retire_id=args.retire,
        sort=sort,
    )


def render_plan(p: Promotion, *, retire_end: date | None, lab_status: str, lab_move: bool) -> str:
    """Every row the promotion writes, as text. Printed on every run, dry or not."""
    e = p.entry
    out = [
        f"promote {p.candidate_id} -> paper roster id {e.id}",
        "",
        "  strategies INSERT",
        f"    id             {e.id}",
        f"    name           {e.name}",
        f"    sub            {e.sub}",
        f"    icon           {e.icon}",
        "    is_champion    false",
        "    is_benchmark   false",
        f"    sort           {p.sort}",
        f"    engine         {e.engine}",
        f"    rules_id       {e.rules_id}",
        f"    object_name    {e.object_name}  (a paper.roster.RESOLVER key)",
        "    registry_id    NULL  (Decisions D1: a promoted entry is never a REGISTRY entry)",
        f"    gate_note      {e.gate_note}",
        f"    gate_applicable {str(e.gate_applicable).lower()}",
        "    status         active",
        f"    promoted_from  {p.method_id}",
        "    paper_start    NULL  (the next paper night freezes the spec and starts the clock)",
        f"    params.digest  {p.digest}",
        f"    params.spec    {roster.spec_text(p.params['spec'])}",
        f"    params.backtest_gate {p.params['backtest_gate']}",
    ]
    if p.retire_id is not None:
        end = "NULL (never traded)" if retire_end is None else str(retire_end)
        out += [
            "",
            f"  strategies UPDATE {p.retire_id}",
            "    status         retired",
            f"    paper_end      {end}",
            "    (same transaction as the INSERT: the swap is atomic)",
        ]
    out += [
        "",
        f"  lab/lab.sqlite, method {p.method_id} (now {lab_status!r})",
        "    methods.analysis  += a dated '# Promotion' section",
        f"    insights          += [observation] "
        f"'<method name> starts paper trading as {e.id}' (plain words)",
        "    methods.status    "
        + ("test-passed -> paper" if lab_move and lab_status == "test-passed"
           else f"{lab_status} (unchanged)"),
        "",
        "  backtest.registry.REGISTRY  untouched (Decisions D1)",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------- the roster write


def _next_sort(conn) -> int:
    return int(conn.execute("SELECT coalesce(max(sort), 0) + 1 FROM strategies").fetchone()[0])


def _check_target(conn, p: Promotion) -> bool:
    """True when the row must be inserted, False when this promotion already owns an unfrozen one.

    AlreadyStarted when the id has a ``paper_start`` (invariant 3: add, never mutate -- a changed
    strategy is a new id with its own paper clock). RosterConflict when the id exists but is not
    this promotion's own row.
    """
    row = paper_store.read_strategy(conn, p.entry.id)
    if row is None:
        return True
    if row.paper_start is not None:
        raise AlreadyStarted(
            f"{p.entry.id} already has paper_start {row.paper_start}: a started strategy is never "
            f"re-pointed at another algorithm, because months of track record would then belong "
            f"to code that did not earn it. Promote under a new roster id (and --retire "
            f"{p.entry.id} if it is being replaced)."
        )
    # `promoted_from` is on the StrategyRow phase 2 already reads here; a second SELECT would be
    # the same value with a row-factory assumption attached.
    if row.promoted_from == p.method_id and row.params.get("digest") == p.digest:
        log.info(
            "%s already exists unfrozen from %s with the same digest; re-recording the lab side",
            p.entry.id, p.method_id,
        )
        return False
    raise RosterConflict(
        f"{p.entry.id} already exists (promoted_from {row.promoted_from!r}, digest "
        f"{row.params.get('digest')!r}) and is not this promotion's row (promoted_from "
        f"{p.method_id!r}, digest {p.digest!r}); choose another roster id"
    )


def _insert(conn, p: Promotion) -> None:
    """Write the roster row, then prove the paper night can read it back.

    **Every definition column migration 006 added is written here.** ``object_name``,
    ``gate_note`` and ``gate_applicable`` are not display sugar: ``roster.from_row`` reads them off
    the row and raises ``UnknownObject`` / ``BadRosterRow`` without them, which would make the very
    next paper night fail for the whole board (plan invariant 9) rather than for this row alone.
    ``registry_id`` is NULL by construction (D1: a promoted entry is never a REGISTRY entry).
    """
    conn.execute(
        "INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, "
        "rules_id, object_name, registry_id, gate_note, gate_applicable, status, promoted_from, "
        "params) "
        "VALUES (%s, %s, %s, %s, false, false, %s, %s, %s, %s, NULL, %s, %s, 'active', %s, %s)",
        (
            p.entry.id,
            p.entry.name,
            p.entry.sub,
            p.entry.icon,
            p.sort,
            p.entry.engine,
            p.entry.rules_id,
            p.entry.object_name,
            p.entry.gate_note,
            p.entry.gate_applicable,
            p.method_id,
            Jsonb(p.params),
        ),
    )
    # The round trip, inside the transaction: read the row back exactly as `paper` will and build
    # an entry from it. Any RosterError aborts the promotion with the night's own message, so a
    # row the night would refuse is never committed. Phase 1 asked for this hook by name.
    written = paper_store.read_strategy(conn, p.entry.id)
    rebuilt = roster.from_row(written)
    if roster.strategy_params(rebuilt)["digest"] != p.digest:
        raise PromoteError(
            f"{p.entry.id}: the row just written rebuilds to digest "
            f"{roster.strategy_params(rebuilt)['digest']!r}, not {p.digest!r}; the promotion was "
            f"rolled back. The row and the code disagree about what this strategy is"
        )


# --------------------------------------------------------------------------- CLI


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--method", required=True, metavar="M0001",
                   help="the lab method whose variant is promoted (its file must be committed)")
    p.add_argument("--candidate", default=None, metavar="M0001-A",
                   help="which variant; required when the method has more than one")
    p.add_argument("--id", required=True, metavar="FND",
                   help="the new roster id (its own paper clock; never an existing started id)")
    p.add_argument("--name", required=True, help="display name, e.g. 'FND · Fundamentals'")
    p.add_argument("--sub", required=True, help="display subtitle, one line")
    p.add_argument("--icon", default=DEFAULT_ICON, help=f"lucide icon name (default {DEFAULT_ICON})")
    p.add_argument("--sort", type=int, default=None,
                   help="display order (default: one past the current maximum)")
    p.add_argument("--gate-note", required=True,
                   help="the honest backtest-gate sentence, in the style of the roster's "
                        "neighbours. No roster entry has passed a gate; say what happened")
    p.add_argument("--gate-not-applicable", action="store_true",
                   help="the quant backtest gate does not apply to this entry (an LLM strategy, "
                        "as C is); it still counts as not passed")
    p.add_argument("--fractional", action="store_true",
                   help="trade the variant in fractional shares: its rules' fractional preset "
                        "(e.g. monthly-hold -> monthly-hold-frac). Gotrade takes fractional limit "
                        "orders; its take-profit/stop-loss order needs whole shares")
    p.add_argument("--retire", default=None, metavar="ID",
                   help="retire this strategy in the same transaction as the insert")
    p.add_argument("--lab-db", type=Path, default=lab_store.DB_PATH,
                   help="lab database (default: lab/lab.sqlite, or $SEER_LAB_DB)")
    p.add_argument("--lab-status-stays", action="store_true",
                   help="record the promotion but leave the method's lab status alone. Required "
                        "when the method is not at 'test-passed', because TRANSITIONS has no edge "
                        "to 'paper' from anywhere else. An acknowledgement that the roster is "
                        "taking a method the lab has not passed")


def run(args: argparse.Namespace) -> int:
    try:
        return _run(args)
    except (PromoteError, roster.RosterError, lab_store.LabError, paper_store.StoreError) as e:
        log.error("%s", e)
        return 2


def _run(args: argparse.Namespace) -> int:
    if args.retire == args.id:
        raise PromoteError(f"--retire {args.retire} is the id being promoted; nothing to swap")
    if not args.gate_note.strip():
        raise PromoteError("--gate-note must say what the backtest gate did; no entry has passed one")

    data_date = dates.run_dates(datetime.now(timezone.utc)).data_date

    lab_conn = lab_store.connect(args.lab_db)
    try:
        method_row = lab_store.get_method(lab_conn, args.method)
        if method_row is None:
            raise lab_store.LabError(
                f"no method {args.method} in {args.lab_db}; `lab idea` records a method before "
                f"anything can be promoted from it"
            )
        lab_status = str(method_row["status"])
        move = not args.lab_status_stays
        if move and lab_status not in ("test-passed", "paper"):
            raise lab_store.LabError(
                f"{args.method} is {lab_status!r} and the lab's TRANSITIONS have no edge "
                f"{lab_status!r} -> 'paper'; only 'test-passed' reaches 'paper'. The roster may "
                f"still take this method -- its admission rule is not the lab's gate (plan "
                f"Decisions D5) -- but say so: re-run with --lab-status-stays."
            )

        conn = db.connect()
        try:
            with conn.cursor() as cur:
                sort = args.sort if args.sort is not None else _next_sort(cur)
            p = build_promotion(args, data_date, sort)

            retire_end: date | None = None
            with db.transaction(conn, args.dry_run):
                insert = _check_target(conn, p)
                if p.retire_id is not None:
                    retire_end = paper_store.retire(conn, p.retire_id)
                if insert:
                    _insert(conn, p)
                print(render_plan(p, retire_end=retire_end, lab_status=lab_status, lab_move=move))
            if args.dry_run:
                log.info("dry-run: the roster transaction was rolled back; nothing written")
        finally:
            conn.close()

        lab_store.begin_immediate(lab_conn)
        try:
            new_status = lab_store.record_promotion(
                lab_conn,
                method_id=p.method_id,
                strategy_id=p.entry.id,
                candidate_id=p.candidate_id,
                object_name=p.entry.object_name,
                spec_digest=p.digest,
                retired_id=p.retire_id,
                move_status=move,
            )
            if args.dry_run:
                lab_conn.rollback()
                log.info("dry-run: the lab transaction was rolled back; nothing written")
            else:
                lab_conn.commit()
                log.info("%s recorded in %s (status %s)", p.method_id, args.lab_db, new_status)
        except BaseException:
            lab_conn.rollback()
            raise
    finally:
        lab_conn.close()

    if not args.dry_run:
        print(
            f"\n{p.entry.id} is on the roster as active with no paper_start. The next paper night "
            f"freezes its spec and starts its clock. Commit {args.lab_db} and "
            f"{lab_store.snapshot_path(Path(args.lab_db))} with `lab stage`."
        )
    return 0
