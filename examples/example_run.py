"""Offline demo of the full workflow using synthetic price data.

No network, no API keys, no extra dependencies beyond numpy/pandas. Run with:

    python examples/example_run.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

# Allow running directly (``python examples/example_run.py``) without install.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from risk_tool.black_litterman import GrowthView, reweight_with_view
from risk_tool.broker import preview_orders
from risk_tool.data import returns_to_covariance
from risk_tool.optimizer import mean_variance_weights, portfolio_stats
from risk_tool.risk_aversion import (
    implied_risk_aversion,
    save_impval,
    score_questionnaire,
)


def synthetic_returns(tickers, days=504, seed=7):
    """Generate correlated daily returns so the demo is deterministic."""

    rng = np.random.default_rng(seed)
    n = len(tickers)
    # Distinct drifts/vols per asset, plus a shared market factor.
    drift = np.linspace(0.0004, 0.0009, n)
    vol = np.linspace(0.015, 0.03, n)
    market = rng.normal(0, 0.01, size=days)
    data = {}
    for i, t in enumerate(tickers):
        idio = rng.normal(0, vol[i], size=days)
        data[t] = drift[i] + 0.6 * market + idio
    return pd.DataFrame(data)


def main():
    tickers = ["AAPL", "META", "NVDA"]
    returns = synthetic_returns(tickers)
    cov = returns_to_covariance(returns)
    mu = returns.mean() * 252

    print("Example portfolio:", ", ".join(tickers))
    print("\nAnnualized expected returns:")
    print(mu.round(4).to_string())

    # 1) impval from a questionnaire ----------------------------------------
    answers = {
        "horizon": "7-15 years",
        "drawdown": "Hold and wait it out",
        "loss_tolerance": "20-40%",
        "goal": "Grow steadily with some ups and downs",
        "experience": "Some experience",
    }
    impval_q = score_questionnaire(answers)
    print(f"\n[Questionnaire] impval (λ) = {impval_q}")

    # 2) impval implied from a past portfolio -------------------------------
    past_w = pd.Series([0.5, 0.3, 0.2], index=tickers)
    impval_p = implied_risk_aversion(past_w.values, cov.values, mu.values)
    print(f"[Past portfolio] implied impval (λ) = {impval_p}")

    impval = impval_q
    save_impval(impval, meta={"source": "questionnaire (demo)"})
    print(f"Using impval = {impval} (saved to impval.json)")

    # 3) base mean-variance weights -----------------------------------------
    weights = mean_variance_weights(mu, cov, impval)
    print("\n--- Base mean-variance portfolio ---")
    for sym, wt in weights.items():
        print(f"  {sym:<6} {wt:7.2%}")
    exp_ret, vol = portfolio_stats(weights.values, mu.values, cov.values)
    print(f"  Expected return {exp_ret:.2%} | vol {vol:.2%}")

    # 4) add a new stock with a Black-Litterman growth view -----------------
    all_tickers = tickers + ["MSFT"]
    returns2 = synthetic_returns(all_tickers, seed=11)
    cov2 = returns_to_covariance(returns2)
    market_weights = pd.Series(np.full(4, 0.25), index=all_tickers)

    view = GrowthView(ticker="MSFT", growth_pct=0.40, horizon_years=2.0)
    bl_weights, posterior = reweight_with_view(impval, cov2, market_weights, [view])

    print("\n--- After adding MSFT (+40% over 2y view, Black-Litterman) ---")
    print("Posterior expected returns:")
    for sym, r in posterior.items():
        print(f"  {sym:<6} {r:7.2%}")
    print("New target weights:")
    for sym, wt in bl_weights.items():
        print(f"  {sym:<6} {wt:7.2%}")

    # 5) paper-trading order preview (offline) ------------------------------
    print("\n--- Paper-trading preview on $100,000 ---")
    for o in preview_orders(bl_weights, 100_000):
        print(f"  {o.side.upper()} {o.symbol:<6} ${o.notional:,.2f} ({o.target_weight:.2%})")


if __name__ == "__main__":
    main()
