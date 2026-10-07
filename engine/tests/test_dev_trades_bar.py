"""The dev-window gate keeps its 100-closed-trades bar; design §1 item 1 no longer has one.

That asymmetry is deliberate, dated and recorded -- design §13, "Revision 2026-10-07 (owner):
go-live item 1 is 18 months, and counts no trades", and the comment above the constant itself at
``backtest/dev.py``. What it did not have was anything that fails. Three prose comments and a design
section are the right record and the wrong guard: a comment cannot notice when someone deletes the
line beneath it.

**The thing being guarded.** The owner replaced item 1's "≥ 100 closed trades" with "≥ 18 months of
forward paper trading" on 2026-10-07, because a trade count scales with how many names a book holds
rather than with how much evidence exists about it. The dev-window gate -- which design §1 item 5's
"identical rules" applies to every lab candidate -- kept its own trades condition. The next reader to
find one gate asking for trades and the other not will reasonably try to make them agree, and the
cheap way to make them agree is to delete ``_MIN_TRADES``. That silently re-judges the recorded basis
of all 110 dev trials: ``lab.store.owner_failures`` and ``lab.store.published_verdict`` re-derive
every verdict from this constant **at read time**, and ``trials`` is append-only, so the rows stay
byte for byte while what they mean changes underneath the leaderboard.

This file is the house guard for exactly that shape of mistake, next to
``web/lib/golive.test.ts`` (which pins the two ``MAX_DRAWDOWN`` definitions to each other),
``test_lab_npolicy.py``'s ``test_the_shipped_defaults_reproduce_todays_n`` (which holds N at 110) and
``test_lab_gate_wording.py`` (which holds the shipped gate labels to the live constants).

**Written against the live constants, never against ``trials.failed``.** All 110 recorded rows carry
the superseded ``"DSR >= 0.95"`` label and the superseded 15% drawdown bar, because ``trials`` is
append-only and a recorded label names the bar in force on its run date. ``store.owner_failures`` is
the function that re-judges a recorded row against today's constants, and the third test uses it.

It is its own module rather than a case in ``test_backtest_tuning.py`` because that file belongs to
the session that landed the §13 revision, and because the failure messages below are the payload --
not the assertions.
"""

from __future__ import annotations

import sqlite3

from seer_engine.backtest import dev, tuning
from seer_engine.lab import store

#: The dev-window bar as the owner left it on 2026-10-07. A literal, not a reference: a guard that
#: reads the value it guards from the thing it guards passes unconditionally.
TRADES_BAR = 100

#: The forward-paper bar design §1 item 1 now states, in months. ``None`` on a tree that predates the
#: §13 revision, which the second test returns early on rather than skipping -- CI fails on any
#: skipped test, and the asymmetry being described does not exist on such a tree anyway.
PAPER_MONTHS: int | None = getattr(tuning, "MIN_PAPER_MONTHS", None)

#: The dated record of the decision, for every failure message below to point at.
RECORD = "docs/plans/2026-10-03-seer-design.md §13"

#: The label ``dev.make_row`` writes into ``trials.failed`` when the trades bar is the miss.
#: Unpacked in ``FAILURE_LABELS`` order, exactly as ``store.owner_failures`` unpacks it.
_SPY, _DRAWDOWN, _PF, TRADES_LABEL, _OWNER = dev.FAILURE_LABELS

#: Measured 2026-10-07 against the committed lab database, read-only, with no trial recorded and the
#: lab's N unmoved at 110: the only recorded dev trials whose **sole** miss against today's five
#: owner conditions is the trades bar. 26 of 110 clear all five with the bar; 28 without it. Both are
#: P7a seed trials carrying ``dsr IS NULL`` -- which is what the third test is really about.
HELD_OUT_BY_THE_TRADES_BAR: tuple[tuple[str, int], ...] = (
    ("F1-SPY-10MSMA-M", 13),
    ("F1-SPY-SMA200-M", 11),
)


