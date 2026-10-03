"""Seer backtest (P3): Strategy A over the point-in-time universe through the simulator.

Every module here except ``io`` is pure: no database, network, clock or randomness
(tests/test_strategy_purity.py). ``io`` and ``seer_engine.commands.backtest`` are the only
places that read the database or write files. See engine/package_readme.md.
"""
