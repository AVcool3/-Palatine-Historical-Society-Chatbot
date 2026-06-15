import numpy as np
import pandas as pd
import pytest

from risk_tool.optimizer import mean_variance_weights, portfolio_stats


def _inputs():
    tickers = ["AAPL", "META", "NVDA"]
    cov = pd.DataFrame(
        [
            [0.04, 0.006, 0.008],
            [0.006, 0.05, 0.010],
            [0.008, 0.010, 0.09],
        ],
        index=tickers,
        columns=tickers,
    )
    mu = pd.Series([0.12, 0.15, 0.25], index=tickers)
    return mu, cov


def test_weights_sum_to_one_and_long_only():
    mu, cov = _inputs()
    w = mean_variance_weights(mu, cov, risk_aversion=3.0)
    assert w.sum() == pytest.approx(1.0, abs=1e-6)
    assert (w >= -1e-9).all()


def test_higher_risk_aversion_reduces_vol():
    mu, cov = _inputs()
    w_low = mean_variance_weights(mu, cov, risk_aversion=1.0)
    w_high = mean_variance_weights(mu, cov, risk_aversion=10.0)
    _, vol_low = portfolio_stats(w_low.values, mu.values, cov.values)
    _, vol_high = portfolio_stats(w_high.values, mu.values, cov.values)
    assert vol_high <= vol_low + 1e-9


def test_dimension_mismatch_raises():
    mu = pd.Series([0.1, 0.2], index=["A", "B"])
    cov = pd.DataFrame(np.eye(3))
    with pytest.raises(ValueError):
        mean_variance_weights(mu, cov, 3.0)
