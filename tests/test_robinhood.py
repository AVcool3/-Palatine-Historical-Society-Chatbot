import pandas as pd
import pytest

from risk_tool.robinhood import (
    holdings_to_weights,
    load_holdings_from_csv,
    map_to_alpaca_orders,
)


def _write_csv(tmp_path, text):
    p = tmp_path / "positions.csv"
    p.write_text(text)
    return str(p)


def test_load_csv_with_market_value(tmp_path):
    path = _write_csv(
        tmp_path,
        "Symbol,Quantity,Market Value\nAAPL,10,2000\nMETA,5,3000\n",
    )
    holdings = load_holdings_from_csv(path)
    assert list(holdings.index) == ["AAPL", "META"]
    assert holdings.loc["META", "market_value"] == 3000


def test_load_csv_computes_value_from_price(tmp_path):
    path = _write_csv(
        tmp_path,
        "ticker,shares,price\nNVDA,4,100\nAAPL,10,50\n",
    )
    holdings = load_holdings_from_csv(path)
    # value = price * shares
    assert holdings.loc["NVDA", "market_value"] == 400
    assert holdings.loc["AAPL", "market_value"] == 500


def test_load_csv_flexible_columns_and_dupes(tmp_path):
    path = _write_csv(
        tmp_path,
        "Instrument,Shares Held,Equity\naapl,10,1000\nAAPL,5,500\n",
    )
    holdings = load_holdings_from_csv(path)
    # Two lots of AAPL collapse into one row.
    assert list(holdings.index) == ["AAPL"]
    assert holdings.loc["AAPL", "market_value"] == 1500
    assert holdings.loc["AAPL", "quantity"] == 15


def test_load_csv_without_symbol_raises(tmp_path):
    path = _write_csv(tmp_path, "foo,bar\n1,2\n")
    with pytest.raises(ValueError):
        load_holdings_from_csv(path)


def test_holdings_to_weights_sum_to_one():
    holdings = pd.DataFrame(
        {"quantity": [10, 5], "market_value": [2000.0, 3000.0]},
        index=["AAPL", "META"],
    )
    holdings.index.name = "ticker"
    weights = holdings_to_weights(holdings)
    assert weights.sum() == pytest.approx(1.0)
    assert weights["META"] == pytest.approx(0.6)


def test_holdings_to_weights_uses_price_lookup_for_missing():
    holdings = pd.DataFrame(
        {"quantity": [10.0, 5.0], "market_value": [pd.NA, pd.NA]},
        index=["AAPL", "META"],
    )
    holdings.index.name = "ticker"
    lookup = lambda tickers: pd.Series({"AAPL": 100.0, "META": 200.0})
    weights = holdings_to_weights(holdings, price_lookup=lookup)
    # AAPL 10*100=1000, META 5*200=1000 -> 50/50
    assert weights["AAPL"] == pytest.approx(0.5)
    assert weights["META"] == pytest.approx(0.5)


def test_map_to_alpaca_orders_reproduces_allocation():
    weights = pd.Series({"AAPL": 0.6, "META": 0.4})
    orders = map_to_alpaca_orders(weights, 10_000)
    by = {o.symbol: o.notional for o in orders}
    assert by["AAPL"] == pytest.approx(6000)
    assert by["META"] == pytest.approx(4000)
