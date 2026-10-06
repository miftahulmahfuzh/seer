"""FND on the paper roster (plan roster-promotion-pipeline, phase 6; requirement R1).

The allocator itself is covered by test_f_fundamental.py. This module covers the three things
that only exist once FND is a ROSTER entry:

1. the entry is what the roster says it is, and its gate note claims nothing;
2. `paper.book.decide_book` -- the nightly decision -- reaches `market.fundamentals`, because
   FUNDAMENTAL's history-only path is a fixed empty result, not a degraded one;
3. A MARKET WITH NO PANEL YIELDS NO TRADES, NOT WRONG TRADES. A database without
   005_fundamentals.sql applied, or with `fundamental_facts` truncated (which production's is,
   deliberately -- see the data-pipeline runbook), gives FND an EMPTY_PANEL. The portfolio then
   holds cash. That must be an asserted, understood outcome and not a silence that reads like a
   deliberate cash position.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from stratkit import hist, session_days

from seer_engine.backtest.book_runner import run_rules
from seer_engine.backtest.market import EMPTY_FUNDAMENTALS, Market, Membership
from seer_engine.fundamentals import Fact, FundamentalPanel
from seer_engine.paper.book import decide_book
from seer_engine.paper.replay import PaperHead, expected_book
from seer_engine.paper.roster import (
    FND_ID,
    FUNDAMENTAL_PARAMS,
    RESOLVER,
    ROSTER_IDS,
    SEED_ROWS,
    backtest_gate,
    entry,
)
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.allocator import MarketAware, prepare_for
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FACTOR
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalPrepared
from seer_engine.strategies.f_index import TIMING

SYMBOLS: tuple[str, ...] = ("AAA", "BBB", "CCC", "DDD", "EEE")
# The first session of a month under MONTHLY_HOLD, so decide_book's data_date is the session
# before it and the decision is a rank session.
DECIDE_FOR = date(2026, 11, 2)
DATA_DATE = date(2026, 10, 30)
# Enough sessions to cover DV_N = 20 and reach DECIDE_FOR; the first is in January 2026.
DAYS: list[date] = session_days(230, date(2026, 1, 2))
assert DAYS[-1] >= DECIDE_FOR, "the fixture calendar must reach the decision session"


# ---- the world ---------------------------------------------------------------------------------


# Ten sessions past DECIDE_FOR: a run started on the decision session has somewhere to
# execute, and the no-look-ahead test has later bars that it must ignore.
RUN_END: date = [d for d in DAYS if d > DECIDE_FOR][9]


def _days() -> list[date]:
    return [d for d in DAYS if d <= RUN_END]


def _history() -> dict[str, History]:
    """Five liquid names with distinct closes, every session of 2026 through RUN_END.

    The closes are single digits on purpose. MONTHLY_HOLD is whole-share, equal sizing puts
    1/`top` = 1/20 of the book in each name, and the book starts at INITIAL_IDR / usd_idr =
    $1,250 -- so a $100 share buys zero shares and every order is rejected `too_small`. At these
    prices each target is a double-digit share count, which is what makes the replay test below
    assert something. Volume keeps mean dollar volume (~$30-70M) over the $20M floor.
    """
    days = _days()
    out: dict[str, History] = {}
    for k, symbol in enumerate(SYMBOLS):
        closes = [6.0 + 2.0 * k + 0.002 * i for i in range(len(days))]
        out[symbol] = hist(symbol, closes, days=days, volumes=[5_000_000.0] * len(days))
    return out


def _fact(symbol: str, taxonomy: str, tag: str, unit: str, period_start: date | None,
          period_end: date, val: float, filed: date, form: str = "10-K") -> Fact:
    return Fact(symbol=symbol, taxonomy=taxonomy, tag=tag, unit=unit, period_start=period_start,
                period_end=period_end, val=float(val),
                accn=f"{symbol}-{tag}-{period_end:%Y%m%d}", form=form,
                fy=period_end.year, fp="FY" if form == "10-K" else "Q", filed=filed)


# Ten consecutive calendar quarters ending 2026-06-30, each filed 40 days after its close, so
# every one of them is visible on DATA_DATE. sue.MIN_QUARTERS is 9.
_QUARTERS: list[tuple[date, date]] = [
    (date(y, m0, 1), date(y, m1, d1))
    for y in (2024, 2025, 2026)
    for m0, m1, d1 in ((1, 3, 31), (4, 6, 30), (7, 9, 30), (10, 12, 31))
][:10]
# Year-on-year EPS growth that is uneven, so the dispersion of the prior surprises is non-zero
# (sue() is NaN when it is not) and the five symbols rank differently.
_EPS = (1.00, 1.10, 1.20, 1.30, 1.45, 1.70, 1.55, 1.80, 2.10, 2.00)


def _panel() -> FundamentalPanel:
    """A real panel: every symbol filed, well inside max_stale_days, with every factor finite.

    The facts differ per symbol so the composite ranking has something to order by; the values
    themselves are not asserted, only that a panel produces targets and no panel produces none.
    `rank="composite"` reads all four factors and `fundamental_rows` drops a row whose SUE is
    NaN, so the quarterly diluted-EPS series is not optional here.
    """
    year_start, year_end = date(2025, 1, 1), date(2025, 12, 31)
    filed = date(2026, 2, 20)
    facts: list[Fact] = []
    for k, symbol in enumerate(SYMBOLS):
        for tag, unit, value in (
            ("Assets", "USD", 1_000_000_000.0 + 1e8 * k),
            ("StockholdersEquity", "USD", 400_000_000.0 + 2e7 * k),
        ):
            facts.append(_fact(symbol, "us-gaap", tag, unit, None, year_end, value, filed))
        facts.append(_fact(symbol, "dei", "EntityCommonStockSharesOutstanding", "shares",
                           None, year_end, 10_000_000.0 + 1e6 * k, filed))
        for tag, value in (
            ("NetIncomeLoss", 50_000_000.0 + 5e6 * k),
            ("GrossProfit", 400_000_000.0 + 3e7 * k),
        ):
            facts.append(_fact(symbol, "us-gaap", tag, "USD", year_start, year_end, value, filed))
        for i, (q_start, q_end) in enumerate(_QUARTERS):
            facts.append(_fact(symbol, "us-gaap", "EarningsPerShareDiluted", "USD/shares",
                               q_start, q_end, _EPS[i] + 0.07 * k, q_end + timedelta(days=40),
                               form="10-Q"))
    return FundamentalPanel.from_facts(tuple(facts))


def _market(panel) -> Market:
    days = _days()
    return Market(
        history=_history(),
        membership=Membership(intervals=tuple((s, days[0], None) for s in SYMBOLS)),
        fx=tuple((d, Decimal("16000.0000")) for d in days),
        fundamentals=panel,
    )


@pytest.fixture(scope="module")
def with_panel() -> Market:
    return _market(_panel())


@pytest.fixture(scope="module")
def no_panel() -> Market:
    return _market(EMPTY_FUNDAMENTALS)


# ---- 1. the entry ------------------------------------------------------------------------------


def test_fnd_is_the_sixth_roster_entry():
    assert ROSTER_IDS[5] == FND_ID == "FND"
    assert len(ROSTER_IDS) == 10  # 010 appends fractional F4, F1 and RM; 011 appends RMW
    e = entry(FND_ID)
    assert (e.sort, e.engine, e.rules_id, e.is_champion, e.is_benchmark) == (6, "book", "monthly-hold", False, False)
    assert e.obj is FUNDAMENTAL
    assert e.object_name == "FUNDAMENTAL"
    assert e.params is FUNDAMENTAL_PARAMS
    assert e.rules is MONTHLY_HOLD
    assert e.registry_id is None  # D1: promoted strategies never enter backtest.registry.REGISTRY


def test_fnd_claims_no_backtest_gate_pass():
    e = entry(FND_ID)
    gate = backtest_gate(e)
    assert gate == {"passed": False, "note": e.gate_note}
    assert e.gate_applicable is True  # the quant gate DOES apply to it; it simply has not passed
    assert "failed" in e.gate_note
    for word in ("passed", "pass ", "beat SPY"):
        assert word not in e.gate_note.replace("beats SPY TR", "")


def test_fnd_lookback_is_the_dollar_volume_window():
    # fundamental_lookback = max(DV_N=20, trend n=0). A filing's availability is its `filed`
    # date, not a bar count, so nothing here needs a long warm-up.
    assert entry(FND_ID).lookback == 20


def test_the_resolver_names_fundamental_and_the_seed_row_uses_it():
    """The extension point phase 1 defined and phase 5 refuses without: one RESOLVER entry.

    Checked here rather than in test_paper_roster.py so the FND-specific facts stay in one file.
    """
    binding = RESOLVER["FUNDAMENTAL"]
    assert binding.obj is FUNDAMENTAL
    assert binding.params is FUNDAMENTAL_PARAMS
    assert binding.from_registry is False       # D1: never a backtest.registry entry
    row = next(r for r in SEED_ROWS if r.id == FND_ID)
    assert (row.object_name, row.registry_id, row.rules_id) == ("FUNDAMENTAL", None, "monthly-hold")
    # Retired by 010: the owner replaced FND with RM (lab M0011) on 2026-10-07.
    assert (row.status, row.paper_end, row.gate_applicable) == ("retired", None, True)


def test_the_roster_params_equal_the_lab_candidate_promote_writes_from():
    """The one drift that would break FND's SECOND night, not its first.

    `promote --candidate M0005-ALL` freezes the spec from the LAB module's params object;
    `roster.from_row` rebuilds it from FUNDAMENTAL_PARAMS. The two are separate objects by design
    -- roster.py must never import a lab method, whose `source_sha` is frozen for lab reasons --
    so only value equality keeps `store.check_digest` quiet. Importing the lab module is free
    here; it is forbidden in roster.py.
    """
    from seer_engine.lab.methods.m0005_fundamental_factors import METHOD as M0005

    candidate = next(c for c in M0005.candidates if c.id == "M0005-ALL")
    assert candidate.params == FUNDAMENTAL_PARAMS
    assert candidate.allocator is FUNDAMENTAL
    assert candidate.rules is MONTHLY_HOLD
    # and therefore the digest the roster recomputes is the digest promote would have frozen
    assert candidate.params.as_dict() == FUNDAMENTAL_PARAMS.as_dict()


# ---- 2. the night reaches the panel ------------------------------------------------------------


def test_fundamental_is_the_only_market_aware_roster_object():
    assert isinstance(FUNDAMENTAL, MarketAware)
    # The guard that keeps decide_book's branch honest: if another roster object ever gains
    # prepare_market, it starts taking the prepared path and this test says so.
    assert not isinstance(FACTOR, MarketAware)
    assert not isinstance(TIMING, MarketAware)


def test_decide_book_ranks_fnd_from_the_market_panel(with_panel):
    e = entry(FND_ID)
    targets, idle_added = decide_book(with_panel, e.obj, e.params, e.rules, DATA_DATE, frozenset())
    assert targets, "FND decided nothing against a Market carrying a panel"
    assert idle_added is False  # MONTHLY_HOLD has no idle_symbol
    assert {t.symbol for t in targets} <= set(SYMBOLS)
    assert sum(t.weight for t in targets) <= Decimal(1)


def test_decide_book_would_rank_nothing_without_the_market_aware_branch(with_panel):
    """The regression this phase exists to prevent, stated as an assertion.

    `allocator.targets(history, ...)` is the expression decide_book used for every allocator
    before phase 6. For FUNDAMENTAL it is EMPTY_PANEL by construction, so it is not a slower or
    coarser answer -- it is a fixed empty one. If this ever stops being true, the branch in
    decide_book can go; until then removing it silently empties the portfolio.
    """
    e = entry(FND_ID)
    history = {s: h.upto(DATA_DATE) for s, h in with_panel.history.items()}
    members = with_panel.membership.members_on(DATA_DATE)
    assert e.obj.targets(history, members, DATA_DATE, frozenset(), e.params) == ()


def test_decide_book_prepares_fnd_from_the_whole_market(with_panel):
    prepared = entry(FND_ID).obj.prepare_market(with_panel)
    assert isinstance(prepared, FundamentalPrepared)
    assert prepared.panel is with_panel.fundamentals


def test_decide_book_for_fnd_reads_no_bar_from_the_session_on(with_panel):
    """No look-ahead at the roster level: later bars cannot change the decision for DATA_DATE."""
    e = entry(FND_ID)
    before = decide_book(with_panel, e.obj, e.params, e.rules, DATA_DATE, frozenset())
    cut = Market(
        history={s: h.upto(DATA_DATE) for s, h in with_panel.history.items()},
        membership=with_panel.membership,
        fx=tuple(row for row in with_panel.fx if row[0] <= DATA_DATE),
        fundamentals=with_panel.fundamentals,
    )
    assert decide_book(cut, e.obj, e.params, e.rules, DATA_DATE, frozenset()) == before


def test_decide_book_off_a_decision_session_is_none_for_fnd(with_panel):
    e = entry(FND_ID)
    # The session after 2026-10-29 is 2026-10-30, mid-month: not a MONTHLY_HOLD decision session.
    assert decide_book(with_panel, e.obj, e.params, e.rules, date(2026, 10, 29), frozenset()) == (None, False)


# ---- 3. no panel, no trades --------------------------------------------------------------------


def test_a_market_with_no_panel_yields_no_trades_not_wrong_trades(no_panel):
    """The exit criterion, at the roster level.

    EMPTY_FUNDAMENTALS is what every Market carried before the panel landed and what
    `io.load_panel` still returns when `fundamental_facts` is missing or empty -- production's
    state. FND must then target NOTHING. Not a partial basket from whichever symbols happen to
    have a fact; not an exception that fails the paper night for the other five strategies;
    nothing.
    """
    e = entry(FND_ID)
    assert no_panel.fundamentals is EMPTY_FUNDAMENTALS
    targets, idle_added = decide_book(no_panel, e.obj, e.params, e.rules, DATA_DATE, frozenset())
    assert targets == ()
    assert idle_added is False


def test_an_empty_panel_is_the_same_answer_through_both_paths(no_panel):
    """And the empty answer is the SAME empty answer the history-only path gives.

    This is the P4 identity at the roster level: with no panel, the branch decide_book takes
    cannot matter. It is what makes the all-cash outcome a contract rather than a coincidence.
    """
    e = entry(FND_ID)
    history = {s: h.upto(DATA_DATE) for s, h in no_panel.history.items()}
    members = no_panel.membership.members_on(DATA_DATE)
    assert decide_book(no_panel, e.obj, e.params, e.rules, DATA_DATE, frozenset())[0] == ()
    assert e.obj.targets(history, members, DATA_DATE, frozenset(), e.params) == ()


def test_the_night_and_the_replay_decide_fnd_the_same_way(with_panel):
    """Steps 1 and 2 agree -- the one thing an empty panel cannot prove.

    With no panel both dispatch branches return (), so the empty-panel tests above say nothing
    about whether `paper.book.decide_book` and `paper.replay.expected_book` take the SAME branch.
    With a panel they diverge completely, which is why this is the test that would catch a
    `prepared=` left off one half: the night would buy and the replay would find an empty book,
    and `paper_check` would report FND `mismatch` on its very first decision session.
    """
    e = entry(FND_ID)
    # The replay's call, as paper/replay.py makes it: run_rules with the prepared Market.
    prepared = run_rules(with_panel, e.obj, e.params, e.rules, DECIDE_FOR, RUN_END,
                         prepared=prepare_for(e.obj, with_panel))
    # The same call without `prepared=`, which is what replay.py did before phase 6.
    plain = run_rules(with_panel, e.obj, e.params, e.rules, DECIDE_FOR, RUN_END)
    assert plain.fills == (), "the history-only replay of FUNDAMENTAL is a fixed empty book"
    assert prepared.fills, "the prepared replay of FND bought nothing against a real panel"

    # And what it bought on the decision session is what the NIGHT decided for that session.
    targets, _ = decide_book(with_panel, e.obj, e.params, e.rules, DATA_DATE, frozenset())
    bought = {f.symbol for f in prepared.fills if f.session_date == DECIDE_FOR and f.side == "buy"}
    assert bought == {t.symbol for t in targets}

    # Finally the real replay entry point, which is the half that `paper_check` calls: it must
    # reach the prepared branch by itself, from nothing but the allocator's type.
    head = PaperHead(FND_ID, "book", DECIDE_FOR, RUN_END, Decimal("16000.0000"))
    records = expected_book(with_panel, e.obj, e.params, e.rules, head, {})
    assert {f.symbol for f in records.fills if f.session_date == DECIDE_FOR and f.side == "buy"} == bought
    assert dict(records.targets)[DECIDE_FOR] == targets
