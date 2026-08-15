"""Risk-aversion parameter (``impval``).

Two ways to obtain the coefficient of risk aversion ``λ`` (lambda):

* :func:`score_questionnaire` — map answers to a short multiple-choice
  questionnaire onto a sensible ``λ`` range.
* :func:`implied_risk_aversion` — reverse-optimize ``λ`` from a portfolio the
  user has actually held.

Either way the result is persisted with :func:`save_impval` under the name
``impval`` so the rest of the workflow can pick it up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from .config import DEFAULT_RISK_FREE_RATE, IMPVAL_PATH

# Risk aversion is clamped to this range. ~1 is aggressive, ~10 very conservative.
LAMBDA_MIN = 1.0
LAMBDA_MAX = 10.0


@dataclass(frozen=True)
class Question:
    """A single questionnaire item.

    ``options`` maps a human-readable answer to a score in [0, 1] where 0 is the
    most risk-tolerant answer and 1 the most risk-averse.
    """

    key: str
    prompt: str
    options: Mapping[str, float]


QUESTIONNAIRE: tuple[Question, ...] = (
    Question(
        key="horizon",
        prompt="When do you expect to need this money?",
        options={
            "More than 15 years": 0.0,
            "7-15 years": 0.33,
            "3-7 years": 0.66,
            "Less than 3 years": 1.0,
        },
    ),
    Question(
        key="drawdown",
        prompt="Your portfolio drops 25% in a month. You...",
        options={
            "Buy more — it's on sale": 0.0,
            "Hold and wait it out": 0.4,
            "Sell some to reduce risk": 0.75,
            "Sell everything": 1.0,
        },
    ),
    Question(
        key="loss_tolerance",
        prompt="What's the largest one-year loss you could accept?",
        options={
            "Over 40%": 0.0,
            "20-40%": 0.35,
            "10-20%": 0.7,
            "Less than 10%": 1.0,
        },
    ),
    Question(
        key="goal",
        prompt="What best describes your goal?",
        options={
            "Maximize long-term growth, risk is fine": 0.0,
            "Grow steadily with some ups and downs": 0.4,
            "Mostly preserve capital, modest growth": 0.75,
            "Preserve capital above all": 1.0,
        },
    ),
    Question(
        key="experience",
        prompt="How would you describe your investing experience?",
        options={
            "Very experienced, comfortable with volatility": 0.0,
            "Some experience": 0.4,
            "A little experience": 0.7,
            "New to investing": 1.0,
        },
    ),
)


def score_questionnaire(answers: Mapping[str, str]) -> float:
    """Convert questionnaire answers into a risk-aversion parameter ``λ``.

    Parameters
    ----------
    answers:
        Mapping of question ``key`` -> chosen option text. Missing questions are
        treated as the neutral midpoint (0.5).

    Returns
    -------
    float
        ``λ`` in ``[LAMBDA_MIN, LAMBDA_MAX]``. Higher means more risk-averse.
    """

    scores = []
    for question in QUESTIONNAIRE:
        choice = answers.get(question.key)
        if choice is None:
            scores.append(0.5)
            continue
        if choice not in question.options:
            raise ValueError(
                f"Invalid answer {choice!r} for question {question.key!r}. "
                f"Valid options: {list(question.options)}"
            )
        scores.append(question.options[choice])

    avg = float(np.mean(scores)) if scores else 0.5
    return round(LAMBDA_MIN + avg * (LAMBDA_MAX - LAMBDA_MIN), 4)


def implied_risk_aversion(
    weights: Sequence[float] | pd.Series,
    cov: pd.DataFrame | np.ndarray,
    expected_returns: Sequence[float] | pd.Series,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    clamp: bool = True,
) -> float:
    """Reverse-optimize the risk aversion implied by a held portfolio.

    Treats the supplied portfolio as the user's optimal mean-variance portfolio
    and backs out ``λ`` from the first-order condition:

    .. math::

        \\lambda = \\frac{\\mu^\\top w - r_f}{w^\\top \\Sigma w}

    i.e. excess return per unit of variance.

    Parameters
    ----------
    weights:
        Portfolio weights (should sum to ~1).
    cov:
        Annualized covariance matrix aligned to ``weights``.
    expected_returns:
        Annualized expected returns aligned to ``weights``.
    risk_free_rate:
        Annual risk-free rate subtracted to get excess return.
    clamp:
        If ``True`` (default) the result is clamped to ``[LAMBDA_MIN, LAMBDA_MAX]``.
    """

    w = np.asarray(weights, dtype=float)
    mu = np.asarray(expected_returns, dtype=float)
    sigma = np.asarray(cov, dtype=float)

    variance = float(w @ sigma @ w)
    if variance <= 0:
        raise ValueError("Portfolio variance must be positive to imply λ.")

    excess_return = float(mu @ w) - risk_free_rate
    lam = excess_return / variance

    # A held portfolio with negative excess return implies a meaningless (or
    # negative) λ; fall back to a neutral, mildly risk-averse value.
    if lam <= 0:
        lam = (LAMBDA_MIN + LAMBDA_MAX) / 2

    if clamp:
        lam = max(LAMBDA_MIN, min(LAMBDA_MAX, lam))
    return round(float(lam), 4)


def save_impval(lam: float, path: str = IMPVAL_PATH, meta: dict | None = None) -> str:
    """Persist the risk-aversion parameter as ``impval``.

    Returns the path written. The JSON payload always contains an ``impval``
    key plus any extra ``meta`` provided (e.g. how it was derived).
    """

    payload = {"impval": round(float(lam), 4)}
    if meta:
        payload.update(meta)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return path


def load_impval(path: str = IMPVAL_PATH) -> float:
    """Load a previously saved ``impval``."""

    with open(path, encoding="utf-8") as fh:
        return float(json.load(fh)["impval"])
