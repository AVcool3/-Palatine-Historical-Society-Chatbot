# Project Docs — Risk Aversion Parameter Tool

## Overview

This project turns three ideas into one workflow:

1. **A personal risk number.** Every investor has a different tolerance for risk.
   We capture it as a single coefficient of risk aversion, `λ` (lambda), stored
   under the name **`impval`**.
2. **A data-driven portfolio.** Given a set of tickers we pull historical prices,
   estimate a covariance matrix, and compute mean-variance weights scaled by
   `impval`.
3. **Opinions, handled rigorously.** When the user wants to add a stock they
   rarely think in covariances — they think *"I expect this to grow X% over Y
   years."* The Black-Litterman model is the principled way to fold that opinion
   into the portfolio.

Execution is done against a **paper-trading** account (Alpaca) so nothing risks
real capital.

---

## 1. The risk-aversion parameter (`impval`)

`impval` is the `λ` in the mean-variance utility function

```
U(w) = μᵀw − (λ/2) · wᵀΣw
```

Higher `λ` ⇒ the variance term dominates ⇒ safer portfolios.

### Mode A — Questionnaire

Five multiple-choice questions (horizon, drawdown reaction, loss tolerance,
goal, experience). Each answer carries a score in `[0, 1]` (0 = risk-tolerant,
1 = risk-averse). The mean score is linearly mapped to `λ ∈ [1, 10]`:

```
λ = 1 + mean_score · (10 − 1)
```

Implemented in `score_questionnaire`.

### Mode B — Implied from a past portfolio (reverse optimization)

If the user has a portfolio they already hold, we assume it *is* their optimal
mean-variance portfolio and solve the first-order condition for `λ`:

```
λ = (μᵀw − r_f) / (wᵀΣw)
```

— excess return per unit of variance. Implemented in `implied_risk_aversion`,
clamped to `[1, 10]`, with a neutral fallback when the implied value is
non-positive.

### Mode C — Implied from a Robinhood portfolio

The user's live Robinhood holdings can be imported (see *Importing Robinhood*
below), converted to weights by market value, and fed into Mode B's reverse
optimization to imply `impval` from what they actually hold.

The chosen value is persisted as `impval` via `save_impval` (JSON).

---

## 2. Covariance matrix & weighting

- `get_price_history` downloads auto-adjusted closes from Yahoo Finance.
- `covariance_matrix` / `mean_returns` compute **annualized** statistics from
  daily log returns (× 252 trading days).
- `mean_variance_weights` solves

  ```
  max_w  μᵀw − (λ/2) wᵀΣw   s.t.  Σwᵢ = 1,  wᵢ ≥ 0
  ```

  via SciPy SLSQP, with an analytic `(λΣ)⁻¹μ` fallback projected onto the
  simplex if SciPy is unavailable.

The default example universe is **AAPL, META, NVDA**.

---

## 3. Black-Litterman reweighting

When a stock is added we go through the canonical Black-Litterman pipeline
(`black_litterman.py`):

1. **Equilibrium (prior) returns** — reverse-optimize from market weights:
   `Π = λ Σ w_mkt`. (The demo/CLI use equal weights as a stand-in for market-cap
   weights; supply real cap weights for production use.)
2. **Views from user input** — a *growth prediction over a horizon* becomes an
   absolute view on annualized return:

   ```
   q = (1 + growth_pct)^(1 / horizon_years) − 1
   ```

   The view's uncertainty `Ω` is scaled by a confidence heuristic that decays
   with the horizon (near-term predictions trusted more than far-out ones).
3. **Posterior returns** — the Black-Litterman master formula blends prior and
   views:

   ```
   E[R] = [ (τΣ)⁻¹ + Pᵀ Ω⁻¹ P ]⁻¹ [ (τΣ)⁻¹ Π + Pᵀ Ω⁻¹ Q ]
   ```

4. **Re-optimize** the portfolio with the posterior returns and the same
   `impval`.

---

## 4. Paper trading (Alpaca) — required

`broker.py` wraps the Alpaca **paper** Trading API:

- `account_equity()` reads simulated equity.
- `plan_orders()` converts target weights into notional dollar orders.
- `submit_orders()` places them — only when explicitly confirmed.

Credentials come from `.env` (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
`ALPACA_PAPER=true`) and are **mandatory** for the interactive CLI:
`config.require_alpaca_config()` raises `MissingCredentialsError` and the CLI
exits with an actionable message if they are absent. (The offline demo and unit
tests do not require them.)

## 5. Importing Robinhood (`robinhood.py`)

Robinhood exposes **no official public API**, so imports use one of:

- **CSV export** (`load_holdings_from_csv`) — recommended, credential-free.
  Column names are matched flexibly (`symbol`/`ticker`, `quantity`/`shares`,
  `price`/`market_value`/`equity`); duplicate lots are summed.
- **Live pull** (`load_holdings_from_robinhood`) — uses the unofficial
  `robin_stocks` library with the user's login + MFA. Credentials are never
  stored; the endpoint is undocumented and may break.

`holdings_to_weights` converts a holdings table to weights by market value
(fetching latest closes via yfinance for any missing values). `map_to_alpaca_orders`
replicates that **allocation** (not share counts) as an Alpaca notional order
plan. This is portfolio *mapping*, not a broker transfer — moving the actual
account (ACATS) is out of scope.

---

## Module map

| Module | Responsibility |
| --- | --- |
| `config.py` | Settings, constants, Alpaca credential loading |
| `data.py` | Prices → returns → covariance / mean returns |
| `risk_aversion.py` | Questionnaire + reverse optimization → `impval` |
| `optimizer.py` | Mean-variance optimization |
| `black_litterman.py` | Equilibrium returns, views, posterior, reweight |
| `broker.py` | Alpaca paper-trading wrapper |
| `robinhood.py` | Import Robinhood holdings (CSV / live) → weights → Alpaca |
| `cli.py` | Interactive end-to-end workflow |

## Testing

`tests/` covers risk-aversion scoring/implication, optimizer behavior
(weights normalize, higher `λ` lowers volatility), Black-Litterman view
handling, and broker order math. All tests are offline (synthetic data) — no
network or API keys required:

```bash
pip install -r requirements.txt
pytest -q
```

## Disclaimer

Educational software for paper trading and research. Not investment advice.
