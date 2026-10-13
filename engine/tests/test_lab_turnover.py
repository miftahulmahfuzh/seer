"""``lab turnover``: pricing a book shape against Gotrade's schedule. Report only, N never moves.

The two properties this file exists to defend. First, the arithmetic is the SIMULATOR'S: every
order goes through ``sim.costs.fee_parts``, a re-pick is a sell plus a buy, and the numbers
reproduce the ones ``lab/name_count.py``'s docstring already put on the record -- so the lab can
never hold two different answers to "what does an order cost". Second, the command RECORDS
NOTHING: it is a free sweep over a grid, which is exactly the search the luck gate exists to
charge for, so it may inform a decision and may never be one.
"""

from __future__ import annotations

import ast
from decimal import Decimal as D
from pathlib import Path

import pytest

from seer_engine import cli
from seer_engine.backtest import runner as backtest_runner
from seer_engine.lab import store, turnover
from seer_engine.lab.seed import seed
from seer_engine.paper.compare import SESSIONS_PER_YEAR
from seer_engine.sim import costs
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.model import q
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    conn = store.connect(path)
    seed(conn)
    yield conn, path
    conn.close()


def _untouched(conn):
    """Everything `lab turnover` must leave exactly as it found it -- insights included."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM insights").fetchone()[0],
        conn.execute("SELECT count(*) FROM method_amendments").fetchone()[0],
        tuple(tuple(r) for r in conn.execute(
            "SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


# ---- the arithmetic is the simulator's --------------------------------------------------------


def test_the_opening_round_trip_reproduces_the_recorded_name_count_measurement():
    """1.035% in month 0 and 0.614% by month 3 at twenty names, 0.628% and 0.612% at eleven.

    Those four numbers are on the record in ``lab/name_count.py``'s docstring, measured at
    17,841 IDR/USD. If this module computed anything else, the lab would be holding two
    incompatible answers to the same question and one of them would be wrong.
    """
    cases = {
        (20, 0): D("0.01035"), (20, 3): D("0.00614"),
        (11, 0): D("0.00628"), (11, 3): D("0.00612"),
    }
    for (names, month), expected in cases.items():
        slot = turnover.slot_usd(turnover.equity_usd(month), names)
        buy, sell = turnover.round_trip(slot)
        rate = (buy.total + sell.total) / slot
        assert abs(rate - expected) < D("0.00001"), (names, month, rate)


def test_the_opening_fees_are_the_cents_gotrade_prints():
    """A twenty-name book opens with $28.0253 slots: $0.13 to buy, $0.16 to sell, to the cent."""
    slot = turnover.slot_usd(turnover.equity_usd(0), 20)
    assert slot == D("28.0253")
    buy, sell = turnover.round_trip(slot)
    assert (buy.trading, buy.regulatory, buy.ppn, buy.total) == (D("0.10"), D("0.02"), D("0.01"), D("0.13"))
    assert (sell.trading, sell.regulatory, sell.ppn, sell.total) == (D("0.10"), D("0.04"), D("0.02"), D("0.16"))


def test_a_repick_is_a_sell_plus_a_buy_and_the_sell_is_dearer():
    """P4-D3: the sell pays an uncapped 0.04% the buy does not, at every slot on the ramp."""
    for row in turnover.floor_table([10, 20, 30]):
        assert row.sell_fee > row.buy_fee, row
        assert row.buy_fee == costs.fee_parts("buy", row.slot_usd).total
        assert row.sell_fee == costs.fee_parts("sell", row.slot_usd).total


def test_every_order_in_a_cell_is_priced_through_fee_parts():
    """The cell's total fee equals the hand-computed sum of its own fee_parts calls."""
    p = turnover.price_one("monthly", 20, D("0.50"), years=2)
    expected = D(0)
    for k in range(turnover.REPICKS_PER_YEAR["monthly"] * 2):
        slot = turnover.slot_usd(turnover.equity_usd(k), 20)
        expected += (costs.fee_parts("buy", slot).total + costs.fee_parts("sell", slot).total) * 10
    assert p.fees_usd == expected.quantize(D("0.01"))
    assert p.replaced_per_repick == 10
    assert p.orders == 2 * 10 * 24


