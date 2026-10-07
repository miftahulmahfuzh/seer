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

It also does not scan files the recorded ``trials.failed`` strings live in: ``trials`` is
append-only, so the 110 rows judged under 0.95 carry that exact text forever and any test fixture
asserting on them is quoting data, not stating the rule.
"""

from __future__ import annotations

import re

import pytest

from seer_engine import config
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
