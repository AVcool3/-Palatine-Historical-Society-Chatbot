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
from .broker import PaperBroker, preview_orders
from .data import covariance_matrix, get_price_history, mean_returns
from .optimizer import mean_variance_weights, portfolio_stats
from .risk_aversion import (
    QUESTIONNAIRE,
    implied_risk_aversion,
    save_impval,
    score_questionnaire,
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

    mode = _choose(
        "\nHow should we determine your risk-aversion parameter (impval)?",
        ["Answer a questionnaire", "Imply it from a past portfolio"],
    )
    if mode.startswith("Answer"):
        impval = derive_impval_via_questionnaire()
        meta = {"source": "questionnaire"}
    else:
        impval = derive_impval_via_past_portfolio()
        meta = {"source": "past_portfolio"}

    path = save_impval(impval, meta=meta)
    print(f"Saved impval = {impval} -> {path}")

    tickers = [
        t.strip().upper()
        for t in _ask(
            "\nPortfolio tickers (comma-separated)", ",".join(config.DEFAULT_PORTFOLIO)
        ).split(",")
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

    # --- Paper trading preview ---
    cfg = config.load_alpaca_config()
    if cfg.is_configured:
        try:
            broker = PaperBroker(cfg)
            equity = broker.account_equity()
            print(f"\nAlpaca paper account equity: ${equity:,.2f}")
            orders = broker.plan_orders(weights, equity=equity)
            for o in orders:
                print(f"  {o.side.upper()} {o.symbol:<6} ${o.notional:,.2f} ({o.target_weight:.2%})")
            if _ask("Submit these orders to the PAPER account? (y/n)", "n").lower().startswith("y"):
                broker.submit_orders(orders)
                print("Orders submitted to paper account.")
            else:
                print("Preview only — nothing submitted.")
        except Exception as exc:  # network / credential issues
            print(f"\n[Alpaca skipped] {exc}")
    else:
        print("\n[Alpaca not configured] Showing a $100,000 notional preview instead.")
        for o in preview_orders(weights, 100_000):
            print(f"  {o.side.upper()} {o.symbol:<6} ${o.notional:,.2f} ({o.target_weight:.2%})")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