def test_the_dev_window_gate_still_requires_a_hundred_closed_trades() -> None:
    """``dev._MIN_TRADES`` is 100, and the reason it is 100 is no longer the reason it once was."""
    assert dev._MIN_TRADES == TRADES_BAR, (
        f"`backtest.dev._MIN_TRADES` is {dev._MIN_TRADES}, not {TRADES_BAR}.\n"
        f"\n"
        f"If you changed it because design §1 item 1 no longer mentions trades: please change it\n"
        f"back, and read {RECORD} and the comment above the constant in\n"
        f"backtest/dev.py before deciding again. The owner deleted item 1's trades clause on\n"
        f"2026-10-07 and left this one standing on purpose. The two gates ask different questions:\n"
        f"item 1 asks how much forward evidence a strategy has accumulated making real decisions,\n"
        f"which is a question about time -- hence 18 months -- and the dev-window gate asks whether\n"
        f"a 20-year backtest produced enough closed trades for its profit factor and drawdown to\n"
        f"mean anything, which is a question about sample size. Deleting the clause from item 1 was\n"
        f"right. Deleting it here moves the sample-size problem out of condition 1 and into\n"
        f"condition 3: the two trials this bar holds out score profit factors of 75.45 and 14.48\n"
        f"off 11 and 13 closed trades over twenty years, and neither number means anything.\n"
        f"\n"
        f"It is also not a free edit. All 110 recorded dev trials were judged against this\n"
        f"constant; `lab.store.owner_failures` and `lab.store.published_verdict` re-judge them\n"
        f"against it at read time, and `trials` is append-only -- so moving it re-decides what the\n"
        f"lab's whole record means without leaving a mark anywhere. That may still be the right\n"
        f"call one day. It is an owner decision, it needs a dated revision in\n"
        f"docs/plans/2026-10-03-seer-design.md alongside §13, and it is not a tidy-up.\n"
        f"\n"
        f"If the owner has since decided to move it: record the decision and its date in the design\n"
        f"doc, then set TRADES_BAR here to the new value."
    )


def test_the_forward_paper_bar_and_the_dev_trades_bar_are_two_separate_dials() -> None:
    """The dev gate still has a trades condition, and §1 item 1's bar is a dial of its own.

    There is no arithmetic relationship to assert between 18 months and 100 trades, and inventing
    one would be worse than asserting nothing: §13's point is precisely that the forward gate
    stopped counting trades, so any equation tying the two together would re-introduce the coupling
    the owner removed. What is worth pinning is that **both dials exist and each is held to its own
    value**, so moving one can never quietly carry the other along.

    **Why the second half is conditional and not a ``pytest.skip``.** ``tuning.MIN_PAPER_MONTHS``
    arrives with the §13 revision and does not exist on a tree that predates it, so this file must
    pass on both. A skip is not available: ``.github/workflows/engine-ci.yml`` greps the run for
    ``^SKIPPED`` and fails the job on any hit, because a silently skipped suite is how 385
    Postgres-gated tests once passed for free. The first assertion below therefore holds in both
    worlds and the second is inert until the revision merges.
    """
    assert TRADES_LABEL in dev.FAILURE_LABELS, (
        f"`dev.FAILURE_LABELS` no longer carries a closed-trades condition.\n"
        f"\n"
        f"The dev-window gate keeps its trades bar even though design §1 item 1 dropped one\n"
        f"({RECORD}); removing the label removes the condition from every candidate the lab screens\n"
        f"and from the `failed` string every future trial records. If that is intended it is an\n"
        f"owner decision with a dated revision behind it, and this test is what to update once that\n"
        f"revision exists."
    )
    if PAPER_MONTHS is None:
        return
    assert PAPER_MONTHS == 18, (
        f"`tuning.MIN_PAPER_MONTHS` is {PAPER_MONTHS}, not 18.\n"
        f"\n"
        f"That is design §1 item 1's forward-paper bar, set by the owner on 2026-10-07 ({RECORD}).\n"
        f"It is an owner dial and it moves by a dated revision, not by a code change. If the owner\n"
        f"moved it, record that and update this test.\n"
        f"\n"
        f"Note what this test does NOT say: it does not tie 18 months to the dev gate's 100 trades\n"
        f"in any way. They are two dials with two units measuring two different things, and §13's\n"
        f"whole point is that the forward gate stopped counting trades. Moving this one is never a\n"
        f"reason to move `dev._MIN_TRADES`, and moving that one is never a reason to move this."
    )


