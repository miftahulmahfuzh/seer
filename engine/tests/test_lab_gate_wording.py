"""Phase 7 (lab-luck-gate): no shipped document states a luck bar the lab does not apply.

The owner moved ``DSR_MIN`` from 0.95 to 0.90 on 2026-10-07 (design §7.1), and six shipped files
went on claiming 0.95 -- the skill the unattended explorer reads, the format every pre-registration
is written in, two readmes and two pages of the site. The threshold lives in exactly one place in
the code and must read the same way everywhere it is written down.

This test is therefore written against ``store.DSR_MIN`` rather than against the literal ``0.95``:
the bar is a dial the owner turns, and a guard that only knows the last value is a guard that has
to be rewritten every time it would have been useful.

A stale bar in a skill, a readme or the committed pre-registration format is worse than no bar at
all: ``SKILL.md`` is what the next unattended exploration session reads and acts on, and
``prereg.gate_text``'s words are copied verbatim into every ``docs/lab/prereg/MNNNN.md`` the lab
will ever write -- files that are committed before a test number exists and are never rewritten.

Two things this test deliberately does **not** do:

- It does not forbid "every dev trial" or "N = all lab trials". ``DSR_POLICY`` ships as
  ``all-trials`` (design §7.2), so those phrases are *correct*; the N lever was measured and
  deliberately left alone, and a test that scrubbed the wording would make the design document lie.
- It does not scan ``docs/plans/2026-10-04-method-lab-design.md``. That document records decisions
  by appending dated revisions, so §3 keeps its original sentence and §7 quotes it as the thing it
  supersedes. Deleting it there would destroy the record this test exists to protect.

The journal is swept too, and on a different rule, because it is a different kind of document.
``SCANNED`` holds shipped files, where **every line states a rule** and any out-of-date bar is a
bug. Insight bodies are **dated records**: the bar one of them states was correct on its date, and
``insights`` refuses UPDATE and DELETE outright, so rewriting one is not even available. Only one
insight asserts the *current* state -- the one ``web/app/sera/overview.ts`` renders as its
headline, ``newest(kind === 'synthesis')`` -- and that single row is what is swept. Every older
insight, of any kind, is history and exempt by construction.

That sweep needed a second matcher, measured rather than assumed: over the 27 committed insights
``BAR_WITH_NUMBER`` matches **none**. It reads the engineering idiom (``DSR >= 0.95``), and the
journal is written for the owner in plain English ("on a scale where we require 0.95"). Adding
journal bodies to ``SCANNED`` would therefore have shipped a guard that is green on insight #21,
the row that caused this. The two matchers sit adjacent below, share ``_code_spans()``, and are
both compared against the live constants; the division of labour between them is recorded above
``PROSE_BARS``.

It also does not scan files the recorded ``trials.failed`` strings live in: ``trials`` is
append-only, so the 110 rows judged under 0.95 carry that exact text forever and any test fixture
asserting on them is quoting data, not stating the rule.
"""

from __future__ import annotations

import re
import sqlite3

import pytest

from seer_engine import config
from seer_engine.backtest import tuning
from seer_engine.lab import prereg, store

#: A statement of the luck bar with a number in it: "DSR >= 0.95", "DSR ≥ 0.9",
#: "Luck check ≥ 0.95", "luck check of at least 0.90". The number is captured and compared against
#: the live constant, so this guard catches the *next* threshold move too and not only this one --
#: which is the point, because the last one went unrecorded in six places at once.
#:
#: Code that interpolates the constant (``DSR >= {store.DSR_MIN:.2f}``,
#: ``Luck check ≥ ${num(gate.dsrMin)}``) has no digit after the operator and never matches: reading
#: the threshold from the gate is always the right answer, and this regex is shaped to leave it
#: alone.
BAR_WITH_NUMBER = re.compile(
    r"(?:DSR|luck\s+check)\s*(?:>=|≥|of\s+at\s+least)\s*(\d+\.\d+)",
    re.I,
)

# ----------------------------------------------------------------- the journal's owner-facing prose

