"""Configuration and settings loading.

Settings come from environment variables (optionally via a local ``.env`` file).
Nothing here touches the network; it just centralizes configuration so the rest
of the package stays clean.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # optional dependency; the package still works without it
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


# Trading days per year, used to annualize daily statistics.
TRADING_DAYS = 252

# A reasonable default annual risk-free rate used for excess-return math.
DEFAULT_RISK_FREE_RATE = 0.04

# Default example portfolio referenced throughout the docs.
DEFAULT_PORTFOLIO = ("AAPL", "META", "NVDA")

# Where the derived risk-aversion parameter is persisted.
IMPVAL_PATH = os.environ.get("IMPVAL_PATH", "impval.json")


@dataclass(frozen=True)
class AlpacaConfig:
    """Alpaca paper-trading credentials and endpoint selection."""

    api_key: str | None
    secret_key: str | None
    paper: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key) and bool(self.secret_key)


def load_alpaca_config() -> AlpacaConfig:
    """Read Alpaca credentials from the environment.

    Returns an :class:`AlpacaConfig`; ``is_configured`` is ``False`` when keys
    are missing so callers can degrade gracefully instead of crashing.
    """

    paper = os.environ.get("ALPACA_PAPER", "true").strip().lower() not in (
        "false",
        "0",
        "no",
    )
    return AlpacaConfig(
        api_key=os.environ.get("ALPACA_API_KEY"),
        secret_key=os.environ.get("ALPACA_SECRET_KEY"),
        paper=paper,
    )


class MissingCredentialsError(RuntimeError):
    """Raised when required Alpaca credentials are absent."""


def require_alpaca_config() -> AlpacaConfig:
    """Load Alpaca config, raising if it is not fully configured.

    Use this on code paths where an Alpaca paper account is mandatory (the
    interactive workflow). Fails fast with an actionable message instead of
    silently degrading.
    """

    cfg = load_alpaca_config()
    if not cfg.is_configured:
        raise MissingCredentialsError(
            "Alpaca paper credentials are required. Set ALPACA_API_KEY and "
            "ALPACA_SECRET_KEY in your environment or .env file "
            "(see .env.example). Create free paper keys at "
            "https://alpaca.markets/."
        )
    return cfg
