"""Market data: prices, returns, and covariance matrices.

Prices are pulled from Yahoo Finance via :mod:`yfinance`. Everything downstream
operates on pandas/numpy objects so the math modules never need to know where
the data came from — which also makes the package easy to test with synthetic
data (see :mod:`tests`).
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from .config import TRADING_DAYS


def get_price_history(
    tickers: Sequence[str],
    period: str = "2y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Download adjusted close prices for ``tickers``.

    Parameters
    ----------
    tickers:
        Iterable of ticker symbols, e.g. ``["AAPL", "META", "NVDA"]``.
    period:
        Any period string accepted by yfinance (``"1y"``, ``"2y"``, ``"5y"`` …).
    interval:
        Sampling interval (``"1d"`` by default).

    Returns
    -------
    pandas.DataFrame
        Columns are tickers, the index is the date, values are adjusted close
        prices. Rows with missing data are dropped.
    """

    import yfinance as yf  # imported lazily so tests/offline use don't need it

    tickers = list(tickers)
    raw = yf.download(
        tickers,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )

    # yfinance returns a column MultiIndex when several fields are present.
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:  # single ticker -> flat columns
        prices = raw[["Close"]]
        prices.columns = tickers

    prices = prices[tickers] if set(tickers).issubset(prices.columns) else prices
    return prices.dropna(how="any")


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily log returns from a price frame."""

    return np.log(prices / prices.shift(1)).dropna(how="any")


def covariance_matrix(
    prices: pd.DataFrame,
    annualize: bool = True,
) -> pd.DataFrame:
    """Covariance matrix of returns derived from ``prices``.

    By default the result is annualized (multiplied by ``TRADING_DAYS``) so it
    is comparable with annualized expected returns.
    """

    rets = log_returns(prices)
    cov = rets.cov()
    if annualize:
        cov = cov * TRADING_DAYS
    return cov


def mean_returns(prices: pd.DataFrame, annualize: bool = True) -> pd.Series:
    """Mean (expected) returns derived from ``prices``.

    Annualized by default so it pairs with :func:`covariance_matrix`.
    """

    rets = log_returns(prices)
    mu = rets.mean()
    if annualize:
        mu = mu * TRADING_DAYS
    return mu


def returns_to_covariance(
    returns: pd.DataFrame,
    annualize: bool = True,
) -> pd.DataFrame:
    """Covariance matrix straight from a returns frame (offline-friendly)."""

    cov = returns.cov()
    return cov * TRADING_DAYS if annualize else cov


def align(*objs: Iterable) -> tuple:
    """Reindex a covariance matrix / return vectors / weights to a common order.

    Accepts pandas objects and returns them aligned on the intersection of their
    labels in a stable order. Useful when combining data from different sources.
    """

    labels = None
    for obj in objs:
        idx = obj.columns if isinstance(obj, pd.DataFrame) else obj.index
        labels = list(idx) if labels is None else [x for x in labels if x in set(idx)]

    aligned = []
    for obj in objs:
        if isinstance(obj, pd.DataFrame):
            aligned.append(obj.loc[labels, labels])
        else:
            aligned.append(obj.loc[labels])
    return tuple(aligned)