#: The owner-facing twin of ``BAR_WITH_NUMBER``, and the reason this file carries two matchers
#: rather than one. They divide the corpus by **idiom**, not by file.
#:
#: ``BAR_WITH_NUMBER`` reads the engineering form -- ``DSR >= 0.95``, ``Luck check ≥ 0.95`` -- which
#: is how a skill, a pre-registration format and a TypeScript module write a threshold. The lab
#: journal is not written that way: it is written for the owner, in plain English. Measured over the
#: 27 committed insights, ``BAR_WITH_NUMBER`` matches **none** of them -- insight #21 included, the
#: ``synthesis`` row whose "on a scale where we require 0.95" was still the Overview headline the
#: day the gate moved to 0.90, so the page contradicted itself. Sweeping journal bodies with that
#: matcher alone would be a guard that is green on the one document that caused the bug, which is
#: worse than no guard at all because it reads as coverage.
#:
#: The two live here adjacent so neither is edited out of sight of the other; both are compared
#: against the live constants, and both share ``_code_spans()``.

#: A number that can be a bar: a percentage (the drawdown bar is always written ``20%``) or a bare
#: decimal (the luck bar is always written ``0.90``). A bare integer is never a bar in this prose --
#: it counts trials, names held, years -- so it is left out and cannot false-positive.
_NUM = r"(\d+(?:\.\d+)?%|\d+\.\d+)"

#: A percentage alone, for the "number first" shape ("at the new 20% limit").
_PCT = r"(\d+(?:\.\d+)?%)"

#: What the prose calls the bar, qualified or bare. Bare ``bar``/``limit`` is swept too, because
#: that is how the journal actually writes it ("our limit is 15%"); which constant such a number is
#: compared against is decided by its *form*, not by the noun -- see ``_stated_bars``.
_BAR_NOUN = (
    r"(?:luck\s+(?:bar|check|test)|DSR|(?:max(?:imum)?\s+)?drawdown\s+(?:bar|limit)|bar|limit)"
)

#: A present-tense copula or destination. **The design is in what this omits.** ``from``, ``by``,
#: ``within``, ``of`` and ``as`` are absent on purpose: each marks a number that is *not* the rule
#: in force, and leaving them out is the whole reason insight #27 needs no rewrite --
#:
#: - "the luck bar went **from** 0.95 to 0.90" -- ``from`` introduces the superseded side. The
#:   ``to 0.90`` half matches and passes, which is the correct reading of that sentence.
#: - "the drawdown limit **from** 15% to 20%" -- the same.
#: - "**quoted** the luck bar **as** 0.95" -- a quotation of another document, not an assertion.
#: - "clears the luck bar **by** 0.016", "**within** 0.03 of the bar" -- margins, not bars.
#:
#: This is deliberately *not* a blacklist of historical words. A blacklist is itself a loophole --
#: anyone can type the escape word -- whereas these are the ordinary grammar of superseding, and
#: they are the prose analogue of ``_code_spans()``: both say *this number is quoted, not asserted*.
_REL = r"(?:is|are|to|at|=|>=|≥|of\s+at\s+least)"

#: The two shapes a stated bar takes here: the noun then the number ("the luck bar moved to 0.90",
#: "we require 0.95"), and a percentage then the noun ("at the new 20% limit").
PROSE_BARS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"(?:\b{_BAR_NOUN}\s+(?:\w+\s+){{0,2}}?{_REL}|\brequires?)\s*{_NUM}", re.I),
    re.compile(rf"{_PCT}\s+(?:\w+\s+){{0,1}}?(?:bar|limit)\b", re.I),
)


#: Files this phase is responsible for. Paths are relative to the repository root.
SCANNED: tuple[str, ...] = (
    ".claude/skills/explore-and-experiment-new-method/SKILL.md",
    "docs/lab/prereg/README.md",
    "engine/package_readme.md",
    "engine/src/seer_engine/lab/prereg.py",
    "web/lib/sera/glossary.ts",
    "web/lib/sera/derive.ts",
    "web/app/sera/overview.ts",
    "web/app/sera/page.tsx",
    "web/app/sera/how/view.ts",
    "web/app/sera/methods/view.ts",
)


