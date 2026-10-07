"""The delisting stress harness: hazard arithmetic, the perturbation, and its read-only contract.

Everything is synthetic: no research store, no lab database, no Postgres. The store is gitignored
and lives in the main checkout, so a test that needed it would be a test that quietly did not run.

Four groups:

1. ``measure_hazard`` on a market small enough to count by hand, including the two cross-checks
   against the store's recorded ``unserved`` list.
2. ``survivors`` picks the right population -- priced, still in the index at the window's end --
   and clips its exposure to both the window and the symbol's own bars.
3. ``draw_deaths`` is reproducible from its seed, identical at every assumed return, and matches
   the hazard it was given; ``kill`` truncates, marks the last bar down, retires the symbol from
   the index the next day, and leaves the original Market alone.
4. The unchanged engine does the rest: a killed symbol is force-closed at the rewritten mark by
   ``book_runner.run_book``. And the module imports nothing from ``seer_engine.lab``, in its own
   source and in a fresh interpreter, so it can never record a trial or move the lab's N.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from random import Random

import numpy as np
import pytest
from allocatorkit import FIXED, FixedParams
from stratkit import hist, session_days

import seer_engine
from seer_engine import delisting
from seer_engine.backtest.book_runner import run_book
from seer_engine.backtest.dev import DEV_END, MEMBERSHIP_START
from seer_engine.backtest.market import Market, Membership
from seer_engine.delisting import (
    MIN_PRICE,
    Death,
    draw_deaths,
    kill,
    measure_hazard,
    stressed,
    survivors,
)
from seer_engine.prices import to_decimal
from seer_engine.sim.rules import DAILY_SWITCH

SOURCE = Path(seer_engine.__file__).resolve().parent / "delisting.py"

# --------------------------------------------------------------------------- fixtures
#
# One hand-countable market. Window 2001-01-01 .. 2003-01-01 = 730 days = 1.99863 years.
#   AAA  member 2001-01-01 -> open, priced          -- the only survivor that can be killed
#   BBB  member 2001-01-01 -> 2002-01-01, priced    -- already left the index inside the window
#   CCC  member 2001-01-01 -> 2002-07-01, unpriced  -- an unpriced exit (what the harness injects)
#   DDD  member 2001-01-01 -> open, unpriced        -- unpriced and never died: not modellable
#   SPY  never a member, priced
# Mid-year counts: 2001-06-30 -> {AAA,BBB,CCC,DDD} = 4; 2002-06-30 -> {AAA,CCC,DDD} = 3.
# mean 3.5, member_years = round(3.5 x 1.99863) = 7. exits 2 -> 2/7; unpriced exits 1 -> 1/7.

W_START, W_END = date(2001, 1, 1), date(2003, 1, 1)
DAYS = session_days(400, date(2001, 1, 2))
INTERVALS = (
    ("AAA", date(2001, 1, 1), None),
    ("BBB", date(2001, 1, 1), date(2002, 1, 1)),
    ("CCC", date(2001, 1, 1), date(2002, 7, 1)),
    ("DDD", date(2001, 1, 1), None),
)


def counted_market() -> Market:
    return Market(
        history={
            "AAA": hist("AAA", [100.0] * 400, days=DAYS),
            "BBB": hist("BBB", [50.0] * 400, days=DAYS),
            "SPY": hist("SPY", [200.0] * 400, days=DAYS),
        },
        membership=Membership(INTERVALS),
        fx=(),
    )


def flat_market(n: int = 20, symbols: tuple[str, ...] = ("AAA", "BBB")) -> tuple[Market, list[date]]:
    """``n`` sessions of flat 100.00 for each of ``symbols``, all members from the first day."""
    days = session_days(n, date(2001, 1, 2))
    intervals = tuple((s, days[0], None) for s in symbols)
    return (
        Market(
            history={s: hist(s, [100.0] * n, days=days) for s in symbols},
            membership=Membership(intervals),
            fx=(),
        ),
        days,
    )


def uniform_market(count: int, years: int = 10) -> Market:
    """``count`` identical priced survivors, each a member for the whole window."""
    days = session_days(years * 252, date(2001, 1, 2))
    symbols = tuple(f"S{i:03d}" for i in range(count))
    return Market(
        history={s: hist(s, [100.0] * len(days), days=days) for s in symbols},
        membership=Membership(tuple((s, days[0], None) for s in symbols)),
        fx=(),
    )


# --------------------------------------------------------------------------- 1. the hazard


def test_the_window_constants_are_the_dev_windows_own():
    assert (delisting.WINDOW_START, delisting.WINDOW_END) == (MEMBERSHIP_START, DEV_END)


def test_measure_hazard_counts_both_populations_of_the_hole():
    h = measure_hazard(counted_market(), window_start=W_START, window_end=W_END)
    assert (h.ever_members, h.served, h.unserved) == (4, 2, 2)
    assert (h.exits, h.served_exits, h.unserved_exits) == (2, 1, 1)
    assert h.exits_by_year == ((2002, 2),)


def test_member_years_is_the_mid_year_mean_times_the_window_length():
    h = measure_hazard(counted_market(), window_start=W_START, window_end=W_END)
    assert h.mean_members == pytest.approx(3.5)
    assert h.window_years == pytest.approx(730 / 365.25)
    assert h.member_years == 7
    assert h.exit_rate == pytest.approx(2 / 7)
    assert h.unserved_exit_rate == pytest.approx(1 / 7)


def test_an_open_interval_anywhere_means_the_symbol_never_left():
    # AAA in both indices: one interval closes inside the window, the other is still open.
    market = Market(
        history={"AAA": hist("AAA", [100.0] * 400, days=DAYS)},
        membership=Membership((("AAA", date(2001, 1, 1), date(2002, 1, 1)),
                               ("AAA", date(2001, 6, 1), None))),
        fx=(),
    )
    h = measure_hazard(market, window_start=W_START, window_end=W_END)
    assert h.exits == 0


def test_the_unserved_cross_checks_name_both_kinds_of_disagreement():
    market = counted_market()
    silent = measure_hazard(market, window_start=W_START, window_end=W_END)
    assert silent.unrecorded_unserved == ()  # no list passed in is not a disagreement
    assert silent.unserved_but_priced == ()
    partial = measure_hazard(market, unserved=("CCC",), window_start=W_START, window_end=W_END)
    assert partial.unrecorded_unserved == ("DDD",)
    wrong = measure_hazard(market, unserved=("AAA", "CCC", "DDD"),
                           window_start=W_START, window_end=W_END)
    assert wrong.unserved_but_priced == ("AAA",)


def test_measure_hazard_refuses_a_backwards_or_too_short_window():
    market = counted_market()
    with pytest.raises(ValueError, match="must be after"):
        measure_hazard(market, window_start=W_END, window_end=W_START)
    with pytest.raises(ValueError, match="30 June"):
        measure_hazard(market, window_start=date(2001, 7, 1), window_end=date(2002, 6, 1))


# --------------------------------------------------------------------------- 2. who can die


def test_survivors_keeps_only_the_priced_names_still_in_the_index():
    out = survivors(counted_market(), window_start=W_START, window_end=W_END)
    assert [e.symbol for e in out] == ["AAA"]  # BBB left, CCC and DDD have no bars, SPY is no member


def test_survivor_exposure_is_clipped_to_the_window_and_to_the_bars():
    market = counted_market()
    out = survivors(market, window_start=date(2001, 6, 1), window_end=date(2002, 6, 1))
    (exposure,) = out
    bars = market.history["AAA"]
    first = max(date(2001, 6, 1), bars.dates[0].item())
    last = min(date(2002, 6, 1), bars.dates[-1].item())
    assert exposure.spans == ((first, last),)
    assert exposure.days == (last - first).days
    assert exposure.years == pytest.approx(exposure.days / 365.25)


def test_two_touching_intervals_merge_into_one_span():
    days = session_days(400, date(2001, 1, 2))
    market = Market(
        history={"AAA": hist("AAA", [100.0] * 400, days=days)},
        membership=Membership((("AAA", date(2001, 1, 1), date(2001, 7, 1)),
                               ("AAA", date(2001, 7, 1), None))),
        fx=(),
    )
    (exposure,) = survivors(market, window_start=W_START, window_end=W_END)
    assert len(exposure.spans) == 1


def test_a_symbol_with_one_bar_cannot_be_killed():
    days = session_days(1, date(2001, 1, 2))
    market = Market(
        history={"AAA": hist("AAA", [100.0], days=days)},
        membership=Membership((("AAA", date(2001, 1, 1), None),)),
        fx=(),
    )
    assert survivors(market, window_start=W_START, window_end=W_END) == ()


# --------------------------------------------------------------------------- 3. who does die


def test_a_zero_hazard_kills_nobody():
    market = uniform_market(50)
    assert draw_deaths(market, survivors(market, window_start=W_START, window_end=date(2011, 1, 1)),
                       0.0, Random(1)) == ()


def test_the_draw_is_reproducible_from_the_seed_alone():
    market = uniform_market(80)
    pool = survivors(market, window_start=W_START, window_end=date(2011, 1, 1))
    assert draw_deaths(market, pool, 0.05, Random(11)) == draw_deaths(market, pool, 0.05, Random(11))
    assert draw_deaths(market, pool, 0.05, Random(11)) != draw_deaths(market, pool, 0.05, Random(12))


def test_the_same_seed_kills_the_same_names_at_every_assumed_return():
    market = uniform_market(60)
    pool = survivors(market, window_start=W_START, window_end=date(2011, 1, 1))
    _m0, deaths0 = stressed(market, pool, hazard_per_year=0.08, delisting_return=0.0, rng=Random(5))
    _m1, deaths1 = stressed(market, pool, hazard_per_year=0.08, delisting_return=-0.9, rng=Random(5))
    assert deaths0 == deaths1 != ()


def test_the_share_that_dies_matches_the_hazard_it_was_given():
    market = uniform_market(150)
    pool = survivors(market, window_start=W_START, window_end=date(2011, 1, 1))
    expected = 1.0 - np.exp(-0.1 * pool[0].years)
    shares = [len(draw_deaths(market, pool, 0.1, Random(seed))) / len(pool) for seed in range(20)]
    assert float(np.mean(shares)) == pytest.approx(expected, abs=0.05)


def test_every_death_lands_on_a_bar_inside_the_exposure_with_a_later_bar_left():
    market = uniform_market(120)
    pool = survivors(market, window_start=W_START, window_end=date(2011, 1, 1))
    by_symbol = {e.symbol: e for e in pool}
    deaths = draw_deaths(market, pool, 0.3, Random(3))
    assert deaths
    for death in deaths:
        h = market.history[death.symbol]
        assert h.index_of(death.last_bar) is not None  # it is a real bar
        assert death.last_bar < h.dates[-1].item()  # something is always left to force-close
        assert death.last_bar <= by_symbol[death.symbol].spans[-1][1]  # inside the member-time


def test_draw_deaths_refuses_a_bad_rate_or_a_rng_that_is_not_a_Random():
    market = uniform_market(5)
    pool = survivors(market, window_start=W_START, window_end=date(2011, 1, 1))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        draw_deaths(market, pool, 1.5, Random(0))
    with pytest.raises(TypeError, match="random.Random"):
        draw_deaths(market, pool, 0.1, np.random.default_rng(0))


# --------------------------------------------------------------------------- 3b. the perturbation


def test_kill_truncates_the_history_and_rewrites_the_last_bar():
    market, days = flat_market()
    out = kill(market, (Death("AAA", days[9]),), -0.5)
    h = out.history["AAA"]
    assert len(h) == 10
    assert h.last_date() == days[9]
    bar = out.bar("AAA", days[9])
    assert bar.close == to_decimal(50.0)
    assert bar.open == bar.high == bar.low == bar.close  # flat: nothing can fill above the death
    assert out.bar("AAA", days[10]) is None
    assert list(h.close[:9]) == [100.0] * 9  # every earlier bar is exactly what it was


def test_kill_floors_a_total_loss_at_one_price_quantum():
    market, days = flat_market()
    out = kill(market, (Death("AAA", days[5]),), -1.0)
    assert out.bar("AAA", days[5]).close == to_decimal(MIN_PRICE)


def test_a_zero_return_still_flattens_the_last_bar_but_moves_no_price():
    market, days = flat_market()
    out = kill(market, (Death("AAA", days[5]),), 0.0)
    bar = out.bar("AAA", days[5])
    assert bar.close == to_decimal(100.0)
    assert bar.open == bar.high == bar.low == bar.close


def test_kill_retires_the_symbol_from_the_index_the_day_after_its_last_bar():
    market, days = flat_market()
    out = kill(market, (Death("AAA", days[9]),), -0.3)
    assert out.membership.members_on(days[9]) == frozenset({"AAA", "BBB"})
    assert out.membership.members_on(days[10]) == frozenset({"BBB"})
    assert market.membership.members_on(days[10]) == frozenset({"AAA", "BBB"})  # the original stands


def test_kill_leaves_the_market_it_was_given_untouched():
    market, days = flat_market()
    before = len(market.history["AAA"])
    out = kill(market, (Death("AAA", days[9]),), -0.5)
    assert len(market.history["AAA"]) == before
    assert market.history["AAA"].last_date() == days[-1]
    assert out is not market
    assert out.history["BBB"] is market.history["BBB"]  # untouched symbols are shared, not copied


def test_kill_with_no_deaths_returns_the_same_market():
    market, _days = flat_market()
    assert kill(market, (), -0.5) is market


def test_the_forewarned_variant_spreads_the_loss_over_the_last_sessions():
    market, days = flat_market()
    out = kill(market, (Death("AAA", days[9]),), -0.75, decline_sessions=3)
    h = out.history["AAA"]
    step = 0.25 ** (1 / 3)
    assert float(h.close[-1]) == pytest.approx(25.0)
    assert float(h.close[-2]) == pytest.approx(100.0 * step**2)
    assert float(h.close[-3]) == pytest.approx(100.0 * step)
    assert float(h.high[-3]) > float(h.close[-3])  # the decline bars keep their shape: tradable
    assert float(h.high[-1]) == float(h.close[-1])  # the death bar does not
    assert float(h.close[-4]) == pytest.approx(100.0)


def test_kill_refuses_spy_a_missing_symbol_a_repeat_and_a_bad_return():
    market, days = flat_market(symbols=("AAA", "SPY"))
    with pytest.raises(ValueError, match="SPY cannot be delisted"):
        kill(market, (Death("SPY", days[5]),), -0.5)
    with pytest.raises(ValueError, match="no bars in this market"):
        kill(market, (Death("ZZZ", days[5]),), -0.5)
    with pytest.raises(ValueError, match="two death dates"):
        kill(market, (Death("AAA", days[5]), Death("AAA", days[7])), -0.5)
    with pytest.raises(ValueError, match=r"\[-1, 0\]"):
        kill(market, (Death("AAA", days[5]),), 0.5)
    with pytest.raises(ValueError, match="decline_sessions"):
        kill(market, (Death("AAA", days[5]),), -0.5, decline_sessions=0)


# --------------------------------------------------------------------------- 4. the engine, unchanged


def test_the_engine_force_closes_a_killed_symbol_at_the_rewritten_mark():
    """The whole point: no edit to backtest/ or sim/ is needed for any of this to work.

    AAA is killed on day 9 at -50%. `book_runner` finds it gone on day 10 and
    `sim.book.close_book_unpriced` sells it at its mark -- which is the rewritten close.
    """
    market, days = flat_market(n=20, symbols=("AAA", "BBB"))
    stressed_market = kill(market, (Death("AAA", days[9]),), -0.5)
    params = FixedParams(weights=(("AAA", Decimal("0.4")), ("BBB", Decimal("0.4"))))
    result = run_book(stressed_market, FIXED, params, DAILY_SWITCH,
                      days[1], days[-1], usd_idr=Decimal("16000"))
    forced = [t for t in result.trades if t.exit_reason == "forced"]
    assert [(t.symbol, t.exit_date, t.exit_price) for t in forced] == [
        ("AAA", days[10], to_decimal(50.0))
    ]
    assert sorted(p.symbol for p in result.open_at_end) == ["BBB"]


def test_the_unstressed_market_force_closes_nothing():
    market, days = flat_market(n=20, symbols=("AAA", "BBB"))
    params = FixedParams(weights=(("AAA", Decimal("0.4")), ("BBB", Decimal("0.4"))))
    result = run_book(market, FIXED, params, DAILY_SWITCH,
                      days[1], days[-1], usd_idr=Decimal("16000"))
    assert [t for t in result.trades if t.exit_reason == "forced"] == []


# --------------------------------------------------------------------------- 4b. the read-only guard


def _imported_names() -> set[str]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_the_source_imports_no_lab_module_and_no_database_driver():
    """A harness that cannot import the lab's writer cannot record a trial or move N."""
    names = _imported_names()
    assert not {n for n in names if n.startswith("seer_engine.lab")}, names
    assert not {"sqlite3", "psycopg"} & names, names


def _fresh_python(code: str) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(seer_engine.__file__).resolve().parent.parent) + os.pathsep + env.get("PYTHONPATH", "")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env=env, check=True, timeout=180)
    return out.stdout.strip()


def test_importing_the_module_loads_nothing_from_the_lab():
    loaded = _fresh_python(
        "import json, sys; import seer_engine.delisting; "
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('seer_engine.lab'))))"
    )
    assert json.loads(loaded) == []
