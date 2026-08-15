import numpy as np
import pandas as pd
import pytest

from risk_tool.risk_aversion import (
    LAMBDA_MAX,
    LAMBDA_MIN,
    implied_risk_aversion,
    load_impval,
    save_impval,
    score_questionnaire,
)


def test_questionnaire_aggressive_is_low():
    answers = {
        "horizon": "More than 15 years",
        "drawdown": "Buy more — it's on sale",
        "loss_tolerance": "Over 40%",
        "goal": "Maximize long-term growth, risk is fine",
        "experience": "Very experienced, comfortable with volatility",
    }
    lam = score_questionnaire(answers)
    assert lam == pytest.approx(LAMBDA_MIN)


def test_questionnaire_conservative_is_high():
    answers = {
        "horizon": "Less than 3 years",
        "drawdown": "Sell everything",
        "loss_tolerance": "Less than 10%",
        "goal": "Preserve capital above all",
        "experience": "New to investing",
    }
    lam = score_questionnaire(answers)
    assert lam == pytest.approx(LAMBDA_MAX)


def test_questionnaire_missing_answers_are_neutral():
    lam = score_questionnaire({})
    assert LAMBDA_MIN < lam < LAMBDA_MAX


def test_questionnaire_rejects_bad_option():
    with pytest.raises(ValueError):
        score_questionnaire({"horizon": "nope"})


def test_implied_risk_aversion_in_range():
    tickers = ["A", "B", "C"]
    cov = pd.DataFrame(np.diag([0.04, 0.05, 0.06]), index=tickers, columns=tickers)
    mu = pd.Series([0.10, 0.12, 0.15], index=tickers)
    w = pd.Series([0.4, 0.4, 0.2], index=tickers)
    lam = implied_risk_aversion(w.values, cov.values, mu.values)
    assert LAMBDA_MIN <= lam <= LAMBDA_MAX


def test_implied_risk_aversion_zero_variance_raises():
    with pytest.raises(ValueError):
        implied_risk_aversion([1.0], np.array([[0.0]]), [0.1])


def test_save_and_load_impval(tmp_path):
    p = tmp_path / "impval.json"
    save_impval(3.14, path=str(p), meta={"source": "test"})
    assert load_impval(str(p)) == pytest.approx(3.14)