def _code_spans(line: str) -> list[tuple[int, int]]:
    """The backtick-delimited ranges of ``line``, as [start, end) offsets.

    A code span in these documents is a **quotation of a literal** -- the exact text the engine
    writes into the append-only ``trials.failed`` column, or the exact value of a constant. Prose
    is where a document *states the rule*, and prose is what this guard is for.
    """
    return [(m.start(), m.end()) for m in re.finditer(r"`+[^`]*`+", line)]


@pytest.mark.parametrize("rel", SCANNED)
def test_no_shipped_document_states_a_luck_bar_the_lab_does_not_apply(rel: str) -> None:
    path = config.REPO_ROOT / rel
    assert path.is_file(), f"{rel} is gone; update SCANNED or restore the file"
    hits = []
    for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        spans = _code_spans(line)
        for m in BAR_WITH_NUMBER.finditer(line):
            # A match inside a code span is quoting a recorded label, not stating the rule. The
            # 110 committed rows carry ``DSR >= 0.95`` for ever (``trials`` is append-only), and
            # ``engine/package_readme.md`` documents exactly that, in backticks, four times. The
            # module docstring above already exempts recorded strings on principle; this is the
            # same exemption made mechanical, so the guard keeps scanning every line of prose in
            # a file that also has to quote the old label verbatim.
            if any(a <= m.start() and m.end() <= b for a, b in spans):
                continue
            written = m.group(1)
            if float(written) != store.DSR_MIN:
                hits.append(f"  line {i}: says {written}, the gate applies {store.DSR_MIN}: {line.strip()}")
    assert not hits, (
        f"{rel} states a luck bar the lab does not apply. The threshold is the owner's dial "
        f"(design §7.1, moved from 0.95 to {store.DSR_MIN} on 2026-10-07), so a document that "
        f"types the number goes stale the next time it moves -- prefer reading it from "
        f"`store.DSR_MIN` or from `gate.dsrMin`:\n" + "\n".join(hits)
    )


def test_the_gate_text_is_built_from_the_constants_that_decide_the_verdict() -> None:
    """The words written into every pre-registration are built, not retyped (``gate_text``).

    Both numbers: the bar the owner set, and the policy that chooses N. Neither can be recovered
    from the other, so a pre-registration that names only one is not a record of a pass.
    """
    text = prereg.gate_text()
    assert f"{store.DSR_MIN:.2f}" in text
    assert store.DSR_POLICY in text
    assert all(float(w) == store.DSR_MIN for w in BAR_WITH_NUMBER.findall(text))


#: The two literals in ``web/`` that have to agree with the engine's threshold-bearing labels.
_WEB_PREFIX = re.compile(r"DSR_FAILURE_PREFIX\s*=\s*'([^']*)'")
_WEB_DD_PREFIX = re.compile(r"DRAWDOWN_FAILURE_PREFIX\s*=\s*'([^']*)'")


def test_the_web_mirrors_the_engines_drawdown_label_prefix() -> None:
    """The drawdown twin of the luck-label pin, and new since the owner moved that bar too.

    ``tuning.MAX_DRAWDOWN`` is 0.20 since 2026-10-07 (design §1 item 4, phase 8), so the engine
    writes ``max DD <= 20%`` while 30 committed rows say ``max DD <= 15%``. Both are misses. The
    site matches the shape; this test is what keeps the shape equal to the engine's.
    """
    from seer_engine.backtest import dev

    src = (config.REPO_ROOT / "web" / "lib" / "sera" / "derive.ts").read_text(encoding="utf-8")
    m = _WEB_DD_PREFIX.search(src)
    assert m is not None, (
        "web/lib/sera/derive.ts no longer defines DRAWDOWN_FAILURE_PREFIX as a single-quoted "
        "literal; if the web stopped matching the drawdown label by prefix, say so here"
    )
    prefix = m.group(1)
    assert prefix, "an empty prefix would mark every failure as a drawdown miss"
    assert dev.FAILURE_LABELS[1].startswith(prefix), (
        f"the engine writes {dev.FAILURE_LABELS[1]!r} into trials.failed, but the site looks for "
        f"{prefix!r}. Every missed drawdown would render as a pass on seertrade.site/sera"
    )
    assert "max DD <= 15%".startswith(prefix), (
        "the 30 committed rows judged under the old 15% bar must still read as drawdown misses"
    )


