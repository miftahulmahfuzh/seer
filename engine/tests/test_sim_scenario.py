"""The hand-checked multi-session scenario, determinism and the benchmark (handover §6.2, §6.3, §7).

Every number below is worked out by hand in the comments, from the plan's Decisions:

- ``buy_cost(p, sh) = q(p * sh * 1.001)`` and ``sell_proceeds(p, sh) = q(p * sh * 0.999)``,
  where ``q`` rounds half-up to 4 dp.
- ``pnl_usd = sell_proceeds(exit) - buy_cost(fill)``.
- Sizing: ``budget = min(q(equity / 4), cash - sum of buy_cost(limit, shares) of pending orders)``,
  ``shares = floor(budget / (limit * 1.001))``, lowest free slot first, picks in the given order.
- Session order: time stop at the open, gap at the open (SL then TP), intraday SL then TP,
  fills, expiries, mark to close. The fill session is day 1. An intraday exit on day k records
  ``days_held = k``; an exit at the open of day k records ``k - 1``.
- Equity = cash + sum(shares * last close), quantized.

The scenario runs over 12 real consecutive NYSE sessions around Thanksgiving 2025
(Thursday 2025-11-27 is a holiday, Friday 2025-11-28 is a half day).
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from simkit import D, P

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim import (
    Event,
    Order,
    Pick,
    Portfolio,
    Rejection,
    Snapshot,
    buy_cost,
    initial_cash_usd,
    new_portfolio,
    size_picks,
    step,
)

INITIAL_IDR = Decimal("20000000")
USD_IDR = Decimal("16250")
# 20,000,000 / 16,250 = 1230.769230... -> 1230.7692
INITIAL_CASH = Decimal("1230.7692")

S1, S2, S3, S4, S5, S6 = (
    D("2025-11-20"),
    D("2025-11-21"),
    D("2025-11-24"),
    D("2025-11-25"),
    D("2025-11-26"),
    D("2025-11-28"),  # after the Thanksgiving holiday; a half day
)
S7, S8, S9, S10, S11, S12 = (
    D("2025-12-01"),
    D("2025-12-02"),
    D("2025-12-03"),
    D("2025-12-04"),
    D("2025-12-05"),
    D("2025-12-08"),
)
SESSIONS = (S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12)


def _pick(symbol: str, last: str, limit: str, tp: str, sl: str) -> Pick:
    return Pick(
        symbol=symbol,
        last_price=P(last),
        limit_price=P(limit),
        tp_price=P(tp),
        sl_price=P(sl),
    )


# PICKS[i] is sized on the night before SESSIONS[i], for SESSIONS[i].
PICKS: tuple[tuple[Pick, ...], ...] = (
    # Night before S1. equity 1230.7692, q(equity / 4) = 307.6923.
    (
        # CCC: avail 1230.7692; 307.6923 / 25.025 = 12.29 -> 12 shares, slot 1.
        #      pending cost buy_cost(25.00, 12) = 300.3000.
        _pick("CCC", "25.40", "25.00", "30.00", "22.00"),
        # AAA: avail 1230.7692 - 300.3000 = 930.4692; 307.6923 / 10.01 = 30.74 -> 30, slot 2.
        #      pending cost 10.00 * 30 * 1.001 = 300.3000.
        _pick("AAA", "10.25", "10.00", "10.80", "9.50"),
        # BBB: avail 630.1692; 307.6923 / 20.02 = 15.37 -> 15, slot 3.
        #      pending cost 20.00 * 15 * 1.001 = 300.3000.
        _pick("BBB", "20.30", "20.00", "21.00", "18.80"),
        # XXX: 307.6923 / 400.40 = 0.77 -> 0 shares -> rejected lt_one_share (ineligible).
        _pick("XXX", "405.00", "400.00", "440.00", "380.00"),
        # DDD: avail 329.8692; 307.6923 / 50.05 = 6.15 -> 6, slot 4.
        _pick("DDD", "50.60", "50.00", "55.00", "47.00"),
        # YYY: all 4 slots taken -> rejected no_slot.
        _pick("YYY", "5.10", "5.00", "5.50", "4.70"),
    ),
    # Night before S2. equity 1246.9767, q(1246.9767 / 4) = q(311.744175) = 311.7442. Free: slot 4.
    (
        # AAA is held (open since S1) -> rejected held (no adding to a holding).
        _pick("AAA", "10.50", "10.40", "11.20", "9.90"),
        # EEE: avail = cash 337.3767; 311.7442 / 40.04 = 7.79 -> 7, slot 4.
        _pick("EEE", "40.50", "40.00", "42.00", "37.00"),
    ),
    # Night before S3. equity 1246.2147, q(311.553675) = 311.5537. Free: slot 3 (BBB stopped out).
    (
        # FFF: avail 338.8147; 311.5537 / 15.015 = 20.75 -> 20, slot 3 (slot reuse after an exit).
        _pick("FFF", "15.20", "15.00", "16.50", "14.00"),
    ),
    # Night before S4. equity 1268.9907, q(317.247675) = 317.2477. Free: slot 2 (AAA took profit).
    (
        # GGG: avail 362.1907; 317.2477 / 30.03 = 10.56 -> 10, slot 2.
        _pick("GGG", "30.40", "30.00", "33.00", "28.00"),
    ),
    # Night before S5: every slot is taken; zero picks is valid.
    (),
    # Night before S6. equity 1288.1087, q(322.027175) = 322.0272. Free: slots 3 and 4.
    (
        # HHH: avail 637.3087; 322.0272 / 12.3123 = 26.15 -> 26, slot 3.
        #      pending cost q(12.30 * 26 * 1.001) = q(320.1198) = 320.1198.
        _pick("HHH", "12.45", "12.30", "13.30", "11.30"),
        # III: avail 637.3087 - 320.1198 = 317.1889 < 322.0272, so the CASH CAP binds.
        #      317.1889 / 16.016 = 19.80 -> 19 (equity / 4 alone would give 20.11 -> 20), slot 4.
        _pick("III", "16.20", "16.00", "17.60", "14.80"),
    ),
    # Night before S7. equity 1291.9761, q(322.994025) = 322.9940. Free: slots 1 (CCC) and 4 (III).
    (
        # JJJ: avail 658.4761; 322.9940 / 8.008 = 40.33 -> 40, slot 1.
        #      pending cost 8.00 * 40 * 1.001 = 320.3200.
        _pick("JJJ", "8.10", "8.00", "8.80", "7.40"),
        # KKK: avail 658.4761 - 320.3200 = 338.1561; 322.9940 / 45.045 = 7.17 -> 7, slot 4.
        _pick("KKK", "45.50", "45.00", "50.00", "42.00"),
    ),
    # Night before S8: every slot is taken.
    (),
    # Night before S9. equity 1329.5023, q(332.375575) = 332.3756. Free: slot 2 (GGG took profit).
    (
        # LLL: avail 353.7023; 332.3756 / 22.022 = 15.09 -> 15, slot 2.
        _pick("LLL", "22.30", "22.00", "24.00", "20.50"),
    ),
    # Nights before S10, S11, S12: zero picks (slots 3 and 1 stay free on purpose).
    (),
    (),
    (),
)

# BARS[i] is SESSIONS[i]'s bars: (symbol, open, high, low, close). Only symbols with a live order.
BARS: tuple[tuple[tuple[str, str, str, str, str], ...], ...] = (
    # S1 2025-11-20
    (
        ("CCC", "25.10", "25.50", "24.80", "25.30"),  # low 24.80 < 25.00, open >= limit: fill at 25.00
        ("AAA", "10.20", "10.30", "9.90", "10.10"),  # low 9.90 < 10.00: fill at 10.00
        ("BBB", "19.50", "20.40", "19.30", "20.20"),  # open 19.50 < 20.00: fill at the OPEN 19.50
        ("DDD", "51.00", "52.00", "50.00", "51.50"),  # low == limit (touch, not below): expires
    ),
    # S2 2025-11-21
    (
        ("CCC", "25.30", "26.00", "25.00", "25.80"),
        ("AAA", "10.10", "10.60", "9.90", "10.50"),
        ("BBB", "20.00", "21.20", "18.80", "19.00"),  # high > TP 21 AND low <= SL 18.80: SL first
        ("EEE", "40.20", "40.50", "39.60", "40.40"),  # fill at 40.00
    ),
    # S3 2025-11-24
    (
        ("CCC", "25.80", "26.50", "25.50", "26.20"),
        ("AAA", "10.50", "10.85", "10.40", "10.70"),  # high 10.85 > TP 10.80: TP intraday
        ("EEE", "40.40", "41.50", "40.10", "41.20"),
        ("FFF", "15.10", "15.30", "14.90", "15.20"),  # fill at 15.00
    ),
    # S4 2025-11-25
    (
        ("CCC", "26.20", "27.00", "26.00", "26.80"),
        ("GGG", "29.80", "30.50", "29.70", "30.30"),  # open 29.80 < 30.00: fill at the open
        ("FFF", "15.20", "15.60", "14.50", "14.60"),
        ("EEE", "41.20", "41.90", "40.80", "41.70"),
    ),
    # S5 2025-11-26
    (
        ("CCC", "26.80", "28.00", "26.50", "27.90"),
        ("GGG", "30.30", "31.80", "30.20", "31.60"),
        ("FFF", "13.80", "14.20", "13.50", "14.00"),  # open 13.80 <= SL 14.00: gap exit at the open
        ("EEE", "42.57", "43.00", "42.10", "42.80"),  # open 42.57 >= TP 42.00: tp exit at the open
    ),
    # S6 2025-11-28 (half day after the holiday)
    (
        ("CCC", "28.10", "30.50", "27.60", "30.20"),  # day 6: time stop at the open, before TP
        ("GGG", "31.60", "32.00", "31.00", "31.50"),
        ("HHH", "12.13", "12.40", "11.95", "12.25"),  # open 12.13 < 12.30: fill at the open
        ("III", "16.20", "16.50", "16.00", "16.40"),  # low == limit: expires
    ),
    # S7 2025-12-01
    (
        ("GGG", "31.50", "32.50", "31.20", "32.40"),
        ("HHH", "12.25", "12.60", "12.00", "12.50"),
        ("JJJ", "8.05", "8.20", "7.90", "8.15"),  # fill at 8.00
        ("KKK", "44.83", "45.60", "44.50", "45.40"),  # open 44.83 < 45.00: fill at the open
    ),
    # S8 2025-12-02
    (
        ("GGG", "32.40", "33.40", "32.20", "33.10"),  # high 33.40 > TP 33.00: TP on day 5
        ("HHH", "12.50", "12.70", "12.20", "12.30"),
        ("JJJ", "8.15", "8.40", "8.05", "8.35"),
        ("KKK", "45.40", "46.20", "45.00", "46.00"),
    ),
    # S9 2025-12-03
    (
        ("HHH", "12.30", "12.40", "11.80", "11.90"),
        ("JJJ", "8.35", "8.60", "8.20", "8.55"),
        ("KKK", "46.00", "46.80", "45.70", "46.50"),
        ("LLL", "22.10", "24.50", "21.80", "22.20"),  # fill at 22.00; high > TP not checked today
    ),
    # S10 2025-12-04
    (
        ("HHH", "11.90", "12.00", "11.30", "11.40"),  # low == SL 11.30 (touch): SL
        ("JJJ", "8.55", "8.75", "8.40", "8.70"),
        ("KKK", "46.50", "47.20", "45.90", "46.10"),
        ("LLL", "22.20", "22.90", "22.00", "22.80"),
    ),
    # S11 2025-12-05
    (
        ("JJJ", "8.70", "8.95", "8.60", "8.90"),  # high 8.95 > TP 8.80: TP on day 5
        ("KKK", "46.10", "46.60", "45.20", "45.60"),
        ("LLL", "22.80", "23.50", "22.60", "23.30"),
    ),
    # S12 2025-12-08
    (
        ("KKK", "45.27", "45.90", "44.70", "45.50"),  # day 6: time stop at the open 45.27
        ("LLL", "23.30", "23.80", "23.00", "23.70"),
    ),
)


@dataclass(frozen=True)
class Run:
    placed: tuple[tuple[Order, ...], ...]
    rejected: tuple[tuple[Rejection, ...], ...]
    events: tuple[tuple[Event, ...], ...]
    snapshots: tuple[Snapshot, ...]
    live: tuple[tuple[Order, ...], ...]
    final: Portfolio


def run_scenario(reverse_bar_order: bool = False) -> Run:
    """P4's nightly loop, 12 times: size the night's picks, then step the session."""
    pf = new_portfolio(initial_cash_usd(INITIAL_IDR, USD_IDR))
    placed, rejected, events, snapshots, live = [], [], [], [], []
    for i, session in enumerate(SESSIONS):
        sized = size_picks(pf, PICKS[i], session)
        placed.append(sized.placed)
        rejected.append(sized.rejected)
        rows = tuple(reversed(BARS[i])) if reverse_bar_order else BARS[i]
        bars = {
            sym: Bar(sym, session, P(o), P(h), P(lo), P(c), 1_000_000)
            for sym, o, h, lo, c in rows
        }
        result = step(sized.portfolio, session, bars)
        pf = result.portfolio
        events.append(result.events)
        snapshots.append(result.snapshot)
        live.append(pf.orders)
    return Run(
        tuple(placed), tuple(rejected), tuple(events), tuple(snapshots), tuple(live), pf
    )


def _order(session: date, slot: int, pick: Pick, shares: int) -> Order:
    return Order(
        session_date=session,
        slot=slot,
        symbol=pick.symbol,
        last_price=pick.last_price,
        limit_price=pick.limit_price,
        tp_price=pick.tp_price,
        sl_price=pick.sl_price,
        shares=shares,
    )


def _ev(e: Event) -> tuple:
    """The parts of an event the Decisions pin down exactly, ``days_held`` included: a fill
    is day 1, an expired order has 0, and an exit records the count the Decisions give."""
    o = e.order
    return (
        e.session_date,
        e.kind,
        o.slot,
        o.symbol,
        o.status,
        o.shares,
        o.fill_date,
        o.fill_price,
        o.exit_date,
        o.exit_price,
        o.exit_reason,
        o.days_held,
        o.pnl_usd,
        e.cash_usd,
        e.forced,
    )


def _fill(d, slot, sym, sh, price, cost):
    return (d, "fill", slot, sym, "open", sh, d, P(price), None, None, None, 1, None,
            Decimal(cost), False)


def _expire(d, slot, sym, sh):
    return (d, "expire", slot, sym, "expired", sh, None, None, None, None, None, 0, None,
            None, False)


def _exit(d, slot, sym, sh, fill_d, fill, price, reason, held, pnl, proceeds):
    return (d, "exit", slot, sym, "closed", sh, fill_d, P(fill), d, P(price), reason, held,
            Decimal(pnl), Decimal(proceeds), False)


# Per session, in phase 1's event order: all exits (any reason) by slot, then all fills by
# slot, then all expiries by slot.
EXPECTED_EVENTS: tuple[tuple[tuple, ...], ...] = (
    # S1
    (
        # buy_cost(25.00, 12): 25.00 * 12 = 300.00 * 1.001 = 300.3000
        _fill(S1, 1, "CCC", 12, "25.00", "-300.3000"),
        # 10.00 * 30 = 300.00 * 1.001 = 300.3000
        _fill(S1, 2, "AAA", 30, "10.00", "-300.3000"),
        # 19.50 * 15 = 292.50 * 1.001 = 292.7925
        _fill(S1, 3, "BBB", 15, "19.50", "-292.7925"),
        _expire(S1, 4, "DDD", 6),
    ),
    # S2
    (
        # BBB day 2, SL intraday at 18.80: 18.80 * 15 = 282.00 * 0.999 = 281.7180
        #   pnl = 281.7180 - 292.7925 = -11.0745; days_held = 2
        _exit(S2, 3, "BBB", 15, S1, "19.50", "18.80", "sl", 2, "-11.0745", "281.7180"),
        # 40.00 * 7 = 280.00 * 1.001 = 280.2800
        _fill(S2, 4, "EEE", 7, "40.00", "-280.2800"),
    ),
    # S3
    (
        # AAA day 3, TP intraday at 10.80: 10.80 * 30 = 324.00 * 0.999 = 323.6760
        #   pnl = 323.6760 - 300.3000 = 23.3760; days_held = 3
        _exit(S3, 2, "AAA", 30, S1, "10.00", "10.80", "tp", 3, "23.3760", "323.6760"),
        # 15.00 * 20 = 300.00 * 1.001 = 300.3000
        _fill(S3, 3, "FFF", 20, "15.00", "-300.3000"),
    ),
    # S4
    (
        # 29.80 * 10 = 298.00 * 1.001 = 298.2980
        _fill(S4, 2, "GGG", 10, "29.80", "-298.2980"),
    ),
    # S5
    (
        # FFF day 3, gap at the open 13.80: 13.80 * 20 = 276.00 * 0.999 = 275.7240
        #   pnl = 275.7240 - 300.3000 = -24.5760; exit at the open of day 3 -> days_held 2
        _exit(S5, 3, "FFF", 20, S3, "15.00", "13.80", "gap", 2, "-24.5760", "275.7240"),
        # EEE day 4, gap through TP at the open 42.57: 42.57 * 7 = 297.99 * 0.999 = 297.69201
        #   -> 297.6920; pnl = 297.6920 - 280.2800 = 17.4120; at the open of day 4 -> 3
        _exit(S5, 4, "EEE", 7, S2, "40.00", "42.57", "tp", 3, "17.4120", "297.6920"),
    ),
    # S6
    (
        # CCC day 6 (across the holiday): time stop at the open 28.10, although high > TP.
        #   28.10 * 12 = 337.20 * 0.999 = 336.8628; pnl = 336.8628 - 300.3000 = 36.5628;
        #   days_held 5
        _exit(S6, 1, "CCC", 12, S1, "25.00", "28.10", "time", 5, "36.5628", "336.8628"),
        # 12.13 * 26 = 315.38 * 1.001 = 315.69538 -> 315.6954
        _fill(S6, 3, "HHH", 26, "12.13", "-315.6954"),
        _expire(S6, 4, "III", 19),
    ),
    # S7
    (
        # 8.00 * 40 = 320.00 * 1.001 = 320.3200
        _fill(S7, 1, "JJJ", 40, "8.00", "-320.3200"),
        # 44.83 * 7 = 313.81 * 1.001 = 314.12381 -> 314.1238
        _fill(S7, 4, "KKK", 7, "44.83", "-314.1238"),
    ),
    # S8
    (
        # GGG day 5, TP intraday at 33.00: 33.00 * 10 = 330.00 * 0.999 = 329.6700
        #   pnl = 329.6700 - 298.2980 = 31.3720; days_held 5
        _exit(S8, 2, "GGG", 10, S4, "29.80", "33.00", "tp", 5, "31.3720", "329.6700"),
    ),
    # S9
    (
        # 22.00 * 15 = 330.00 * 1.001 = 330.3300
        _fill(S9, 2, "LLL", 15, "22.00", "-330.3300"),
    ),
    # S10
    (
        # HHH day 5, SL touched at 11.30: 11.30 * 26 = 293.80 * 0.999 = 293.5062
        #   pnl = 293.5062 - 315.6954 = -22.1892; days_held 5
        _exit(S10, 3, "HHH", 26, S6, "12.13", "11.30", "sl", 5, "-22.1892", "293.5062"),
    ),
    # S11
    (
        # JJJ day 5, TP intraday at 8.80: 8.80 * 40 = 352.00 * 0.999 = 351.6480
        #   pnl = 351.6480 - 320.3200 = 31.3280; days_held 5
        _exit(S11, 1, "JJJ", 40, S7, "8.00", "8.80", "tp", 5, "31.3280", "351.6480"),
    ),
    # S12
    (
        # KKK day 6: time stop at the open 45.27: 45.27 * 7 = 316.89 * 0.999 = 316.57311
        #   -> 316.5731; pnl = 316.5731 - 314.1238 = 2.4493; days_held 5
        _exit(S12, 4, "KKK", 7, S7, "44.83", "45.27", "time", 5, "2.4493", "316.5731"),
    ),
)

# Snapshot after each session: cash, and equity = cash + sum(shares * close).
EXPECTED_SNAPSHOTS = (
    # S1: cash 1230.7692 - 300.3000 - 300.3000 - 292.7925 = 337.3767
    #     equity 337.3767 + 12*25.30 (303.60) + 30*10.10 (303.00) + 15*20.20 (303.00) = 1246.9767
    Snapshot(S1, Decimal("337.3767"), Decimal("1246.9767")),
    # S2: cash 337.3767 + 281.7180 - 280.2800 = 338.8147
    #     equity 338.8147 + 12*25.80 (309.60) + 30*10.50 (315.00) + 7*40.40 (282.80) = 1246.2147
    Snapshot(S2, Decimal("338.8147"), Decimal("1246.2147")),
    # S3: cash 338.8147 + 323.6760 - 300.3000 = 362.1907
    #     equity 362.1907 + 12*26.20 (314.40) + 20*15.20 (304.00) + 7*41.20 (288.40) = 1268.9907
    Snapshot(S3, Decimal("362.1907"), Decimal("1268.9907")),
    # S4: cash 362.1907 - 298.2980 = 63.8927
    #     equity 63.8927 + 12*26.80 (321.60) + 10*30.30 (303.00) + 20*14.60 (292.00)
    #            + 7*41.70 (291.90) = 1272.3927
    Snapshot(S4, Decimal("63.8927"), Decimal("1272.3927")),
    # S5: cash 63.8927 + 275.7240 + 297.6920 = 637.3087
    #     equity 637.3087 + 12*27.90 (334.80) + 10*31.60 (316.00) = 1288.1087
    Snapshot(S5, Decimal("637.3087"), Decimal("1288.1087")),
    # S6: cash 637.3087 + 336.8628 - 315.6954 = 658.4761
    #     equity 658.4761 + 10*31.50 (315.00) + 26*12.25 (318.50) = 1291.9761
    Snapshot(S6, Decimal("658.4761"), Decimal("1291.9761")),
    # S7: cash 658.4761 - 320.3200 - 314.1238 = 24.0323
    #     equity 24.0323 + 40*8.15 (326.00) + 10*32.40 (324.00) + 26*12.50 (325.00)
    #            + 7*45.40 (317.80) = 1316.8323
    Snapshot(S7, Decimal("24.0323"), Decimal("1316.8323")),
    # S8: cash 24.0323 + 329.6700 = 353.7023
    #     equity 353.7023 + 40*8.35 (334.00) + 26*12.30 (319.80) + 7*46.00 (322.00) = 1329.5023
    Snapshot(S8, Decimal("353.7023"), Decimal("1329.5023")),
    # S9: cash 353.7023 - 330.3300 = 23.3723
    #     equity 23.3723 + 40*8.55 (342.00) + 15*22.20 (333.00) + 26*11.90 (309.40)
    #            + 7*46.50 (325.50) = 1333.2723
    Snapshot(S9, Decimal("23.3723"), Decimal("1333.2723")),
    # S10: cash 23.3723 + 293.5062 = 316.8785
    #      equity 316.8785 + 40*8.70 (348.00) + 15*22.80 (342.00) + 7*46.10 (322.70) = 1329.5785
    Snapshot(S10, Decimal("316.8785"), Decimal("1329.5785")),
    # S11: cash 316.8785 + 351.6480 = 668.5265
    #      equity 668.5265 + 15*23.30 (349.50) + 7*45.60 (319.20) = 1337.2265
    Snapshot(S11, Decimal("668.5265"), Decimal("1337.2265")),
    # S12: cash 668.5265 + 316.5731 = 985.0996
    #      equity 985.0996 + 15*23.70 (355.50) = 1340.5996
    Snapshot(S12, Decimal("985.0996"), Decimal("1340.5996")),
)

# Live orders after each step: (slot, symbol, status, days_held). The fill session is day 1.
EXPECTED_LIVE = (
    ((1, "CCC", "open", 1), (2, "AAA", "open", 1), (3, "BBB", "open", 1)),
    ((1, "CCC", "open", 2), (2, "AAA", "open", 2), (4, "EEE", "open", 1)),
    ((1, "CCC", "open", 3), (3, "FFF", "open", 1), (4, "EEE", "open", 2)),
    ((1, "CCC", "open", 4), (2, "GGG", "open", 1), (3, "FFF", "open", 2), (4, "EEE", "open", 3)),
    ((1, "CCC", "open", 5), (2, "GGG", "open", 2)),
    ((2, "GGG", "open", 3), (3, "HHH", "open", 1)),
    ((1, "JJJ", "open", 1), (2, "GGG", "open", 4), (3, "HHH", "open", 2), (4, "KKK", "open", 1)),
    ((1, "JJJ", "open", 2), (3, "HHH", "open", 3), (4, "KKK", "open", 2)),
    ((1, "JJJ", "open", 3), (2, "LLL", "open", 1), (3, "HHH", "open", 4), (4, "KKK", "open", 3)),
    ((1, "JJJ", "open", 4), (2, "LLL", "open", 2), (4, "KKK", "open", 4)),
    ((2, "LLL", "open", 3), (4, "KKK", "open", 5)),
    ((2, "LLL", "open", 4),),
)

# Closed trades: symbol -> pnl_usd (from EXPECTED_EVENTS). Sum = 84.6604.
EXPECTED_PNL = {
    "BBB": Decimal("-11.0745"),
    "AAA": Decimal("23.3760"),
    "FFF": Decimal("-24.5760"),
    "EEE": Decimal("17.4120"),
    "CCC": Decimal("36.5628"),
    "GGG": Decimal("31.3720"),
    "HHH": Decimal("-22.1892"),
    "JJJ": Decimal("31.3280"),
    "KKK": Decimal("2.4493"),
}


def test_scenario_runs_on_consecutive_nyse_sessions():
    assert len(SESSIONS) >= 10
    assert SESSIONS == tuple(dates.sessions(S1, S12))
    assert D("2025-11-27") not in SESSIONS  # Thanksgiving: no session, no day counted


def test_scenario_initial_cash():
    assert initial_cash_usd(INITIAL_IDR, USD_IDR) == INITIAL_CASH


def test_scenario_sizing_each_night():
    run = run_scenario()
    p = PICKS
    assert run.placed == (
        (
            _order(S1, 1, p[0][0], 12),
            _order(S1, 2, p[0][1], 30),
            _order(S1, 3, p[0][2], 15),
            _order(S1, 4, p[0][4], 6),
        ),
        (_order(S2, 4, p[1][1], 7),),
        (_order(S3, 3, p[2][0], 20),),
        (_order(S4, 2, p[3][0], 10),),
        (),
        (_order(S6, 3, p[5][0], 26), _order(S6, 4, p[5][1], 19)),  # III capped by cash
        (_order(S7, 1, p[6][0], 40), _order(S7, 4, p[6][1], 7)),
        (),
        (_order(S9, 2, p[8][0], 15),),
        (),
        (),
        (),
    )
    assert run.rejected == (
        (Rejection("XXX", "lt_one_share"), Rejection("YYY", "no_slot")),
        (Rejection("AAA", "held"),),
        (), (), (), (), (), (), (), (), (), (),
    )


def test_scenario_events_each_session():
    run = run_scenario()
    assert len(run.events) == len(EXPECTED_EVENTS)
    for session, got, want in zip(SESSIONS, run.events, EXPECTED_EVENTS):
        assert tuple(_ev(e) for e in got) == want, session


def test_scenario_every_snapshot():
    assert run_scenario().snapshots == EXPECTED_SNAPSHOTS


def test_scenario_live_orders_and_days_held():
    run = run_scenario()
    got = tuple(
        tuple((o.slot, o.symbol, o.status, o.days_held) for o in live) for live in run.live
    )
    assert got == EXPECTED_LIVE


def test_scenario_every_closed_trade_pnl():
    run = run_scenario()
    exits = [e for session in run.events for e in session if e.kind == "exit"]
    assert {e.order.symbol: e.order.pnl_usd for e in exits} == EXPECTED_PNL
    assert len(exits) == len(EXPECTED_PNL)
    assert sum(EXPECTED_PNL.values()) == Decimal("84.6604")
    # Handover §3 formula, unrounded: (exit - fill) * sh - 0.001 * (exit + fill) * sh.
    # The simulator's rounded pnl matches it to within 0.0001.
    for e in exits:
        o = e.order
        formula = (o.exit_price - o.fill_price) * o.shares - Decimal("0.001") * (
            o.exit_price + o.fill_price
        ) * o.shares
        assert abs(o.pnl_usd - formula) <= Decimal("0.0001"), o.symbol


def test_scenario_cash_reconciles_with_events_and_pnl():
    run = run_scenario()
    previous = INITIAL_CASH
    for snap, events in zip(run.snapshots, run.events):
        moved = sum((e.cash_usd for e in events if e.cash_usd is not None), Decimal("0"))
        assert snap.cash_usd - previous == moved, snap.date
        previous = snap.cash_usd
    # Closed P/L reconciles with the cash change once the open position's cost is put back:
    # 985.0996 - 1230.7692 = -245.6696 = 84.6604 - buy_cost(22.00, 15) (330.3300).
    open_cost = sum(
        (buy_cost(o.fill_price, o.shares) for o in run.final.orders if o.status == "open"),
        Decimal("0"),
    )
    assert open_cost == Decimal("330.3300")
    assert run.final.cash - INITIAL_CASH == sum(EXPECTED_PNL.values()) - open_cost
    assert run.final.cash - INITIAL_CASH == Decimal("-245.6696")


def test_scenario_final_portfolio():
    final = run_scenario().final
    assert final.cash == Decimal("985.0996")
    assert final.equity == Decimal("1340.5996")
    assert final.last_session == S12
    assert final.marks == (("LLL", Decimal("23.7000")),)
    assert final.orders == (
        Order(
            session_date=S9,
            slot=2,
            symbol="LLL",
            last_price=P("22.30"),
            limit_price=P("22.00"),
            tp_price=P("24.00"),
            sl_price=P("20.50"),
            shares=15,
            status="open",
            fill_date=S9,
            fill_price=P("22.00"),
            days_held=4,
        ),
    )


def test_scenario_is_deterministic():
    first = run_scenario()
    second = run_scenario()
    assert first == second
    assert repr(first) == repr(second)  # also the exact Decimal spellings
    # The insertion order of the bars mapping must not leak into any output.
    assert repr(run_scenario(reverse_bar_order=True)) == repr(first)


# ---------------------------------------------------------------------------------------
# Benchmark (handover §7): 2,950 sessions x 4 slots on synthetic bars, Decimal throughout.
# ---------------------------------------------------------------------------------------

BENCH_SESSIONS = 2950
BENCH_BOUND_S = 20.0
_LIMIT, _TP, _SL, _LAST = P("99.50"), P("106.00"), P("96.00"), P("100.00")
# (open, high, low, close) shapes against limit 99.50 / TP 106 / SL 96.
_SHAPES = {
    "quiet": (P("100.00"), P("101.00"), P("99.00"), P("100.00")),  # fills a pending order
    "nofill": (P("100.00"), P("101.00"), P("99.60"), P("100.50")),  # low >= limit: expires
    "tp": (P("100.00"), P("107.00"), P("99.00"), P("105.00")),  # high > TP
    "sl": (P("100.00"), P("101.00"), P("95.50"), P("97.00")),  # low <= SL
    "gap": (P("95.00"), P("96.50"), P("94.00"), P("95.50")),  # open <= SL
}
# Each placed order gets the next plan in this cycle; "time" means quiet until the day-6 open.
_PLANS = ("tp", "sl", "time", "expire", "gap", "tp", "sl", "time")
_TRIGGER_DAY = {"tp": 3, "sl": 2, "gap": 4}


def _bench_shape(order: Order, plan: str) -> str:
    if order.status == "pending":
        return "nofill" if plan == "expire" else "quiet"
    return plan if _TRIGGER_DAY.get(plan) == order.days_held + 1 else "quiet"


def test_benchmark_2950_sessions_x_4_slots():
    sessions = dates.sessions(D("2015-01-02"), D("2026-10-02"))[:BENCH_SESSIONS]
    assert len(sessions) == BENCH_SESSIONS
    pf = new_portfolio(Decimal("100000"))
    plan_of: dict[str, str] = {}
    placed_count = 0
    kinds: Counter[tuple[str, str | None]] = Counter()
    snapshots = 0
    started = time.perf_counter()
    for i, session in enumerate(sessions):
        picks = [
            Pick(
                symbol=f"S{i}_{j}",
                last_price=_LAST,
                limit_price=_LIMIT,
                tp_price=_TP,
                sl_price=_SL,
            )
            for j in range(4)
        ]
        sized = size_picks(pf, picks, session)
        for order in sized.placed:
            plan_of[order.symbol] = _PLANS[placed_count % len(_PLANS)]
            placed_count += 1
        bars = {}
        for order in sized.portfolio.orders:
            o, h, lo, c = _SHAPES[_bench_shape(order, plan_of[order.symbol])]
            bars[order.symbol] = Bar(order.symbol, session, o, h, lo, c, 1_000_000)
        result = step(sized.portfolio, session, bars)
        pf = result.portfolio
        snapshots += 1
        for e in result.events:
            kinds[(e.kind, e.order.exit_reason)] += 1
    elapsed = time.perf_counter() - started
    print(f"\nbenchmark: {BENCH_SESSIONS} sessions x 4 slots in {elapsed:.3f} s; {dict(kinds)}")
    assert snapshots == BENCH_SESSIONS
    for key in (("fill", None), ("expire", None), ("exit", "tp"), ("exit", "sl"),
                ("exit", "gap"), ("exit", "time")):
        assert kinds[key] > 0, key
    assert pf.equity > 0
    assert elapsed < BENCH_BOUND_S
