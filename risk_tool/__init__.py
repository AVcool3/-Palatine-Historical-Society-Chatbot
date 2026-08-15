"""Risk Aversion Parameter Tool.

A small toolkit for deriving a personal risk-aversion parameter (``impval``),
building a covariance matrix and mean-variance weighted portfolio, applying the
Black-Litterman model with user-supplied views, and previewing the result
against an Alpaca paper-trading account.
"""

from .risk_aversion import (
    QUESTIONNAIRE,
    score_questionnaire,
    implied_risk_aversion,
    save_impval,
    load_impval,
)
from .data import get_price_history, covariance_matrix, mean_returns
from .optimizer import mean_variance_weights
from .black_litterman import (
    equilibrium_returns,
    growth_view_to_return,
    black_litterman_returns,
    reweight_with_view,
)
from .robinhood import (
    load_holdings_from_csv,
    load_holdings_from_robinhood,
    holdings_to_weights,
    map_to_alpaca_orders,
)

__version__ = "0.2.0"

__all__ = [
    "QUESTIONNAIRE",
    "score_questionnaire",
    "implied_risk_aversion",
    "save_impval",
    "load_impval",
    "get_price_history",
    "covariance_matrix",
    "mean_returns",
    "mean_variance_weights",
    "equilibrium_returns",
    "growth_view_to_return",
    "black_litterman_returns",
    "reweight_with_view",
    "load_holdings_from_csv",
    "load_holdings_from_robinhood",
    "holdings_to_weights",
    "map_to_alpaca_orders",
]