def test_the_web_mirrors_the_engines_luck_label_prefix() -> None:
    """``web/lib/sera/derive.ts`` matches the luck label by prefix; this pins that prefix here.

    ``trials`` is append-only, so a row judged before 2026-10-07 carries ``DSR >= 0.95`` for ever
    and one judged after carries ``DSR >= 0.90``. Both are misses. Phase 4 exports a prefix matcher
    from ``store`` for the Python readers; the web cannot call it -- ``derive.ts`` is TypeScript in
    the Next build, with no path to a Python symbol -- so it mirrors the prefix as one constant,
    and this test is the mirror's pin.

    The property, not the helper's name, is what is checked: whatever phase 4 calls its matcher,
    ``DSR_LABEL`` has to start with what the web looks for, or the site renders a failed luck check
    as a green tick -- silently, and on the one page the owner actually reads.
    """
    src = (config.REPO_ROOT / "web" / "lib" / "sera" / "derive.ts").read_text(encoding="utf-8")
    m = _WEB_PREFIX.search(src)
    assert m is not None, (
        "web/lib/sera/derive.ts no longer defines DSR_FAILURE_PREFIX as a single-quoted literal; "
        "if the web stopped matching the luck label by prefix, say so here and delete this test"
    )
    prefix = m.group(1)
    assert prefix, "DSR_FAILURE_PREFIX is empty: that would mark every failure as a luck miss"
    assert store.DSR_LABEL.startswith(prefix), (
        f"the engine writes {store.DSR_LABEL!r} into trials.failed, but the site looks for "
        f"{prefix!r}. Every luck-check miss would render as a pass on seertrade.site/sera"
    )


# ------------------------------------------------------------------- the lab journal's newest note

def _stated_bars(text: str) -> list[tuple[int, str, float, float]]:
    """Every bar ``text`` states as the rule in force: (line, as written, what it means, the bar).

    The number's **form** routes it, not the noun it sits beside: a percentage is the drawdown bar
    and a bare decimal is the luck bar. That is how the whole journal reads -- the luck bar is
    always ``0.90``, the drawdown bar always ``20%`` -- and it is what lets an unqualified sentence
    ("our limit is 15%") be swept at all.

    A hit inside a code span is skipped by the same rule as the docs sweep above, for the same
    reason: backticks quote a recorded literal rather than state the rule.
    """
    out: list[tuple[int, str, float, float]] = []
    for i, line in enumerate(text.split("\n"), start=1):
        spans = _code_spans(line)
        seen: set[int] = set()
        for pat in PROSE_BARS:
            for m in pat.finditer(line):
                if m.start(1) in seen or any(a <= m.start() and m.end() <= b for a, b in spans):
                    continue
                seen.add(m.start(1))
                written = m.group(1)
                if written.endswith("%"):
                    out.append((i, written, float(written[:-1]) / 100, tuning.MAX_DRAWDOWN))
                else:
                    out.append((i, written, float(written), store.DSR_MIN))
    return out


def _insights(where: str) -> list[sqlite3.Row]:
    """Rows of the committed journal, read without touching the file.

    ``COMMITTED_DB`` and not ``DB_PATH``: this guard is about what ships to the page, and a swarm
    worktree points ``SEER_LAB_DB`` at another checkout. Reading the database rather than
    ``web/data/lab.json`` is equivalent and already pinned -- ``test_lab_snapshot.py``'s
    ``test_the_committed_snapshot_is_the_export_of_the_committed_database`` asserts the two are the
    same export, byte for byte.
    """
    conn = store.connect_readonly(store.COMMITTED_DB)
    try:
        return conn.execute(f"SELECT id, kind, title, body, added FROM insights {where}").fetchall()
    finally:
        conn.close()


