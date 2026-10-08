"""The money of the bracket path, priced by a rule set's cost model (plan set phase 4).

``sim.model.buy_cost`` and ``sell_proceeds`` multiply one module-level constant, ``COST_RATE``:
every design §5 fill paid an assumed 0.1% a side whatever its rule set said, and
``sim.sizing`` precomputed ``1 + COST_RATE`` at import. Gotrade's measured schedule
(``sim.costs``, fitted to the owner's receipts) is not proportional -- a $0.10 minimum on every
order, a capped regulatory fee -- so the bracket path has to be handed the rule set and ask it.

Four functions, the bracket twins of ``sim.book``'s private helpers:

- :func:`buy_cash` -- cash out to buy ``shares`` at ``price``;
- :func:`sell_cash` -- cash in selling them;
- :func:`order_fee` -- the fee inside one of those two numbers;
- :func:`whole_shares_for` -- the most WHOLE shares whose buy cash fits a budget.

Under ``cost_model="flat"`` each is the old arithmetic with ``rules.cost_rate`` in place of the
constant, so ``buy_cash(p, n, DESIGN_V0) == sim.model.buy_cost(p, n)`` and
``sell_cash(p, n, DESIGN_V0) == sim.model.sell_proceeds(p, n)`` exactly, for every price and
share count (pinned by ``tests/test_sim_sizing.py``). That is what keeps the closed A, A2, B and
C records byte-identical.

Shares are whole: a bracket ``Order`` holds an ``int`` share count. A fractional rule set is a
book rule set and :func:`bracket_rules` refuses it here.

Pure: no clock, no I/O, no randomness, no floats.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

from seer_engine.sim.costs import SIDES, Side, gotrade_cash, gotrade_shares_for
from seer_engine.sim.model import q
from seer_engine.sim.rules import BRACKET_ENGINES, TradeRules

_ONE = Decimal(1)


def _price(name: str, x: object) -> Decimal:
    if not isinstance(x, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(x).__name__}")
    if not x.is_finite():
        raise ValueError(f"{name} must be finite, got {x!r}")
    if x <= 0:
        raise ValueError(f"{name} must be > 0, got {x}")
    return x


def _shares(name: str, x: object) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{name} must be an int, got {type(x).__name__}")
    if x < 0:
        raise ValueError(f"{name} must be >= 0, got {x}")
    return x


def bracket_rules(rules: object) -> TradeRules:
    """``rules`` if the bracket path can run them; TypeError or ValueError saying why not.

    A book rule set belongs to ``sim.book.step_book``, and a fractional one cannot be held in a
    bracket ``Order`` at all (``sim.model.Order.shares`` is an ``int``).
    """
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
    if rules.engine not in BRACKET_ENGINES:
        raise ValueError(
            f"rules {rules.id!r} run the {rules.engine!r} engine; the bracket path takes one of "
            f"{BRACKET_ENGINES} (run a book rule set with sim.book.step_book)"
        )
    if rules.fractional:
        raise ValueError(
            f"rules {rules.id!r} are fractional; a bracket order holds a whole share count "
            f"(sim.model.Order.shares is an int)"
        )
    return rules


def buy_cash(price: Decimal, shares: int, rules: TradeRules) -> Decimal:
    """Cash paid to buy ``shares`` at ``price`` under ``rules``.

    "flat": ``q(price x shares x (1 + rules.cost_rate))`` -- ``sim.model.buy_cost`` with the rule
    set's own rate. "gotrade": ``q(price x shares)`` plus the measured schedule's fee, which
    carries a $0.10 per-order minimum (``sim.costs.gotrade_cash``).
    """
    _price("price", price)
    _shares("shares", shares)
    bracket_rules(rules)
    if rules.cost_model == "gotrade":
        return gotrade_cash("buy", price, shares)[0]
    return q(price * shares * (_ONE + rules.cost_rate))


def sell_cash(price: Decimal, shares: int, rules: TradeRules) -> Decimal:
    """Cash received selling ``shares`` at ``price`` under ``rules``.

    "flat": ``q(price x shares x (1 - rules.cost_rate))`` -- ``sim.model.sell_proceeds`` with the
    rule set's own rate. "gotrade": ``q(price x shares)`` less the schedule's fee, the fee capped
    at the amount so a dust sale never costs more than it brings in.
    """
    _price("price", price)
    _shares("shares", shares)
    bracket_rules(rules)
    if rules.cost_model == "gotrade":
        return gotrade_cash("sell", price, shares)[0]
    return q(price * shares * (_ONE - rules.cost_rate))


def order_fee(side: Side, price: Decimal, shares: int, rules: TradeRules) -> Decimal:
    """The fee inside one order's cash: ``buy_cash - amount``, or ``amount - sell_cash``.

    The bracket simulator does not record a per-fill fee (an ``Order`` has no cost column), so
    nothing in ``sim`` calls this; it is here so a reporting caller never has to re-derive the
    schedule. ``side`` matters only under "gotrade", which charges more on a sell.
    """
    if side not in SIDES:
        raise ValueError(f"side must be one of {SIDES}, got {side!r}")
    _price("price", price)
    _shares("shares", shares)
    bracket_rules(rules)
    if rules.cost_model == "gotrade":
        return gotrade_cash(side, price, shares)[1]
    return q(price * shares * rules.cost_rate)


def whole_shares_for(budget: Decimal, price: Decimal, rules: TradeRules) -> int:
    """The most whole shares at ``price`` whose :func:`buy_cash` fits ``budget``; 0 when none does.

    "flat": ``floor(budget / (price x (1 + rules.cost_rate)))``, stepped back while the exact
    unrounded cost exceeds the budget -- ``sim.sizing._whole_shares`` verbatim, with the rule
    set's rate in place of the import-time ``_ONE_PLUS_COST``. Decimal division rounds to 28
    significant digits, so a quotient a hair under an integer could round up to it.

    "gotrade": there is no unit cost to divide by, because the $0.10 minimum makes the fee
    non-proportional in the share count. The cost never falls as shares grow, so the answer is
    SOLVED by bisection on the rounded cash (``sim.costs.gotrade_shares_for``, which
    ``sim.book._shares_for`` already uses for the book engine). It never overspends.
    """
    _price("price", price)
    if not isinstance(budget, Decimal):
        raise TypeError(f"budget must be a Decimal, got {type(budget).__name__}")
    if not budget.is_finite():
        raise ValueError(f"budget must be finite, got {budget!r}")
    bracket_rules(rules)
    if budget <= 0:
        return 0
    if rules.cost_model == "gotrade":
        return int(gotrade_shares_for(budget, price, _ONE))
    unit = price * (_ONE + rules.cost_rate)
    shares = int((budget / unit).to_integral_value(rounding=ROUND_FLOOR))
    while shares > 0 and unit * shares > budget:
        shares -= 1
    return max(shares, 0)
