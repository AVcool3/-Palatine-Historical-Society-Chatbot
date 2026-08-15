"""Alpaca paper-trading wrapper.

Translates target portfolio weights into notional orders against an Alpaca
**paper** account. By default it only *previews* orders; pass ``submit=True`` to
actually place them on the simulated account.

The ``alpaca-py`` SDK is imported lazily so the rest of the package works
without it installed and without network access.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import AlpacaConfig, load_alpaca_config


@dataclass(frozen=True)
class PlannedOrder:
    """A single notional order derived from a target weight."""

    symbol: str
    target_weight: float
    notional: float  # dollars to allocate
    side: str  # "buy" or "sell"


class PaperBroker:
    """Thin convenience wrapper around the Alpaca paper trading client."""

    def __init__(self, config: AlpacaConfig | None = None):
        self.config = config or load_alpaca_config()
        self._client = None

    @property
    def client(self):
        """Lazily build the Alpaca TradingClient (paper endpoint)."""

        if self._client is None:
            if not self.config.is_configured:
                raise RuntimeError(
                    "Alpaca credentials missing. Set ALPACA_API_KEY and "
                    "ALPACA_SECRET_KEY (see .env.example)."
                )
            from alpaca.trading.client import TradingClient

            self._client = TradingClient(
                self.config.api_key,
                self.config.secret_key,
                paper=self.config.paper,
            )
        return self._client

    def account_equity(self) -> float:
        """Total equity of the paper account in dollars."""

        account = self.client.get_account()
        return float(account.equity)

    def plan_orders(
        self,
        weights: pd.Series,
        equity: float | None = None,
    ) -> list[PlannedOrder]:
        """Convert target weights into notional buy orders.

        Parameters
        ----------
        weights:
            Target weights summing to ~1.
        equity:
            Account equity to allocate. If omitted, it is read from the account
            (requires configured credentials).
        """

        if equity is None:
            equity = self.account_equity()

        orders: list[PlannedOrder] = []
        for symbol, weight in weights.items():
            notional = round(float(weight) * float(equity), 2)
            if notional <= 0:
                continue
            orders.append(
                PlannedOrder(
                    symbol=str(symbol),
                    target_weight=float(weight),
                    notional=notional,
                    side="buy",
                )
            )
        return orders

    def submit_orders(self, orders: list[PlannedOrder]) -> list:
        """Submit planned orders as notional market orders (paper account)."""

        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        results = []
        for order in orders:
            request = MarketOrderRequest(
                symbol=order.symbol,
                notional=order.notional,
                side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            results.append(self.client.submit_order(request))
        return results


def preview_orders(weights: pd.Series, equity: float) -> list[PlannedOrder]:
    """Build a notional order plan without touching the network.

    Handy for the offline demo and tests — same math as ``PaperBroker.plan_orders``
    but never instantiates a client.
    """

    broker = PaperBroker.__new__(PaperBroker)  # skip __init__/credentials
    return PaperBroker.plan_orders(broker, weights, equity=equity)
