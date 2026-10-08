"""The owner's recurring contribution schedule as a value (R3, plan phase 5).

Until now every simulated book was a lump sum that never grew: ``backtest.runner`` converted
``INITIAL_IDR`` once and that was all the money there would ever be. The owner's real plan is
10,000,000 IDR to start and **5,000,000 IDR more on the 25th of every month, indefinitely**
(decided 2026-10-08). This module is that plan as one frozen value.

The schedule names CALENDAR dates, never sessions. The 25th is a date on the owner's bank
statement; whether the NYSE is open that day is the market's business, not the schedule's.
A runner credits a contribution dated ``d`` at the OPEN of the first NYSE session on or after
``d``, which it gets by asking ``due(previous session, this session)`` once per session.

That split is the whole point, and it was measured. The rank sessions are month-start, so a
deposit on the 25th waits for the next rotation before it can be invested:

    deposit      credited     rotation     gap            idle
    2026-10-25   2026-10-26   2026-11-02    8 cal days    5 sessions
    2026-11-25   2026-11-25   2026-12-01    6             3
    2026-12-25   2026-12-28   2027-01-04   10             4
    2027-01-25   2027-01-25   2027-02-01    7             5
    2027-02-25   2027-02-25   2027-03-01    4             2
    2027-03-25   2027-03-25   2027-04-01    7             4
    2027-04-25   2027-04-26   2027-05-03    8             5
    2027-05-25   2027-05-25   2027-06-01    7             4
    2027-06-25   2027-06-25   2027-07-01    6             4
    2027-07-25   2027-07-26   2027-08-02    8             5
    2027-08-25   2027-08-25   2027-09-01    7             5
    2027-09-25   2027-09-27   2027-10-01    6             4

Mean 7.0 calendar days, range 4 (February 2027) to 10 (December 2026); mean 4.2 idle NYSE
sessions, range 2 to 5. A schedule that baked in a fixed seven-day lag would be wrong in ten
months of twelve, and one that deposited at the rotation instead would hold a week less idle
cash every month and so quietly OVERSTATE returns. Reproducing the idle cash is the point.

``day_of_month`` is capped at 28 so a schedule can never silently skip February.

Amounts are in IDR, because that is the currency the owner's money arrives in. A runner converts
with ``usd_at`` at the SAME ``usd_idr`` it converted its starting capital at, so the contributed
dollars and the starting dollars are measured on one rate and the result is about the strategy
rather than about the rupiah.

Pure: no clock, no I/O, no floats, no market calendar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from seer_engine.prices import PRICE_QUANTUM

MAX_DAY_OF_MONTH = 28  # every month has a 28th; 29-31 would skip months


def _date(name: str, x: object) -> date:
    if isinstance(x, datetime) or not isinstance(x, date):
        raise TypeError(f"{name} must be a date, got {type(x).__name__}")
    return x


@dataclass(frozen=True, slots=True)
class ContributionSchedule:
    """``amount_idr`` arriving on ``day_of_month`` of every calendar month, indefinitely."""

    amount_idr: Decimal
    day_of_month: int = 25

    def __post_init__(self) -> None:
        if not isinstance(self.amount_idr, Decimal):
            raise TypeError(f"amount_idr must be a Decimal, got {type(self.amount_idr).__name__}")
        if not self.amount_idr.is_finite() or self.amount_idr <= 0:
            raise ValueError(f"amount_idr must be a finite amount > 0, got {self.amount_idr}")
        if isinstance(self.day_of_month, bool) or not isinstance(self.day_of_month, int):
            raise TypeError(f"day_of_month must be an int, got {type(self.day_of_month).__name__}")
        if not 1 <= self.day_of_month <= MAX_DAY_OF_MONTH:
            raise ValueError(
                f"day_of_month must be 1..{MAX_DAY_OF_MONTH} so no month is skipped, got {self.day_of_month}"
            )

    def dates_in(self, first: date, last: date) -> tuple[date, ...]:
        """Every contribution date in ``[first, last]``, both ends inclusive, ascending."""
        _date("first", first)
        _date("last", last)
        if last < first:
            return ()
        out: list[date] = []
        year, month = first.year, first.month
        while True:
            d = date(year, month, self.day_of_month)
            if d > last:
                break
            if d >= first:
                out.append(d)
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return tuple(out)

    def due(self, after: date, through: date) -> tuple[date, ...]:
        """Every contribution date ``d`` with ``after < d <= through``, ascending.

        This is the per-session question: with ``after`` the previous session and ``through``
        the session being stepped, the answer is every contribution whose first NYSE session on
        or after it is ``through``.
        """
        _date("after", after)
        return self.dates_in(after + timedelta(days=1), through)

    def usd_at(self, usd_idr: Decimal) -> Decimal:
        """One contribution in USD: ``q(amount_idr / usd_idr)``, as ``sim.initial_cash_usd``."""
        if not isinstance(usd_idr, Decimal):
            raise TypeError(f"usd_idr must be a Decimal, got {type(usd_idr).__name__}")
        if not usd_idr.is_finite() or usd_idr <= 0:
            raise ValueError(f"usd_idr must be > 0, got {usd_idr}")
        return (self.amount_idr / usd_idr).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)

    def credit_usd(self, after: date, through: date, usd_idr: Decimal) -> Decimal:
        """The USD landing on ``through``: one ``usd_at`` per date in ``due(after, through)``.

        Each contribution is converted and rounded on its own, so the cash the book receives is
        the sum of the deposits the owner actually makes, not a rounded multiple.
        """
        one = self.usd_at(usd_idr)
        return one * len(self.due(after, through))


#: The owner's plan, measured from his own words (handover §8 Q3, decided 2026-10-08):
#: 5,000,000 IDR on the 25th of each month on top of a 10,000,000 IDR start.
OWNER_MONTHLY = ContributionSchedule(amount_idr=Decimal("5000000"), day_of_month=25)

#: What a runner will accept as funding: the owner's forward-looking PLAN, or a RECORD of deposits
#: that have already happened -- ``(session, usd)`` pairs, ascending, already landed and already
#: converted. Both answer one question, "how many dollars arrive at the open of this session", and
#: :func:`credit_for` is where they become one answer.
Contributions = ContributionSchedule | Sequence[tuple[date, Decimal]]


def credit_for(
    contributions: Contributions, after: date, session: date, usd_idr: Decimal
) -> Decimal:
    """The dollars credited at the open of ``session``, for a plan or for a record.

    A :class:`ContributionSchedule` is a PLAN: it names calendar dates, and the dollars are
    computed here at ``usd_idr``, this run's single rate. That is right for a backtest, which is
    asking about the strategy and not about the rupiah.

    A sequence of ``(session, usd)`` pairs is a RECORD: the deposits already happened, each was
    already converted at the rate of the day it landed, and those dollars are returned unchanged --
    ``usd_idr`` is not consulted at all. That is right for a REPLAY, which must reproduce the
    dollars a paper night actually wrote. ``paper.store.read_contributions`` is where such a record
    comes from: its ``session_date`` is the key and its ``amount_usd`` the value, each frozen at
    ``usd_idr_on(landing session)`` when the deposit was recorded (phase 6, D6a). Recomputing them
    at one rate would move a stepped book's history the first time the rupiah did, which is the
    one thing a replay may never do.

    ``after`` is the previous session; a record's dates are already landing sessions, so the
    window ``after < d <= session`` selects exactly ``d == session``.
    """
    _date("after", after)
    _date("session", session)
    if isinstance(contributions, ContributionSchedule):
        return contributions.credit_usd(after, session, usd_idr)
    if isinstance(contributions, (str, Mapping)) or not isinstance(contributions, Sequence):
        raise TypeError(
            "contributions must be a ContributionSchedule or a sequence of (date, Decimal) "
            f"pairs, got {type(contributions).__name__}"
        )
    total = Decimal("0.0000")
    previous: date | None = None
    for when, amount in contributions:
        _date("contribution date", when)
        if not isinstance(amount, Decimal):
            raise TypeError(f"contribution amount must be a Decimal, got {type(amount).__name__}")
        if amount <= 0:
            raise ValueError(f"contribution amount must be > 0, got {amount}")
        if previous is not None and when <= previous:
            raise ValueError(f"contributions not strictly ascending at {when}")
        previous = when
        if after < when <= session:
            total += amount
    return total