def test_ppn_is_never_re_derived_only_called():
    """The module calls fee_parts; it must not reimplement the 11% half-down PPN rounding.

    Grepping is the honest test here: a second implementation of the rounding would be a silent
    second fee schedule, which is exactly what sim/costs.py exists to prevent.
    """
    src = Path(turnover.__file__).read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]  # skip the module docstring, which talks about PPN on purpose
    assert "ROUND_HALF_DOWN" not in body
    assert "0.11" not in body
    assert "ppn" not in body.lower()


# ---- the floor --------------------------------------------------------------------------------


def test_the_floor_boundary_is_forty_seven_dollars_fifty():
    """0.2% of $47.50 is exactly $0.095, which rounds half-up to the $0.10 minimum and ties it."""
    assert turnover.floor_binds(D("47.48")) is True
    assert turnover.floor_binds(D("47.49")) is True
    assert turnover.floor_binds(D("47.50")) is False
    assert turnover.floor_binds(D("47.51")) is False


def test_the_floor_binds_for_two_months_at_twenty_names_and_never_at_ten():
    """P4-D6: the floor is a transient, and how long it lasts depends on the book size."""
    sweep = turnover.measure(cadences=["monthly"], names=[10, 20, 30], churns=[D("1.0")], years=1)
    assert sweep.floor_ends(10) == 0     # the opening slot is $56.05, already above $47.50
    assert sweep.floor_ends(20) == 2     # binds in months 0 and 1 only
    assert sweep.floor_ends(30) == 4     # binds in months 0..3


def test_the_round_trip_rate_falls_as_the_floor_lets_go():
    """The twenty-name ramp goes 1.035% -> 0.737% -> 0.660% -> 0.614% over four months.

    A single static fee number would be wrong by a factor of nearly two across those months,
    which is the reason the floor gets its own table rather than an average.
    """
    rows = [r for r in turnover.floor_table([20]) if r.month < 4]
    rates = [r.round_trip_rate for r in rows]
    assert rates == sorted(rates, reverse=True)
    assert abs(rates[0] - D("0.01035")) < D("0.00001")
    assert abs(rates[3] - D("0.00614")) < D("0.00001")


def test_a_large_slot_pays_the_plain_rate_and_nothing_more():
    """Once the floor is gone a round trip settles near 0.503%: 0.2% a side + 0.04% + PPN."""
    buy, sell = turnover.round_trip(D("1710.00"))
    rate = (buy.total + sell.total) / D("1710.00")
    assert abs(rate - D("0.00503")) < D("0.00001")


# ---- the headline -----------------------------------------------------------------------------


def test_a_daily_chart_model_must_add_more_than_the_market_returns():
    """The number the handover asked for, and the one that kills the idea.

    The cheapest daily book this grid can express -- one name of twenty swapped per session --
    must add about 7% a year to be level with doing nothing, which is roughly what the market
    itself returns. A book that genuinely re-picks itself every session must add about 290%.
    """
    cheapest = turnover.price_one("daily", 20, D("0.05"))
    full = turnover.price_one("daily", 20, D("1.00"))
    assert cheapest.replaced_per_repick == 1
    assert abs(cheapest.breakeven_per_year - D("0.0703")) < D("0.0010")
    assert abs(full.breakeven_per_year - D("2.9045")) < D("0.0100")


def test_the_lab_s_own_monthly_cadence_is_the_cheap_control():
    """The control is a cost the lab already pays, not a number chosen to flatter the comparison."""
    assert MONTHLY_HOLD_FRAC_GOTRADE.cadence == turnover.CONTROL_CADENCE
    control = turnover.price_one("monthly", 20, D("0.25"))
    assert abs(control.breakeven_per_year - D("0.0163")) < D("0.0010")
    weekly = turnover.price_one("weekly", 20, D("0.25"))
    assert abs(weekly.breakeven_per_year - D("0.0727")) < D("0.0010")


def test_break_even_rises_as_the_cadence_shortens():
    """Monotone in the only direction it can be: more re-picks, more orders, more fees."""
    be = [turnover.price_one(c, 20, D("0.50")).breakeven_per_year for c in ("monthly", "weekly", "daily")]
    assert be[0] < be[1] < be[2]


