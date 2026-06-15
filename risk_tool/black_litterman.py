"""Black-Litterman model.

When a new stock is added, the user supplies a *growth prediction over a time
horizon*. We turn that into a Black-Litterman view, blend it with the
market-implied equilibrium returns, and re-optimize.

Reference: He & Litterman (1999), "The Intuition Behind Black-Litterman Model
Portfolios".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import TRADING_DAYS
from .optimizer import mean_variance_weights


def equilibrium_returns(
    risk_aversion: float,
    cov: pd.DataFrame,
    market_weights: pd.Series,
) -> pd.Series:
    """Reverse-optimized equilibrium (prior) returns ``Π = λ Σ w_mkt``.

    These are the returns the market would have to expect to justify holding the
    market-cap weights, given covariance ``Σ`` and risk aversion ``λ``.
    """

    sigma = cov.loc[market_weights.index, market_weights.index]
    pi = float(risk_aversion) * sigma.values @ market_weights.values
    return pd.Series(pi, index=market_weights.index, name="equilibrium_return")


@dataclass(frozen=True)
class GrowthView:
    """A user view: ``ticker`` will grow ``growth_pct`` over ``horizon_years``."""

    ticker: str
    growth_pct: float  # total expected growth over the horizon, e.g. 0.30 = +30%
    horizon_years: float


def growth_view_to_return(view: GrowthView) -> float:
    """Annualize a horizon growth prediction into an expected annual return.

    A prediction of +30% over 2 years annualizes to ``(1.30)^(1/2) - 1``.
    """

    if view.horizon_years <= 0:
        raise ValueError("horizon_years must be positive.")
    return (1.0 + view.growth_pct) ** (1.0 / view.horizon_years) - 1.0


def view_confidence(view: GrowthView) -> float:
    """Heuristic confidence in a view, in (0, 1].

    Nearer-term predictions are treated as more confident than far-out ones.
    """

    # Confidence decays with horizon; capped to a sensible band.
    return float(max(0.1, min(0.9, 1.0 / (1.0 + 0.25 * view.horizon_years))))


def black_litterman_returns(
    equilibrium: pd.Series,
    cov: pd.DataFrame,
    views: list[GrowthView],
    tau: float = 0.05,
) -> pd.Series:
    """Posterior expected returns combining the prior with absolute views.

    Parameters
    ----------
    equilibrium:
        Prior (equilibrium) returns ``Π`` indexed by asset.
    cov:
        Annualized covariance matrix aligned to ``equilibrium``.
    views:
        Absolute growth views, one per (added) ticker.
    tau:
        Scalar on the prior covariance representing uncertainty in ``Π``.

    Returns
    -------
    pandas.Series
        Posterior expected returns ``E[R]`` indexed like ``equilibrium``.
    """

    assets = list(equilibrium.index)
    sigma = cov.loc[assets, assets].values
    pi = equilibrium.values.reshape(-1, 1)
    n = len(assets)

    if not views:
        return pd.Series(pi.flatten(), index=assets, name="posterior_return")

    k = len(views)
    P = np.zeros((k, n))
    Q = np.zeros((k, 1))
    omega_diag = np.zeros(k)

    for i, view in enumerate(views):
        if view.ticker not in assets:
            raise ValueError(f"View ticker {view.ticker!r} not in asset universe.")
        j = assets.index(view.ticker)
        P[i, j] = 1.0
        Q[i, 0] = growth_view_to_return(view)

        # Omega: lower confidence -> larger variance on the view.
        conf = view_confidence(view)
        base = float(P[i] @ (tau * sigma) @ P[i].T)
        omega_diag[i] = base * (1.0 / conf)

    omega = np.diag(np.where(omega_diag > 0, omega_diag, 1e-8))
    tau_sigma = tau * sigma

    # Posterior mean (Black-Litterman master formula).
    tau_sigma_inv = np.linalg.pinv(tau_sigma)
    omega_inv = np.linalg.pinv(omega)
    middle = np.linalg.pinv(tau_sigma_inv + P.T @ omega_inv @ P)
    posterior = middle @ (tau_sigma_inv @ pi + P.T @ omega_inv @ Q)

    return pd.Series(posterior.flatten(), index=assets, name="posterior_return")


def reweight_with_view(
    risk_aversion: float,
    cov: pd.DataFrame,
    market_weights: pd.Series,
    views: list[GrowthView],
    tau: float = 0.05,
    long_only: bool = True,
) -> tuple[pd.Series, pd.Series]:
    """End-to-end Black-Litterman reweighting.

    Computes equilibrium returns, blends in the user's growth views, and
    re-optimizes the portfolio.

    Returns
    -------
    (weights, posterior_returns):
        New target weights and the posterior expected returns used to derive
        them, both indexed by asset.
    """

    pi = equilibrium_returns(risk_aversion, cov, market_weights)
    posterior = black_litterman_returns(pi, cov, views, tau=tau)
    weights = mean_variance_weights(
        posterior,
        cov.loc[posterior.index, posterior.index],
        risk_aversion,
        long_only=long_only,
    )
    return weights, posterior
