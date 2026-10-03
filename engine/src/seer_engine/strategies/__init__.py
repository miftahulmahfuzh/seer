"""Trading strategies: pure functions from daily bar history to ranked ``sim.Pick``s.

``base`` holds the interface every strategy implements (P3 Strategy A, P6 B and C) and the
``History`` bar container; ``indicators`` the window functions; ``a`` Strategy A; ``a2``
Strategy A2, the P3b rework (Strategy A plus the pre-registered variants V0–V3); ``b``
Strategy B, the P6a learned cross-sectional ranker (features, ranks, candidates, picks; the
model fitting lives in ``b_model``, which this package never imports, so importing it does not
load scikit-learn). Pure: no database, network, clock or randomness
(tests/test_strategy_purity.py).
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
from seer_engine.strategies.a2 import (
    A2_DESIGN_PARAMS,
    STRATEGY_A2,
    STRATEGY_A2_PARAMS,
    VARIANTS,
    A2Params,
    A2Prepared,
    StrategyA2,
)
from seer_engine.strategies.b import (
    FEATURE_NAMES,
    STRATEGY_B,
    BParams,
    BPrepared,
    Design,
    FrozenModel,
    Predictor,
    StrategyB,
    design_at,
    picks_from_design,
    prepare_b,
)
from seer_engine.strategies.base import History, Strategy, history_from_bars

__all__ = [
    "A2_DESIGN_PARAMS",
    "DESIGN_PARAMS",
    "FEATURE_NAMES",
    "STRATEGY_A",
    "STRATEGY_A2",
    "STRATEGY_A2_PARAMS",
    "STRATEGY_A_PARAMS",
    "STRATEGY_B",
    "VARIANTS",
    "A2Params",
    "A2Prepared",
    "AParams",
    "APrepared",
    "BParams",
    "BPrepared",
    "Design",
    "Features",
    "FrozenModel",
    "History",
    "Predictor",
    "Strategy",
    "StrategyA",
    "StrategyA2",
    "StrategyB",
    "design_at",
    "features_at",
    "history_from_bars",
    "picks_from_design",
    "picks_from_features",
    "prepare_b",
]
