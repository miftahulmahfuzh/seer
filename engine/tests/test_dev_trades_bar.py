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

#: Re-measured 2026-10-14 against the committed lab database, read-only, with no trial recorded,
#: after the owner split the dev screen off the real-money bar (design §18): the screen moved
#: 0.20 -> 0.50, so trials that previously missed BOTH drawdown and trades now miss trades alone.
#: These are the recorded dev trials whose **sole** miss against the five owner conditions is the
#: trades bar.
#:
#: The set has grown twice for reasons that are not the bar's. First measured 2026-10-07 at two
#: trials out of 110; M0084 then priced the SPY-200 safety switch on its own and three of its
#: variants trade 10 to 13 times in twenty-two years, taking it to five out of 354; and on
#: 2026-10-14 the screen moved, taking it to twelve. Nothing about the trades bar itself changed
#: on any of those days.
#:
#: **Every one of the twelve still fails the luck test** -- measured at the 0.50 screen, the count
#: clearing ``DSR_MIN`` is zero, the P7a seeds carrying ``dsr IS NULL`` and the rest a real score
#: under the bar. That is the case §13 predicted when it said the bar "binds future trials that do
#: carry a DSR", and it is why the third test below asks whether a held-out trial *clears the luck
#: bar* rather than whether it has one at all. §13's finding -- that dropping the trades bar would
#: change zero eligibility verdicts -- therefore survives the wider set. Every trial the bar has
#: ever held out is a market-timing book: nothing else trades seldom enough to be caught by it.
HELD_OUT_BY_THE_TRADES_BAR: tuple[tuple[str, int], ...] = (
    ("F1-QQQ-SMA200-M", 17),
    ("F1-QQQ-VT15-W", 28),
    ("F1-SPY-10MSMA-M", 13),
    ("F1-SPY-ABS12-M", 9),
    ("F1-SPY-SMA200-M", 11),
    ("F2-SPYQQQ-12M", 14),
    ("F2-SPYQQQ-3M", 36),
    ("F2-SPYQQQ-6M", 28),
    ("M0084-BAND3-M", 9),
    ("M0084-BAND3-W", 10),
    ("M0084-FABER-M", 13),
    ("M0084-MONTHLY", 11),
    # 2026-10-14, second re-take of the same day, and a DIFFERENT cause from the 5 -> 12 above.
    # That growth was the dev screen moving to 50% (design §18). This one is simply new methods of
    # a shape that can never clear 100 trades: M0113 and M0143 recorded SPY-only switch books,
    # which hold one instrument and trade 11-43 times in 22 years. §18's statement about what the
    # screen change did stays true as written and is not amended.
    ("M0113-SMA20", 30),
    ("M0113-SMA200", 11),
    ("M0113-SMA50", 24),
    ("M0113-SMA50-W", 43),
    ("M0113-UP63", 18),
    ("M0143-SPY-UP63", 18),
    # 2026-10-18, retaken against the snapshot below. Five more SPY switch books recorded on
    # 2026-10-16/17, again new methods and not a moved bar. Three of them are the first trials the
    # bar has held out that clear the luck test (``LOAD_BEARING``), so §13's "zero verdicts
    # change" finding stopped being true on 2026-10-16. Design §19 records the re-measurement.
    ("M0038-SPY-2KEY", 23),
    ("M0038-SPY-WATCH", 2),
    ("M0167-SPY-E200S", 3),
    ("M0167-SPY-EHIGHL", 2),
    ("M0205-SPY200", 9),
)

#: The last ``trials.n`` the two sets in this file were measured against. Only rows at or below it
#: are compared, so the measurement is taken against a frozen slice of an append-only table.
#:
#: **Why a snapshot and not the whole table.** Until 2026-10-18 the third test read every dev row,
#: and the set above could only grow: Sera sessions record new methods unattended, and every new
#: SPY switch book trades too seldom to clear 100 by construction. Each one broke ``main`` without
#: any bar moving, and a test that fails every time the lab does its job gets ignored. That is
#: exactly what happened from 2026-10-16. The mistake this file guards against is a *constant*
#: moving, and a moved constant re-judges old rows too, so a frozen slice still catches it. New
#: trials are new evidence, and adding them to the measurement is a deliberate re-take: raise this
#: number, re-run, and update both sets and the design doc together.
SNAPSHOT_N = 736

