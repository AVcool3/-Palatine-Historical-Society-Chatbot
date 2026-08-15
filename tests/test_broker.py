import pandas as pd
import pytest

from risk_tool.broker import preview_orders


def test_preview_orders_notional_split():
    weights = pd.Series({"AAPL": 0.5, "META": 0.3, "NVDA": 0.2})
    orders = preview_orders(weights, 100_000)
    by_symbol = {o.symbol: o for o in orders}
    assert by_symbol["AAPL"].notional == pytest.approx(50_000)
    assert by_symbol["META"].notional == pytest.approx(30_000)
    assert by_symbol["NVDA"].notional == pytest.approx(20_000)
    assert all(o.side == "buy" for o in orders)


def test_preview_orders_skips_zero_weight():
    weights = pd.Series({"AAPL": 1.0, "META": 0.0})
    orders = preview_orders(weights, 10_000)
    assert [o.symbol for o in orders] == ["AAPL"]