def test_the_trades_bar_holds_out_two_trials_and_neither_of_them_has_a_luck_score() -> None:
    """The measurement §13 rests on, re-taken from the committed database on every run.

    This is the fact that made the asymmetry cheap rather than merely defensible: the two trials the
    dev trades bar holds out are both P7a seed imports with ``dsr IS NULL``, and under method-lab
    design §7.1 a luck test that cannot be evaluated is one that was not passed. So dropping the bar
    today would newly clear two candidates through the five owner conditions and change **zero**
    eligibility verdicts. The sample-size argument binds future trials that do carry a DSR; it does
    not bind these two, and §13 says so.

    The set is recomputed from the recorded columns against the live constants, never parsed out of
    ``trials.failed``. It can therefore move for a legitimate reason -- the owner lowering
    ``tuning.MAX_DRAWDOWN`` would drop both of these out of it, since they sit at 18.7% and 18.9%
    against today's 20% bar. That is not a bug in this test: it means §13's measurement has gone
    stale, and §13 is what to update.

    Read-only: ``mode=ro``, no trial recorded, the lab's N unmoved at 110, no test-window look spent.
    """
    conn: sqlite3.Connection = store.connect_readonly(store.COMMITTED_DB)
    try:
        rows = conn.execute("SELECT * FROM trials WHERE window = 'dev'").fetchall()
    finally:
        conn.close()

    held_out = sorted(
        (str(r["candidate_id"]), int(r["trades"]), r["dsr"])
        for r in rows
        if store.owner_failures(r) == (TRADES_LABEL,)
    )
    assert [(name, count) for name, count, _ in held_out] == list(HELD_OUT_BY_THE_TRADES_BAR), (
        f"the set of recorded dev trials whose only miss is the trades bar has changed.\n"
        f"Measured 2026-10-07 and written into {RECORD}: {list(HELD_OUT_BY_THE_TRADES_BAR)}.\n"
        f"Measured now:{' ' * 31}{[(name, count) for name, count, _ in held_out]}.\n"
        f"\n"
        f"This set is recomputed from the recorded columns against the live constants, so an owner\n"
        f"moving `tuning.MAX_DRAWDOWN`, `tuning.MIN_PROFIT_FACTOR` or `dev._MIN_TRADES`\n"
        f"legitimately changes it. If that is what happened, re-take the measurement and update\n"
        f"both this list and the one in {RECORD}, whose argument is built on it."
    )
    scored = [(name, count, dsr) for name, count, dsr in held_out if dsr is not None]
    assert not scored, (
        f"a trial held out by the dev trades bar now carries a luck score: {scored}.\n"
        f"\n"
        f"{RECORD} argues that dropping the dev trades bar would change zero eligibility verdicts\n"
        f"today, and the whole of that argument is that both held-out trials are P7a seed imports\n"
        f"with `dsr IS NULL` -- under method-lab design §7.1 a luck test that cannot be evaluated is\n"
        f"one that was not passed, so the trades bar is not what is keeping them out. `lab\n"
        f"remeasure`'s seed path (method-lab design §7.6) can give a seed trial a DSR, and if it has\n"
        f"given one to a trial in this set, re-check whether that trial now clears the luck bar and\n"
        f"rewrite §13's 'zero verdicts actually change' finding before anyone leans on it again."
    )
