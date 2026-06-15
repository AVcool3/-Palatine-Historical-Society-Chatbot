# Risk Aversion Parameter Tool

A portfolio construction toolkit that:

1. **Derives a personal risk‑aversion parameter** (`impval`) for a user — either
   from a short questionnaire *or* by reverse‑engineering it from one of their
   past portfolios.
2. **Pulls a covariance matrix** for a given portfolio (default example:
   `AAPL`, `META`, `NVDA`) using [`yfinance`](https://pypi.org/project/yfinance/),
   and weights the portfolio with mean‑variance optimization driven by `impval`.
3. **Reweights with the Black‑Litterman model** when a new stock is added: the
   user is prompted for a growth prediction and a time horizon, which become a
   Black‑Litterman *view* used to re‑optimize the portfolio.
4. **Connects to a paper‑trading API** ([Alpaca](https://alpaca.markets/)) to
   read the account and preview/submit the resulting target allocation safely
   against a simulated account.

> ⚠️ This is an educational tool for **paper trading** and research only. It is
> not investment advice and should not be used to trade real money.

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# copy the env template and fill in your Alpaca PAPER keys
cp .env.example .env

# run the interactive workflow
python -m risk_tool.cli
```

If you just want to see the numbers without any API keys or network, run the
offline example which uses bundled synthetic price data:

```bash
python examples/example_run.py
```

---

## How it works

### 1. Risk aversion parameter (`impval`)

`risk_tool/risk_aversion.py` produces a single number, the coefficient of risk
aversion `λ` (lambda), saved as `impval`.

- **Questionnaire mode** — the user answers a handful of multiple‑choice
  questions about loss tolerance, horizon, and reaction to drawdowns. Answers
  are scored and mapped onto a sensible `λ` range (≈ 1 = aggressive, ≈ 10 =
  very conservative).
- **Past‑portfolio mode** — given the weights of a portfolio the user has held
  and the asset covariance matrix, the tool applies *reverse optimization*:

  ```
  λ = (μᵀ w) / (wᵀ Σ w)
  ```

  i.e. the risk aversion implied by treating the held portfolio as the user's
  optimal mean‑variance portfolio.

### 2. Covariance matrix & weighting

`risk_tool/data.py` downloads adjusted close prices with `yfinance`, computes
log returns, and returns an **annualized** covariance matrix and mean‑return
vector. `risk_tool/optimizer.py` solves the long‑only mean‑variance problem

```
maximize   μᵀ w − (λ / 2) · wᵀ Σ w     s.t.  Σ wᵢ = 1,  wᵢ ≥ 0
```

### 3. Black‑Litterman with user views

When a new ticker is added, `risk_tool/black_litterman.py`:

1. Builds the **equilibrium (prior) returns** `Π = λ Σ w_mkt` from market‑cap
   weights (reverse optimization).
2. Turns the user's *growth prediction over a horizon* into an **absolute view**
   (annualized expected return) with a confidence derived from how far out the
   horizon is.
3. Combines prior and views into **posterior expected returns** and re‑runs the
   optimizer to produce new target weights.

### 4. Paper trading

`risk_tool/broker.py` wraps the Alpaca **paper** trading API to read the account
equity and translate target weights into notional orders — preview by default,
submit only when explicitly confirmed.

---

## Project layout

```
risk_tool/
  config.py          # env / settings loading
  data.py            # yfinance prices -> covariance matrix & returns
  risk_aversion.py   # questionnaire + reverse optimization -> impval
  optimizer.py       # mean-variance optimization
  black_litterman.py # Black-Litterman posterior + reweighting
  broker.py          # Alpaca paper-trading wrapper
  cli.py             # interactive end-to-end workflow
examples/
  example_run.py     # offline demo with synthetic data
tests/               # unit tests (no network required)
docs/
  PROJECT_DOCS.md    # design notes & math
```

See [`docs/PROJECT_DOCS.md`](docs/PROJECT_DOCS.md) for the full design write‑up.
