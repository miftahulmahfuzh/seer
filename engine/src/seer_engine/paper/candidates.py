"""The decisions Seer hands to Claude for review, and when a book next ranks (Seer Adversarial, 027).

Claude reviews a roster method's picks before the session they are for opens and says agree,
object or can't tell (the reviewer lives in the owner's notes daemon, mcp-notes, and reads
Seer's database). It cannot re-run Seer's methods and must not try: a second implementation of a
ranking is a second ranking. So the paper night writes down, beside each decision it takes, what
the method ranked, in ``strategy_candidates``; this module is the pure half of that.

- :func:`bracket_candidates`: a bracket method's OWN ranked picks for ``next_session(data_date)``,
  the first :data:`CANDIDATE_TOP`, **before any news veto**. For C (a ``NewsVeto``) that is
  ``strategies.c.candidates`` -- A's ranking cut to C's own ``max_candidates``, the very list
  ``veto`` checks -- and never the allowed subset: a reviewer shown only what C let through could
  not be compared with C on the nights the two disagree. For every other bracket object it is
  ``obj.picks``. It is computed BESIDE the decision, never instead of it: ``decide_bracket`` is
  called exactly as before, so a list can never move a trade.
- :func:`book_candidates`: the targets of a book's rank or kickoff decision, the rule set's idle
  instrument dropped (it is the runner's residual, not a pick), ranked by weight, largest first,
  then symbol. A resize-only decision is never listed (plan D3): it re-scales a basket already
  reviewed at its rank, and an objection takes effect at the next rank.
- :func:`next_rank_session`: the next session on which a book will choose a new basket, so the
  reviewer can look early at a monthly book from its nightly preview without porting Seer's
  cadence rules.

Pure (tests/test_strategy_purity.py globs ``paper/*.py``): no database, clock, logging or I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine import dates
from seer_engine.sim.book import Target
from seer_engine.sim.rules import TradeRules, is_rank_session
from seer_engine.strategies.base import History, Strategy
from seer_engine.strategies.c import NewsVeto
from seer_engine.strategies.c import candidates as c_candidates

#: How many of a bracket method's ranked picks are listed: C's own ``max_candidates``, so A's list
#: and C's list are the same length and the three-way comparison lines up rank for rank.
CANDIDATE_TOP = 10

#: How far :func:`next_rank_session` looks: a year of sessions, more than any cadence's gap.
RANK_SCAN_SESSIONS = 260


@dataclass(frozen=True, slots=True)
class Candidate:
    """One listed pick: its place in the method's ranking and, for a book, its target weight."""

    rank: int
    symbol: str
    weight: Decimal | None = None

    def __post_init__(self) -> None:
        if isinstance(self.rank, bool) or not isinstance(self.rank, int):
            raise TypeError(f"rank must be an int, got {type(self.rank).__name__}")
        if self.rank < 1:
            raise ValueError(f"rank must be >= 1, got {self.rank}")
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(f"symbol must be a non-empty str, got {self.symbol!r}")
        if self.weight is not None:
            if not isinstance(self.weight, Decimal):
                raise TypeError(f"{self.symbol}: weight must be a Decimal, got {type(self.weight).__name__}")
            if not self.weight.is_finite() or self.weight <= 0:
                raise ValueError(f"{self.symbol}: weight must be a positive finite Decimal, got {self.weight!r}")


def bracket_candidates(
    obj: Strategy,
    params: Any,
    history: Mapping[str, History],
    members: Set[str],
    data_date: date,
    *,
    top: int = CANDIDATE_TOP,
) -> tuple[Candidate, ...]:
    """The first ``top`` of ``obj``'s own ranked picks on ``data_date`` (for its next session).

    ``history`` is cut at ``data_date`` here, as ``paper.bracket.decide_bracket`` cuts it, so
    nothing dated after the night is read. A ``NewsVeto`` lists the candidates its check reviews
    (A's ranking), not the ones it allowed. A symbol ranked twice is listed once, at its first rank.
    """
    if isinstance(top, bool) or not isinstance(top, int) or top < 1:
        raise ValueError(f"top must be a positive int, got {top!r}")
    cut = {s: h.upto(data_date) for s, h in history.items()}
    if isinstance(obj, NewsVeto):
        picks = c_candidates(cut, members, data_date, params)
    else:
        picks = obj.picks(cut, members, data_date, params)
    out: list[Candidate] = []
    seen: set[str] = set()
    for p in picks:
        if p.symbol in seen:
            continue
        seen.add(p.symbol)
        out.append(Candidate(rank=len(out) + 1, symbol=p.symbol))
        if len(out) == top:
            break
    return tuple(out)


def book_candidates(targets: Sequence[Target], idle_symbol: str | None) -> tuple[Candidate, ...]:
    """A rank or kickoff decision's targets as a ranked list: ``idle_symbol`` dropped, the rest by
    weight (largest first), then symbol. Empty when the decision holds nothing but the idle row.

    ValueError when a symbol is targeted twice (that is not a book decision).
    """
    if isinstance(targets, (str, Mapping)) or not isinstance(targets, Sequence):
        raise TypeError(f"targets must be a sequence of Target, got {type(targets).__name__}")
    rows: list[Target] = []
    seen: set[str] = set()
    for t in targets:
        if not isinstance(t, Target):
            raise TypeError(f"targets holds Targets, got {type(t).__name__}")
        if idle_symbol is not None and t.symbol == idle_symbol:
            continue
        if t.symbol in seen:
            raise ValueError(f"{t.symbol} is targeted twice; not a book decision")
        seen.add(t.symbol)
        rows.append(t)
    ranked = sorted(rows, key=lambda t: (-t.weight, t.symbol))
    return tuple(Candidate(rank=i, symbol=t.symbol, weight=t.weight) for i, t in enumerate(ranked, start=1))


def next_rank_session(rules: TradeRules, data_date: date, *, kickoff: bool) -> date | None:
    """The next session after ``data_date`` on which a book under ``rules`` chooses a new basket.

    ``kickoff`` says tonight's decision (for ``next_session(data_date)``) is the book's kickoff,
    a rank taken off the cadence (``paper.book.needs_kickoff``): then that session is the answer.
    Otherwise the first ``is_rank_session`` session after ``data_date``; a resize-only session is
    never one. None when no rank session falls within :data:`RANK_SCAN_SESSIONS` sessions.
    """
    nxt = dates.next_session(data_date)
    if kickoff:
        return nxt
    d = nxt
    for _ in range(RANK_SCAN_SESSIONS):
        if is_rank_session(rules, d):
            return d
        d = dates.next_session(d)
    return None
