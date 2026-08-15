"""Import a Robinhood portfolio and map it onto the Alpaca workflow.

Robinhood has **no official public API**, so there are two supported paths, in
order of preference:

1. **CSV import** (recommended, no credentials) — export your positions to a CSV
   and load it with :func:`load_holdings_from_csv`. Column names are matched
   flexibly (``symbol``/``ticker``, ``quantity``/``shares``, and any of
   ``price``/``market_value``/``equity``/``value``).

2. **Live pull via ``robin_stocks``** (unofficial) — :func:`load_holdings_from_robinhood`
   logs in with your Robinhood credentials (and MFA) using the third-party
   ``robin_stocks`` library. This depends on an undocumented endpoint, requires
   handing over your login, and may break or violate Robinhood's terms. Prefer
   the CSV path.

Either path yields a holdings table which :func:`holdings_to_weights` turns into
portfolio weights. Those weights plug straight into the rest of the tool: imply
an ``impval`` from them (reverse optimization) or replicate the allocation on an
Alpaca paper account with :func:`map_to_alpaca_orders`.
"""

from __future__ import annotations

import pandas as pd

# Accepted column aliases (compared case-insensitively, spaces/underscores ignored).
_SYMBOL_COLS = {"symbol", "ticker", "instrument", "name"}
_QUANTITY_COLS = {"quantity", "shares", "qty", "sharesheld"}
_VALUE_COLS = {"marketvalue", "value", "equity", "totalvalue", "position"}
_PRICE_COLS = {"price", "lastprice", "currentprice", "averagebuyprice", "close"}


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _find_column(columns, aliases) -> str | None:
    for col in columns:
        if _normalize(str(col)) in aliases:
            return col
    return None


def load_holdings_from_csv(path: str) -> pd.DataFrame:
    """Load a Robinhood positions export into a normalized holdings table.

    Returns a DataFrame indexed by ticker with a ``quantity`` column and,
    whenever it can be determined, a ``market_value`` column. Missing market
    values are backfilled from a ``price`` column (× quantity) or left as NaN to
    be filled later from live prices.
    """

    raw = pd.read_csv(path)
    return _normalize_holdings(raw)


def _normalize_holdings(raw: pd.DataFrame) -> pd.DataFrame:
    sym_col = _find_column(raw.columns, _SYMBOL_COLS)
    if sym_col is None:
        raise ValueError(
            f"Could not find a symbol/ticker column in {list(raw.columns)}."
        )

    qty_col = _find_column(raw.columns, _QUANTITY_COLS)
    val_col = _find_column(raw.columns, _VALUE_COLS)
    price_col = _find_column(raw.columns, _PRICE_COLS)

    out = pd.DataFrame()
    out["ticker"] = raw[sym_col].astype(str).str.strip().str.upper()
    out["quantity"] = (
        pd.to_numeric(raw[qty_col], errors="coerce") if qty_col else pd.NA
    )

    if val_col is not None:
        out["market_value"] = pd.to_numeric(raw[val_col], errors="coerce")
    elif price_col is not None and qty_col is not None:
        price = pd.to_numeric(raw[price_col], errors="coerce")
        out["market_value"] = price * out["quantity"]
    else:
        out["market_value"] = pd.NA

    out = out[out["ticker"].str.len() > 0].set_index("ticker")
    # Collapse duplicate tickers (e.g. multiple lots) by summing.
    return out.groupby(level=0).sum(min_count=1)


def load_holdings_from_robinhood(
    username: str,
    password: str,
    mfa_code: str | None = None,
) -> pd.DataFrame:
    """Pull live holdings via the unofficial ``robin_stocks`` library.

    Requires ``pip install robin_stocks``. This uses an undocumented Robinhood
    endpoint and your real credentials — use at your own risk and prefer the CSV
    path. Credentials are never stored by this function.
    """

    import robin_stocks.robinhood as rh  # optional dependency

    rh.login(username=username, password=password, mfa_code=mfa_code)
    try:
        built = rh.build_holdings()  # {symbol: {quantity, price, equity, ...}}
    finally:
        rh.logout()

    rows = []
    for symbol, info in built.items():
        rows.append(
            {
                "ticker": symbol.upper(),
                "quantity": float(info.get("quantity", "nan")),
                "market_value": float(info.get("equity", "nan")),
            }
        )
    df = pd.DataFrame(rows).set_index("ticker")
    return df


def holdings_to_weights(
    holdings: pd.DataFrame,
    price_lookup=None,
) -> pd.Series:
    """Convert a holdings table into portfolio weights (by market value).

    Parameters
    ----------
    holdings:
        Output of :func:`load_holdings_from_csv` / :func:`load_holdings_from_robinhood`.
    price_lookup:
        Optional callable ``tickers -> pandas.Series`` of current prices, used to
        fill any missing market values. When omitted and values are missing, the
        default fetches the latest close via :mod:`yfinance`.

    Returns
    -------
    pandas.Series
        Weights indexed by ticker, summing to 1.
    """

    holdings = holdings.copy()
    missing = holdings["market_value"].isna()

    if missing.any():
        if "quantity" not in holdings or holdings.loc[missing, "quantity"].isna().any():
            raise ValueError(
                "Cannot compute weights: missing market_value and quantity for "
                f"{list(holdings.index[missing])}."
            )
        tickers = list(holdings.index[missing])
        prices = (price_lookup or _default_price_lookup)(tickers)
        holdings.loc[missing, "market_value"] = (
            holdings.loc[missing, "quantity"].astype(float)
            * prices.reindex(tickers).values
        )

    values = holdings["market_value"].astype(float)
    total = values.sum()
    if total <= 0:
        raise ValueError("Total market value must be positive to compute weights.")
    weights = values / total
    weights.name = "weight"
    return weights


def _default_price_lookup(tickers) -> pd.Series:
    """Latest close per ticker via yfinance (lazy import)."""

    from .data import get_price_history

    prices = get_price_history(list(tickers), period="5d")
    return prices.iloc[-1]


def map_to_alpaca_orders(weights: pd.Series, equity: float):
    """Translate Robinhood-derived weights into an Alpaca notional order plan.

    This is the "map Robinhood -> Alpaca" step: it replicates the Robinhood
    *allocation* (not share counts) on the Alpaca paper account, scaled to the
    account's equity. Returns a list of ``PlannedOrder`` — preview only; submit
    them with :meth:`risk_tool.broker.PaperBroker.submit_orders`.
    """

    from .broker import preview_orders

    return preview_orders(weights, equity)
