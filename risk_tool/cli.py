"""Interactive end-to-end workflow.

Run with ``python -m risk_tool.cli``.

Flow:
    1. Derive the risk-aversion parameter (``impval``) from a questionnaire or
       from a past portfolio, and save it.
    2. Pull a covariance matrix for a portfolio (default AAPL/META/NVDA) and
       compute mean-variance weights.
    3. Optionally add a new stock with a growth prediction + horizon and
       reweight using Black-Litterman.
    4. Preview the target allocation against an Alpaca paper account.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import config
from .black_litterman import GrowthView, reweight_with_view
from .broker import PaperBroker
from .config import MissingCredentialsError, require_alpaca_config
from .data import covariance_matrix, get_price_history, mean_returns
from .optimizer import mean_variance_weights, portfolio_stats
from .risk_aversion import (
    QUESTIONNAIRE,
    implied_risk_aversion,
    save_impval,
    score_questionnaire,
)
from .robinhood import (
    holdings_to_weights,
    load_holdings_from_csv,
    load_holdings_from_robinhood,
)


def _ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    resp = input(f"{prompt}{suffix}: ").strip()
    return resp or (default or "")


def _choose(prompt: str, options: list[str]) -> str:
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    while True:
        raw = input("Choose a number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("  Please enter a valid number.")


def derive_impval_via_questionnaire() -> float:
    print("\n--- Risk questionnaire ---")
    answers: dict[str, str] = {}
    for question in QUESTIONNAIRE:
        choice = _choose(f"\n{question.prompt}", list(question.options))
        answers[question.key] = choice
    lam = score_questionnaire(answers)
    print(f"\nDerived risk-aversion parameter (impval): {lam}")
    return lam


def derive_impval_via_past_portfolio() -> float:
    print("\n--- Imply risk aversion from a past portfolio ---")
    tickers = [
        t.strip().upper()
        for t in _ask(
            "Tickers of your past portfolio (comma-separated)",
            ",".join(config.DEFAULT_PORTFOLIO),
        ).split(",")
        if t.strip()
    ]
    weights = []
    for t in tickers:
        weights.append(float(_ask(f"Weight held in {t} (0-1)", "")))
    w = pd.Series(weights, index=tickers)
    w = w / w.sum()

    prices = get_price_history(tickers)
    cov = covariance_matrix(prices)
    mu = mean_returns(prices)
    lam = implied_risk_aversion(w.values, cov.loc[tickers, tickers].values, mu[tickers].values)
    print(f"\nImplied risk-aversion parameter (impval): {lam}")
    return lam


def import_robinhood_weights() -> pd.Series:
    """Load a Robinhood portfolio and return its weights (by market value)."""

    print("\n--- Import a Robinhood portfolio ---")
    how = _choose(
        "How do you want to import it?",
        [
            "From a CSV export (recommended)",
            "Live via robin_stocks login (unofficial)",
        ],
    )
    if how.startswith("From a CSV"):
        path = _ask("Path to your Robinhood positions CSV")
        holdings = load_holdings_from_csv(path)
    else:
        print(
            "NOTE: this uses your real Robinhood login via the unofficial "
            "robin_stocks library; credentials are not stored."
        )
        user = _ask("Robinhood email/username")
        pw = _ask("Robinhood password")
        mfa = _ask("MFA code (blank if none)", "") or None
        holdings = load_holdings_from_robinhood(user, pw, mfa)

    weights = holdings_to_weights(holdings)
    print("\nImported Robinhood allocation:")
    for sym, wt in weights.sort_values(ascending=False).items():
        print(f"  {sym:<6} {wt:7.2%}")
    return weights


def derive_impval_from_weights(weights: pd.Series) -> float:
    """Imply risk aversion from an existing set of portfolio weights."""

    tickers = list(weights.index)
    prices = get_price_history(tickers)
    cov = covariance_matrix(prices)
    mu = mean_returns(prices)
    lam = implied_risk_aversion(
        weights.reindex(tickers).values,
        cov.loc[tickers, tickers].values,
        mu[tickers].values,
    )
    print(f"\nImplied risk-aversion parameter (impval): {lam}")
    return lam


def build_base_portfolio(tickers: list[str], impval: float):
    print(f"\nPulling price history & covariance for: {', '.join(tickers)} ...")
    prices = get_price_history(tickers)
    cov = covariance_matrix(prices)
    mu = mean_returns(prices)
    weights = mean_variance_weights(mu, cov, impval)
    return prices, cov, mu, weights


def _print_weights(weights: pd.Series, mu, cov):
    print("\nTarget weights:")
    for sym, wt in weights.items():
        print(f"  {sym:<6} {wt:7.2%}")
    exp_ret, vol = portfolio_stats(
        weights.values, mu[weights.index].values, cov.loc[weights.index, weights.index].values
    )
    print(f"  Expected annual return: {exp_ret:.2%}")
    print(f"  Expected annual vol   : {vol:.2%}")


def main(argv: list[str] | None = None) -> int:
    print("=" * 60)
    print(" Risk Aversion Parameter Tool")
    print("=" * 60)

    # Alpaca paper credentials are required to run the workflow — fail fast.
    try:
        cfg = require_alpaca_config()
    except MissingCredentialsError as exc:
        print(f"\nError: {exc}")
        return 1

    mode = _choose(
        "\nHow should we determine your risk-aversion parameter (impval)?",
        [
            "Answer a questionnaire",
            "Imply it from a past portfolio (enter tickers/weights)",
            "Imply it from my Robinhood portfolio",
        ],
    )
    rh_weights = None
    if mode.startswith("Answer"):
        impval = derive_impval_via_questionnaire()
        meta = {"source": "questionnaire"}
    elif mode.startswith("Imply it from a past"):
        impval = derive_impval_via_past_portfolio()
        meta = {"source": "past_portfolio"}
    else:
        rh_weights = import_robinhood_weights()
        impval = derive_impval_from_weights(rh_weights)
        meta = {"source": "robinhood"}

    path = save_impval(impval, meta=meta)
    print(f"Saved impval = {impval} -> {path}")

    # Default the portfolio universe to the imported Robinhood holdings if present.
    default_tickers = (
        ",".join(rh_weights.index) if rh_weights is not None else ",".join(config.DEFAULT_PORTFOLIO)
    )
    tickers = [
        t.strip().upper()
        for t in _ask("\nPortfolio tickers (comma-separated)", default_tickers).split(",")
        if t.strip()
    ]
    prices, cov, mu, weights = build_base_portfolio(tickers, impval)
    _print_weights(weights, mu, cov)

    # --- Optionally add a new stock with a Black-Litterman view ---
    if _ask("\nAdd a new stock with a growth prediction? (y/n)", "n").lower().startswith("y"):
        new_ticker = _ask("New ticker").strip().upper()
        growth = float(_ask(f"Expected total growth for {new_ticker} (e.g. 0.30 = +30%)"))
        horizon = float(_ask("Over how many years?"))

        all_tickers = tickers + [new_ticker]
        prices = get_price_history(all_tickers)
        cov = covariance_matrix(prices)

        # Equal-weight market prior over the expanded universe (no market-cap
        # data needed for the demo; swap in real cap weights if available).
        market_weights = pd.Series(
            np.full(len(all_tickers), 1.0 / len(all_tickers)), index=all_tickers
        )
        view = GrowthView(ticker=new_ticker, growth_pct=growth, horizon_years=horizon)
        weights, posterior = reweight_with_view(impval, cov, market_weights, [view])

        print("\nBlack-Litterman posterior expected returns:")
        for sym, r in posterior.items():
            print(f"  {sym:<6} {r:7.2%}")
        _print_weights(weights, posterior, cov)
        mu = posterior

    # --- Paper trading (Alpaca credentials guaranteed present above) ---
    broker = PaperBroker(cfg)
    try:
        equity = broker.account_equity()
    except Exception as exc:  # network error reaching Alpaca
        print(f"\nError contacting Alpaca paper account: {exc}")
        return 1

    print(f"\nAlpaca paper account equity: ${equity:,.2f}")
    orders = broker.plan_orders(weights, equity=equity)
    for o in orders:
        print(f"  {o.side.upper()} {o.symbol:<6} ${o.notional:,.2f} ({o.target_weight:.2%})")
    if _ask("Submit these orders to the PAPER account? (y/n)", "n").lower().startswith("y"):
        broker.submit_orders(orders)
        print("Orders submitted to paper account.")
    else:
        print("Preview only — nothing submitted.")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
