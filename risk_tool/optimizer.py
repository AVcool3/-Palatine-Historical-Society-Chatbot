"""Mean-variance portfolio optimization.

Solves the long-only mean-variance problem

.. math::

    \\max_w \\; \\mu^\\top w - \\frac{\\lambda}{2} w^\\top \\Sigma w
    \\quad \\text{s.t.} \\quad \\mathbf{1}^\\top w = 1, \\; w \\ge 0

using SciPy's SLSQP when available, with a robust analytic/clipping fallback so
the package still runs in minimal environments.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _as_arrays(expected_returns, cov):
    mu = np.asarray(expected_returns, dtype=float)
    sigma = np.asarray(cov, dtype=float)
    if sigma.shape[0] != sigma.shape[1] or sigma.shape[0] != mu.shape[0]:
        raise ValueError("Dimensions of expected returns and covariance disagree.")
    return mu, sigma


def mean_variance_weights(
    expected_returns,
    cov,
    risk_aversion: float,
    long_only: bool = True,
) -> pd.Series:
    """Optimal mean-variance weights for a given risk aversion ``λ``.

    Parameters
    ----------
    expected_returns:
        Annualized expected returns (pandas Series or array).
    cov:
        Annualized covariance matrix aligned to ``expected_returns``.
    risk_aversion:
        The ``impval`` (λ). Larger values pull weight toward lower-variance mixes.
    long_only:
        If ``True`` (default), weights are constrained to be non-negative.

    Returns
    -------
    pandas.Series
        Weights summing to 1, indexed by asset when the inputs carry labels.
    """

    mu, sigma = _as_arrays(expected_returns, cov)
    n = len(mu)
    labels = (
        list(expected_returns.index)
        if isinstance(expected_returns, pd.Series)
        else list(range(n))
    )

    weights = _optimize(mu, sigma, float(risk_aversion), long_only)
    return pd.Series(weights, index=labels, name="weight")


def _optimize(mu, sigma, lam, long_only):
    try:
        from scipy.optimize import minimize

        def neg_utility(w):
            return -(mu @ w - 0.5 * lam * w @ sigma @ w)

        def neg_utility_grad(w):
            return -(mu - lam * sigma @ w)

        n = len(mu)
        bounds = [(0.0, 1.0)] * n if long_only else [(-1.0, 1.0)] * n
        constraints = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
        x0 = np.full(n, 1.0 / n)

        result = minimize(
            neg_utility,
            x0,
            jac=neg_utility_grad,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-10},
        )
        if result.success:
            return _normalize(result.x, long_only)
    except Exception:
        pass

    return _analytic_fallback(mu, sigma, lam, long_only)


def _analytic_fallback(mu, sigma, lam, long_only):
    """Closed-form unconstrained solution, then project onto the simplex."""

    n = len(mu)
    try:
        inv = np.linalg.pinv(sigma)
        raw = inv @ mu / lam
    except Exception:
        raw = np.full(n, 1.0 / n)
    return _normalize(raw, long_only)


def _normalize(w, long_only):
    w = np.asarray(w, dtype=float)
    if long_only:
        w = np.clip(w, 0.0, None)
    total = w.sum()
    if total == 0:
        return np.full(len(w), 1.0 / len(w))
    return w / total


def portfolio_stats(weights, expected_returns, cov):
    """Return (expected_return, volatility) for a weight vector."""

    w = np.asarray(weights, dtype=float)
    mu = np.asarray(expected_returns, dtype=float)
    sigma = np.asarray(cov, dtype=float)
    exp_ret = float(mu @ w)
    vol = float(np.sqrt(max(w @ sigma @ w, 0.0)))
    return exp_ret, vol