def _text(row: sqlite3.Row) -> str:
    return f"{row['title']}\n{row['body']}"


def test_the_newest_synthesis_does_not_state_a_bar_the_lab_does_not_apply() -> None:
    """The one journal row the Overview renders as its headline, swept for a stale bar.

    The Overview's story is ``newest(snap.insights.filter(i => i.kind === 'synthesis'))``, so
    exactly one insight asserts the *current* state of the lab and every other is a dated record.
    That asymmetry is the whole scope rule: a sweep over the journal that flagged every historical
    synthesis would be flagging correct prose and would be switched off within a week.

    This is the guard that was missing when insight #21 said "we require 0.95" on the headline
    while the gate panel beneath it read 0.90, on the same page, in prod. The ordering below
    mirrors ``newest()`` in ``web/app/sera/overview.ts``: newest ``added`` first, ties to the
    larger id.
    """
    rows = _insights("WHERE kind = 'synthesis' ORDER BY added DESC, id DESC")
    assert rows, "the committed lab database holds no synthesis insight for the Overview to headline"
    row = rows[0]
    hits = [
        f"  line {i}: says {written}, the lab applies {live}"
        for i, written, value, live in _stated_bars(_text(row))
        if abs(value - live) > 1e-9
    ]
    assert not hits, (
        f"insight #{row['id']} ({row['added']}) is the Overview's headline and states a bar the lab "
        f"does not apply. The luck bar is `store.DSR_MIN` ({store.DSR_MIN}) and the drawdown bar is "
        f"`tuning.MAX_DRAWDOWN` ({tuning.MAX_DRAWDOWN}). Do not rewrite this insight -- `insights` "
        f"refuses UPDATE outright and the row was correct on its date. Append a newer synthesis "
        f"recording the current bars, as `0033820` did, so `newest()` promotes it:\n" + "\n".join(hits)
    )


#: The insight that put a stale bar on the Overview: a ``synthesis`` added 2026-10-06 whose
#: "we require 0.95" outlived the move of ``DSR_MIN`` to 0.90 the next morning. ``insights`` refuses
#: UPDATE and DELETE outright, so this row, its id and its wording are permanent -- which is what
#: makes it a fixture rather than a snapshot of something that might change underneath.
STALE_INSIGHT_ID = 21

#: The insight that superseded it (``0033820``), which states the current bars *and* names the old
#: ones in prose while doing so. The hard case for any matcher, and the one the card said must not
#: be forced into a rewrite.
SUPERSEDING_INSIGHT_ID = 27


def test_the_prose_matcher_still_catches_the_insight_that_caused_this_guard() -> None:
    """Non-vacuity. A guard scoped to "the newest row" cannot prove itself from live data.

    Today the newest synthesis is correct, so the test above passes whether the matcher works or
    matches nothing whatsoever -- which is this card's own failure mode, recurring one level up,
    and precisely how ``BAR_WITH_NUMBER`` came to be green on a journal it cannot read. So the
    matcher is pinned here against the text that actually caused the contradiction on the page.

    The ``BAR_WITH_NUMBER`` assertion is not redundant: it records the measurement that forced a
    second matcher into this file. If someone later widens the engineering regex until it does
    read owner-facing prose, this fails and says so, rather than leaving two overlapping matchers
    to drift apart silently.
    """
    row = _insights(f"WHERE id = {STALE_INSIGHT_ID}")[0]
    assert row["kind"] == "synthesis" and row["added"].startswith("2026-10-06"), (
        f"insight #{STALE_INSIGHT_ID} is not the 2026-10-06 synthesis this fixture assumes; "
        f"`insights` is append-only, so if this fails the table has been rebuilt -- find the row "
        f'whose body says "on a scale where we require 0.95" and point this id at it'
    )
    text = _text(row)
    assert not BAR_WITH_NUMBER.search(text), (
        "the engineering matcher now reads owner-facing journal prose. That is a real change in "
        "the division of labour documented above PROSE_BARS -- update that comment and this test "
        "together, or the two matchers will drift"
    )
    stale = {written for _, written, value, live in _stated_bars(text) if abs(value - live) > 1e-9}
    assert "0.95" in stale, (
        'the prose matcher no longer reads "on a scale where we require 0.95" as a stale luck bar. '
        "It is the sentence this whole guard exists for; a matcher that misses it is green by "
        f"accident. Found: {sorted(stale)}"
    )
    assert "15%" in stale, (
        'the prose matcher no longer reads "past our 15% limit" as a stale drawdown bar. Both bars '
        f"moved on 2026-10-07 and both have to be swept. Found: {sorted(stale)}"
    )


