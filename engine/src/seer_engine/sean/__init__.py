"""Sean: the owner's real Gotrade orders, marked to market.

- ``ledger``: pure average-cost ledger (plan contract B), the twin of web/lib/sean/ledger.ts.
- ``marks``: daily closes for every symbol the owner has held (``sean_marks``).
- ``equity``: the daily profit/loss series (``sean_equity``) the Overview page draws.

The command is ``python -m seer_engine sean marks`` (commands/sean.py).
"""
