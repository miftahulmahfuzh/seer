"""Trading strategies: pure functions from daily bar history to ranked ``sim.Pick``s.

``base`` holds the interface every strategy implements (P3 Strategy A, P6 B and C) and the
``History`` bar container; ``indicators`` the window functions; ``a`` Strategy A. Pure: no
database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from seer_engine.strategies.a import (
    DESIGN_PARAMS,
    STRATEGY_A,
    STRATEGY_A_PARAMS,
    AParams,
    APrepared,
    Features,
    StrategyA,
    features_at,
    picks_from_features,
)
from seer_engine.strategies.base import History, Strategy, history_from_bars

__all__ = [
    "DESIGN_PARAMS",
    "STRATEGY_A",
    "STRATEGY_A_PARAMS",
    "AParams",
    "APrepared",
    "Features",
    "History",
    "Strategy",
    "StrategyA",
    "features_at",
    "history_from_bars",
    "picks_from_features",
]
