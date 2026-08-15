import numpy as np
import pandas as pd
import pytest

from risk_tool.black_litterman import (
    GrowthView,
    black_litterman_returns,
    equilibrium_returns,
    growth_view_to_return,
    reweight_with_view,
)


def _cov():
    tickers = ["AAPL", "META", "NVDA"]
    return pd.DataFrame(
        [
            [0.04, 0.006, 0.008],
            [0.006, 0.05, 0.010],
            [0.008, 0.010, 0.09],
        ],
        index=tickers,
        columns=tickers,
    )


def test_growth_view_annualization():
    # +30% over 2 years annualizes to sqrt(1.3) - 1.
    v = GrowthView("X", growth_pct=0.30, horizon_years=2.0)
    assert growth_view_to_return(v) == pytest.approx(1.3 ** 0.5 - 1.0)


def test_growth_view_bad_horizon():
    with pytest.raises(ValueError):
        growth_view_to_return(GrowthView("X", 0.1, 0.0))


def test_equilibrium_returns_shape():
    cov = _cov()
    mw = pd.Series([0.4, 0.4, 0.2], index=cov.index)
    pi = equilibrium_returns(3.0, cov, mw)
    assert list(pi.index) == list(cov.index)
    assert np.isfinite(pi.values).all()


def test_no_views_returns_prior():
    cov = _cov()
    mw = pd.Series([0.4, 0.4, 0.2], index=cov.index)
    pi = equilibrium_returns(3.0, cov, mw)
    post = black_litterman_returns(pi, cov, [])
    np.testing.assert_allclose(post.values, pi.values)


def test_bullish_view_raises_that_assets_return():
    cov = _cov()
    mw = pd.Series([0.4, 0.4, 0.2], index=cov.index)
    pi = equilibrium_returns(3.0, cov, mw)
    view = GrowthView("NVDA", growth_pct=0.80, horizon_years=1.0)
    post = black_litterman_returns(pi, cov, [view])
    # A strong bullish view should push NVDA's posterior above its prior.
    assert post["NVDA"] > pi["NVDA"]


def test_reweight_with_view_runs_and_normalizes():
    cov = _cov()
    mw = pd.Series([1 / 3, 1 / 3, 1 / 3], index=cov.index)
    view = GrowthView("NVDA", growth_pct=0.50, horizon_years=1.0)
    weights, posterior = reweight_with_view(3.0, cov, mw, [view])
    assert weights.sum() == pytest.approx(1.0, abs=1e-6)
    assert (weights >= -1e-9).all()


def test_view_on_unknown_ticker_raises():
    cov = _cov()
    mw = pd.Series([1 / 3, 1 / 3, 1 / 3], index=cov.index)
    pi = equilibrium_returns(3.0, cov, mw)
    with pytest.raises(ValueError):
        black_litterman_returns(pi, cov, [GrowthView("TSLA", 0.2, 1.0)])