#: The held-out trials whose **recorded** luck score clears ``DSR_MIN``. These are the ones the
#: trades bar is the only thing keeping off the leaderboard. Measured 2026-10-18: each one also
#: clears at the lab's live trial count (0.965, 0.946 and 0.958 at N = 146), and ``store.verdict``
#: marks all three eligible once ``dev._MIN_TRADES`` is set to 0 in memory. Two of them profit
#: on every trade they make, two trades in twenty-two years, so their profit factor is infinite.
#: That is the sample-size case §13 kept the bar for, and here it is doing that job.
#:
#: The recorded score is read rather than ``store.dsr_at``'s live one because the live score moves
#: with every method the lab tries. Pinning it would bring back the drift the snapshot removes.
LOAD_BEARING: tuple[str, ...] = ("M0038-SPY-2KEY", "M0038-SPY-WATCH", "M0167-SPY-EHIGHL")


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
        f"condition 3: the trials this bar holds out score profit factors of 75.45, 808.97 and\n"
        f"infinity off 2 to 43 closed trades over twenty years, and none of those numbers means\n"
        f"anything. Since 2026-10-16 the bar is also load-bearing: three of them clear the luck\n"
        f"test and would become eligible the moment it went (design §19).\n"
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


def test_the_trades_bar_holds_out_a_known_set_and_three_of_them_clear_the_luck_bar() -> None:
    """The measurement §13 rests on, re-taken from the committed database on every run.

    On 2026-10-07 this was the fact that made the asymmetry cheap rather than merely defensible:
    the two trials the dev trades bar held out were both P7a seed imports with ``dsr IS NULL``, and
    under method-lab design §7.1 a luck test that cannot be evaluated is one that was not passed. So
    dropping the bar then would have changed **zero** eligibility verdicts. §13 also said the
    sample-size argument "binds future trials that do carry a DSR".

    That case has now arrived. The set grew twice for bar moves and new methods (design §18), and
    the finding held until 2026-10-16, when M0038 and M0167 recorded SPY switch books that trade 2
    to 23 times in twenty-two years **and** clear ``DSR_MIN``. Three trials now hinge on the trades
    bar alone (``LOAD_BEARING``). The second assertion therefore no longer says "none of them clears
    the luck bar". It pins exactly which ones do, so a fourth arriving inside the snapshot, or one
    of the three dropping out, is a re-take rather than a silent change. §13 is a dated record and
    is **not** amended. The re-measurement lives in design §19.

    Both sets are recomputed from the recorded columns against the live constants, never parsed out
    of ``trials.failed``, and only over rows ``n <= SNAPSHOT_N``. A moved ``DEV_MAX_DRAWDOWN``,
    ``MIN_PROFIT_FACTOR`` or ``_MIN_TRADES`` re-judges those frozen rows and fails here. A new
    trial does not, because adding new evidence to the measurement is a deliberate re-take.

    Read-only: ``mode=ro``, no trial recorded, the lab's N unmoved, no test-window look spent.
    """
    conn: sqlite3.Connection = store.connect_readonly(store.COMMITTED_DB)
    try:
        rows = conn.execute(
            "SELECT * FROM trials WHERE window = 'dev' AND n <= ?", (SNAPSHOT_N,)
        ).fetchall()
    finally:
        conn.close()

    held_out = sorted(
        (str(r["candidate_id"]), int(r["trades"]), r["dsr"])
        for r in rows
        if store.owner_failures(r) == (TRADES_LABEL,)
    )
    assert [(name, count) for name, count, _ in held_out] == sorted(HELD_OUT_BY_THE_TRADES_BAR), (
        f"the set of recorded dev trials (n <= {SNAPSHOT_N}) whose only miss is the trades bar\n"
        f"has changed.\n"
        f"Pinned: {sorted(HELD_OUT_BY_THE_TRADES_BAR)}.\n"
        f"Now:    {[(name, count) for name, count, _ in held_out]}.\n"
        f"\n"
        f"These rows are frozen, so new trials cannot cause this. A live constant moved:\n"
        f"`tuning.DEV_MAX_DRAWDOWN`, `tuning.MIN_PROFIT_FACTOR` or `dev._MIN_TRADES`. If the owner\n"
        f"moved it with a dated revision, re-take the measurement, update this list and\n"
        f"LOAD_BEARING, and record the re-measurement in the design doc beside {RECORD}. If\n"
        f"nobody meant to move it, move it back: every recorded verdict re-derives from it."
    )
    lucky = tuple(
        sorted(name for name, _, dsr in held_out if dsr is not None and float(dsr) >= store.DSR_MIN)
    )
    assert lucky == LOAD_BEARING, (
        f"the held-out trials that also clear the luck bar have changed.\n"
        f"Pinned: {list(LOAD_BEARING)}.\n"
        f"Now:    {list(lucky)}.\n"
        f"\n"
        f"These are the trials the dev trades bar is the only thing keeping ineligible: each\n"
        f"clears `DSR >= {store.DSR_MIN}` and misses nothing else. Dropping or lowering the bar\n"
        f"would put every one of them on the leaderboard off a profit factor measured on a\n"
        f"handful of trades. If `store.DSR_MIN` moved, that was an owner decision. Re-take the\n"
        f"measurement and record it in the design doc beside {RECORD} before anyone leans on the\n"
        f"old count."
    )