def test_the_answer_does_not_hinge_on_assumed_growth():
    """Zero growth is the default and the conservative one; 10% and 20% move it by under 6%."""
    base = turnover.price_one("daily", 20, D("1.00")).breakeven_per_year
    for g in (D("0.10"), D("0.20")):
        grown = turnover.price_one("daily", 20, D("1.00"), growth=g).breakeven_per_year
        assert abs(grown - base) / base < D("0.06")


# ---- purity and provenance --------------------------------------------------------------------


def test_the_module_opens_nothing():
    """Pure: no clock, no randomness, no network, no database, no research store.

    The one file it may touch is the CSV a caller explicitly names, which is why ``csv`` and
    ``pathlib`` are allowed and nothing else is.
    """
    tree = ast.parse(Path(turnover.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"random", "time", "sqlite3", "urllib", "requests", "numpy", "os"}
    src = Path(turnover.__file__).read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]
    for banned in ("date.today", "datetime.now", "research.load_store", "store.connect", "print("):
        assert banned not in body, banned


def test_the_funding_plan_is_the_owners_real_one():
    """Not a restatement of it: the same objects the runner and the paper book use."""
    assert turnover.SCHEDULE is OWNER_MONTHLY
    assert turnover.SCHEDULE.amount_idr == D("5000000")
    assert turnover.SCHEDULE.day_of_month == 25
    assert turnover.INITIAL_IDR == backtest_runner.INITIAL_IDR == D("10000000")
    assert turnover.REPICKS_PER_YEAR["daily"] == SESSIONS_PER_YEAR == 252
    assert turnover.equity_usd(0) == q(D("10000000") / turnover.USD_IDR)
    assert turnover.equity_usd(3) == q(D("25000000") / turnover.USD_IDR)


@pytest.mark.parametrize("bad", ["daily,hourly", "", "fortnightly"])
def test_check_cadences_refuses_a_horizon_sim_rules_does_not_offer(bad):
    with pytest.raises(store.LabError):
        turnover.check_cadences(bad)


@pytest.mark.parametrize("bad", ["0", "1.5", "-0.2", ""])
def test_check_churns_refuses_a_turnover_outside_zero_to_one(bad):
    with pytest.raises(store.LabError):
        turnover.check_churns(bad)


def test_check_names_refuses_a_single_stock_or_the_whole_index():
    with pytest.raises(store.LabError):
        turnover.check_names("1")
    with pytest.raises(store.LabError):
        turnover.check_names("500")
    assert turnover.check_names("30,10,10") == (10, 30)
    assert turnover.check_names(None) == turnover.NAMES


# ---- the command records nothing ---------------------------------------------------------------


def test_cli_lab_turnover_reports_without_moving_n(lab, capsys, tmp_path):
    """The whole contract in one test: it prints the grid and the lab is byte-identical after."""
    conn, path = lab
    before = _untouched(conn)
    csv_path = tmp_path / "grid.csv"
    assert cli.main([
        "lab", "--db", str(path), "turnover",
        "--cadence", "daily,monthly", "--names", "20", "--churn", "1.0",
        "--years", "2", "--csv", str(csv_path),
    ]) == 0
    out = capsys.readouterr().out
    assert "lab turnover -- what Gotrade charges a book for trading often" in out
    assert "report only" in out
    assert "nothing was recorded" in out
    assert "`lab stage` is not needed" in out
    assert "the $0.10 floor, month by month" in out
    assert csv_path.exists()
    assert _untouched(conn) == before


def test_cli_refuses_a_bad_cadence_with_exit_2(lab):
    _conn, path = lab
    assert cli.main(["lab", "--db", str(path), "turnover", "--cadence", "hourly"]) == 2
    assert cli.main(["lab", "--db", str(path), "turnover", "--churn", "2.0"]) == 2
    assert cli.main(["lab", "--db", str(path), "turnover", "--years", "0"]) == 2


def test_lab_help_still_formats(capsys):
    """Invariant 11: a literal `%` in any `help=` string makes argparse's help renderer die."""
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "turnover" in out
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "turnover", "--help"])
    assert e.value.code == 0
    assert "--cadence" in capsys.readouterr().out
