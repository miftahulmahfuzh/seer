"""Gotrade's fee schedule (Sean plan, phase 6): ``sim.costs`` replays the owner's real receipts.

``tests/fixtures/gotrade_fees.json`` holds the fee columns of all 30 receipts (no tickers,
prices or shares). Every receipt of the CURRENT regime (2026-06-16 on: 22 buys and the one
sell) must come out to the cent; so must every older receipt except LLY 2026-03-25, which paid
$1.08 where 0.3% is $1.10 (the schedule overcharges it by $0.02: conservative, documented in
``sim/costs.py``). No database needed.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from seer_engine.sim import costs
from seer_engine.sim.costs import (
    COST_MODELS,
    GOTRADE,
    FeeParts,
    FeeRegime,
    GotradeSchedule,
    fee_parts,
    gotrade_cash,
    gotrade_shares_for,
)
from seer_engine.sim.model import q

FIXTURE = Path(__file__).parent / "fixtures" / "gotrade_fees.json"
ROWS = json.loads(FIXTURE.read_text())["rows"]
CURRENT_SINCE = date(2026, 6, 16)
# The one receipt the schedule does not reproduce: (date, side, amount) -> (trading, printed).
ANOMALIES = {("2026-03-25", "buy", "366.62"): (Decimal("1.10"), Decimal("1.08"))}
M = Decimal


def _expected(row: dict[str, str]) -> tuple[Decimal, Decimal, Decimal]:
    return M(row["trading"]), M(row["regulatory"]), M(row["ppn"])


def _got(row: dict[str, str], on: date | None) -> FeeParts:
    return fee_parts(row["side"], M(row["amount"]), on)


# ============================================================== the fixture


def test_fixture_is_fee_columns_only_and_complete():
    assert len(ROWS) == 30
    for row in ROWS:
        assert set(row) == {"date", "side", "amount", "trading", "regulatory", "ppn"}
        assert row["side"] in ("buy", "sell")
        date.fromisoformat(row["date"])
        for k in ("amount", "trading", "regulatory", "ppn"):
            assert M(row[k]) == M(row[k]).quantize(Decimal("0.01")) and M(row[k]) >= 0
    assert sum(1 for r in ROWS if r["side"] == "sell") == 1
    assert sum(1 for r in ROWS if date.fromisoformat(r["date"]) >= CURRENT_SINCE) == 23


# ============================================================== the fit


def test_every_current_regime_receipt_to_the_cent():
    current = [r for r in ROWS if date.fromisoformat(r["date"]) >= CURRENT_SINCE]
    assert len(current) == 23
    for row in current:
        for on in (date.fromisoformat(row["date"]), None):  # None is the current regime
            f = _got(row, on)
            assert (f.trading, f.regulatory, f.ppn) == _expected(row), row
            assert f.total == sum(_expected(row)), row


def test_every_older_receipt_to_the_cent_but_the_documented_anomaly():
    for row in ROWS:
        f = _got(row, date.fromisoformat(row["date"]))
        key = (row["date"], row["side"], row["amount"])
        if key in ANOMALIES:
            model, printed = ANOMALIES[key]
            assert (f.trading, M(row["trading"])) == (model, printed)
            assert f.trading - printed == Decimal("0.02")  # the schedule errs on the side of cost
            assert (f.regulatory, f.ppn) == (M(row["regulatory"]), M(row["ppn"]))
            continue
        assert (f.trading, f.regulatory, f.ppn) == _expected(row), row


def test_regimes_and_their_dates():
    assert [r.since for r in GOTRADE.regimes] == [
        date(2025, 6, 10),
        date(2025, 6, 26),
        date(2026, 3, 25),
        date(2026, 6, 16),
    ]
    cur = GOTRADE.current
    assert cur is GOTRADE.regimes[-1] is GOTRADE.regime_on(None)
    assert (cur.trading_rate, cur.trading_min) == (M("0.002"), M("0.10"))
    assert (cur.regulatory_rate, cur.regulatory_cap, cur.sell_extra_rate, cur.ppn_rate) == (
        M("0.00054"),
        M("0.11"),
        M("0.0004"),
        M("0.11"),
    )
    assert GOTRADE.regime_on(date(2026, 6, 15)).trading_rate == M("0.003")
    assert GOTRADE.regime_on(date(2026, 6, 16)) is cur
    assert GOTRADE.regime_on(date(2030, 1, 1)) is cur
    assert GOTRADE.regime_on(date(2025, 6, 25)).ppn_rate == 0
    with pytest.raises(ValueError, match="before 2025-06-10"):
        GOTRADE.regime_on(date(2025, 6, 9))
    with pytest.raises(TypeError):
        GOTRADE.regime_on(datetime(2026, 1, 2))  # type: ignore[arg-type]


# ============================================================== the rules, one by one


def test_trading_fee_rounds_half_up_with_a_ten_cent_minimum():
    assert fee_parts("buy", M("27.90")).trading == M("0.10")  # 0.0558 -> the minimum
    assert fee_parts("buy", M("1673.14")).trading == M("3.35")  # 3.34628 -> half-up
    assert fee_parts("buy", M("50.00")).trading == M("0.10")
    assert fee_parts("buy", M("75.00")).trading == M("0.15")  # 0.15 exactly
    # 2026-03-25: half-up, not up -- $147.55 x 0.3% = 0.44265 printed $0.44
    assert fee_parts("buy", M("147.55"), date(2026, 3, 25)).trading == M("0.44")


def test_regulatory_fee_rounds_up_and_is_capped():
    assert fee_parts("buy", M("27.90")).regulatory == M("0.02")  # 0.015066 -> up
    assert fee_parts("buy", M("105.27")).regulatory == M("0.06")
    assert fee_parts("buy", M("147.55")).regulatory == M("0.08")
    assert fee_parts("buy", M("366.62")).regulatory == M("0.11")  # capped
    assert fee_parts("buy", M("100000")).regulatory == M("0.11")
    assert fee_parts("buy", M("1832.90"), date(2025, 6, 26)).regulatory == M("0.10")  # 2025 cap


def test_sells_pay_an_uncapped_extra_regulatory_part():
    # $72.51: 0.04 (buy formula) + 0.03 (0.04% up) = the receipt's 0.07
    assert fee_parts("sell", M("72.51")).regulatory == M("0.07")
    # $1,000: 0.11 (capped) + 0.40 (uncapped)
    assert fee_parts("sell", M("1000")).regulatory == M("0.51")
    assert fee_parts("sell", M("1000")).total > fee_parts("buy", M("1000")).total


def test_ppn_is_eleven_percent_of_the_printed_fees_rounded_half_down():
    # WDC 2026-06-16: 2.39 + 0.11 = 2.50 -> 0.275 -> printed 0.27 (half-up would say 0.28)
    f = fee_parts("buy", M("1196.77"))
    assert (f.trading, f.regulatory, f.ppn, f.total) == (M("2.39"), M("0.11"), M("0.27"), M("2.77"))


def test_amount_is_taken_to_the_cent_and_only_zero_pays_nothing():
    assert fee_parts("buy", M("27.8951")) == fee_parts("buy", M("27.90"))
    assert fee_parts("buy", M("0")) == FeeParts(M("0.00"), M("0.00"), M("0.00"), M("0.00"))
    assert fee_parts("buy", M("0.004")) == fee_parts("buy", M("0.01"))  # never a free sliver
    assert fee_parts("buy", M("0.004")).trading == M("0.10")
    assert fee_parts("buy", 100) == fee_parts("buy", M("100"))


def test_bad_inputs():
    with pytest.raises(TypeError):
        fee_parts("buy", 27.9)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        fee_parts("buy", True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        fee_parts("buy", M("-1"))
    with pytest.raises(ValueError):
        fee_parts("buy", M("NaN"))
    with pytest.raises(ValueError, match="side"):
        fee_parts("short", M("10"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="total"):
        FeeParts(M("0.10"), M("0.02"), M("0.01"), M("0.14"))
    with pytest.raises(ValueError, match="ascending"):
        GotradeSchedule(regimes=(GOTRADE.regimes[1], GOTRADE.regimes[0]))
    with pytest.raises(ValueError):
        GotradeSchedule(regimes=())
    with pytest.raises(TypeError):
        FeeRegime(
            since=date(2026, 1, 2),
            trading_rate=0.002,  # type: ignore[arg-type]
            trading_min=M("0.10"),
            regulatory_rate=M("0.00054"),
            regulatory_cap=None,
            sell_extra_rate=M(0),
            ppn_rate=M("0.11"),
        )


def test_fees_never_fall_as_the_amount_grows():
    for side in ("buy", "sell"):
        prev = M(0)
        for cents in range(0, 400_000, 37):
            total = fee_parts(side, M(cents) / 100).total
            assert total >= prev, (side, cents)
            prev = total


def test_cost_models():
    assert COST_MODELS == ("flat", "gotrade")


# ============================================================== simulated orders


def test_gotrade_cash_buy_and_sell():
    # q(10.1 x 2.7323) = 27.5962; fees on $27.60: 0.10 + 0.02 + 0.01
    assert gotrade_cash("buy", M("10.1"), M("2.7323")) == (M("27.7262"), M("0.13"))
    # q(10.5 x 2.7323) = 28.6892; fees on $28.69: 0.10 + (0.02 + 0.02) + 0.02
    assert gotrade_cash("sell", M("10.5"), M("2.7323")) == (M("28.5292"), M("0.16"))
    assert gotrade_cash("buy", M("101"), 9) == (M("911.14"), M("2.14"))


def test_a_dust_sale_never_costs_more_than_it_brings_in():
    proceeds, fee = gotrade_cash("sell", M("0.5"), M("0.1"))  # $0.05 of stock
    assert (proceeds, fee) == (M("0.0000"), M("0.0500"))


def test_shares_for_is_exact_and_never_overspends():
    assert gotrade_shares_for(M("28.0000"), M("10.2"), M("0.0001")) == M("2.7323")
    assert gotrade_cash("buy", M("10.2"), M("2.7323"))[0] == M("27.9995")
    assert gotrade_cash("buy", M("10.2"), M("2.7324"))[0] == M("28.0005")
    assert gotrade_shares_for(M("1000"), M("101"), M(1)) == 9
    assert gotrade_shares_for(M("0"), M("10"), M("0.0001")) == 0
    assert gotrade_shares_for(M("0.10"), M("10"), M("0.0001")) == 0  # the minimum fee eats it
    with pytest.raises(ValueError):
        gotrade_shares_for(M("10"), M("0"), M(1))
    with pytest.raises(TypeError):
        gotrade_shares_for(10.0, M("10"), M(1))  # type: ignore[arg-type]


def test_shares_for_is_the_most_that_fits_on_a_grid():
    for budget_cents in (1, 13, 99, 2_790, 2_800, 10_000, 36_662, 99_999, 250_000):
        budget = M(budget_cents) / 100
        for price in (M("0.37"), M("1"), M("10.2"), M("98.765"), M("455.1"), M("1189.736")):
            for quantum in (M("0.0001"), M(1)):
                n = gotrade_shares_for(budget, price, quantum)
                if n > 0:
                    assert gotrade_cash("buy", price, n)[0] <= budget
                assert gotrade_cash("buy", price, n + quantum)[0] > budget
                assert n == q(n) and (n / quantum) == int(n / quantum)


def test_module_is_decimal_only():
    source = Path(costs.__file__).read_text()
    assert "float(" not in source