def test_the_prose_matcher_reads_a_superseding_sentence_as_history() -> None:
    """The other half of the pin: the numbers in insight #27 that must *not* be flagged.

    #27 is the note that fixed #21, and it states the current bars while naming the old ones in the
    same breath -- "went from 0.95 to 0.90", "quoted the luck bar as 0.95", "clears the luck bar by
    0.016", "within 0.03 of the bar". Every one of those is a superseded side, a quotation or a
    margin, and every one is skipped by what ``_REL`` leaves out rather than by a list of excused
    words. Without this test, widening ``_REL`` by one convenient alternative would start flagging a
    correct insight, and the pressure would then be to rewrite a row the schema refuses to update.
    """
    row = _insights(f"WHERE id = {SUPERSEDING_INSIGHT_ID}")[0]
    assert row["kind"] == "synthesis" and "0.95" in row["body"], (
        f"insight #{SUPERSEDING_INSIGHT_ID} is not the superseding synthesis this fixture assumes"
    )
    bars = _stated_bars(_text(row))
    assert bars, "the matcher reads no bar at all in the note that announced both bars moving"
    stale = [f"{written} on line {i} (the lab applies {live})" for i, written, value, live in bars
             if abs(value - live) > 1e-9]
    assert not stale, (
        "the prose matcher now flags a superseded bar that insight #27 only names in passing. The "
        "sentence is correct and the row cannot be edited (`insights_no_update` aborts), so the fix "
        "belongs in `_REL` or `_BAR_NOUN`, never in the journal: " + ", ".join(stale)
    )


#: The Overview's headline selection, mirrored from ``web/app/sera/overview.ts``. A Python guard
#: over "the newest synthesis" is guarding a row nobody sees if the page stops headlining that row,
#: so the selection is pinned the same way the label prefixes above are: by reading the source.
_HEADLINE = re.compile(
    r"newest\(\s*snap\.insights\.filter\(\s*(\w+)\s*=>\s*\1\.kind\s*===\s*'synthesis'\s*\)\s*\)"
)
_NEWEST_ORDER = re.compile(r"\.added\.localeCompare\(\s*\w+\.added\s*\)\s*\|\|\s*\w+\.id\s*-\s*\w+\.id")


def test_the_site_still_headlines_the_newest_synthesis() -> None:
    """``overview.ts`` picks the row the test above sweeps, and picks it the same way.

    Two halves, because the scope rule rests on both: *which kind* is headlined (only a synthesis
    asserts the current state; other journal notes can be machine records), and *which one of them*
    (newest ``added``, ties to the larger id). ``web/app/sera/overview.test.ts`` covers the
    ordering's behaviour on the web side; this pins that the Python sweep is aimed at the same row.
    """
    src = (config.REPO_ROOT / "web" / "app" / "sera" / "overview.ts").read_text(encoding="utf-8")
    assert _HEADLINE.search(src), (
        "web/app/sera/overview.ts no longer headlines `newest(insights.filter(kind === "
        "'synthesis'))`. The journal sweep is scoped to exactly that row -- if the page now "
        "headlines something else, scope the sweep to the new selection or this guard is watching "
        "a row no reader ever sees"
    )
    assert _NEWEST_ORDER.search(src), (
        "web/app/sera/overview.ts no longer resolves `newest()` by `added` then `id`; the sweep's "
        "`ORDER BY added DESC, id DESC` would pick a different insight than the page renders"
    )
